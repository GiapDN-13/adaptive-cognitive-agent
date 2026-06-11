"""(B) Agent co biet KHI NAO tu tao tool/skill/hook (self-extension)? Goi LLM that.
- Thao tac LAP DI LAP LAI co the dong goi -> nen create_tool.
- Viec 1 lan -> KHONG tao tool, lam thang."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
from app.agent.meta_tools import register_meta_tools
register_all_builtins(tool_registry)
register_meta_tools(tool_registry)

WANT = ("create_tool", "create_skill", "create_hook", "shell_exec", "write_file", "think")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]
print("Self-ext tools co trong registry:", [n for n in WANT if tool_registry.has_tool(n)])


async def first(q):
    c = create_llm_client()
    r = await c.converse(messages=[{"role": "user", "content": [{"text": q}]}],
                         system=build_system_prompt(False), tools=TOOLS, max_tokens=600)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    return tu


async def main():
    cases = [
        ("Thao tac lap lai nhieu lan -> co the create_tool (hoac think/shell)",
         "Toi se can tinh CVSS score tu vector string RAT NHIEU LAN trong qua trinh audit. "
         "Hay tao mot cong cu tai su dung de moi lan chi viec goi.",
         {"create_tool", "think", "shell_exec", "write_file"}),
        ("Viec 1 lan don gian -> KHONG tao tool",
         "Tinh tong 2+2 giup toi.",
         {"think", "shell_exec"}),
    ]
    for label, q, ok in cases:
        tu = await first(q)
        name = tu["name"] if tu else "(text)"
        v = "OK" if name in ok else f"dung {name} (xem lai)"
        print(f"\n{'='*60}\n{label}\n  -> {name}  >> {v}")

asyncio.run(main())
