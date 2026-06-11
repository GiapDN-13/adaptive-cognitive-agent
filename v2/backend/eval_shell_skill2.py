"""Đánh giá lại năng lực viết shell SAU khi thêm prompt rules + skill.
Tập trung vào 3 điểm yếu trước đó: session-riêng (cd/venv), quoting, fail-fast.
"""
import asyncio, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt

# Task được thiết kế để LỘ 3 điểm yếu nếu agent không biết
TASKS = [
    # Bẫy session-riêng: nếu agent tách cd + pip thành 2 lệnh → sai
    "Tạo venv ở /workspace/proj rồi cài fastapi vào ĐÚNG venv đó. Lưu ý quan trọng về môi trường shell.",
    # Bẫy quoting: file có khoảng trắng trong tên
    "Đếm tổng số dòng của tất cả file .txt trong /workspace, kể cả file có khoảng trắng trong tên.",
    # Bẫy fail-fast: nhiều bước, bước giữa có thể fail
    "Build pipeline: tạo thư mục, clone giả lập (mkdir), chạy test, deploy — phải DỪNG nếu bất kỳ bước nào fail.",
]


async def main():
    client = create_llm_client()
    system = build_system_prompt(False)
    for i, task in enumerate(TASKS, 1):
        msg = [{"role": "user", "content": [{"text":
            f"Viết lệnh shell (bash) để: {task}\nChỉ trả về lệnh trong ```bash``` block."}]}]
        r = await client.converse(messages=msg, system=system, max_tokens=700)
        text = "".join(b.get("text", "") for b in r.get("output", {}).get("message", {}).get("content", []))
        print(f"\n{'='*70}\nTASK {i}: {task}\n{'-'*70}\n{text.strip()[:900]}")

asyncio.run(main())
