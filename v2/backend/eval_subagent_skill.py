"""(B) Agent co biet KHI NAO spawn_critic / spawn_subagent (vs lam inline)? Goi LLM that.
- Quyet dinh kien truc lon/claim rui ro -> nen spawn_critic (phan bien).
- Task con doc lap, can context rieng -> spawn_subagent.
- Viec nho/truc tiep -> KHONG spawn (lam luon)."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
from app.agent.meta_tools import register_meta_tools
register_all_builtins(tool_registry)
register_meta_tools(tool_registry)

WANT = ("spawn_critic", "spawn_subagent", "shell_exec", "write_file", "think", "verify_work", "web_search")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]


async def first(q):
    c = create_llm_client()
    r = await c.converse(messages=[{"role": "user", "content": [{"text": q}]}],
                         system=build_system_prompt(False), tools=TOOLS, max_tokens=500)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    txt = " ".join(b.get("text", "") for b in blocks).strip()
    return tu, txt


async def main():
    cases = [
        ("DECIDE lon/rui ro -> nen spawn_critic hoac think phan bien",
         "Toi quyet dinh dung SQLite lam DB chinh cho he thong 10 trieu user dong thoi. Danh gia quyet dinh nay.",
         {"spawn_critic", "think", "web_search"}),
        ("Viec nho -> KHONG spawn, lam truc tiep",
         "Tao file /workspace/hi.txt noi dung 'hello'.",
         {"write_file", "shell_exec"}),
        ("Task con phuc tap doc lap -> spawn_subagent hoac think",
         "Hay review toan bo bao mat codebase /workspace/app (nhieu file, can dao sau) va bao cao lo hong.",
         {"spawn_subagent", "think", "shell_exec"}),
    ]
    for label, q, ok_tools in cases:
        tu, txt = await first(q)
        name = tu["name"] if tu else "(text)"
        verdict = "OK" if name in ok_tools else f"dung {name} (xem lai)"
        print(f"\n{'='*60}\n{label}\n  -> {name}  >> {verdict}")

asyncio.run(main())
