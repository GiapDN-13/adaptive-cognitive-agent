"""Chạy trace_run_full N lần (build TRỌN, gate bắn tự nhiên như production), lưu events
mỗi lần, chấm D1-D7 + đếm gate bắn. Cho thống kê D6/gate trên nhiều mẫu.

Chạy: python /app/run_gate_stat.py [N=3]
"""
import asyncio, sys, json, re, importlib
sys.path.insert(0, "/app"); sys.path.insert(0, ".")
from app.llm.client import create_llm_client
from app.config import settings

RUBRIC = """Chấm 7 trụ tư duy, PASS khắt khe.
[D1] QUY MÔ định lượng. [D2] Xử lý nội dung Excel. [D3] Phân rã+khó-trước.
[D4] Đa nhánh (≥2 PA+trade-off+chọn). [D5] Tự phản chiếu. [D6] Chấm điểm CÓ TRỌNG SỐ.
[D7] Biết khi không biết (model ID/dim đánh dấu cần verify).
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

async def judge(blob):
    if len((blob or "").strip()) < 150: return None
    heavy = getattr(settings, "bedrock_heavy_model", "") or None
    c = create_llm_client()
    j = await _conv(c, messages=[{"role":"user","content":[{"text":RUBRIC+"\n\n=== THINKING ===\n"+blob[-12000:]}]}],
                    system="Giám khảo khắt khe.", max_tokens=1500, model=heavy)
    out = "".join(b.get("text","") for b in j.get("output",{}).get("message",{}).get("content",[]))
    clean = out.replace("*","").replace("`","")
    v = dict((k, val.upper()) for k, val in re.findall(r"(D[1-7])\s*[:\-—]*\s*(PASS|FAIL)", clean, re.IGNORECASE))
    return {k: v.get(k)=="PASS" for k in [f"D{i}" for i in range(1,8)]} if v else None

async def main():
    n = int(sys.argv[1]) if len(sys.argv)>1 else 3
    import trace_run_full as T
    dims=[f"D{i}" for i in range(1,8)]; tally={d:0 for d in dims}; valid=0; fired=0
    for i in range(n):
        # chạy 1 trace build trọn
        import app.deps as deps
        from app.core.docker_manager import DockerManager
        from app.core.session_manager import SessionManager
        from app.agent.loop import run_agent_loop
        from app.agent.tool_registry import tool_registry
        from app.agent.builtin_tools import register_all_builtins
        register_all_builtins(tool_registry)
        dm = DockerManager(); deps._docker_manager = dm
        sm = SessionManager(dm); deps._session_manager = sm
        sess = await sm.create()
        # seed docs + creds như trace_run_full
        await dm.exec_command_simple(sess.container_id, "mkdir -p /workspace/docs")
        for name, content in T.DOCS.items():
            await dm.copy_file_to(sess.container_id, content.encode(), f"/workspace/docs/{name}")
        creds = T._read_host_creds()
        if creds.get("AWS_ACCESS_KEY_ID"):
            ini = "[default]\n" + f"aws_access_key_id = {creds['AWS_ACCESS_KEY_ID']}\n" + \
                  f"aws_secret_access_key = {creds['AWS_SECRET_ACCESS_KEY']}\n"
            if creds.get("AWS_SESSION_TOKEN"): ini += f"aws_session_token = {creds['AWS_SESSION_TOKEN']}\n"
            ini += "region = us-east-1\n"
            await dm.exec_command_simple(sess.container_id, "mkdir -p /root/.aws")
            await dm.copy_file_to(sess.container_id, ini.encode(), "/root/.aws/credentials")
            await dm.copy_file_to(sess.container_id, b"[default]\nregion = us-east-1\n", "/root/.aws/config")
        tr = T.Tracer(); tr.bind(sess.id)
        # dừng sau khi build vài file (gate đã bắn + có sản phẩm) để tiết kiệm
        import app.agent.loop as loop
        real_exec = loop._execute_tool; wcount = {"n": 0}
        # KHÔNG cắt ở write_file (T11 chạy ở end_turn — phải để agent tới đó). Cắt khi
        # agent gọi spawn_evaluator (dấu hiệu sắp report → T10 + T11 đã chạy xong) để
        # tiết kiệm, hoặc khi đã build kha khá + hết iteration.
        async def ex(s, tn, ti, w, c):
            r = await real_exec(s, tn, ti, w, c)
            if tn in ("write_file","create_tool"): wcount["n"] += 1
            if tn == "spawn_evaluator": loop._cancel_flags[s.id] = True  # sắp report
            return r
        loop._execute_tool = ex
        try:
            await asyncio.wait_for(run_agent_loop(sess, T.TASK, tr), timeout=1200)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        finally:
            loop._execute_tool = real_exec
            try: await dm.destroy_container(sess.container_id)
            except Exception: pass
        # đếm gate bắn (pre-build T10 + post-build D6 T11) + gom thinking
        gate_n = sum(1 for e in tr.events if e.get("type")=="agent_status" and ("pre-build gate" in str(e.get("detail","")) or "chấm điểm" in str(e.get("detail",""))))
        blob = "".join(e.get("content","") for e in tr.events if e.get("type") in ("agent_thinking","agent_chunk") and e.get("content"))
        try:
            res = await judge(blob)
        except Exception as e:
            print(f"  run {i+1}: judge ERR {type(e).__name__}", flush=True); continue
        if res is None:
            print(f"  run {i+1}: SKIP (think {len(blob)}, writes={wcount['n']}, gate={gate_n})", flush=True); continue
        valid+=1; fired += 1 if gate_n else 0
        for d in dims: tally[d]+= 1 if res[d] else 0
        print(f"  run {i+1}: "+" ".join(f"{d}={'P' if res[d] else 'F'}" for d in dims)+f" (gate_fired={gate_n}, writes={wcount['n']})", flush=True)
    print(f"\n{'='*52}")
    if valid:
        for d in dims: print(f"  {d}: {tally[d]}/{valid} ({tally[d]/valid*100:.0f}%)")
        print(f"gate bắn ở {fired}/{valid} run | TB {sum(tally[d]/valid for d in dims):.1f}/7")
    sys.exit(0)
asyncio.run(main())
