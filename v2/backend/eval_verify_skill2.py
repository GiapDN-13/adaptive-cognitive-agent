"""(B) SAU SUA: agent co THUC SU goi verify_work dung cach + tu sua khi gap ERROR khong?
Day nhieu turn, feed toolResult that, quan sat den khi agent emit verify_work."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)

WANT = ("verify_work", "shell_exec", "write_file", "read_file", "think")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]


async def step(msgs):
    c = create_llm_client()
    r = await c.converse(messages=msgs, system=build_system_prompt(False), tools=TOOLS, max_tokens=600)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tu = next((b["toolUse"] for b in blocks if "toolUse" in b), None)
    return blocks, tu


def fake_result(tu, output_text):
    return {"role": "user", "content": [{"toolResult": {
        "toolUseId": tu["toolUseId"],
        "content": [{"text": output_text}],
    }}]}


async def drive(label, first_user, scripted_results, max_turns=6):
    print(f"\n{'='*68}\n{label}\n{'-'*68}")
    msgs = [{"role": "user", "content": [{"text": first_user}]}]
    for turn in range(max_turns):
        blocks, tu = await step(msgs)
        msgs.append({"role": "assistant", "content": blocks})
        if not tu:
            txt = " ".join(b.get("text", "") for b in blocks).strip()
            print(f"  [turn {turn}] (no tool) {txt[:140]}")
            return None
        name = tu["name"]; inp = tu.get("input", {})
        print(f"  [turn {turn}] {name}: {json.dumps(inp, ensure_ascii=False)[:160]}")
        if name == "verify_work":
            return inp
        msgs.append(fake_result(tu, scripted_results.get(name, "OK")))
    print("  (het luot, agent chua goi verify_work)")
    return None


async def main():
    inp = await drive(
        "T1: tieu chi kiem NOI DUNG output -> agent co goi verify_work assert_mode=contains?",
        "File /workspace/app.py da viet xong. Nghiem thu DoD: chay 'python3 /workspace/app.py' "
        "PHAI in ra dung chuoi 'Server ready on port 8080'. Hay nghiem thu tieu chi nay bang verify_work.",
        scripted_results={"shell_exec": "Server ready on port 8080", "read_file": "print('Server ready on port 8080')"},
    )
    if inp and inp.get("assert_mode") == "contains" and "Server ready" in (inp.get("expected") or ""):
        print("  >> KET LUAN: CHON DUNG (contains + expected co chuoi) OK")
    elif inp:
        print(f"  >> KET LUAN: CHUA TOI UU (mode={inp.get('assert_mode')}, expected={inp.get('expected')!r})")

    inp = await drive(
        "T2: tieu chi 'import duoc' -> agent dung exit_code (khong lam dung expected sai)?",
        "Da cai package 'requests'. Nghiem thu DoD: 'python3 -c \"import requests\"' chay thanh cong. "
        "Hay nghiem thu bang verify_work.",
        scripted_results={"shell_exec": ""},
    )
    if inp:
        am = inp.get("assert_mode") or "exit_code"; exp = inp.get("expected") or ""
        good = am == "exit_code" and ("Server" not in exp)
        print(f"  >> KET LUAN: {'DUNG (exit_code)' if good else 'XEM LAI'} (mode={am}, expected={exp!r})")

    print(f"\n{'='*68}\nT3: agent nhan verdict ERROR (expected rong) -> co TU SUA loi goi khong?\n{'-'*68}")
    msgs = [{"role": "user", "content": [{"text":
        "Nghiem thu: chay 'python3 /workspace/app.py' phai in 'READY' tren stdout. Goi verify_work de kiem tieu chi noi dung nay."}]}]
    vw_tu = None
    for turn in range(5):
        blocks, tu = await step(msgs)
        msgs.append({"role": "assistant", "content": blocks})
        if not tu:
            print(f"  [turn {turn}] (no tool)"); break
        print(f"  [turn {turn}] {tu['name']}: {json.dumps(tu.get('input',{}),ensure_ascii=False)[:140]}")
        if tu["name"] == "verify_work":
            vw_tu = tu; break
        # feed ket qua gia cho think/read/shell de di tiep
        msgs.append(fake_result(tu, "OK" if tu["name"] != "shell_exec" else "READY"))
    if not vw_tu:
        print("  >> agent chua goi verify_work trong 5 luot"); return
    # INJECT verdict ERROR (gia lap agent goi thieu expected -> ERROR)
    err = ("VERIFY [READY]: ERROR  [exit_code=0]\nAssessment: assert_mode=contains requires a "
           "non-empty `expected` value to check against. Provide the substring/pattern...\n"
           "NOTE: This is a verify_work CONFIGURATION error, NOT a failed criterion. Fix the call and re-run.")
    msgs.append(fake_result(vw_tu, err))
    blocks2, tu2 = await step(msgs)
    if tu2 and tu2["name"] == "verify_work":
        fixed = tu2.get("input", {})
        print(f"  [sau ERROR] verify_work lan 2: {json.dumps(fixed,ensure_ascii=False)[:150]}")
        ok = (fixed.get("expected") or "").strip() != ""
        print(f"  >> {'TU SUA DUNG (da dien expected) OK' if ok else 'van thieu expected'}")
    else:
        txt = " ".join(b.get('text','') for b in blocks2).strip()
        detail = json.dumps(tu2.get('input',{}),ensure_ascii=False)[:140] if tu2 else txt[:140]
        print(f"  [sau ERROR] {tu2['name'] if tu2 else '(no tool)'}: {detail}")

asyncio.run(main())
