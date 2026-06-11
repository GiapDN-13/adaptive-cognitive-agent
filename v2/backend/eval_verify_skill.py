"""(B) Agent co biet KHI NAO + CACH dung verify_work khong? (goi LLM that)"""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)

WANT = ("verify_work", "shell_exec", "write_file", "read_file", "think", "ask_user")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]


async def call(msgs):
    c = create_llm_client()
    r = await c.converse(messages=msgs, system=build_system_prompt(False), tools=TOOLS, max_tokens=500)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    txt = " ".join(b["text"] for b in blocks if "text" in b).strip()
    return tu, txt


async def main():
    cases = [
        ("SC1: vua viet xong script, co nen TU kiem chung khong?",
         "Toi vua viet xong file /workspace/add.py co ham add(a,b). Hay dam bao no chay dung."),
        ("SC2: claim 'da xong' — agent co verify bang test_command dung kieu exit-code?",
         "Da cai xong package 'requests' trong container. Xac nhan no import duoc."),
        ("SC3: tieu chi can so sanh NOI DUNG output (khong chi exit code)",
         "Chay /workspace/app.py va xac nhan no in ra dung chuoi 'Server ready on port 8080'."),
    ]
    for label, q in cases:
        tu, txt = await call([{"role": "user", "content": [{"text": q}]}])
        print(f"\n{'='*64}\n{label}\n{'-'*64}")
        if tu:
            print(f"  TOOL: {tu['name']}")
            print(f"  INPUT: {json.dumps(tu.get('input', {}), ensure_ascii=False)}")
        else:
            print(f"  (no tool) TEXT: {txt[:200]}")

    # --- Multi-turn: context = da build xong, dang o BUOC NGHIEM THU theo DoD ---
    print(f"\n\n{'#'*64}\n# MULTI-TURN: agent o buoc SELF-VERIFY (chon dung assert_mode?)\n{'#'*64}")
    convo = [
        {"role": "user", "content": [{"text":
            "Build xong /workspace/app.py. DoD chi co 1 tieu chi: chay no PHAI in ra dung chuoi "
            "'Server ready on port 8080' tren stdout. Hay goi verify_work de nghiem thu tieu chi NOI DUNG nay ngay."}]},
    ]
    # cho agent tiep tuc — quan sat no goi verify_work the nao
    tu, txt = await call(convo)
    print(f"  TOOL: {tu['name'] if tu else None}")
    if tu:
        inp = tu.get('input', {})
        print(f"  INPUT: {json.dumps(inp, ensure_ascii=False)}")
        if tu['name'] == 'verify_work':
            am = inp.get('assert_mode', '(default exit_code)')
            exp = inp.get('expected', '')
            ok = am == 'contains' and 'Server ready' in exp
            print(f"  >> assert_mode={am}, expected={exp!r}  => {'CHON DUNG (contains)' if ok else 'CHUA DUNG'}")
    else:
        print(f"  TEXT: {txt[:200]}")

asyncio.run(main())
