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


# Pure gate/decision logic lives in gates.py (unit-tested without LLM/Docker).
# These thin wrappers keep loop.py's existing call sites unchanged.
from app.agent import gates


def _latest_task_request(session) -> str:
    """Verbatim user TASK message for the blind evaluator (skips greetings).
    Delegates to gates.latest_task_request; see it for the bug this guards."""
    return gates.latest_task_request(getattr(session, "messages", []) or [], extract_text=_extract_text)


async def _preexisting_workspace_note(session) -> str | None:
    """If /workspace holds files from a PRIOR task (container reuse), return a
    context note so the agent doesn't claim them as its own work. The `ls` (I/O)
    is here; the message logic is the pure gates.preexisting_workspace_note."""
    cid = getattr(session, "container_id", None)
    if not cid:
        return None
    try:
        from app.deps import get_docker_manager
        dm = get_docker_manager()
        # List top-level entries; ignore dotfiles. Cheap, bounded.
        _code, out = await dm.exec_command_simple(
            cid, "ls -1 /workspace 2>/dev/null | grep -v '^[.]' | head -40"
        )
    except Exception:
        return None
    return gates.preexisting_workspace_note((out or "").splitlines())


def _is_transient_server_error(e: Exception) -> bool:
    """Transient Bedrock server error (5xx/throttle) → backoff+retry. See gates."""
    return gates.is_transient_server_error(e)


_PREBUILD_JUDGE_PROMPT = """Bạn là bộ chấm CỔNG TRƯỚC-KHI-BUILD, NGHIÊM KHẮC. Đọc chuỗi suy
nghĩ của một agent vừa định bắt tay XÂY (write_file) một hệ thống. Chỉ cho qua (DAT) khi
HỘI ĐỦ CẢ 2 trụ ở mức CÓ BẰNG CHỨNG TRONG TEXT — KHÔNG suy diễn hộ, KHÔNG nương tay:

A. ƯỚC QUY MÔ ĐỊNH LƯỢNG: có CON SỐ tổng khối lượng/tải suy từ ngữ cảnh (vd "4 phòng × ~15
   người × N file → ~nghìn tài liệu"), VÀ tách rõ trục "đồng thời" khỏi trục "khối lượng dữ
   liệu". Phán "nhỏ/lớn/đủ" suông = CHƯA ĐẠT.

B. ĐA NHÁNH CÓ CHẤM ĐIỂM (khắt khe — đây là chỗ hay bị trượt): với ÍT NHẤT MỘT quyết định
   kiến trúc, phải có ĐỦ 3 yếu tố:
   (1) nêu ≥2 PHƯƠNG ÁN cụ thể (vd ChromaDB vs Qdrant vs pgvector),
   (2) mỗi phương án kèm TRADE-OFF (điểm mạnh/yếu theo tiêu chí: recall/độ trễ/chi phí/scale),
   (3) CHỌN có CHẤM ĐIỂM/ƯU TIÊN: nêu TIÊU CHÍ nào QUAN TRỌNG NHẤT với bài (không cào bằng)
       và phương án thắng VÌ ăn điểm ở đúng tiêu chí đó (vd "X thắng vì mạnh ở [tiêu chí ưu
       tiên] dù thua ở [tiêu chí nhẹ]"). Bảng điểm là tốt nhất nhưng KHÔNG bắt buộc; tối thiểu
       phải thấy rõ ƯU TIÊN + lý do thắng gắn với ưu tiên đó.
   Chỉ liệt kê tên option rồi chọn ("dùng X cho đơn giản/đủ dùng/cân bằng/phù hợp hơn") mà
   KHÔNG nêu tiêu chí ưu tiên = CHƯA ĐẠT. Để USER quyết hộ mà agent không tự chấm = CHƯA ĐẠT.

C. KHÔNG CLAIM CHI TIẾT KỸ THUẬT TỪ TRÍ NHỚ: nếu thinking khẳng định CHẮC NỊCH chi tiết dễ
   sai (model ID "có sẵn", embedding "N chiều", "(đã test)", tên hàm/version API) MÀ KHÔNG
   đánh dấu là giả định cần verify / KHÔNG có dấu hiệu đã chạy lệnh kiểm trong môi trường này
   → CHƯA ĐẠT. Đạt nếu: đã verify (có chạy lệnh kiểm) HOẶC đánh dấu rõ "[giả định — cần
   verify]". Nếu thinking KHÔNG đụng tới chi tiết loại này → C không áp dụng (đừng vì C mà chặn).

NGUYÊN TẮC: nếu KHÔNG CHẮC một trụ đã đạt → trả CHUA_DAT (mặc định nghiêng về chặn). Chỉ
miễn khi task hiển nhiên KHÔNG phải thiết kế hệ thống (vd sửa 1 hàm, đổi text) → DAT.

Trả ĐÚNG 2 dòng:
VERDICT: DAT | CHUA_DAT
FEEDBACK: <nếu CHUA_DAT: trụ nào thiếu (A/B/C) + thiếu yếu tố gì cụ thể; nếu DAT để "-">
"""


async def _prebuild_quality_gate(thinking_text: str, session_id: str) -> tuple[str, str]:
    """LLM-judge cho cổng pre-build (T10): chấm chuỗi suy nghĩ đã đủ chất lượng (ước quy
    mô + đa nhánh có chấm điểm) chưa. Trả (verdict, feedback) với verdict ∈ {DAT, CHUA_DAT}.
    Fail-open: lỗi/judge không rõ → DAT (không chặn oan, tránh treo task vì sự cố hạ tầng)."""
    if len((thinking_text or "").strip()) < 80:
        return "CHUA_DAT", "Chuỗi suy nghĩ quá ngắn — chưa thấy phân tích quy mô hay so sánh phương án nào."
    try:
        client = _get_llm()
        heavy = getattr(settings, "bedrock_heavy_model", "") or None
        resp = await asyncio.wait_for(
            client.converse(
                messages=[{"role": "user", "content": [{"text": _PREBUILD_JUDGE_PROMPT + "\n\n=== SUY NGHĨ ===\n" + thinking_text[-8000:]}]}],
                system="Bộ chấm khắt khe nhưng công bằng. Trả đúng 2 dòng VERDICT/FEEDBACK.",
                max_tokens=400,
                model=heavy,
            ),
            timeout=60,
        )
        out = "".join(b.get("text", "") for b in resp.get("output", {}).get("message", {}).get("content", []))
        up = out.upper()
        if "CHUA_DAT" in up or "CHƯA ĐẠT" in up:
            fb = ""
            for line in out.splitlines():
                if "FEEDBACK" in line.upper():
                    fb = line.split(":", 1)[-1].strip()
            return "CHUA_DAT", (fb or "Bổ sung: ước quy mô định lượng + so sánh ≥2 phương án có chấm điểm.")
        return "DAT", "-"
    except Exception:
        logger.exception(f"[{session_id[:8]}] prebuild gate judge error — fail-open (cho qua)")
        return "DAT", "-"


_D6_JUDGE_PROMPT = """Đọc TOÀN BỘ suy nghĩ của agent (đã build xong 1 hệ thống). Trả lời 1
câu hỏi DUY NHẤT: agent có CHẤM ĐIỂM CÓ TRỌNG SỐ cho ít nhất MỘT quyết định kiến trúc lõi
(vd chọn vector store / embedding / retrieval) không?

CÓ (trả YES) khi: nêu ≥2 phương án + nêu TIÊU CHÍ kèm TRỌNG SỐ/ƯU TIÊN (tiêu chí nào nặng
ký nhất với bài) + cho thấy phương án thắng VÌ điểm/ưu tiên đó (bảng điểm, hoặc "X thắng vì
mạnh ở tiêu chí ưu tiên dù thua ở tiêu chí nhẹ").
KHÔNG (trả NO) khi: chỉ chọn kèm lý do chung ("vì scale tốt", "phù hợp", "đơn giản") mà
không có trọng số/ưu tiên tường minh; hoặc không so sánh phương án nào.

Trả ĐÚNG 1 từ: YES hoặc NO"""


async def _has_weighted_scoring(thinking_text: str, session_id: str) -> bool:
    """T11 judge: thinking đã có chấm điểm CÓ TRỌNG SỐ (D6) cho 1 quyết định kiến trúc chưa?
    Fail-open: lỗi → True (coi như có, không chặn oan vì sự cố hạ tầng)."""
    if len((thinking_text or "").strip()) < 80:
        return True  # quá ngắn để phán — không chặn (pre-build gate đã lo phần thiếu hẳn)
    try:
        client = _get_llm()
        heavy = getattr(settings, "bedrock_heavy_model", "") or None
        resp = await asyncio.wait_for(
            client.converse(
                messages=[{"role": "user", "content": [{"text": _D6_JUDGE_PROMPT + "\n\n=== SUY NGHĨ ===\n" + thinking_text[-9000:]}]}],
                system="Trả đúng 1 từ YES hoặc NO.",
                max_tokens=10,
                model=heavy,
            ),
            timeout=60,
        )
        out = "".join(b.get("text", "") for b in resp.get("output", {}).get("message", {}).get("content", [])).upper()
        return "NO" not in out  # NO → thiếu D6 → False (chặn); YES/khác → True
    except Exception:
        logger.exception(f"[{session_id[:8]}] D6 gate judge error — fail-open")
        return True


def _is_expired_token(e: Exception) -> bool:
    """AWS STS expired/invalid-token → pause for fresh token. See gates."""
    return gates.is_expired_token(e)


async def _pause_for_fresh_credentials(session_id: str, ws_send: Callable) -> bool:
    """AWS creds expired mid-task. Instead of crashing (which would force a
    backend recreate and lose context), pause and ask the user to paste a fresh
    token into the mounted ~/.aws/credentials, then click Continue. On Continue
    we rebuild the boto3 client so it reads the new token — no restart.

    Returns True if the user signalled to continue, False on timeout/cancel.
    Reuses the existing agent_question → user_response channel (no frontend change).
    """
    await ws_send({
        "type": "agent_question",
        "question": (
            "⏸️ Token AWS đã hết hạn. Hãy dán token mới vào ~/.aws/credentials "
            "(profile [default]), rồi bấm \"Tiếp tục\" để tôi chạy tiếp đúng chỗ "
            "đang dở — KHÔNG mất context."
        ),
        "options": ["Tiếp tục"],
    })
    await ws_send({"type": "agent_status", "tool": "thinking", "detail": "chờ token AWS mới..."})
    # Give the user a long window (15 min) to fetch + paste a new token.
    resp = await _wait_for_user_response(session_id, timeout=900)
    if resp in ("(no response - timeout)", "(cancelled)") or _cancel_flags.get(session_id):
        return False
    # Rebuild the client so the freshly-pasted token takes effect.
    try:
        client = _get_llm()
        if hasattr(client, "reload_credentials"):
            client.reload_credentials()
        logger.info(f"[{session_id[:8]}] credentials reloaded after expiry — resuming")
    except Exception:
        logger.exception(f"[{session_id[:8]}] failed to reload credentials")
        return False
    return True

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
        # #4 — Container có thể được TÁI DÙNG (rehydrate sau restart, hoặc reconnect
        # tab cũ). Nếu /workspace đã có sản phẩm từ phiên trước, agent dễ tưởng đó là
        # thứ MÌNH vừa tạo → loạn (vd thấy mekongai-rag/ rồi báo "tôi đã build xong").
        # Chèn 1 ghi chú trung thực vào context để agent xác nhận trước khi đụng/xoá.
        note = await _preexisting_workspace_note(session)
        if note:
            session.messages.append({"role": "user", "content": note})
            await save_session_messages(session.id, session.messages)

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
    # T8: gate vòng-lặp-tới-khi-ĐỦ. Theo dõi verdict giám khảo gần nhất + số lần
    # bị chặn vì THIẾU (cap để không treo nếu agent loay hoay không sửa nổi).
    last_evaluator_verdict = None          # None | "THIEU" | "DU" | "UNCLEAR"
    evaluator_thieu_blocks = 0
    MAX_THIEU_BLOCKS = 3
    # T10 (PRE-BUILD gate): ổn định hóa chuỗi tư duy. Đo cho thấy agent đào sâu
    # KHÔNG nhất quán (lúc 5/7 lúc 0/7) — vì prompt-only để agent "tùy hứng". Gate
    # này CHẶN lần write_file/create_tool đầu tiên của task build NẾU chuỗi think
    # chưa thể hiện đủ: (a) ước QUY MÔ định lượng, (b) so ≥2 NHÁNH cho 1 quyết định.
    # Ép quay lại think rồi mới cho build. Cap 2 lần để không deadlock.
    thinking_text_so_far = ""              # gom mọi 'thought' của think để soi gate
    prebuild_gate_blocks = 0
    MAX_PREBUILD_BLOCKS = 2
    # T11 (POST-BUILD D6 gate): pre-build gate bắn thưa khi agent build nhanh → D6
    # (chấm điểm có trọng số) hay lọt. Bổ sung 1 cổng ở end_turn: đã build mà toàn bộ
    # suy nghĩ CHƯA thể hiện chấm điểm có trọng số cho quyết định kiến trúc → chặn báo
    # xong 1 lần, ép bổ sung. Cap 1 lần để không treo.
    d6_gate_nudged = False

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

        # T10: gom MỌI text suy nghĩ của assistant (kể cả khi agent suy bằng văn xuôi
        # thay vì gọi tool `think`) để cổng pre-build soi đúng — tránh chặn nhầm khi
        # agent đã đào sâu nhưng không dùng tool think.
        _turn_text = _extract_text(content_blocks)
        if _turn_text:
            thinking_text_so_far += "\n" + _turn_text

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
            # Gate 1: đã build mà CHƯA bao giờ gọi giám khảo → ép gọi lần đầu.
            if (not is_subagent and built_something
                    and "spawn_evaluator" not in tools_used_ever
                    and not evaluator_gate_nudged):
                evaluator_gate_nudged = True
                task_req = _latest_task_request(session)
                task_hint = (
                    f"\nYÊU CẦU CẦN NGHIỆM THU (nguyên văn lượt giao việc thực chất — "
                    f"truyền ĐÚNG chuỗi này vào original_request, KHÔNG lấy lời chào): \"{task_req[:400]}\""
                ) if task_req else ""
                messages.append({"role": "assistant", "content": content_blocks})
                messages.append({"role": "user", "content": [{"text": (
                    "[SYSTEM — CỔNG NGHIỆM THU: bạn sắp báo 'hoàn thành' một sản phẩm đã BUILD "
                    "nhưng CHƯA qua giám khảo mù. Tự verify_work của bạn là chủ quan — bắt buộc gọi "
                    "`spawn_evaluator` (giám khảo độc lập, model mạnh, tự điều tra trên sản phẩm thật) "
                    "với original_request (nguyên văn yêu cầu gốc), product (đường dẫn/cách chạy), và "
                    "data_location (file thật). Nếu verdict THIẾU → làm tiếp rồi gọi lại. Chỉ báo hoàn "
                    "thành sau khi giám khảo phán ĐỦ. Gọi spawn_evaluator NGAY bây giờ."
                    + task_hint + "]"
                )}]})
                continue
            # T11 — POST-BUILD D6 GATE: đã build, đã (hoặc đang) định báo xong, nhưng suy
            # nghĩ chưa thể hiện CHẤM ĐIỂM CÓ TRỌNG SỐ cho quyết định kiến trúc → chặn 1 lần.
            # Bắt được run "build nhanh" mà pre-build gate đã lọt. Chỉ áp khi thật sự build.
            if (not is_subagent and built_something and not d6_gate_nudged):
                has_d6 = await _has_weighted_scoring(thinking_text_so_far, session.id)
                if not has_d6:
                    d6_gate_nudged = True
                    messages.append({"role": "assistant", "content": content_blocks})
                    messages.append({"role": "user", "content": [{"text": (
                        "[SYSTEM — CỔNG CHẤM ĐIỂM: bạn đã build nhưng các quyết định kiến trúc lõi "
                        "(vd vector store / embedding / retrieval) CHƯA được chấm điểm có trọng số rõ "
                        "ràng. Hãy dùng `think`: với quyết định kiến trúc quan trọng nhất, nêu 2-3 "
                        "PHƯƠNG ÁN + các TIÊU CHÍ kèm TRỌNG SỐ/ƯU TIÊN (tiêu chí nào nặng ký nhất với "
                        "bài này) + cho thấy phương án đã chọn thắng VÌ điểm có trọng số cao hơn (hoặc "
                        "nếu phương án đang dùng KHÔNG thắng → đổi cho đúng). Làm xong rồi mới báo cáo.]"
                    )}]})
                    continue
            # Gate 2 (T8): đã gọi giám khảo nhưng verdict THIẾU → CHẶN báo cáo, ép làm
            # tiếp phần thiếu rồi gọi lại — lặp tới khi ĐỦ hoặc chạm cap (chống treo).
            if (not is_subagent and built_something
                    and last_evaluator_verdict == "THIEU"
                    and evaluator_thieu_blocks < MAX_THIEU_BLOCKS):
                evaluator_thieu_blocks += 1
                last_evaluator_verdict = None  # reset, chờ lần kiểm lại
                messages.append({"role": "assistant", "content": content_blocks})
                messages.append({"role": "user", "content": [{"text": (
                    f"[SYSTEM — GIÁM KHẢO PHÁN THIẾU (lần {evaluator_thieu_blocks}/{MAX_THIEU_BLOCKS}): "
                    "TUYỆT ĐỐI chưa được báo 'hoàn thành'. Nhưng TRƯỚC KHI tự sửa, hãy PHÂN LOẠI mỗi điểm thiếu:\n"
                    "• Thiếu do CẦN INPUT TỪ NGƯỜI DÙNG (API key/credentials như Bedrock, tài liệu thật, quyết "
                    "định nghiệp vụ, quyền truy cập) → DỪNG và `ask_user` xin thứ đó. TUYỆT ĐỐI KHÔNG tự chế giải "
                    "pháp thay thế để CHE LẤP (vd thiếu Bedrock thì lặng lẽ đổi sang BM25) — đó là né vấn đề gốc. "
                    "Nếu thật sự có fallback hợp lý, vẫn phải `ask_user` nêu rõ 'thiếu X; chờ bạn cấp X, hoặc dùng "
                    "fallback Y với hạn chế Z?' để người dùng QUYẾT, không tự ý.\n"
                    "• Thiếu do LỖI KỸ THUẬT bạn tự sửa được (quên index, pipeline lỗi, chưa verify) → LÀM phần đó "
                    "(write_file/shell_exec + verify_work), rồi GỌI LẠI `spawn_evaluator`.\n"
                    "Chỉ báo hoàn thành khi giám khảo phán ĐỦ.]"
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
                # T10: gom suy nghĩ (think.thought) để gate pre-build soi đã đào đủ chưa.
                if tool_name == "think" and isinstance(tool_input, dict):
                    thinking_text_so_far += "\n" + str(tool_input.get("thought", ""))

                # T10 PRE-BUILD GATE (LLM-judge): chặn lần BUILD đầu tiên nếu chuỗi suy
                # nghĩ CHƯA đạt chất lượng (đa nhánh + so trade-off + chấm điểm + ước quy
                # mô). Heuristic từ khóa không đủ (ép "đi qua cửa" chứ không ép chất lượng)
                # — nên dùng 1 LLM nhẹ chấm như T7/T8. Cap để không deadlock.
                _build_before = (tools_used_ever - {tool_name}) & {"write_file", "create_tool"}
                if (not is_subagent
                        and tool_name in ("write_file", "create_tool")
                        and not _build_before
                        and prebuild_gate_blocks < MAX_PREBUILD_BLOCKS):
                    _verdict, _feedback = await _prebuild_quality_gate(thinking_text_so_far, session.id)
                    if _verdict == "CHUA_DAT":
                        prebuild_gate_blocks += 1
                        await ws_send({"type": "agent_status", "tool": "thinking", "detail": f"pre-build gate ({prebuild_gate_blocks}/{MAX_PREBUILD_BLOCKS})"})
                        # Không thực thi build; trả nudge (kèm feedback cụ thể của bộ chấm).
                        tool_results.append({
                            "toolResult": {
                                "toolUseId": tool_id,
                                "content": [{"text": (
                                    "[SYSTEM — CỔNG TRƯỚC-KHI-BUILD: chưa được tạo file/công cụ. "
                                    "Một bộ chấm độc lập thấy chuỗi suy nghĩ của bạn CHƯA ĐẠT chuẩn tư duy "
                                    "trước khi build. CỤ THỂ CẦN BỔ SUNG:\n" + _feedback + "\n"
                                    "Hãy dùng `think` xử lý ĐÚNG các điểm trên — bằng CON SỐ + TIÊU CHÍ + "
                                    "SO SÁNH ≥2 PHƯƠNG ÁN có chấm điểm — RỒI mới write_file. Không lặp lại "
                                    "lời chung chung; phải thực sự so sánh và chấm điểm.]"
                                )}],
                            }
                        })
                        continue  # bỏ qua thực thi tool này, sang block kế

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

                # T8: bắt verdict của giám khảo mù để gate vòng-lặp-tới-khi-ĐỦ.
                if tool_name == "spawn_evaluator":
                    last_evaluator_verdict = gates.classify_evaluator_verdict(result)

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
                        intent = "kill_or_free_port" if gates.detect_kill_port_intent(
                            str(tool_input.get("command", ""))) else None
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
    """Tool call written as text instead of a real toolUse block. See gates."""
    return gates.looks_like_faked_tool_call(text)


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


async def _call_llm_with_expiry_pause(
    messages: list[dict],
    system_prompt: str,
    tools_list: list,
    ws_send: Callable,
    cancel_event: threading.Event | None,
    session_id: str,
    force_model: str | None = None,
) -> dict:
    """Wrap _call_llm so transient failures recover instead of crashing the task:
      • ExpiredTokenException → pause for a fresh token, reload client, retry.
      • InternalServerException / 5xx / throttling (Bedrock server hiccup) → wait
        with exponential backoff, retry the SAME request (boto3 already exhausted
        its own retries, but the error is transient on AWS's side, not ours).
    Oversized-context stalls (RuntimeError) still propagate to _retry_after_stall."""
    expired_retries = 0
    server_retries = 0
    while True:
        try:
            return await _call_llm(
                messages, system_prompt, tools_list,
                ws_send=ws_send, cancel_event=cancel_event, force_model=force_model,
            )
        except (asyncio.CancelledError, asyncio.TimeoutError, RuntimeError):
            raise
        except Exception as e:
            if _is_expired_token(e) and expired_retries < 3 and not _cancel_flags.get(session_id):
                expired_retries += 1
                logger.warning(f"[{session_id[:8]}] AWS token expired mid-call — pausing for fresh creds (attempt {expired_retries})")
                if await _pause_for_fresh_credentials(session_id, ws_send):
                    continue  # retry same request with reloaded client
            if _is_transient_server_error(e) and server_retries < 4 and not _cancel_flags.get(session_id):
                server_retries += 1
                backoff = min(2 ** server_retries, 20)  # 2,4,8,16,20s
                logger.warning(f"[{session_id[:8]}] Bedrock transient server error — retry {server_retries}/4 after {backoff}s: {type(e).__name__}")
                await ws_send({"type": "agent_status", "tool": "thinking", "detail": f"Bedrock quá tải, thử lại ({server_retries}/4)..."})
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    raise
                continue  # retry same request after backoff
            raise


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
            response = await _call_llm_with_expiry_pause(
                messages, system_prompt, tools_list, ws_send, cancel_event, session_id, force_model
            )
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
