"""VERIFY: nguyen tac dao sau co TONG QUAT khong? Test cac linh vuc KHONG co trong prompt
(prompt chi vi du: tai lieu/data/API/bao mat). Neu agent tu dao dung dac tinh an cua
linh vuc LA -> nguyen tac that su tong quat, khong phai bat chuoc vi du."""
import asyncio, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)

WANT = ("think","ask_user","web_search","shell_exec","write_file","read_file","propose_plan")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]

async def think_of(task):
    c = create_llm_client()
    r = await c.converse(messages=[{"role":"user","content":[{"text":task}]}],
                         system=build_system_prompt(False), tools=TOOLS, max_tokens=3000)
    for b in r.get("output",{}).get("message",{}).get("content",[]):
        if "toolUse" in b and b["toolUse"]["name"]=="think":
            return b["toolUse"]["input"].get("thought","")
    return ""

async def main():
    # 3 linh vuc KHONG nam trong vi du prompt:
    cases = [
        ("FIRMWARE IoT", "Viết firmware cho thiết bị IoT đọc cảm biến nhiệt độ gửi về server."),
        ("XỬ LÝ VIDEO", "Làm tool tự động cắt highlight từ video trận đấu bóng đá dài 2 tiếng."),
        ("MÔ HÌNH TÀI CHÍNH", "Xây mô hình dự báo giá cổ phiếu cho quỹ đầu tư."),
    ]
    for label, q in cases:
        t = await think_of(q)
        print("="*70)
        print(f"[{label}] {q}")
        print("-"*70)
        print(t.strip()[:900] if t else "(agent khong think — xem lai)")

asyncio.run(main())
