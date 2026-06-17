"""VERIFY T6 — DANG TIN: before/after x N lan x nhieu case, CHAM BANG CODE.
Doi chung prompt CU (truoc T6, /app/prompts_old.py) vs MOI (app.agent.prompts).
Bang chung = TI LE dat, khong phai loi nguoi cham.

Case:
  A. RAG '1k user' (mo ho) -> agent PHAI lam ro con so (ask_user/think hoi 'dong thoi vs dang ky')
  B. Chot vector DB cu the     -> PHAI spawn_critic hoac doi chieu con so (khong chot 'cho don gian')
  C. Viec NHO (dem dong file)  -> KHONG duoc spawn_critic (chong spawn bua) [ca control]
"""
import asyncio, sys, json, importlib.util
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)
from app.agent.prompts import build_system_prompt as build_NEW

# load prompt CU tu file tam
spec = importlib.util.spec_from_file_location("prompts_old", "/app/prompts_old.py")
old_mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(old_mod)
build_OLD = old_mod.build_system_prompt

WANT = ("think","ask_user","spawn_critic","web_search","shell_exec","write_file","read_file","propose_plan")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]
N = 8

async def run_once(system, prompt):
    c = create_llm_client()
    r = await c.converse(messages=[{"role":"user","content":[{"text":prompt}]}],
                         system=system, tools=TOOLS, max_tokens=3000)
    blocks = r.get("output",{}).get("message",{}).get("content",[])
    tools_called = [b["toolUse"]["name"] for b in blocks if "toolUse" in b]
    text = " ".join((b["toolUse"]["input"].get("thought","") if b.get("toolUse",{}).get("name")=="think" else b.get("text",""))
                    for b in blocks).lower()
    return tools_called, text

# --- assertion bang code cho tung case ---
def assert_A(tools, text):  # phai LAM RO con so 1k
    asks = ("đồng thời" in text and ("đăng ký" in text or "concurrent" in text or "cùng lúc" in text)) \
        or ("1k" in text and "đồng thời" in text) or ("bao nhiêu" in text and "đồng thời" in text)
    return ("ask_user" in tools) or asks

def assert_B(tools, text):  # phai phan bien/doi chieu, khong chot bua
    return ("spawn_critic" in tools) or ("đồng thời" in text and ("qdrant" in text or "chromadb" in text)) \
        or ("giới hạn" in text and ("user" in text or "đồng thời" in text))

def assert_C(tools, text):  # viec nho: KHONG duoc spawn_critic
    return "spawn_critic" not in tools

CASES = [
    ("A. RAG 1k user (lam ro con so)", "Tao chatbot RAG cho cong ty MekongAI voi khoang 1k nguoi dung.", assert_A),
    ("B. Chot vector DB (phan bien)", "Toi dinh dung ChromaDB lam vector DB cho he RAG 1000 nguoi dung dong thoi. Trien khai di.", assert_B),
    ("C. Viec nho (KHONG spawn bua)", "Dem so dong trong file /workspace/app.py.", assert_C),
]

async def measure(label, build_fn):
    print(f"\n{'='*60}\n{label}\n{'='*60}")
    for cname, prompt, check in CASES:
        sysp = build_fn(False)
        passed = 0
        for i in range(N):
            try:
                tools, text = await run_once(sysp, prompt)
                if check(tools, text): passed += 1
            except Exception as e:
                print(f"   (run {i} err: {type(e).__name__})")
        print(f"  {cname}: {passed}/{N} dat")

async def main():
    await measure("PROMPT CU (truoc T6)", build_OLD)
    await measure("PROMPT MOI (co T6)", build_NEW)

asyncio.run(main())
