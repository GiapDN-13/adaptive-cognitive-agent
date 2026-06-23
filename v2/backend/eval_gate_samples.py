"""Thu THỐNG KÊ trace mà gate BẮN: chạy agent loop thật N lần, dừng ngay sau build đầu
(sau khi đã qua gate), chấm D1-D7 trên TOÀN BỘ thinking. So với baseline 1-turn (D4/D6~17%)
để biết gate nâng D4/D6 bao nhiêu. Chống nhiễu: retry Bedrock 503/throttle, parser linh hoạt.

Chạy: python /app/eval_gate_samples.py [N=3]
"""
import asyncio, sys, re, types
sys.path.insert(0, "/app"); sys.path.insert(0, ".")
import app.agent.loop as loop
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.config import settings

TASK = ("Xây chatbot RAG cho doanh nghiệp MekongAI — ~1000 nhân viên, 4 phòng ban, mỗi phòng "
        "nhiều người và mỗi người nhiều tài liệu, đa định dạng, phân quyền phòng ban. Tài liệu "
        "mẫu ở /workspace/docs, creds Bedrock ở /root/.aws/credentials. Thiết kế và BUILD.")
RUBRIC = """Chấm 7 trụ tư duy, PASS khắt khe, kèm trích dẫn.
[D1] QUY MÔ định lượng (người×file→nghìn+, tách đồng-thời/khối-lượng).
[D2] Xử lý nội dung Excel (ngữ nghĩa hàng/cột).
[D3] Phân rã + phần khó nhất trước.
[D4] Đa nhánh (≥2 PA + trade-off + chọn).
[D5] Tự phản chiếu (Wait/Aha).
[D6] Chấm điểm CÓ TRỌNG SỐ.
[D7] Biết khi không biết (đánh dấu model ID/dim cần verify).
TRẢ mỗi dòng: D1: PASS|FAIL — .. (đủ D1..D7)"""

async def _conv(c, **kw):
    last = None
    for a in range(4):
        try: return await c.converse(**kw)
        except Exception as e:
            s = f"{type(e).__name__}{e}".lower()
            if any(m in s for m in ("serviceunavailable","throttl","timeout","too many","503","500","internalserver")):
                last = e; await asyncio.sleep(2**a); continue
            raise
    raise last

async def one(i):
    cap = {"thinking": "", "gate_fired": 0, "built": False}
    real_exec = loop._execute_tool
    async def exec_stop(s, tn, ti, w, c):
        r = await real_exec(s, tn, ti, w, c)
        if tn in ("write_file", "create_tool"):
            cap["built"] = True
            loop._cancel_flags[s.id] = True   # dừng sau build đầu (đã qua gate)
        return r
    loop._execute_tool = exec_stop
    real_gate = loop._prebuild_quality_gate
    async def gate_watch(tt, sid):
        v, fb = await real_gate(tt, sid)
        if v == "CHUA_DAT": cap["gate_fired"] += 1
        return v, fb
    loop._prebuild_quality_gate = gate_watch

    import app.deps as deps
    from app.core.docker_manager import DockerManager
    from app.core.session_manager import SessionManager
    dm = DockerManager(); deps._docker_manager = dm
    sm = SessionManager(dm); deps._session_manager = sm
    sess = await sm.create(); sid = sess.id
    loop._session_generation[sid] = 0; loop._cancel_flags.pop(sid, None)
    async def ans(s):
        for _ in range(100):
            if s in loop._pending_responses: break
            await asyncio.sleep(0.1)
        await loop.handle_user_response(s, "Build luôn, tự quyết hợp lý cho quy mô doanh nghiệp thật, không hỏi thêm.")
    async def appr(rid):
        for _ in range(100):
            if rid in loop._pending_approvals: break
            await asyncio.sleep(0.1)
        await loop.handle_approval(sid, {"request_id": rid, "approved": True})
    async def ws(m):
        if m.get("type") in ("agent_thinking","agent_chunk") and m.get("content"):
            cap["thinking"] += m["content"]
        if m.get("type") == "agent_question": asyncio.create_task(ans(sid))
        if m.get("type") == "approval_request": asyncio.create_task(appr(m.get("request_id")))
    try:
        for fn, ct in [("hr.txt","HR nghi phep 12 ngay"),("fin.csv","Hang muc,Dinh muc\nCong tac,2000000"),
                       ("eng.txt","ENG deploy 9-16h"),("adm.txt","ADMIN gio lam 8h30")]:
            await dm.copy_file_to(sess.container_id, ct.encode(), f"/workspace/docs/{fn}")
    except Exception: pass
    from app.agent.tool_registry import tool_registry
    tools = tool_registry.get_tool_specs(is_subagent=False)   # TOOLS THẬT — agent mới build được + gate mới bắn
    try:
        await asyncio.wait_for(loop._run_loop(sess, [{"role":"user","content":[{"text":TASK}]}],
            build_system_prompt(False), tools, ws, gen=0, cancel_event=None, max_iterations=25), timeout=500)
    except (asyncio.TimeoutError, asyncio.CancelledError): pass
    finally:
        loop._execute_tool = real_exec; loop._prebuild_quality_gate = real_gate
        try: await dm.destroy_container(sess.container_id)
        except Exception: pass
    return cap

async def judge(blob):
    if len((blob or "").strip()) < 150: return None
    heavy = getattr(settings, "bedrock_heavy_model", "") or None
    c = create_llm_client()
    j = await _conv(c, messages=[{"role":"user","content":[{"text":RUBRIC+"\n\n=== THINKING ===\n"+blob[-12000:]}]}],
                    system="Giám khảo khắt khe.", max_tokens=1500, model=heavy)
    out = "".join(b.get("text","") for b in j.get("output",{}).get("message",{}).get("content",[]))
    clean = out.replace("*","").replace("`","")
    v = dict((k, val.upper()) for k, val in re.findall(r"(D[1-7])\s*[:\-—]*\s*(PASS|FAIL)", clean, re.IGNORECASE))
    if not v: return None
    return {k: v.get(k)=="PASS" for k in [f"D{i}" for i in range(1,8)]}

async def main():
    n = int(sys.argv[1]) if len(sys.argv)>1 else 3
    dims=[f"D{i}" for i in range(1,8)]; tally={d:0 for d in dims}; valid=0; fired=0
    for i in range(n):
        try:
            cap = await one(i); res = await judge(cap["thinking"])
        except Exception as e:
            print(f"  run {i+1}: ERROR {type(e).__name__}:{str(e)[:70]}", flush=True); continue
        if res is None:
            print(f"  run {i+1}: SKIP (think {len(cap['thinking'])}, built={cap['built']})", flush=True); continue
        valid+=1; fired += 1 if cap["gate_fired"] else 0
        for d in dims: tally[d]+= 1 if res[d] else 0
        print(f"  run {i+1}: "+" ".join(f"{d}={'P' if res[d] else 'F'}" for d in dims)+f" (gate_fired={cap['gate_fired']}, built={cap['built']})", flush=True)
    print(f"\n{'='*52}")
    if valid:
        for d in dims: print(f"  {d}: {tally[d]}/{valid} ({tally[d]/valid*100:.0f}%)")
        print(f"gate đã bắn ở {fired}/{valid} run | TB {sum(tally[d]/valid for d in dims):.1f}/7")
    sys.exit(0)
asyncio.run(main())
