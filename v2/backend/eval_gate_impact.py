"""ĐO TÁC ĐỘNG T10 GATE — N lần, qua _run_loop THẬT (gate active), dừng sau khi agent
qua lần BUILD đầu tiên, rồi chấm thinking-tới-lúc-đó theo rubric D1/D3/D4/D6 (các trụ
mà gate nhắm tới: quy mô + phân rã + đa nhánh + chấm điểm).

Khác eval_depth_multi.py: cái kia gọi converse 1 lần (KHÔNG qua loop -> gate KHÔNG bắn).
Cái này chạy ĐÚNG agent loop nên T10 có hiệu lực -> đo được gate giúp ổn định tới đâu.

Chạy: python /app/eval_gate_impact.py [N=3]
"""
import asyncio, sys, types, re
sys.path.insert(0, "/app"); sys.path.insert(0, ".")
import app.agent.loop as loop
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.config import settings

TASK = (
    "Xây chatbot RAG cho doanh nghiệp MekongAI — ~1000 nhân viên, 4 phòng ban "
    "(HR/Finance/Engineering/Admin), mỗi phòng nhiều người và mỗi người nhiều tài liệu. "
    "Tài liệu đa định dạng (PDF/Word/Excel). Phân quyền theo phòng ban. Thiết kế và build."
)

RUBRIC = """Chấm CHIỀU SÂU TƯ DUY (4 trụ mà cổng pre-build nhắm tới). PASS khắt khe, kèm trích dẫn.
[D1] Suy luận QUY MÔ định lượng (người×file→nghìn+, tách trục đồng-thời vs khối-lượng).
[D3] Phân rã + phần KHÓ NHẤT trước.
[D4] Đa nhánh (≥2 phương án + so trade-off + chọn).
[D6] Chấm điểm CÓ TRỌNG SỐ (tiêu chí + ưu tiên + nhánh thắng vì điểm cao hơn).
TRẢ:
D1: PASS|FAIL — <bc>
D3: PASS|FAIL — <bc>
D4: PASS|FAIL — <bc>
D6: PASS|FAIL — <bc>
"""

async def one_run(i):
    # Đo CHẤT LƯỢNG tư duy TRƯỚC build = thinking tại thời điểm gate CHO QUA (DAT).
    # Đó là lúc tư duy-trước-build hoàn tất; không cần chờ build chạy (chậm/timeout).
    # Hook vào _prebuild_quality_gate: khi DAT -> chốt thinking + dừng loop.
    captured = {"thinking": "", "built": False, "gate_blocks": 0}
    real_gate = loop._prebuild_quality_gate
    async def gate_capture(thinking_text, session_id):
        v, fb = await real_gate(thinking_text, session_id)
        if v == "CHUA_DAT":
            captured["gate_blocks"] += 1
        else:  # DAT -> tư duy đủ để build -> chốt & dừng
            captured["thinking"] = thinking_text
            captured["built"] = True
            loop._cancel_flags[session_id] = True
        return v, fb
    loop._prebuild_quality_gate = gate_capture
    real_exec = loop._execute_tool
    async def exec_stop(session, tool_name, tool_input, ws_send, cancel_event):
        # Phòng khi gate không bắn (task nhỏ): vẫn chốt ở build đầu.
        r = await real_exec(session, tool_name, tool_input, ws_send, cancel_event)
        if tool_name in ("write_file", "create_tool") and not captured["built"]:
            captured["built"] = True
            loop._cancel_flags[session.id] = True
        return r
    loop._execute_tool = exec_stop

    ANSWER = ("Quyết hết, build luôn không hỏi thêm: 1000 đăng ký, peak ~30-50 đồng thời "
              "NHƯNG tài liệu doanh nghiệp tăng dần (nghìn+) — bạn tự chọn vector store cho đúng. "
              "LLM/embedding: Bedrock thật (creds ở /root/.aws/credentials). File mẫu ở /workspace/docs. "
              "Auth tự build đơn giản, Admin xem tất cả. MVP production-ready.")
    async def _answer_later(sess_id):
        for _ in range(100):
            if sess_id in loop._pending_responses:
                break
            await asyncio.sleep(0.1)
        await loop.handle_user_response(sess_id, ANSWER)
    async def ws(msg):
        # Gom CẢ think-tool (agent_thinking) LẪN văn xuôi stream (agent_chunk) —
        # agent có thể suy bằng text thay vì gọi tool think.
        if msg.get("type") in ("agent_thinking", "agent_chunk") and msg.get("content"):
            captured["thinking"] += msg["content"]
        if msg.get("type") == "agent_question":
            asyncio.create_task(_answer_later(sid))
        if msg.get("type") == "approval_request":
            rid = msg.get("request_id")
            async def _appr():
                for _ in range(100):
                    if rid in loop._pending_approvals: break
                    await asyncio.sleep(0.1)
                await loop.handle_approval(sid, {"request_id": rid, "approved": True})
            asyncio.create_task(_appr())

    # Tạo container THẬT để write_file/shell_exec không lỗi (lệch thinking).
    import app.deps as deps
    from app.core.docker_manager import DockerManager
    from app.core.session_manager import SessionManager
    dm = DockerManager(); deps._docker_manager = dm
    sm = SessionManager(dm); deps._session_manager = sm
    sess = await sm.create()
    sid = sess.id
    sess.messages = [{"role": "user", "content": TASK}]
    loop._session_generation[sid] = 0
    loop._cancel_flags.pop(sid, None)
    # Seed creds + 1 file mẫu mỗi phòng (để agent build thật, không kẹt vì thiếu đồ).
    try:
        import configparser, os
        cp = configparser.ConfigParser(); cp.read("/root/.aws/credentials")
        if cp.has_section("default"):
            s = cp["default"]; ini = "[default]\n"
            ini += f"aws_access_key_id = {s.get('aws_access_key_id','').strip()}\n"
            ini += f"aws_secret_access_key = {s.get('aws_secret_access_key','').strip()}\n"
            if s.get("aws_session_token"): ini += f"aws_session_token = {s.get('aws_session_token').strip()}\n"
            ini += "region = us-east-1\n"
            await dm.exec_command_simple(sess.container_id, "mkdir -p /root/.aws /workspace/docs")
            await dm.copy_file_to(sess.container_id, ini.encode(), "/root/.aws/credentials")
            await dm.copy_file_to(sess.container_id, b"[default]\nregion = us-east-1\n", "/root/.aws/config")
        for fn, ct in [("hr.txt", "HR: nghi phep 12 ngay/nam."), ("finance.csv", "Hang muc,Dinh muc\nCong tac,2000000"),
                       ("eng.txt", "ENG: deploy 9h-16h."), ("admin.txt", "ADMIN: gio lam 8h30-17h30.")]:
            await dm.copy_file_to(sess.container_id, ct.encode(), f"/workspace/docs/{fn}")
    except Exception:
        pass
    try:
        from app.agent.tool_registry import tool_registry
        tools = tool_registry.get_tool_specs(is_subagent=False)
    except Exception:
        tools = []
    # Bedrock cần content dạng list-of-blocks (không phải str).
    msgs = [{"role": "user", "content": [{"text": TASK}]}]
    try:
        await asyncio.wait_for(
            loop._run_loop(sess, msgs, build_system_prompt(False), tools, ws,
                           gen=0, cancel_event=None, max_iterations=30),
            timeout=600)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
    finally:
        loop._execute_tool = real_exec
        loop._prebuild_quality_gate = real_gate
        try:
            await dm.destroy_container(sess.container_id)
        except Exception:
            pass
    # captured["thinking"] đã được set tại thời điểm gate cho qua (DAT). Bổ sung
    # thinking từ messages phòng trường hợp gate không bắn (chốt ở exec_stop).
    if len((captured["thinking"] or "").strip()) < 150:
        acc = captured["thinking"] or ""
        for m in sess.messages:
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict):
                        if "text" in b:
                            acc += "\n" + b["text"]
                        if "toolUse" in b and isinstance(b["toolUse"].get("input"), dict):
                            acc += "\n" + str(b["toolUse"]["input"].get("thought", ""))
        captured["thinking"] = acc
    return captured

async def judge(blob):
    if len(blob) < 150:
        return None
    heavy = getattr(settings, "bedrock_heavy_model", "") or "us.anthropic.claude-opus-4-7"
    c = create_llm_client()
    r = await c.converse(messages=[{"role": "user", "content": [{"text": RUBRIC + "\n\n=== THINKING ===\n" + blob}]}],
                         system="Giám khảo khắt khe.", max_tokens=1200, model=heavy)
    out = "".join(b.get("text", "") for b in r.get("output", {}).get("message", {}).get("content", []))
    v = dict(re.findall(r"(D[1346]):\s*(PASS|FAIL)", out))
    return {k: v.get(k) == "PASS" for k in ["D1", "D3", "D4", "D6"]}

async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    dims = ["D1", "D3", "D4", "D6"]
    tally = {d: 0 for d in dims}; valid = 0
    for i in range(n):
        try:
            cap = await one_run(i)
            res = await judge(cap["thinking"])
        except Exception as e:
            print(f"  run {i+1}: ERROR {type(e).__name__}: {str(e)[:90]}"); continue
        if res is None:
            print(f"  run {i+1}: SKIP (thinking ngắn {len(cap['thinking'])}, built={cap['built']})"); continue
        valid += 1
        for d in dims: tally[d] += 1 if res[d] else 0
        print(f"  run {i+1}: " + " ".join(f"{d}={'P' if res[d] else 'F'}" for d in dims) + f"  (gate_blocks={cap.get('gate_blocks',0)}, built={cap['built']})")
    print(f"\n{'='*48}")
    if valid:
        for d in dims:
            print(f"  {d}: {tally[d]}/{valid} ({tally[d]/valid*100:.0f}%)")
        print(f"TB: {sum(tally[d]/valid for d in dims):.1f}/4")
    sys.exit(0)

asyncio.run(main())
