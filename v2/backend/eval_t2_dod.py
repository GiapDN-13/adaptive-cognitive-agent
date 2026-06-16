"""VERIFY T2: agent dat DoD PHU THEO THANH PHAN + khac nhau giua cac task. LLM that.
Cho thang boi canh day du + yeu cau dat DoD -> doc think dau tien."""
import asyncio, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)

WANT = ("think","shell_exec","write_file","verify_work","read_file")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]

async def dod_for(task):
    c = create_llm_client()
    q = (f"{task}\n\nTôi đã trả lời đủ bối cảnh rồi. Bây giờ HÃY đặt Definition of Done "
         f"(các tiêu chí hoàn thành đo được) cho task này bằng think, phủ hết các thành phần quan trọng.")
    r = await c.converse(messages=[{"role":"user","content":[{"text":q}]}],
                         system=build_system_prompt(False), tools=TOOLS, max_tokens=3000)
    blocks = r.get("output",{}).get("message",{}).get("content",[])
    for b in blocks:
        if "toolUse" in b and b["toolUse"]["name"]=="think":
            return b["toolUse"]["input"].get("thought","")
    return " ".join(b.get("text","") for b in blocks)

async def main():
    a = await dod_for("Task: làm sạch + phân tích file CSV bán hàng ~50k dòng, có dòng thiếu doanh thu và trùng.")
    print("="*66); print("[A] DATA CLEANING — DoD:"); print(a.strip()[:800])
    b = await dod_for("Task: xây API đặt hàng FastAPI + PostgreSQL, hàng vật lý, ~100 req/s, cần auth + thanh toán.")
    print("="*66); print("[B] API — DoD:"); print(b.strip()[:800])

asyncio.run(main())
