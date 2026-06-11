"""(B) Agent có đủ thông tin DÙNG read_file đúng không?
Test hành vi thật: gọi LLM + toolConfig, mô phỏng tool result, xem agent có biết
dùng offset để đọc tiếp / xử lý binary / không bị kẹt."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tools import TOOL_DEFINITIONS

TOOLS = [t for t in TOOL_DEFINITIONS if t["toolSpec"]["name"] in ("read_file", "shell_exec", "write_file")]


async def call(msgs):
    c = create_llm_client()
    r = await c.converse(messages=msgs, system=build_system_prompt(False), tools=TOOLS, max_tokens=450)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    txt = " ".join(b["text"] for b in blocks if "text" in b).strip()
    return tu, txt


async def main():
    # SC1: file lớn, agent đọc trang 1, header nói "còn 800 dòng" → có đọc TIẾP bằng offset không?
    print("="*68 + "\nSC1: đọc trang 1 → có tự đọc tiếp bằng offset không?\n" + "-"*68)
    msgs = [
        {"role": "user", "content": [{"text": "Đọc TOÀN BỘ file /workspace/app.py (1000 dòng) để hiểu code."}]},
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t1", "name": "read_file", "input": {"path": "/workspace/app.py"}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "t1", "content": [{"text": "[/workspace/app.py: lines 1-200 of 1000] — 800 more line(s) below (use offset=201)\n<200 dòng code>"}]}}]},
    ]
    tu, txt = await call(msgs)
    print(f"  TOOL: {tu['name'] if tu else None}  INPUT: {json.dumps(tu.get('input',{}),ensure_ascii=False) if tu else txt[:120]}")

    # SC2: gặp binary → agent có làm theo gợi ý (xxd/file) không, hay kẹt?
    print("\n" + "="*68 + "\nSC2: read trả 'BINARY file' → agent xử lý ra sao?\n" + "-"*68)
    msgs = [
        {"role": "user", "content": [{"text": "Xem nội dung file /workspace/data.bin có gì."}]},
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t2", "name": "read_file", "input": {"path": "/workspace/data.bin"}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "t2", "content": [{"text": "[/workspace/data.bin: BINARY file, 2000 bytes] — not shown as text. To inspect use shell_exec with `file`, `xxd | head`, or `hexdump -C | head`."}]}}]},
    ]
    tu, txt = await call(msgs)
    print(f"  TOOL: {tu['name'] if tu else None}  INPUT: {json.dumps(tu.get('input',{}),ensure_ascii=False) if tu else txt[:160]}")

    # SC3: output bị cap → agent có biết dùng grep/offset để tìm cái cần thay vì đọc lại?
    print("\n" + "="*68 + "\nSC3: output bị truncate → agent đọc tiếp/grep hay đọc lại nguyên?\n" + "-"*68)
    msgs = [
        {"role": "user", "content": [{"text": "Tìm hàm `def login` nằm ở đâu trong /workspace/server.py (file rất lớn)."}]},
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t3", "name": "read_file", "input": {"path": "/workspace/server.py"}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "t3", "content": [{"text": "[/workspace/server.py: lines 1-200 of 5000] — 4800 more below\n...[output truncated at 50000 chars — raise max_bytes, use offset, or grep for specifics]"}]}}]},
    ]
    tu, txt = await call(msgs)
    print(f"  TOOL: {tu['name'] if tu else None}  INPUT: {json.dumps(tu.get('input',{}),ensure_ascii=False) if tu else txt[:160]}")

asyncio.run(main())
