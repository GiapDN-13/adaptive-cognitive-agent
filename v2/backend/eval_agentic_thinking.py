"""REGRESSION T4 — gom T1+T2+T3 (khung tu duy dong + giam khao mu) thanh 1 script
co ASSERTION tu dong (PASS/FAIL + exit code), de tai kiem 1 phat sau moi lan sua prompt.

Chay:
  python eval_agentic_thinking.py          -> T1 + T2 (nhe, ~1-2 phut)
  python eval_agentic_thinking.py full     -> + T3 (giam khao Opus dieu tra, ~3-5 phut)
  python eval_agentic_thinking.py t1|t2|t3 -> chi 1 phan
"""
import asyncio, sys, types, json
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt, build_blind_evaluator_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
from app.config import settings
register_all_builtins(tool_registry)

WANT = ("think","ask_user","web_search","shell_exec","write_file","read_file","propose_plan","verify_work")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]
results = []  # (name, passed, detail)

def record(name, passed, detail=""):
    results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

async def first_think(q, max_tokens=3000):
    """Goi LLM 1 luot, tra (tool_dau, thought_neu_co)."""
    c = create_llm_client()
    r = await c.converse(messages=[{"role":"user","content":[{"text":q}]}],
                         system=build_system_prompt(False), tools=TOOLS, max_tokens=max_tokens)
    blocks = r.get("output",{}).get("message",{}).get("content",[])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    name = tu["name"] if tu else "(text)"
    thought = tu["input"].get("thought","") if (tu and tu["name"]=="think") else " ".join(b.get("text","") for b in blocks)
    return name, thought

# ---------- T1: tu phat trien bai toan (dao sau, dung linh vuc) ----------
async def t1():
    print("\n=== T1: TU PHAT TRIEN BAI TOAN ===")
    # T1a: yeu cau mo ho -> tool dau phai la dao sau (think/ask_user/web_search), KHONG lao vao build
    name, th = await first_think("Làm cho công ty một chatbot RAG để hỏi đáp tài liệu.")
    record("T1a RAG mo ho -> dao sau truoc", name in ("think","ask_user","web_search"),
           f"tool dau = {name}")
    # T1b: dao sau dung dac tinh linh vuc (data) — KHONG nhet bang/scan cua RAG
    name, th = await first_think("Viết script làm sạch và phân tích file dữ liệu bán hàng công ty.")
    low = th.lower()
    data_keys = [k for k in ["thiếu","trùng","duplicate","missing","encoding","định dạng","outlier","null"] if k in low]
    record("T1b data -> dao dung dac tinh data", name=="think" and len(data_keys)>=1,
           f"tool={name}, tu khoa data={data_keys}")
    # T1c: domain LA ngoai prompt (firmware) -> van dao sau dung
    name, th = await first_think("Viết firmware cho thiết bị IoT đọc cảm biến nhiệt độ gửi về server.")
    low = th.lower()
    fw_keys = [k for k in ["esp32","esp8266","mqtt","wifi","ble","lora","chip","giao thức","protocol","firmware"] if k in low]
    record("T1c domain LA (firmware) -> dao sau dung", name in ("think","ask_user") and len(fw_keys)>=1,
           f"tool={name}, tu khoa firmware={fw_keys}")

# ---------- T2: DoD dong theo thanh phan ----------
async def t2():
    print("\n=== T2: DoD DONG THEO THANH PHAN ===")
    async def dod(task):
        c = create_llm_client()
        q = f"{task}\n\nTôi đã trả lời đủ bối cảnh. HÃY đặt Definition of Done (tiêu chí đo được) cho task này, phủ hết các thành phần."
        r = await c.converse(messages=[{"role":"user","content":[{"text":q}]}],
                             system=build_system_prompt(False), tools=TOOLS, max_tokens=3000)
        for b in r.get("output",{}).get("message",{}).get("content",[]):
            if "toolUse" in b and b["toolUse"]["name"]=="think":
                return b["toolUse"]["input"].get("thought","")
        return ""
    a = (await dod("Task: làm sạch + phân tích CSV bán hàng ~50k dòng, có dòng thiếu doanh thu và trùng.")).lower()
    b = (await dod("Task: xây API đặt hàng FastAPI + PostgreSQL, hàng vật lý, ~100 req/s, cần auth + thanh toán.")).lower()
    # A bam dac tinh data, B bam dac tinh API -> 2 bo KHAC nhau
    a_ok = any(k in a for k in ["thiếu","trùng","duplicate","missing","null","outlier"])
    b_ok = any(k in b for k in ["race","tồn kho","lock","auth","thanh toán","concurren","đồng thời"])
    record("T2a DoD data bam dac tinh data", a_ok, f"co tieu chi data: {a_ok}")
    record("T2b DoD API bam dac tinh API", b_ok, f"co tieu chi API: {b_ok}")
    record("T2c 2 bo DoD KHAC nhau (khong cung mau)", a_ok and b_ok and a[:200]!=b[:200])

# ---------- T3: giam khao mu bat san pham THIEU (ca gai loi) ----------
async def t3():
    print("\n=== T3: GIAM KHAO MU (ca gai loi) ===")
    from app.core.docker_manager import DockerManager
    from app.models.session import ContainerConfig
    import app.deps as deps
    import app.agent.loop as loop
    from app.agent.builtin_tools import handle_spawn_evaluator
    dm = DockerManager(); deps._docker_manager = dm
    cid, _ = await dm.create_container('eval-t4-judge', ContainerConfig())
    sess = types.SimpleNamespace(container_id=cid, id='t4judge')
    loop._subagent_depth.clear(); loop._session_generation['t4judge']=0; loop._cancel_flags.clear()
    async def ws(m): pass
    doc = ("BAO CAO QUY 3/2024\nPhan thuyet minh: Cong ty tang truong on dinh.\n"
           "BANG DOANH THU:\nDon vi | Doanh thu | Tam dinh chi\nHai Ha | 1200 | 45\nSong Da | 980 | 12\n")
    await dm.copy_file_to(cid, doc.encode(), "/workspace/baocao.txt")
    rag = ("import sys\nq=sys.argv[1] if len(sys.argv)>1 else ''\nt=open('/workspace/baocao.txt').read()\n"
           "para='\\n'.join(l for l in t.split('\\n') if '|' not in l)\n"
           "print('Cong ty tang truong on dinh.' if 'tang truong' in q.lower() else 'Khong tim thay.')\n")
    await dm.copy_file_to(cid, rag.encode(), "/workspace/rag.py")
    ti = {
        "original_request": "Làm chatbot RAG hỏi đáp tài liệu công ty (file /workspace/baocao.txt).",
        "product": "Script /workspace/rag.py — chạy: python3 /workspace/rag.py \"<câu hỏi>\".",
        "data_location": "/workspace/baocao.txt + /workspace/rag.py",
    }
    out = await handle_spawn_evaluator(sess, ti, ws, None)
    # verdict cua giam khao (bo footer cua handler co chu THIEU)
    body = out.split("[Nếu VERDICT")[0]
    is_thieu = "VERDICT: THIẾU" in body or "VERDICT:THIẾU" in body
    record("T3 giam khao bat san pham THIEU (RAG bo bang)", is_thieu,
           "verdict=THIEU" if is_thieu else f"verdict KHONG ro: ...{body[-120:]}")
    await dm.destroy_container(cid)

async def main():
    sel = (sys.argv[1] if len(sys.argv)>1 else "").lower()
    crashed = False
    try:
        if sel in ("", "full", "t1"): await t1()
        if sel in ("", "full", "t2"): await t2()
        if sel in ("full", "t3"):     await t3()
    except Exception:
        # KHONG nuot loi cam: in ro de phan biet "test FAIL" voi "ha tang loi" (vd creds het han)
        import traceback; traceback.print_exc()
        crashed = True
    finally:
        n = len(results); p = sum(1 for _,ok,_ in results if ok)
        print(f"\n{'='*50}\nKET QUA: {p}/{n} PASS")
        for name,ok,_ in results:
            if not ok: print(f"  FAIL -> {name}")
        if crashed:
            print("RESULT: ERROR (hạ tầng/exception — xem traceback trên, KHÔNG phải test FAIL)")
        else:
            print("RESULT:", "ALL PASS" if p==n and n>0 else ("FAIL" if n else "NO TEST RUN"))
        sys.exit(0 if (p==n and n>0 and not crashed) else 1)

asyncio.run(main())
