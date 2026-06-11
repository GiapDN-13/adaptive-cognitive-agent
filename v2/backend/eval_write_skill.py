"""Đánh giá (B): agent có ĐỦ THÔNG TIN để DÙNG write_file đúng không?
Cho LLM tình huống cần append / path / verify, xem nó chọn tool_use ra sao.
"""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tools import TOOL_DEFINITIONS

# chỉ đưa các tool IO để ép nó dùng write_file (giống loop thật, có toolConfig)
TOOLS = [t for t in TOOL_DEFINITIONS if t["toolSpec"]["name"] in ("write_file", "read_file", "shell_exec")]

SCENARIOS = [
    # 1. Append: nếu agent KHÔNG biết mode → sẽ ghi đè mất log cũ
    "File /workspace/log.txt đã có nội dung. Hãy THÊM dòng 'event B' vào CUỐI file mà KHÔNG xóa nội dung cũ.",
    # 2. Path: agent có tự biết path đi đâu không
    "Ghi chuỗi 'hello' vào file tên notes.txt (tôi không nói thư mục).",
    # 3. Verify: sau khi ghi file quan trọng, agent có kiểm chứng không
    "Ghi file cấu hình /workspace/config.json với nội dung {\"port\": 8080}, và đảm bảo nó đã ghi đúng.",
]


async def main():
    client = create_llm_client()
    system = build_system_prompt(False)
    for i, sc in enumerate(SCENARIOS, 1):
        msg = [{"role": "user", "content": [{"text": sc}]}]
        # gọi qua boto converse với toolConfig để bắt tool_use thật
        r = await client.converse(messages=msg, system=system, tools=TOOLS, max_tokens=500)
        blocks = r.get("output", {}).get("message", {}).get("content", [])
        print(f"\n{'='*68}\nSCENARIO {i}: {sc[:70]}\n{'-'*68}")
        for b in blocks:
            if "toolUse" in b:
                tu = b["toolUse"]
                print(f"  TOOL: {tu['name']}  INPUT: {json.dumps(tu.get('input',{}), ensure_ascii=False)[:200]}")
            elif "text" in b and b["text"].strip():
                print(f"  TEXT: {b['text'].strip()[:150]}")

asyncio.run(main())
