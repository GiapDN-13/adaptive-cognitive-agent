"""Test T12 CHỐNG SA-ĐÀ-BUILD (ca gài lỗi): agent write_file liên tục KHÔNG gọi giám khảo.
Kỳ vọng: tới ngưỡng (8) chèn nudge ĐÚNG 1 lần, gợi ý spawn_evaluator; file vẫn được ghi.

Chạy trong container: python /app/test_sprawl_gate.py
"""
import asyncio, sys, types
sys.path.insert(0, "/app"); sys.path.insert(0, ".")
import app.agent.loop as loop

# Agent gọi write_file 10 lần liên tục (mỗi turn 1 write_file), rồi end_turn.
TURNS = []
for i in range(10):
    TURNS.append(("tool_use", [{"toolUse": {"toolUseId": f"w{i}", "name": "write_file",
                                            "input": {"path": f"/workspace/f{i}.py", "content": "x=1"}}}]))
TURNS.append(("end_turn", [{"text": "xong"}]))
_calls = {"n": 0}

async def fake_cont(messages, system_prompt, tools_list, ws_send, cancel_event, session_id, force_model=None):
    i = _calls["n"]; _calls["n"] += 1
    stop, blocks = TURNS[min(i, len(TURNS) - 1)]
    return stop, blocks, messages

_exec = {"writes": 0}
async def fake_execute_tool(session, tool_name, tool_input, ws_send, cancel_event):
    if tool_name == "write_file":
        _exec["writes"] += 1
    return f"[{tool_name} ok]"

# Bỏ qua các gate khác để cô lập T12
async def gate_ok(*a, **k): return "DAT", "-"
async def d6_ok(*a, **k): return "OK"

_nudges = []
async def ws(msg):
    if msg.get("type") == "agent_status" and "sa-đà" in str(msg.get("detail", "")):
        _nudges.append(msg["detail"])

async def main():
    loop._call_llm_with_continuation = fake_cont
    loop._execute_tool = fake_execute_tool
    loop._prebuild_quality_gate = gate_ok
    loop._d6_build_verdict = d6_ok
    sess = types.SimpleNamespace(id="sprawltest", container_id="x", messages=[
        {"role": "user", "content": "Build RAG doanh nghiệp, làm liên tục."}])
    loop._session_generation["sprawltest"] = 0
    loop._cancel_flags.clear()
    msgs = list(sess.messages)
    await loop._run_loop(sess, msgs, "SYS", [], ws, gen=0, cancel_event=None, max_iterations=15)

    # Đếm nudge text trong messages thật mà loop dùng (text block "CỔNG CHỐNG SA-ĐÀ")
    nudge_in_msgs = 0
    for m in msgs:
        c = m.get("content")
        if isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and "text" in b and "CỔNG CHỐNG SA-ĐÀ" in b.get("text", ""):
                    nudge_in_msgs += 1
    print(f"writes thực thi: {_exec['writes']} | nudge status: {len(_nudges)} | nudge trong messages: {nudge_in_msgs}")
    # Kỳ vọng: nudge bắn đúng 1 lần (tại write thứ 8), file vẫn ghi đủ (10).
    ok = (len(_nudges) == 1 and nudge_in_msgs == 1 and _exec["writes"] == 10)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

asyncio.run(main())
