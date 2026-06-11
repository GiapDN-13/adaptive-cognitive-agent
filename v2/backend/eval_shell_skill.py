"""Đánh giá NĂNG LỰC viết shell của agent (không phải tool shell_exec).
Cho LLM sinh shell cho các task thực tế, in ra để chấm chất lượng.
"""
import asyncio, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt

TASKS = [
    "Tạo thư mục /workspace/proj, vào đó, tạo virtualenv, cài fastapi uvicorn, rồi xác nhận import được.",
    "Tìm tất cả file .py trong /workspace lớn hơn 100KB và in kích thước, sắp xếp giảm dần.",
    "Khởi động một web server FastAPI ở app.py trên cổng 8080 chạy nền, đợi nó sẵn sàng, rồi curl thử /health.",
    "Đếm số dòng code (không tính dòng trống, không tính comment) trong tất cả file .py ở /workspace.",
    "Backup file /workspace/config.json thành config.json.bak chỉ khi nó tồn tại, nếu không thì báo lỗi rõ ràng.",
]


async def main():
    client = create_llm_client()
    system = build_system_prompt(False)
    for i, task in enumerate(TASKS, 1):
        msg = [{"role": "user", "content": [{"text":
            f"Viết MỘT lệnh shell (bash) để: {task}\n"
            f"Chỉ trả về lệnh shell trong block ```bash ... ```, không giải thích dài."}]}]
        r = await client.converse(messages=msg, system=system, max_tokens=600)
        blocks = r.get("output", {}).get("message", {}).get("content", [])
        text = "".join(b.get("text", "") for b in blocks)
        print(f"\n{'='*70}\nTASK {i}: {task}\n{'-'*70}")
        print(text.strip()[:900])

asyncio.run(main())
