import asyncio
import logging
import threading
import uuid
from typing import Callable

from app.config import settings

logger = logging.getLogger(__name__)
from app.agent.hook_manager import hook_manager
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.tools import (
    get_tools,
    requires_approval,
    truncate_output,
)
from app.core.persistence import save_session_messages, update_session_title
from app.deps import _docker_manager
from app.llm.client import create_llm_client
from app.llm.streaming import stream_agent_response
from app.models.session import Session

# Increase MAX_ITERATIONS to allow for complex tasks like auditing or massive code generation
MAX_ITERATIONS = 150
_llm_client = None


def _get_llm():
    global _llm_client
    if _llm_client is None:
        _llm_client = create_llm_client()
    return _llm_client

# Pending approvals/responses keyed by request_id (not session_id)
_pending_approvals: dict[str, asyncio.Event] = {}
_approval_results: dict[str, dict] = {}
_pending_responses: dict[str, asyncio.Event] = {}
_response_results: dict[str, str] = {}
_cancel_flags: dict[str, bool] = {}
_session_pending_ids: dict[str, list[str]] = {}
_session_generation: dict[str, int] = {}
_cancel_events: dict[str, threading.Event] = {}


async def run_agent_loop(
    session: Session,
    user_message: str,
    ws_send: Callable,
):
    _cancel_flags[session.id] = False
    gen = _session_generation.get(session.id, 0) + 1
    _session_generation[session.id] = gen
    cancel_event = threading.Event()
    _cancel_events[session.id] = cancel_event
    logger.info(f"[{session.id[:8]}] agent loop start, gen={gen}, msg={user_message[:50]}")

    session.messages.append({"role": "user", "content": user_message})
    await save_session_messages(session.id, session.messages)

    if len(session.messages) == 1:
        title = user_message[:60].strip()
        await update_session_title(session.id, title)

    messages = _build_messages(session)

    try:
        orc_prompt = build_system_prompt(is_subagent=False)
        orc_tools = get_tools(is_subagent=False)
        await _run_loop(session, messages, orc_prompt, orc_tools, ws_send, gen, cancel_event)
        # Session memory: after successful completion, persist learnings
        await _persist_session_memory(session, ws_send)
    except asyncio.CancelledError:
        logger.info(f"[{session.id[:8]}] agent loop cancelled, gen={gen}")
    except Exception as e:
        logger.exception(f"[{session.id[:8]}] agent loop error, gen={gen}")
        if _session_generation.get(session.id) != gen:
            return
        # Đảm bảo UI không kẹt ở trạng thái streaming
        try:
            await ws_send({"type": "agent_chunk", "content": "", "done": True})
        except Exception:
            pass
        error_detail = f"{type(e).__name__}: {str(e)[:200]}"
        friendly = (
            f"⚠️ Gặp sự cố khi xử lý: {error_detail}\n\n"
            f"Bạn có thể thử lại, hoặc chia nhỏ yêu cầu nếu tác vụ quá lớn."
        )
        await ws_send({"type": "error", "message": friendly, "recoverable": True})
        session.messages.append({"role": "assistant", "content": f"[Error] {error_detail}"})
        await save_session_messages(session.id, session.messages)


async def _persist_session_memory(session: Session, ws_send: Callable):
    """Auto-persist session learnings as a skill if the session was complex enough."""
    from app.agent.hook_manager import _session_tool_history
    from app.agent.tool_registry import tool_registry

    history = _session_tool_history.get(session.id, [])
    if len(history) < 5:
        return

    # Check if session created runtime tools (sign of complex work worth remembering)
    runtime_tools = tool_registry.list_runtime_tools()
    created_tools_this_session = [t for t in runtime_tools if t in set(history)]

    # Check if session used pipeline or subagents
    used_pipeline = "execute_pipeline" in history
    used_subagent = "spawn_subagent" in history
    search_count = history.count("web_search")

    # Only persist if session was genuinely complex
    if not (created_tools_this_session or used_pipeline or used_subagent or search_count >= 3):
        return

    # Extract session summary for memory
    msg_count = len(session.messages)
    memory_note = (
        f"Session had {msg_count} messages, {len(history)} tool calls. "
        f"Tools created: {created_tools_this_session or 'none'}. "
        f"Pipeline used: {used_pipeline}. Searches: {search_count}."
    )
    logger.info(f"[{session.id[:8]}] Session memory: {memory_note}")


async def _run_loop(
    session: Session,
    messages: list[dict],
    system_prompt: str,
    tools_list: list,
    ws_send: Callable,
    gen: int = 0,
    cancel_event: threading.Event | None = None,
    is_subagent: bool = False,
    max_iterations: int | None = None,
    force_model: str | None = None,
):
    # Subagents get a smaller default budget so one subagent can't burn the whole
    # session's iteration allowance (main agent uses the full MAX_ITERATIONS).
    iter_budget = max_iterations if max_iterations is not None else (40 if is_subagent else MAX_ITERATIONS)

    def _stale():
        return _session_generation.get(session.id) != gen

    search_count = 0
    max_searches = 10

    # Plateau detection (ported concept from Nexus metacognition): if the agent
    # repeats the same tool+input, it's stuck — nudge it to root-cause instead of
    # retrying blindly. Additive only; does NOT change the exit condition.
    tool_sig_counts: dict[str, int] = {}
    plateau_nudged: set[str] = set()

    # Stagnation detection (quality-based, ported from Nexus orchestrator's
    # progress-based exit): count how many consecutive iterations have produced
    # only "low-signal churn" (shell_exec/read_file/think without write/verify
    # progress). Escalating nudges push the agent to either make real progress,
    # step back to root-cause, or wrap up — instead of debugging in circles for
    # 60+ iterations (the run3 failure mode).
    churn_streak = 0
    stagnation_nudged: set[int] = set()
    PROGRESS_TOOLS = {"write_file", "verify_work", "verify_webapp", "create_tool", "create_skill", "create_hook"}
    faketool_nudges = 0  # times we nudged the agent for writing a tool call as text
    # T7: theo dõi tool đã dùng cả phiên để chặn báo "xong" task BUILD mà chưa qua
    # giám khảo mù (spawn_evaluator). Chỉ nudge 1 lần để không spam.
    tools_used_ever: set[str] = set()
    evaluator_gate_nudged = False

    responded = False
    for iteration in range(iter_budget):
        if _cancel_flags.get(session.id) or _stale():
            break

        # Dynamic tool list — picks up runtime-created tools mid-conversation
        tools_list = tool_registry.get_tool_specs(is_subagent=is_subagent)

        await ws_send({"type": "agent_status", "tool": "thinking", "detail": f"iteration {iteration + 1}"})
        stop_reason, content_blocks, messages = await _call_llm_with_continuation(
            messages, system_prompt, tools_list, ws_send, cancel_event, session.id, force_model=force_model
        )

        if _stale():
            break

        if stop_reason == "end_turn":
            text = _extract_text(content_blocks)
            # Anti "fake tool call": some models (esp. Opus on long/complex prompts)
            # END the turn after WRITING a tool call as text (e.g. "<tool_use>{...}")
            # instead of emitting a real toolUse block — so nothing executes. Detect
            # that pattern and nudge the agent to emit a REAL tool call, up to a few
            # times, instead of accepting the hollow turn as the final answer.
            if text and _looks_like_faked_tool_call(text) and faketool_nudges < 3:
                faketool_nudges += 1
                messages.append({"role": "assistant", "content": content_blocks})
                messages.append({"role": "user", "content": [{"text": (
                    "Bạn vừa VIẾT lời gọi công cụ dưới dạng văn bản — nó KHÔNG được thực thi nên "
                    "bạn chưa nhận được dữ liệu thật. Hãy GỌI CÔNG CỤ THẬT (emit tool use, đúng tên "
                    "tham số: read_file dùng 'path', shell_exec dùng 'command') để điều tra. "
                    "Đừng in chuỗi <tool_use> hay JSON vào câu trả lời."
                )}]})
                continue
            # T7 HARD-GATE: agent định kết thúc task BUILD (đã write_file + verify) nhưng
            # CHƯA bao giờ gọi giám khảo mù → chặn 1 lần, buộc spawn_evaluator trước khi
            # báo "xong". Chỉ áp cho agent chính (không subagent — chính nó LÀ giám khảo),
            # và chỉ khi thực sự đã build (tránh ép task hỏi-đáp tầm thường).
            built_something = bool(tools_used_ever & {"write_file", "verify_webapp"})
            if (not is_subagent and built_something
                    and "spawn_evaluator" not in tools_used_ever
                    and not evaluator_gate_nudged):
                evaluator_gate_nudged = True
                messages.append({"role": "assistant", "content": content_blocks})
                messages.append({"role": "user", "content": [{"text": (
                    "[SYSTEM — CỔNG NGHIỆM THU: bạn sắp báo 'hoàn thành' một sản phẩm đã BUILD "
                    "nhưng CHƯA qua giám khảo mù. Tự verify_work của bạn là chủ quan — bắt buộc gọi "
                    "`spawn_evaluator` (giám khảo độc lập, model mạnh, tự điều tra trên sản phẩm thật) "
                    "với original_request (nguyên văn yêu cầu gốc), product (đường dẫn/cách chạy), và "
                    "data_location (file thật). Nếu verdict THIẾU → làm tiếp rồi gọi lại. Chỉ báo hoàn "
                    "thành sau khi giám khảo phán ĐỦ. Gọi spawn_evaluator NGAY bây giờ.]"
                )}]})
                continue
            if text:
                if not is_subagent:
                    session.messages.append({"role": "assistant", "content": text})
                    await save_session_messages(session.id, session.messages)
                await ws_send({"type": "agent_message", "content": text, "metadata": {"iterations": iteration + 1, "streamed": True}})
            responded = True
            break

        if stop_reason == "tool_use":
            tool_results = []
            for block in content_blocks:
                if "toolUse" not in block:
                    continue

                tool_use = block["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                tool_id = tool_use["toolUseId"]
                tools_used_ever.add(tool_name)  # T7 gate: theo dõi tool đã dùng cả phiên

                tool_desc = tool_input.get("query") or tool_input.get("command") or tool_input.get("path") or ""
                await ws_send({
                    "type": "agent_status",
                    "tool": tool_name,
                    "detail": str(tool_desc)[:100],
                })

                if tool_name == "web_search":
                    search_count += 1
                    if search_count > max_searches:
                        result = "Search limit reached. Please synthesize your findings and respond."
                    else:
                        result = await _execute_tool(
                            session, tool_name, tool_input, ws_send, cancel_event
                        )
                else:
                    result = await _execute_tool(
                        session, tool_name, tool_input, ws_send, cancel_event
                    )

                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_id,
                        "content": [{"text": result}],
                    }
                })

                # Plateau detection: same tool+input repeated ≥3 times → inject a
                # root-cause nudge once (don't spam). Helps break "rebuild/retry blindly" loops.
                try:
                    sig = f"{tool_name}:{hash(str(tool_input))}"
                    tool_sig_counts[sig] = tool_sig_counts.get(sig, 0) + 1
                    if tool_sig_counts[sig] >= 3 and sig not in plateau_nudged:
                        plateau_nudged.add(sig)
                        tool_results.append({"text": (
                            f"[SYSTEM — PLATEAU DETECTED: you've called '{tool_name}' with the same input "
                            f"{tool_sig_counts[sig]} times. STOP repeating. Step back and analyze the ROOT CAUSE: "
                            f"(1) What exactly is happening vs expected? (2) What assumption might be wrong? "
                            f"(3) What DIFFERENT approach is needed? Use `load_skill('systematic-debugging')`, "
                            f"or `spawn_critic`, or `ask_user` if truly stuck. Do NOT retry the same call.]"
                        )})

                    # Intent-plateau: DIFFERENT commands aimed at the SAME goal (the
                    # kill/free-a-port loop: pkill→lsof→fuser→ps→/proc...) slips past the
                    # exact-input check above. Detect by INTENT keyword, not exact input.
                    if tool_name == "shell_exec":
                        cmd_l = str(tool_input.get("command", "")).lower()
                        intent = None
                        if any(k in cmd_l for k in ("pkill", "lsof", "fuser", "kill ", "kill$", "kill -", "/proc/net/tcp", "address already in use")) or ("8080" in cmd_l and ("kill" in cmd_l or "pid" in cmd_l or "netstat" in cmd_l or "ss -" in cmd_l)):
                            intent = "kill_or_free_port"
                        if intent:
                            ic = f"intent:{intent}"
                            tool_sig_counts[ic] = tool_sig_counts.get(ic, 0) + 1
                            if tool_sig_counts[ic] >= 4 and ic not in plateau_nudged:
                                plateau_nudged.add(ic)
                                tool_results.append({"text": (
                                    "[SYSTEM — STUCK FREEING A PORT: you've tried several DIFFERENT commands to "
                                    "kill a process / free a port. This sandbox is python:3.11-slim — it has NO "
                                    "lsof / pkill / fuser / ps. Those commands silently no-op. To find & kill the "
                                    "PID holding a port, use /proc directly, e.g.:\n"
                                    "  python3 - <<'PY'\n"
                                    "import os,glob\n"
                                    "ino={l.split()[9] for l in open('/proc/net/tcp') if l.split()[1].endswith(':1F90') and l.split()[3]=='0A'}  # 1F90=8080, 0A=LISTEN\n"
                                    "for fd in glob.glob('/proc/[0-9]*/fd/*'):\n"
                                    " try:\n"
                                    "  t=os.readlink(fd)\n"
                                    "  if t.startswith('socket:') and t.split('[')[1].rstrip(']') in ino: os.kill(int(fd.split('/')[2]),9)\n"
                                    " except: pass\n"
                                    "PY\n"
                                    "Better: avoid the conflict — start the server with a saved PID "
                                    "(`python -m uvicorn ... & echo $! > /tmp/srv.pid`) and `kill $(cat /tmp/srv.pid)` "
                                    "before restarting, instead of hunting the port each time.]"
                                )})
                except Exception:
                    pass

            # --- Stagnation detection (quality-based exit nudges) ---
            # An iteration "makes progress" if it used a progress tool (built/verified
            # something). Otherwise it's churn (probing/reading/thinking). Long churn
            # streaks = stuck. Escalate nudges by streak length so the agent converges.
            iter_tools = {b["toolUse"]["name"] for b in content_blocks if "toolUse" in b}
            made_progress = bool(iter_tools & PROGRESS_TOOLS)
            if made_progress:
                churn_streak = 0
            else:
                churn_streak += 1

            # Soft nudge at 6 consecutive churn iterations (root-cause prompt).
            if churn_streak == 6 and 6 not in stagnation_nudged:
                stagnation_nudged.add(6)
                tool_results.append({"text": (
                    "[SYSTEM — STAGNATION: ~6 iterations without building or verifying anything "
                    "(only probing/reading/thinking). You may be debugging in circles. STEP BACK: "
                    "state in ONE sentence the exact root cause you're chasing and your single next "
                    "hypothesis. If you can't, `load_skill('systematic-debugging')` and follow its 4 phases. "
                    "Then make a concrete change (write_file) and verify_work it.]"
                )})
            # Hard nudge at 12 — push to either ship what works or ask the user.
            elif churn_streak == 12 and 12 not in stagnation_nudged:
                stagnation_nudged.add(12)
                tool_results.append({"text": (
                    "[SYSTEM — STAGNATION CRITICAL: ~12 iterations with no real progress. Per the "
                    "Rule of Three, STOP iterating on this approach. Either: (a) ship the part that "
                    "already works and report honestly what doesn't (with evidence), or (b) `ask_user` "
                    "for direction. Do NOT keep probing. Decide now.]"
                )})

            if iteration >= iter_budget - 3:
                tool_results.append({"text": "[SYSTEM: You are running low on iterations. Wrap up your research and provide a comprehensive response in the next turn.]"})
            messages.append({"role": "user", "content": tool_results})

        else:
            text = _extract_text(content_blocks)
            if text:
                if not is_subagent:
                    session.messages.append({"role": "assistant", "content": text})
                await ws_send({"type": "agent_message", "content": text, "metadata": None})
            responded = True
            break

    if not responded and not _stale() and not _cancel_flags.get(session.id):
        logger.info(f"[{session.id[:8]}] loop exhausted, running final synthesis")
        messages = _trim_messages_for_synthesis(messages)
        messages.append({"role": "user", "content": [{"text": "You have reached the iteration limit. Synthesize all your findings and provide a comprehensive response now. Do not use any more tools."}]})
        await ws_send({"type": "agent_status", "tool": "thinking", "detail": "final synthesis"})
        try:
            stop_reason, content_blocks, messages = await _call_llm_with_continuation(
                messages, system_prompt, tools_list, ws_send, cancel_event, session.id
            )
            if not _stale():
                text = _extract_text(content_blocks)
                if text:
                    if not is_subagent:
                        session.messages.append({"role": "assistant", "content": text})
                        await save_session_messages(session.id, session.messages)
                    await ws_send({"type": "agent_message", "content": text, "metadata": {"iterations": MAX_ITERATIONS + 1, "streamed": True}})
        except Exception as e:
            logger.error(f"[{session.id[:8]}] final synthesis failed: {e}")
            await ws_send({"type": "agent_message", "content": f"Đã nghiên cứu qua {MAX_ITERATIONS} bước nhưng không thể tổng hợp kết quả do timeout. Vui lòng thử lại với câu hỏi cụ thể hơn.", "metadata": None})


async def _execute_tool(
    session: Session,
    tool_name: str,
    tool_input: dict,
    ws_send: Callable,
    cancel_event: threading.Event | None = None,
) -> str:
    # 1. Pre-hooks
    allowed, abort_reason = await hook_manager.execute_pre_hooks(tool_name, tool_input, session.id)
    if not allowed:
        return abort_reason or "Blocked by pre-execution hook."

    # 2. Execution
    try:
        result = await _do_execute_tool(session, tool_name, tool_input, ws_send, cancel_event)
    except Exception as e:
        result = f"Tool execution error: {e}"

    # 3. Post-hooks
    final_result = await hook_manager.execute_post_hooks(tool_name, tool_input, result, session.id)
    return final_result


async def _do_execute_tool(
    session: Session,
    tool_name: str,
    tool_input: dict,
    ws_send: Callable,
    cancel_event: threading.Event | None = None,
) -> str:
    handler = tool_registry.get_handler(tool_name)
    if handler is None:
        return f"Unknown tool: {tool_name}"
    return await handler(session, tool_input, ws_send, cancel_event)


def _trim_messages_for_synthesis(messages: list[dict]) -> list[dict]:
    """Trim tool results to keep context manageable for final synthesis."""
    trimmed = []
    for msg in messages:
        content = msg.get("content", [])
        if msg.get("role") == "user" and isinstance(content, list):
            new_content = []
            for block in content:
                if "toolResult" in block:
                    result_content = block["toolResult"].get("content", [])
                    truncated_content = []
                    for item in result_content:
                        if "text" in item and len(item["text"]) > 4000:
                            truncated_content.append({"text": item["text"][:4000] + "\n... [truncated for synthesis]"})
                        else:
                            truncated_content.append(item)
                    new_content.append({"toolResult": {**block["toolResult"], "content": truncated_content}})
                else:
                    new_content.append(block)
            trimmed.append({"role": "user", "content": new_content})
        else:
            trimmed.append(msg)
    return trimmed


def _build_messages(session: Session) -> list[dict]:
    messages = []
    for msg in session.messages[-20:]:
        role = msg["role"]
        content = msg["content"]
        if isinstance(content, str):
            messages.append({"role": role, "content": [{"text": content}]})
        else:
            messages.append({"role": role, "content": content})
    return messages


def _extract_text(content_blocks: list) -> str:
    text = ""
    for block in content_blocks:
        if "text" in block:
            text += block["text"]
    return text


def _looks_like_faked_tool_call(text: str) -> bool:
    """Detect when the model WROTE a tool call as text instead of emitting a real
    toolUse block (so nothing executed). Markers: an XML-ish <tool_use> tag, or a
    JSON object naming a tool + its args inline in the prose."""
    if not text:
        return False
    t = text.lower()
    if "<tool_use" in t or "</tool_use" in t or "<tool_call" in t:
        return True
    # JSON-style fake: {"name": "...", "input": {...}} or {"tool": ...}
    import re as _re
    if _re.search(r'\{\s*"(name|tool)"\s*:\s*"[a-z_]+"\s*,\s*"(input|arguments|parameters)"\s*:', t):
        return True
    return False


def extract_last_agent_text(messages: list[dict]) -> str:
    """Robustly pull the subagent's final textual answer.

    The naive `_extract_text(messages[-1])` returns "" when the last message is a
    toolResult (e.g. the subagent hit its iteration budget mid-work). Walk backwards
    to the most recent assistant message that actually contains text.
    """
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            txt = _extract_text(msg.get("content", []))
            if txt and txt.strip():
                return txt
    return ""


# Subagent nesting depth per session — prevents unbounded recursion
# (a subagent spawning a critic spawning a subagent ...).
_subagent_depth: dict[str, int] = {}
_MAX_SUBAGENT_DEPTH = 3


async def _retry_after_stall(
    messages: list[dict],
    system_prompt: str,
    tools_list: list,
    ws_send: Callable,
    cancel_event: threading.Event | None,
    session_id: str,
    max_retries: int = 3,
) -> dict | None:
    """Retry an LLM call after a stall, with exponential backoff. Bedrock stalls are
    usually transient (capacity queueing / throttle), so retrying the SAME request
    after waiting works. Returns the response dict, or None if all retries stall.

    Context is only trimmed when genuinely huge (>120K) — for small contexts trimming
    does nothing and just wastes a retry on an identical request (the old bug)."""
    total_chars = sum(_msg_chars(m) for m in messages)
    if total_chars > 120000:
        messages = _apply_context_window(messages, max_chars=80000)

    for attempt in range(1, max_retries + 1):
        if _cancel_flags.get(session_id):
            return None
        backoff = 2 ** attempt  # 2s, 4s, 8s
        logger.warning(
            f"[{session_id[:8]}] LLM stalled (ctx={total_chars} chars), "
            f"retry {attempt}/{max_retries} after {backoff}s backoff..."
        )
        await ws_send({"type": "agent_status", "tool": "thinking", "detail": f"đang thử lại ({attempt}/{max_retries})..."})
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            raise
        try:
            return await _call_llm(messages, system_prompt, tools_list, ws_send=ws_send, cancel_event=cancel_event)
        except RuntimeError as e:
            if "stalled" in str(e) or "timeout" in str(e).lower():
                continue  # try again
            logger.error(f"[{session_id[:8]}] retry {attempt} non-stall error: {e}")
            return None
        except Exception as e:
            logger.error(f"[{session_id[:8]}] retry {attempt} failed: {e}")
            return None
    logger.error(f"[{session_id[:8]}] all {max_retries} retries stalled")
    return None


async def _call_llm_with_continuation(
    messages: list[dict],
    system_prompt: str,
    tools_list: list,
    ws_send: Callable,
    cancel_event: threading.Event | None,
    session_id: str,
    force_model: str | None = None,
) -> tuple[str, list, list[dict]]:
    """Call LLM with automatic max_tokens continuation. Returns (stop_reason, final_content_blocks, updated_messages)."""
    all_text_parts = []
    max_continuations = 5

    for cont in range(max_continuations):
        if _cancel_flags.get(session_id):
            break

        try:
            response = await _call_llm(messages, system_prompt, tools_list, ws_send=ws_send, cancel_event=cancel_event, force_model=force_model)
        except RuntimeError as e:
            if "stalled" in str(e) or "timeout" in str(e).lower():
                # Bedrock stalls (no token for 120s) are usually TRANSIENT — capacity
                # queueing / throttle, NOT oversized context. Retrying the SAME request
                # after a short backoff succeeds far more often than mangling it.
                # Only trim when context is genuinely large (>120K).
                response = await _retry_after_stall(
                    messages, system_prompt, tools_list, ws_send, cancel_event, session_id
                )
                if response is None:
                    if all_text_parts:
                        combined = "".join(all_text_parts)
                        return "end_turn", [{"text": combined}], messages
                    return "end_turn", [{"text": "Hệ thống đang quá tải tạm thời (LLM không phản hồi sau nhiều lần thử). Vui lòng gửi lại yêu cầu — nếu tác vụ rất lớn, hãy chia nhỏ để tôi xử lý từng phần."}], messages
            else:
                logger.error(f"[{session_id[:8]}] LLM error during continuation {cont}: {e}")
                if all_text_parts:
                    combined = "".join(all_text_parts)
                    return "end_turn", [{"text": combined}], messages
                raise
        except Exception as e:
            logger.error(f"[{session_id[:8]}] LLM error during continuation {cont}: {e}")
            if all_text_parts:
                combined = "".join(all_text_parts)
                return "end_turn", [{"text": combined}], messages
            raise

        stop_reason = response.get("stopReason", "")
        content_blocks = response.get("output", {}).get("message", {}).get("content", [])
        messages.append({"role": "assistant", "content": content_blocks})

        if stop_reason != "max_tokens":
            if all_text_parts:
                text = _extract_text(content_blocks)
                all_text_parts.append(text)
                combined = "".join(all_text_parts)
                content_blocks = [{"text": combined}]
            return stop_reason, content_blocks, messages

        text = _extract_text(content_blocks)
        all_text_parts.append(text)
        await ws_send({"type": "agent_status", "tool": "thinking", "detail": f"continuing response ({cont + 1})..."})
        messages.append({"role": "user", "content": [{"text": "Continue from where you left off. Do not repeat what you already wrote."}]})

    combined = "".join(all_text_parts)
    return "end_turn", [{"text": combined}], messages


def _trim_large_blocks(content, limit: int = 2000):
    """Trim large text inside both toolResult (user) and toolUse input (assistant) blocks.
    Returns possibly-trimmed content list."""
    if not isinstance(content, list):
        return content
    new_content = []
    for block in content:
        if "toolResult" in block:
            rc = block["toolResult"].get("content", [])
            trimmed_rc = []
            for item in rc:
                if "text" in item and len(item["text"]) > limit:
                    trimmed_rc.append({"text": item["text"][:limit] + "\n...[trimmed]"})
                else:
                    trimmed_rc.append(item)
            new_content.append({"toolResult": {**block["toolResult"], "content": trimmed_rc}})
        elif "toolUse" in block:
            # write_file/create_tool put large file content in toolUse input — trim it
            tu = block["toolUse"]
            inp = tu.get("input", {})
            if isinstance(inp, dict):
                new_inp = {}
                for k, v in inp.items():
                    if isinstance(v, str) and len(v) > limit:
                        new_inp[k] = v[:limit] + "\n...[trimmed]"
                    else:
                        new_inp[k] = v
                new_content.append({"toolUse": {**tu, "input": new_inp}})
            else:
                new_content.append(block)
        elif "text" in block and len(block.get("text", "")) > limit * 2:
            new_content.append({"text": block["text"][:limit * 2] + "\n...[trimmed]"})
        else:
            new_content.append(block)
    return new_content


def _msg_chars(m: dict) -> int:
    return len(str(m.get("content", "")))


def _starts_with_orphan_tool_result(content) -> bool:
    """A user message whose content leads with a toolResult — invalid as the first
    message of a suffix because its matching toolUse (assistant) was dropped."""
    if not isinstance(content, list):
        return False
    return any("toolResult" in b for b in content)


def _apply_context_window(messages: list[dict], max_chars: int = 80000) -> list[dict]:
    """Keep context under budget. Two stages:

    1. Trim oversized blocks (toolResult content + toolUse input) everywhere except
       the single most recent message.
    2. If STILL over budget, DROP whole old messages — keep messages[0] (the original
       task) plus the largest *contiguous* suffix that fits. This is the real fix for
       long sessions: trimming block content alone can't shrink 68 accumulated messages.

    The result is kept valid for Bedrock:
      - suffix is contiguous so toolUse→toolResult pairs stay together;
      - the suffix must not start with an orphan toolResult (its toolUse was dropped);
      - no two consecutive user turns (messages[0] is user, so the suffix can't lead
        with a user turn either).
    """
    total = sum(_msg_chars(m) for m in messages)
    if total <= max_chars:
        return messages

    logger.info(f"Context too large ({total} chars), applying windowing (max {max_chars})")

    # --- Stage 1: trim block content (cheap, lossless-ish) ---
    if not messages:
        return messages
    trimmed = [messages[0]]
    for msg in messages[1:-1]:
        content = msg.get("content", [])
        if isinstance(content, list):
            trimmed.append({"role": msg.get("role"), "content": _trim_large_blocks(content)})
        else:
            trimmed.append(msg)
    if len(messages) > 1:
        trimmed.append(messages[-1])  # active turn intact

    if sum(_msg_chars(m) for m in trimmed) <= max_chars:
        new_total = sum(_msg_chars(m) for m in trimmed)
        logger.info(f"Context windowed (block-trim only): {total} -> {new_total} chars")
        return trimmed

    # --- Stage 2: drop whole old messages, keep head + contiguous suffix ---
    head = trimmed[0]
    head_chars = _msg_chars(head)
    budget = max_chars - head_chars

    # Walk from the end, accumulating messages until we exceed budget.
    suffix: list[dict] = []
    running = 0
    for msg in reversed(trimmed[1:]):
        c = _msg_chars(msg)
        if suffix and running + c > budget:
            break
        suffix.append(msg)
        running += c
    suffix.reverse()

    # Drop leading messages that would be invalid as the suffix start:
    #  - an assistant/user turn carrying an orphan toolResult, or
    #  - a user turn (would sit right after head, which is also a user turn).
    while suffix:
        first = suffix[0]
        content = first.get("content", [])
        if _starts_with_orphan_tool_result(content) or first.get("role") == "user":
            dropped = suffix.pop(0)
            running -= _msg_chars(dropped)
        else:
            break

    result = [head] + suffix
    new_total = sum(_msg_chars(m) for m in result)
    logger.info(
        f"Context windowed (dropped {len(trimmed) - len(result)} msgs): "
        f"{total} -> {new_total} chars, kept {len(result)} messages"
    )
    return result


def _select_model(messages: list[dict]) -> str | None:
    """Route to heavy model (Opus) for complex turns, light model (Sonnet) otherwise.

    Heuristic: the last assistant turn that just created a tool, or a turn that
    will likely synthesize a large report, benefits from the heavy model.
    Returns None to use the client default (light) model.
    """
    # Model routing is OPT-IN and disabled by default. The heavy model (Opus)
    # is significantly slower; routing to it on every turn caused multi-minute
    # latency and timeouts. Only enable when explicitly turned on via settings,
    # and only for the most recent user instruction (not accumulated context).
    if not getattr(settings, "enable_model_routing", False):
        return None

    heavy = getattr(settings, "bedrock_heavy_model", "")
    if not heavy:
        return None

    # Only inspect the LAST message (current instruction), not history —
    # otherwise early-turn keywords keep forcing the heavy model forever.
    last = messages[-1] if messages else {}
    recent_text = str(last.get("content", "")).lower()

    # Narrow triggers: only genuinely heavy one-shot reasoning tasks.
    heavy_signals = ["synthesize final", "comprehensive final report", "deep root cause analysis"]
    if any(sig in recent_text for sig in heavy_signals):
        return heavy
    return None  # default: fast light model (Sonnet)


async def _call_llm(messages: list[dict], system_prompt: str, tools_list: list, ws_send: Callable = None, cancel_event: threading.Event | None = None, temperature: float = 0.4, force_model: str | None = None) -> dict:
    client = _get_llm()
    messages = _apply_context_window(messages)
    msg_count = len(messages)
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    timeout = max(180, min(600, total_chars // 100))
    # force_model overrides routing — used by the blind evaluator to pin Opus
    # regardless of the global routing toggle.
    model = force_model or _select_model(messages)
    model_label = (model or "light").split(".")[-1]
    logger.info(f"_call_llm: {msg_count} messages, ~{total_chars} chars, timeout={timeout}s, temp={temperature}, model={model_label}")
    try:
        if ws_send:
            return await asyncio.wait_for(
                stream_agent_response(
                    client=client,
                    messages=messages,
                    system=system_prompt,
                    tools=tools_list,
                    ws_send=ws_send,
                    cancel_event=cancel_event,
                    model=model,
                ),
                timeout=timeout,
            )
        return await asyncio.wait_for(
            client.converse(
                messages=messages,
                system=system_prompt,
                tools=tools_list,
                model=model,
            ),
            timeout=timeout,
        )
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        logger.error(f"_call_llm TIMEOUT ({timeout}s): {msg_count} msgs, {total_chars} chars")
        raise RuntimeError(f"LLM response timeout ({timeout}s)")


async def _wait_for_approval(request_id: str, timeout: int = 600) -> dict:
    event = asyncio.Event()
    _pending_approvals[request_id] = event
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return _approval_results.pop(request_id, {"approved": False})
    except asyncio.TimeoutError:
        # Mark timeout distinctly so callers can tell "no approver" from "rejected".
        return {"approved": False, "timed_out": True}
    finally:
        _pending_approvals.pop(request_id, None)


async def _wait_for_user_response(session_id: str, timeout: int = 600) -> str:
    event = asyncio.Event()
    _pending_responses[session_id] = event
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return _response_results.pop(session_id, "")
    except asyncio.TimeoutError:
        return "(no response - timeout)"
    finally:
        _pending_responses.pop(session_id, None)


async def handle_approval(session_id: str, message: dict):
    request_id = message.get("request_id", session_id)
    _approval_results[request_id] = message
    event = _pending_approvals.get(request_id)
    if event:
        event.set()


async def handle_user_response(session_id: str, content: str):
    _response_results[session_id] = content
    event = _pending_responses.get(session_id)
    if event:
        event.set()


async def handle_cancel(session_id: str):
    _cancel_flags[session_id] = True
    _session_generation[session_id] = _session_generation.get(session_id, 0) + 1
    cancel_event = _cancel_events.get(session_id)
    if cancel_event:
        cancel_event.set()
    for req_id, event in list(_pending_approvals.items()):
        _approval_results[req_id] = {"approved": False}
        event.set()
    for req_id, event in list(_pending_responses.items()):
        _response_results[req_id] = "(cancelled)"
        event.set()


def cleanup_session_state(session_id: str):
    """Remove all global state for a session. Called when session is destroyed
    to prevent unbounded memory growth across many sessions."""
    _cancel_flags.pop(session_id, None)
    _session_generation.pop(session_id, None)
    _cancel_events.pop(session_id, None)
    _session_pending_ids.pop(session_id, None)
    _response_results.pop(session_id, None)
    _subagent_depth.pop(session_id, None)
    # Hook-level session history
    try:
        from app.agent.hook_manager import clear_session_history
        clear_session_history(session_id)
    except Exception:
        pass
    # Pipeline checkpoints
    try:
        from pathlib import Path
        cp_dir = Path("./data/checkpoints")
        if cp_dir.exists():
            for f in cp_dir.glob(f"{session_id}_*.json"):
                f.unlink(missing_ok=True)
    except Exception:
        pass
    logger.info(f"[{session_id[:8]}] cleaned up session global state")


async def _execute_plan_steps(
    session: Session,
    plan_id: str,
    steps: list[dict],
    ws_send: Callable,
) -> str:
    results = []

    for step in steps:
        step_id = step["id"]
        command = step.get("command")
        description = step.get("description", "")

        if _cancel_flags.get(session.id):
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "failed"})
            results.append(f"Step {step_id}: CANCELLED")
            break

        await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "running"})

        if not command or command in ("write_file", "read_file", "web_search", "think", "ask_user", "verify_work"):
            # propose_plan only executes shell commands. A step whose "command" is a
            # tool name can't run here — surface it clearly (NOT a silent success) so
            # the agent knows nothing happened and should run those tools directly.
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "done"})
            results.append(
                f"Step {step_id} ({description}): NOT EXECUTED — '{command or '(empty)'}' is not a shell "
                f"command. propose_plan runs bash only; call the '{command}' tool directly instead."
            )
            continue

        if requires_approval(command):
            request_id = uuid.uuid4().hex[:8]
            await ws_send({
                "type": "approval_request",
                "request_id": request_id,
                "action": "shell_exec",
                "command": command,
                "risk_level": "medium",
            })
            approval = await _wait_for_approval(request_id)
            if not approval.get("approved"):
                await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "failed"})
                results.append(f"Step {step_id}: REJECTED by user")
                break
            command = approval.get("modified_command") or command

        exec_id = uuid.uuid4().hex[:8]
        # Exit code is ground truth for step success (not keyword guessing).
        exit_code, full_output, timed_out = await _docker_manager.exec_command_capture(
            session.container_id, command, timeout=900
        )
        await ws_send({"type": "terminal_output", "exec_id": exec_id, "content": full_output, "stream": "stdout", "done": False})
        await ws_send({"type": "terminal_output", "exec_id": exec_id, "content": "", "stream": "stdout", "done": True})

        truncated, _ = truncate_output(full_output)

        if timed_out or exit_code != 0:
            tag = f"[FAILED exit_code={exit_code}]" + (" [TIMED OUT]" if timed_out else "")
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "failed"})
            results.append(f"Step {step_id} ({description}):\n$ {command}\n{tag}\n{truncated}")
            results.append("Plan paused due to step failure. Agent will analyze and decide next action.")
            break
        else:
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "done"})
            results.append(f"Step {step_id} ({description}):\n$ {command}\n[exit_code=0]\n{truncated}")

    summary = "\n\n---\n\n".join(results)
    # Count ACTUAL successes by the reliable success marker appended only on exit 0
    # (line above). The old check looked for a literal "[FAILED]" that never appears
    # (the real tag is "[FAILED exit_code=N]"), so failed/skipped steps were miscounted
    # as completed — a plan with a failing step reported "N/N completed".
    completed = sum(1 for r in results if "[exit_code=0]" in r)
    total = len(steps)
    suffix = " — plan did NOT fully succeed (a step failed/was skipped; review above)" if completed < total else ""

    return f"Plan execution: {completed}/{total} steps completed{suffix}.\n\n{summary}"
