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
):

    def _stale():
        return _session_generation.get(session.id) != gen

    search_count = 0
    max_searches = 10

    responded = False
    for iteration in range(MAX_ITERATIONS):
        if _cancel_flags.get(session.id) or _stale():
            break

        # Dynamic tool list — picks up runtime-created tools mid-conversation
        tools_list = tool_registry.get_tool_specs(is_subagent=is_subagent)

        await ws_send({"type": "agent_status", "tool": "thinking", "detail": f"iteration {iteration + 1}"})
        stop_reason, content_blocks, messages = await _call_llm_with_continuation(
            messages, system_prompt, tools_list, ws_send, cancel_event, session.id
        )

        if _stale():
            break

        if stop_reason == "end_turn":
            text = _extract_text(content_blocks)
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
                        session, tool_name, tool_input, ws_send
                    )

                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_id,
                        "content": [{"text": result}],
                    }
                })

            if iteration >= MAX_ITERATIONS - 3:
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


async def _call_llm_with_continuation(
    messages: list[dict],
    system_prompt: str,
    tools_list: list,
    ws_send: Callable,
    cancel_event: threading.Event | None,
    session_id: str,
) -> tuple[str, list, list[dict]]:
    """Call LLM with automatic max_tokens continuation. Returns (stop_reason, final_content_blocks, updated_messages)."""
    all_text_parts = []
    max_continuations = 5

    for cont in range(max_continuations):
        if _cancel_flags.get(session_id):
            break

        try:
            response = await _call_llm(messages, system_prompt, tools_list, ws_send=ws_send, cancel_event=cancel_event)
        except RuntimeError as e:
            if "stalled" in str(e) or "timeout" in str(e).lower():
                logger.warning(f"[{session_id[:8]}] LLM stalled, trimming context and retrying...")
                messages = _apply_context_window(messages, max_chars=50000)
                try:
                    response = await _call_llm(messages, system_prompt, tools_list, ws_send=ws_send, cancel_event=cancel_event)
                except Exception as retry_e:
                    logger.error(f"[{session_id[:8]}] Retry also failed: {retry_e}")
                    if all_text_parts:
                        combined = "".join(all_text_parts)
                        return "end_turn", [{"text": combined}], messages
                    return "end_turn", [{"text": "Đã gặp lỗi timeout khi xử lý context lớn. Vui lòng thử lại với câu hỏi ngắn hơn hoặc yêu cầu tôi tổng hợp kết quả."}], messages
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


def _apply_context_window(messages: list[dict], max_chars: int = 80000) -> list[dict]:
    """Trim old tool results if context exceeds limit. Keep first message (user prompt) and recent messages intact."""
    total = sum(len(str(m.get("content", ""))) for m in messages)
    if total <= max_chars:
        return messages

    logger.info(f"Context too large ({total} chars), applying windowing (max {max_chars})")
    result = []
    # Always keep first user message
    if messages:
        result.append(messages[0])

    # For middle messages, progressively trim tool results
    for msg in messages[1:-6]:
        content = msg.get("content", [])
        if msg.get("role") == "user" and isinstance(content, list):
            new_content = []
            for block in content:
                if "toolResult" in block:
                    rc = block["toolResult"].get("content", [])
                    trimmed_rc = []
                    for item in rc:
                        if "text" in item and len(item["text"]) > 2000:
                            trimmed_rc.append({"text": item["text"][:2000] + "\n...[trimmed]"})
                        else:
                            trimmed_rc.append(item)
                    new_content.append({"toolResult": {**block["toolResult"], "content": trimmed_rc}})
                else:
                    new_content.append(block)
            result.append({"role": "user", "content": new_content})
        else:
            result.append(msg)

    # Keep last 6 messages intact (recent context)
    result.extend(messages[-6:])
    new_total = sum(len(str(m.get("content", ""))) for m in result)
    logger.info(f"Context windowed: {total} -> {new_total} chars")
    return result


def _select_model(messages: list[dict]) -> str | None:
    """Route to heavy model (Opus) for complex turns, light model (Sonnet) otherwise.

    Heuristic: the last assistant turn that just created a tool, or a turn that
    will likely synthesize a large report, benefits from the heavy model.
    Returns None to use the client default (light) model.
    """
    heavy = getattr(settings, "bedrock_heavy_model", "")
    if not heavy:
        return None

    # Look at the most recent user/tool-result content for routing signals.
    recent_text = ""
    for m in messages[-3:]:
        content = m.get("content", "")
        recent_text += str(content).lower()

    # Heavy-model triggers: tool creation, synthesis, final report, deep analysis
    heavy_signals = [
        "create_tool", "create a tool", "synthesize", "tổng hợp", "báo cáo",
        "final report", "comprehensive", "root cause", "exploit", "vulnerability",
        "adversarial", "definition of done",
    ]
    if any(sig in recent_text for sig in heavy_signals):
        return heavy
    return None  # default light model


async def _call_llm(messages: list[dict], system_prompt: str, tools_list: list, ws_send: Callable = None, cancel_event: threading.Event | None = None, temperature: float = 0.4) -> dict:
    client = _get_llm()
    messages = _apply_context_window(messages)
    msg_count = len(messages)
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    timeout = max(180, min(600, total_chars // 100))
    model = _select_model(messages)
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
        return {"approved": False}
    finally:
        _pending_approvals.pop(request_id, None)


async def _wait_for_user_response(session_id: str, timeout: int = 120) -> str:
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

        if not command or command in ("write_file", "read_file", "web_search", "think", "ask_user"):
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "done"})
            results.append(f"Step {step_id} ({description}): skipped (no executable command)")
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
        output_parts = []

        async for chunk in _docker_manager.exec_command(session.container_id, command):
            stream_type, content = chunk.split(":", 1)
            output_parts.append(content)
            await ws_send({
                "type": "terminal_output",
                "exec_id": exec_id,
                "content": content,
                "stream": stream_type,
                "done": False,
            })

        await ws_send({
            "type": "terminal_output",
            "exec_id": exec_id,
            "content": "",
            "stream": "stdout",
            "done": True,
        })

        full_output = "".join(output_parts)
        truncated, _ = truncate_output(full_output)

        if "error" in full_output.lower() or "traceback" in full_output.lower():
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "failed"})
            results.append(f"Step {step_id} ({description}):\n$ {command}\n[FAILED]\n{truncated}")
            results.append("Plan paused due to error. Agent will analyze and decide next action.")
            break
        else:
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "done"})
            results.append(f"Step {step_id} ({description}):\n$ {command}\n{truncated}")

    summary = "\n\n---\n\n".join(results)
    completed = sum(1 for r in results if "[FAILED]" not in r and "CANCELLED" not in r and "REJECTED" not in r)
    total = len(steps)

    return f"Plan execution: {completed}/{total} steps completed.\n\n{summary}"
