"""Chạy trace_run_full N lần (build TRỌN, gate bắn tự nhiên như production), lưu events
mỗi lần, chấm D1-D7 + đếm gate bắn. Cho thống kê D6/gate trên nhiều mẫu.

Chạy: python /app/run_gate_stat.py [N=3]
"""
import asyncio, sys, json, re, importlib
sys.path.insert(0, "/app"); sys.path.insert(0, ".")
from app.llm.client import create_llm_client
from app.config import settings

# Dùng CHUNG rubric 10 trụ với eval_depth (không lệch tiêu chí).
import eval_depth as ED
RUBRIC = ED.RUBRIC
NDIM = 10

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
    # GIỮ CẢ ĐẦU (Bước 0/1.5: quy mô/phân rã/đa nhánh — D1-D6) LẪN CUỐI (verify/đo — D8/D10).
    # Cắt giữa nếu quá dài. Lỗi đo cũ: blob[-12000:] cắt mất Bước 0 -> D1-D3 fail oan khi build dài.
    if len(blob) > 16000:
        blob = blob[:9000] + "\n\n…[lược phần giữa]…\n\n" + blob[-7000:]
    j = await _conv(c, messages=[{"role":"user","content":[{"text":RUBRIC+"\n\n=== THINKING ===\n"+blob}]}],
                    system="Giám khảo khắt khe.", max_tokens=2200, model=heavy)
    out = "".join(b.get("text","") for b in j.get("output",{}).get("message",{}).get("content",[]))
    clean = out.replace("*","").replace("`","")
    v = dict((k.upper(), val.upper()) for k, val in re.findall(r"(D1[0-9]|D[1-9])\s*[:\-—]*\s*(PASS|FAIL)", clean, re.IGNORECASE))
    return {k: v.get(k)=="PASS" for k in [f"D{i}" for i in range(1,NDIM+1)]} if v else None

async def main():
    n = int(sys.argv[1]) if len(sys.argv)>1 else 3
    import trace_run_full as T
    dims=[f"D{i}" for i in range(1,NDIM+1)]; tally={d:0 for d in dims}; valid=0; fired=0
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
        line = "  run: "+" ".join(f"{d}={'P' if res[d] else 'F'}" for d in dims)+f" (gate={gate_n},writes={wcount['n']},score={sum(1 for d in dims if res[d])}/{NDIM})"
        print(line, flush=True)
        # APPEND vào file tích lũy bền (sống qua restart) — mỗi trace 1 dòng.
        try:
            with open("/app/data/dist_accum.txt", "a", encoding="utf-8") as f:
                f.write(line.strip()+"\n")
        except Exception: pass
    print(f"\n{'='*52}")
    if valid:
        for d in dims: print(f"  {d}: {tally[d]}/{valid} ({tally[d]/valid*100:.0f}%)")
        print(f"gate bắn ở {fired}/{valid} run | TB {sum(tally[d]/valid for d in dims):.1f}/7")
    sys.exit(0)
asyncio.run(main())
