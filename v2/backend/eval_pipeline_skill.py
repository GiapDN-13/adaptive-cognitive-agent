"""(B) Agent co biet KHI NAO dung execute_pipeline (task da-phase) vs lam tuan tu? Goi LLM that."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
from app.agent.meta_tools import register_meta_tools
register_all_builtins(tool_registry)
register_meta_tools(tool_registry)

WANT = ("execute_pipeline", "spawn_subagent", "shell_exec", "write_file", "think", "propose_plan")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]


async def first(q):
    c = create_llm_client()
    r = await c.converse(messages=[{"role": "user", "content": [{"text": q}]}],
                         system=build_system_prompt(False), tools=TOOLS, max_tokens=700)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    return tu


async def main():
    cases = [
        ("Task da-phase ro rang -> execute_pipeline hoac think lap ke hoach phase",
         "Hay thuc hien audit bao mat /workspace/app theo nhieu giai doan: (1) recon thu thap, "
         "(2) phan tich lo hong, (3) viet bao cao. Moi giai doan can context rieng.",
         {"execute_pipeline", "think", "propose_plan"}),
        ("Viec 1 buoc don gian -> KHONG dung pipeline",
         "Dem so dong trong file /workspace/main.py.",
         {"shell_exec", "think"}),
    ]
    for label, q, ok in cases:
        tu = await first(q)
        name = tu["name"] if tu else "(text)"
        v = "OK" if name in ok else f"dung {name} (xem lai)"
        extra = ""
        if name == "execute_pipeline" and tu:
            st = tu["input"].get("stages", [])
            extra = f"  [{len(st)} stages: {[s.get('name','') for s in st]}]"
        print(f"\n{'='*60}\n{label}\n  -> {name}  >> {v}{extra}")

asyncio.run(main())
