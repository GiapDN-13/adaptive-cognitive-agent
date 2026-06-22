"""Test T10 PRE-BUILD GATE bằng cách gài lỗi: agent định write_file NGAY (không đào
Bước 0). Kỳ vọng: gate CHẶN lần đầu + trả nudge "còn thiếu scale/branch", agent KHÔNG
được thực thi write_file cho tới khi think đủ.

Chạy trong container backend: python /app/test_prebuild_gate.py
"""
import asyncio, sys, types
sys.path.insert(0, "/app"); sys.path.insert(0, ".")
import app.agent.loop as loop

# --- Kịch bản LLM giả lập ---
# Turn 1: write_file ngay (chưa think gì) -> gate phải CHẶN.
# Turn 2: agent (giả lập) think bù scale+branch -> hết gap.
# Turn 3: write_file lại -> lần này cho QUA.
# Turn 4: end_turn.
TURNS = [
    ("tool_use", [{"toolUse": {"toolUseId": "t1", "name": "write_file",
                               "input": {"path": "/workspace/app.py", "content": "print(1)"}}}]),
    ("tool_use", [{"toolUse": {"toolUseId": "t2", "name": "think",
                               "input": {"thought": "Quy mô: nghìn+ tài liệu, tách trục đồng thời. So sánh ChromaDB vs Qdrant trade-off recall/chi phí."}}}]),
    ("tool_use", [{"toolUse": {"toolUseId": "t3", "name": "write_file",
                               "input": {"path": "/workspace/app.py", "content": "print(1)"}}}]),
    ("end_turn", [{"text": "done"}]),
]
_calls = {"n": 0}

async def fake_cont(messages, system_prompt, tools_list, ws_send, cancel_event, session_id, force_model=None):
    i = _calls["n"]; _calls["n"] += 1
    stop, blocks = TURNS[min(i, len(TURNS) - 1)]
    return stop, blocks, messages

# Bắt write_file có thực thi không
_executed = {"write_file": 0}
async def fake_execute_tool(session, tool_name, tool_input, ws_send, cancel_event):
    if tool_name == "write_file":
        _executed["write_file"] += 1
    return f"[{tool_name} executed]"

_gate_events = []
async def ws(msg):
    if msg.get("type") == "agent_status" and "pre-build gate" in str(msg.get("detail", "")):
        _gate_events.append(msg["detail"])

async def main():
    loop._call_llm_with_continuation = fake_cont
    loop._execute_tool = fake_execute_tool
    sess = types.SimpleNamespace(id="gatetest", container_id="x", messages=[
        {"role": "user", "content": "Xây RAG chatbot doanh nghiệp 1000 user, build luôn."}])
    loop._session_generation["gatetest"] = 0
    loop._cancel_flags.clear()

    await loop._run_loop(sess, list(sess.messages), "SYS", [], ws, gen=0, cancel_event=None, max_iterations=8)

    print(f"gate fired: {len(_gate_events)} lần -> {_gate_events}")
    print(f"write_file THỰC THI: {_executed['write_file']} lần")
    ok = (len(_gate_events) >= 1 and _executed["write_file"] == 1)
    # Kỳ vọng: gate chặn turn1 (write_file KHÔNG chạy), turn3 mới chạy 1 lần.
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

asyncio.run(main())
