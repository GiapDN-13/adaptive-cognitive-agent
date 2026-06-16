"""VERIFY T1 (da linh vuc): agent dao sau toi TANG QUYET DINH theo DUNG linh vuc cua tung yeu cau,
KHONG nhet dac tinh cua linh vuc khac vao. Goi LLM that."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)

WANT = ("think","ask_user","web_search","shell_exec","write_file","propose_plan","read_file")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]

async def first_think(q):
    c = create_llm_client()
    r = await c.converse(messages=[{"role":"user","content":[{"text":q}]}],
                         system=build_system_prompt(False), tools=TOOLS, max_tokens=900)
    blocks = r.get("output",{}).get("message",{}).get("content",[])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    name = tu["name"] if tu else "(text)"
    thought = ""
    if tu and tu["name"]=="think": thought = tu["input"].get("thought","")
    elif not tu: thought = " ".join(b.get("text","") for b in blocks)
    return name, thought

async def main():
    cases = [
        ("RAG tài liệu", "Làm cho công ty một chatbot RAG để hỏi đáp tài liệu.",
         ["bảng","ảnh","scan","công thức","ocr"]),   # ky vong dao toi cau truc noi dung
        ("Xử lý dữ liệu", "Viết script làm sạch và phân tích file dữ liệu bán hàng công ty.",
         ["dòng","bẩn","thiếu","encoding","định dạng","quy mô","lớn"]),
        ("API/web", "Xây một API đặt hàng cho web bán hàng của công ty.",
         ["req","tải","đồng thời","auth","race","bảo mật","thanh toán"]),
    ]
    for label, q, expect_keys in cases:
        name, thought = await first_think(q)
        low = thought.lower()
        hit = [k for k in expect_keys if k in low]
        print("="*66)
        print(f"[{label}] yeu cau: {q}")
        print(f"  tool dau: {name}")
        print(f"  dao sau dung linh vuc (tu khoa trung): {hit if hit else 'KHONG thay — dao chua du sau'}")
        print(f"  trich think: {thought[:400].strip()}")

asyncio.run(main())
