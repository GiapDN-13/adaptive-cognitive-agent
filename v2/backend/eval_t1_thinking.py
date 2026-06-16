"""VERIFY T1: agent co TU DAO SAU bai toan khi nhan yeu cau mo ho khong?
(thay vi lao vao code text-only theo nghia den). Goi LLM that."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)

WANT = ("think","ask_user","web_search","shell_exec","write_file","propose_plan","read_file")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]

async def first(q):
    c = create_llm_client()
    r = await c.converse(messages=[{"role":"user","content":[{"text":q}]}],
                         system=build_system_prompt(False), tools=TOOLS, max_tokens=700)
    blocks = r.get("output",{}).get("message",{}).get("content",[])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    txt = " ".join(b.get("text","") for b in blocks).strip()
    return tu, txt

async def main():
    # yeu cau MO HO, dung cai sep dua
    q = "Làm cho công ty một chatbot RAG để hỏi đáp tài liệu."
    tu, txt = await first(q)
    name = tu["name"] if tu else "(text)"
    inp = json.dumps(tu.get("input",{}),ensure_ascii=False) if tu else txt
    print("="*66)
    print("YEU CAU MO HO:", q)
    print("-"*66)
    print(f"  TOOL DAU TIEN: {name}")
    print(f"  INPUT: {inp[:600]}")
    # danh gia: tool dau co phai dao sau (think/ask_user/web_search) khong?
    dig = name in ("think","ask_user","web_search")
    print("-"*66)
    print(f"  >> {'DAT — agent dao sau truoc' if dig else 'CHUA — agent lao vao lam ngay (' + name + ')'}")
    if name == "think":
        # kiem think co noi ve ban chat/doanh nghiep/dang tai lieu khong
        low = inp.lower()
        keys = [k for k in ["bản chất","doanh nghiệp","công ty","ai dùng","ai sẽ","loại tài liệu","dạng","scan","bảng","ảnh","ngành","hỏi lại","research","làm gì","mục đích"] if k in low]
        print(f"  >> think co dao sau ban chat: {keys if keys else 'KHONG thay tu khoa dao sau'}")

asyncio.run(main())
