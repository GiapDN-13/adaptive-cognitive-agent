"""(B) Agent co biet DUNG cac nang luc web moi khong (url fetch / site_map / crawl_site)?"""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)

TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values()
         if e.name in ("web_search", "site_map", "crawl_site", "shell_exec", "read_file", "think")]


async def call(msgs):
    c = create_llm_client()
    r = await c.converse(messages=msgs, system=build_system_prompt(False), tools=TOOLS, max_tokens=400)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    txt = " ".join(b["text"] for b in blocks if "text" in b).strip()
    return tu, txt


async def main():
    cases = [
        ("SC1: doc 1 trang web cu the (URL cho san)",
         "Doc noi dung trang https://react.dev/learn va tom tat."),
        ("SC2: liet ke cac trang cua 1 site (recon)",
         "Liet ke tat ca cac URL/trang cua website example.com de toi nam cau truc site."),
        ("SC3: thu thap tai lieu nhieu trang",
         "Thu thap noi dung tat ca cac trang tai lieu trong https://docs.example.com de tong hop."),
    ]
    for label, q in cases:
        tu, txt = await call([{"role": "user", "content": [{"text": q}]}])
        print(f"\n{'='*60}\n{label}\n{'-'*60}")
        print(f"  TOOL: {tu['name'] if tu else None}  INPUT: {json.dumps(tu.get('input',{}),ensure_ascii=False) if tu else txt[:120]}")

asyncio.run(main())
