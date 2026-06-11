"""(B) Agent co du thong tin DUNG web_search dung khong?
Test hanh vi that: goi LLM + toolConfig."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tools import TOOL_DEFINITIONS

TOOLS = [t for t in TOOL_DEFINITIONS if t["toolSpec"]["name"] in ("web_search", "shell_exec", "write_file", "think")]


async def call(msgs):
    c = create_llm_client()
    r = await c.converse(messages=msgs, system=build_system_prompt(False), tools=TOOLS, max_tokens=450)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    txt = " ".join(b["text"] for b in blocks if "text" in b).strip()
    return tu, txt


async def main():
    print("="*66 + "\nSC1: hoi info moi -> co web_search khong?\n" + "-"*66)
    tu, txt = await call([{"role": "user", "content": [{"text": "Phien ban FastAPI moi nhat hien tai la gi? Tra cuu giup."}]}])
    print(f"  TOOL: {tu['name'] if tu else None}  INPUT: {json.dumps(tu.get('input',{}),ensure_ascii=False) if tu else txt[:120]}")

    print("\n" + "="*66 + "\nSC2: can noi dung chi tiet -> dung fetch_content?\n" + "-"*66)
    tu, txt = await call([{"role": "user", "content": [{"text": "Doc ky va tom tat chi tiet bai huong dan chinh thuc ve FastAPI dependency injection."}]}])
    print(f"  TOOL: {tu['name'] if tu else None}  INPUT: {json.dumps(tu.get('input',{}),ensure_ascii=False) if tu else txt[:120]}")

    print("\n" + "="*66 + "\nSC3: search tra rac+goi y -> agent lam gi tiep?\n" + "-"*66)
    msgs = [
        {"role": "user", "content": [{"text": "Tim so lieu noi bo tren trang can dang nhap example-portal.com"}]},
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t1", "name": "web_search", "input": {"query": "example-portal.com internal data"}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "t1", "content": [{"text": "No relevant results - only generic fallback pages were filtered out. NOTE: DuckDuckGo can't reach sources behind login/captcha; for those, fetch a known URL directly."}]}}]},
    ]
    tu, txt = await call(msgs)
    print(f"  TOOL: {tu['name'] if tu else None}  INPUT: {json.dumps(tu.get('input',{}),ensure_ascii=False) if tu else ''}")
    print(f"  TEXT: {txt[:200]}")

asyncio.run(main())
