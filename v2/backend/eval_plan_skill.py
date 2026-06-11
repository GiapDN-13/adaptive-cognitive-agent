"""(B) Agent dung propose_plan dung khong: step.command la BASH that (khong phai ten tool)?
+ khi nao chon propose_plan vs lam truc tiep. Goi LLM that."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)

WANT = ("propose_plan", "shell_exec", "write_file", "think", "verify_work", "ask_user")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]
TOOL_NAMES = {"shell_exec", "write_file", "read_file", "web_search", "think", "ask_user", "verify_work", "propose_plan"}


async def first(q):
    c = create_llm_client()
    r = await c.converse(messages=[{"role": "user", "content": [{"text": q}]}],
                         system=build_system_prompt(False), tools=TOOLS, max_tokens=700)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    return tu


async def main():
    tu = await first(
        "Hay lap ke hoach nhieu buoc roi thuc thi: tao thu muc /workspace/proj, "
        "tao file main.py in 'hi', cai package 'requests', chay main.py. Dung propose_plan.")
    print("TOOL:", tu["name"] if tu else None)
    if tu and tu["name"] == "propose_plan":
        steps = tu["input"].get("steps", [])
        print(f"  {len(steps)} steps:")
        bad = []
        for s in steps:
            cmd = (s.get("command") or "").strip()
            is_toolname = cmd in TOOL_NAMES
            print(f"   - {s.get('description','')[:40]:42} cmd={cmd[:50]!r}{'  <-- TEN TOOL!' if is_toolname else ''}")
            if is_toolname or not cmd:
                bad.append(s.get("description", ""))
        print(f"  >> {'TAT CA command la bash that OK' if not bad else f'CO {len(bad)} step command sai (ten tool/rong)'}")
    else:
        print(f"  (khong dung propose_plan -> {tu['name'] if tu else 'text'}; co the hop ly neu task don gian)")


asyncio.run(main())
