"""PURE unit tests for app/agent/gates.py — the agent loop's gate decisions.

Runs with NO LLM and NO Docker (unlike eval_agentic_thinking.py which needs both).
This is the regression net for the gate LOGIC: rename a marker, flip a threshold,
break verdict parsing → this catches it instantly.

Run:  python test_gates.py     (exit 0 = all pass, 1 = a failure)
"""
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, '.')
from app.agent import gates

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


# ---- is_greeting / latest_task_request ----
check("greeting: 'Xin chào'", gates.is_greeting("Xin chào"))
check("greeting: 'hi'", gates.is_greeting("hi"))
check("not greeting: real task", not gates.is_greeting("Tạo cho tôi 1 chatbot RAG cho MekongAI"))
check("not greeting: long text starting 'ok'", not gates.is_greeting("ok now build a full RAG pipeline with OCR and RBAC please"))

# the core bug: greeting first, real task later
msgs = [
    {"role": "user", "content": "Xin chào"},
    {"role": "assistant", "content": "Xin chào! 👋"},
    {"role": "user", "content": "Tạo cho tôi 1 chatbot RAG cho MekongAI khoảng 1k users"},
]
r = gates.latest_task_request(msgs)
check("latest_task: picks real task not greeting", "RAG" in r and "chào" not in r, f"got: {r!r}")

# greeting-only → falls back to last user
check("latest_task: greeting-only fallback", gates.latest_task_request(
    [{"role": "user", "content": "Xin chào"}]) == "Xin chào")

# list-style content (Bedrock blocks)
msgs2 = [
    {"role": "user", "content": [{"text": "hi"}]},
    {"role": "user", "content": [{"text": "Phân tích log bảo mật trong /var/log"}]},
]
check("latest_task: list content", "/var/log" in gates.latest_task_request(msgs2))

# empty / no user turns
check("latest_task: empty messages", gates.latest_task_request([]) == "")


# ---- looks_like_faked_tool_call ----
check("faketool: <tool_use> tag", gates.looks_like_faked_tool_call('I will <tool_use>{...}</tool_use>'))
check("faketool: json name+input", gates.looks_like_faked_tool_call('here: {"name": "read_file", "input": {"path": "x"}}'))
check("faketool: plain prose is fine", not gates.looks_like_faked_tool_call("I will read the file and report back."))
check("faketool: empty", not gates.looks_like_faked_tool_call(""))


# ---- classify_evaluator_verdict ----
check("verdict THIEU", gates.classify_evaluator_verdict("...\nVERDICT: THIẾU\nCÒN THIẾU...") == "THIEU")
check("verdict DU", gates.classify_evaluator_verdict("VERDICT: ĐỦ\nĐÃ PHỦ...") == "DU")
check("verdict ASCII THIEU", gates.classify_evaluator_verdict("verdict: thieu") == "THIEU")
check("verdict unclear", gates.classify_evaluator_verdict("I think it's mostly fine") == "UNCLEAR")
check("verdict empty", gates.classify_evaluator_verdict("") == "UNCLEAR")


# ---- detect_kill_port_intent ----
check("killport: pkill", gates.detect_kill_port_intent("pkill -f uvicorn"))
check("killport: lsof", gates.detect_kill_port_intent("lsof -i :8080"))
check("killport: 8080+kill", gates.detect_kill_port_intent("netstat -tlnp | grep 8080"))
check("killport: normal cmd is not", not gates.detect_kill_port_intent("python3 app.py"))
check("killport: ls is not", not gates.detect_kill_port_intent("ls -la /workspace"))

# ---- detect_process_check_intent (loop ps aux trong slim container) ----
check("proc: ps aux|grep", gates.detect_process_check_intent('cd /workspace && ps aux | grep python | grep -v grep'))
check("proc: ps auxf", gates.detect_process_check_intent('ps auxf | grep uvicorn'))
check("proc: pgrep", gates.detect_process_check_intent('pgrep -f uvicorn'))
check("proc: ls khong phai", not gates.detect_process_check_intent('ls -la /workspace'))
check("proc: curl health khong phai", not gates.detect_process_check_intent('curl -s localhost:8080/'))


# ---- is_expired_token vs is_transient_server_error (must NOT overlap) ----
class ExpiredTokenException(Exception): pass
class InternalServerException(Exception): pass
et = ExpiredTokenException("The security token included in the request is expired")
se = InternalServerException("InternalServerException ... (reached max retries: 4)")
check("expired: detected", gates.is_expired_token(et))
check("expired: NOT transient", not gates.is_transient_server_error(et))
check("transient: detected", gates.is_transient_server_error(se))
check("transient: NOT expired", not gates.is_expired_token(se))
check("transient: throttling", gates.is_transient_server_error(Exception("ThrottlingException: Too many requests")))
check("neither: plain ValueError", not gates.is_expired_token(ValueError("bad")) and not gates.is_transient_server_error(ValueError("bad")))


# ---- preexisting_workspace_note ----
note = gates.preexisting_workspace_note(["mekongai-rag", "data", ""])
check("workspace note: lists entries", note and "mekongai-rag" in note and "PHIÊN/TASK TRƯỚC" in note)
check("workspace note: empty -> None", gates.preexisting_workspace_note([]) is None)
check("workspace note: whitespace-only -> None", gates.preexisting_workspace_note(["", "  "]) is None)


# ---- prebuild_thinking_gaps (T10 gate) ----
check("prebuild: trống -> thiếu cả 2", gates.prebuild_thinking_gaps("build now") == ["scale", "branch"])
check("prebuild: có scale, thiếu branch", gates.prebuild_thinking_gaps("corpus ~nghìn tài liệu, 30 đồng thời") == ["branch"])
check("prebuild: có branch, thiếu scale", gates.prebuild_thinking_gaps("ChromaDB vs Qdrant trade-off") == ["scale"])
check("prebuild: đủ cả 2 -> rỗng", gates.prebuild_thinking_gaps("khối lượng nghìn+ chunks; so sánh ChromaDB vs Qdrant theo trade-off") == [])


# ---- summary ----
n = len(results); p = sum(1 for _, ok in results if ok)
print(f"\n{'='*48}\nKET QUA: {p}/{n} PASS")
for name, ok in results:
    if not ok:
        print(f"  FAIL -> {name}")
print("RESULT:", "ALL PASS" if p == n else "FAIL")
sys.exit(0 if p == n else 1)
