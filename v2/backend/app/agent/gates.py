"""Pure decision logic for the agent loop's "hard gates".

`loop.py` accumulated several gate/nudge mechanisms (anti-faketool, evaluator
gate, THIEU-loop, plateau/kill-port, mock-detection, credential/transient-error
classification). The *decisions* behind them are pure functions of their inputs
— but they were inlined in the loop, so they couldn't be unit-tested without
spinning up an LLM + Docker.

This module extracts those pure decisions so each is testable in isolation
(see test_gates.py — no LLM, no Docker). loop.py imports from here; behavior is
unchanged. Keep functions PURE: no I/O, no module globals, no side effects.
"""
import re


# Short social/trivial openers that should NOT be treated as the "real task"
# when picking original_request for the blind evaluator.
GREETING_PREFIXES = (
    "xin chào", "chào ", "chào!", "hi", "hello", "helo", "alo", "ê", "hey",
    "cảm ơn", "thanks", "thank you", "ok", "oke", "okay", "test", "ping",
)


def is_greeting(text: str) -> bool:
    """True for a short pure-greeting/trivial opener (not a real task)."""
    t = (text or "").strip()
    low = t.lower()
    return len(t) < 30 and any(low.startswith(p) for p in GREETING_PREFIXES)


def latest_task_request(messages: list[dict], extract_text=None) -> str:
    """Pick the user's actual TASK message (verbatim), newest→oldest, skipping
    pure greetings. Falls back to the last user turn. `extract_text` optionally
    flattens list-style content; default joins {'text':..} blocks.

    Guards the "Xin chào → judged a RAG build against a greeting" bug."""
    def _flatten(content):
        if isinstance(content, list):
            if extract_text:
                return extract_text(content)
            return " ".join(
                b.get("text", "") for b in content if isinstance(b, dict) and "text" in b
            )
        return str(content)

    last_user = ""
    for m in reversed(messages or []):
        if m.get("role") != "user":
            continue
        text = _flatten(m.get("content", "")).strip()
        if not text:
            continue
        if not last_user:
            last_user = text
        if not is_greeting(text):
            return text
    return last_user


def looks_like_faked_tool_call(text: str) -> bool:
    """Detect when the model WROTE a tool call as text instead of emitting a real
    toolUse block (so nothing executed). Markers: an XML-ish <tool_use> tag, or a
    JSON object naming a tool + its args inline in the prose."""
    if not text:
        return False
    t = text.lower()
    if "<tool_use" in t or "</tool_use" in t or "<tool_call" in t:
        return True
    if re.search(r'\{\s*"(name|tool)"\s*:\s*"[a-z_]+"\s*,\s*"(input|arguments|parameters)"\s*:', t):
        return True
    return False


def classify_evaluator_verdict(result: str) -> str:
    """Map a blind-evaluator tool result to THIEU | DU | UNCLEAR. Tolerant of
    spacing and ASCII-folded forms (THIEU/DU) seen across models."""
    rl = (result or "").upper()
    if "VERDICT: THIẾU" in rl or "VERDICT:THIẾU" in rl or "VERDICT: THIEU" in rl or "VERDICT:THIEU" in rl:
        return "THIEU"
    if "VERDICT: ĐỦ" in rl or "VERDICT:ĐỦ" in rl or "VERDICT: DU" in rl or "VERDICT:DU" in rl:
        return "DU"
    return "UNCLEAR"


def detect_kill_port_intent(command: str) -> bool:
    """True if a shell command is (yet another) attempt to kill a process / free a
    port — the slim-container loop that slips past exact-input plateau detection
    (pkill→lsof→fuser→ps→/proc...). Used to count INTENT repetition, not exact cmd."""
    cmd_l = (command or "").lower()
    if any(k in cmd_l for k in ("pkill", "lsof", "fuser", "kill ", "kill$", "kill -", "/proc/net/tcp", "address already in use")):
        return True
    if "8080" in cmd_l and ("kill" in cmd_l or "pid" in cmd_l or "netstat" in cmd_l or "ss -" in cmd_l):
        return True
    return False


def _err_str(e: Exception) -> str:
    return f"{type(e).__name__}: {e}".lower()


# AWS STS expired/invalid-token markers → PAUSE for fresh token (not fatal).
EXPIRED_TOKEN_MARKERS = (
    "expiredtoken",
    "the security token included in the request is expired",
    "security token",
    "unrecognizedclient",
    "invalidsignatureexception",
)

# Transient Bedrock server-side errors → backoff + retry SAME request.
TRANSIENT_SERVER_MARKERS = (
    "internalserver",
    "serviceunavailable",
    "service unavailable",
    "modelnotready",
    "model not ready",
    "modeltimeout",
    "throttling",
    "too many requests",
    "503",
    "500",
    "reached max retries",
)


def is_expired_token(e: Exception) -> bool:
    s = _err_str(e)
    return any(m in s for m in EXPIRED_TOKEN_MARKERS)


def is_transient_server_error(e: Exception) -> bool:
    s = _err_str(e)
    return any(m in s for m in TRANSIENT_SERVER_MARKERS)


def preexisting_workspace_note(entries: list[str]) -> str | None:
    """Given top-level /workspace entries left from a PRIOR task (container reuse),
    build a context note warning the agent not to claim them as its own work.
    Returns None when there's nothing pre-existing. Pure: caller does the `ls`."""
    items = [e.strip() for e in (entries or []) if e and e.strip()]
    if not items:
        return None
    listing = ", ".join(items[:40])
    return (
        "[SYSTEM — LƯU Ý WORKSPACE: /workspace đã có sẵn các mục từ PHIÊN/TASK TRƯỚC "
        f"(không phải bạn vừa tạo trong yêu cầu này): {listing}. "
        "TUYỆT ĐỐI không tưởng đây là sản phẩm bạn vừa làm, không báo 'đã hoàn thành' "
        "dựa trên chúng. Nếu yêu cầu mới LIÊN QUAN tới chúng → kiểm tra/ xác nhận trước khi "
        "dùng. Nếu yêu cầu mới KHÁC hẳn → làm trong thư mục riêng, và HỎI người dùng trước "
        "khi xoá/ghi đè bất cứ thứ gì có sẵn.]"
    )
