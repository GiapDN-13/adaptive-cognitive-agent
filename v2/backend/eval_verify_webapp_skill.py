"""(B) Agent co biet viet journey verify_webapp DUNG (assert NOI DUNG, khong chi status) khong?
Goi LLM that, multi-turn de ep agent emit verify_webapp."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)

WANT = ("verify_webapp", "verify_work", "shell_exec", "write_file", "read_file", "think")
TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]


async def step(msgs):
    c = create_llm_client()
    r = await c.converse(messages=msgs, system=build_system_prompt(False), tools=TOOLS, max_tokens=700)
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    tus = [b["toolUse"] for b in blocks if "toolUse" in b]
    return blocks, tus


async def drive(label, first_user, scripted, max_turns=6):
    print(f"\n{'='*68}\n{label}\n{'-'*68}")
    msgs = [{"role": "user", "content": [{"text": first_user}]}]
    for turn in range(max_turns):
        blocks, tus = await step(msgs)
        msgs.append({"role": "assistant", "content": blocks})
        if not tus:
            print(f"  [turn {turn}] (no tool) {' '.join(b.get('text','') for b in blocks)[:120]}")
            return None
        for tu in tus:
            print(f"  [turn {turn}] {tu['name']}: {json.dumps(tu.get('input',{}),ensure_ascii=False)[:170]}")
            if tu["name"] == "verify_webapp":
                return tu.get("input", {})
        # feed toolResult cho MOI toolUse block (Bedrock yeu cau day du)
        msgs.append({"role": "user", "content": [
            {"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"text": scripted.get(tu["name"], "OK")}]}}
            for tu in tus
        ]})
    print("  (chua goi verify_webapp)")
    return None


async def main():
    inp = await drive(
        "SC: nghiem thu chatbot RAG dang chay tren :8080 — journey co assert noi dung?",
        "Chatbot RAG da chay tren http://localhost:8080. GET / tra ve HTML co tu 'RAG Chatbot'. "
        "POST /chat voi body {\"message\":\"...\"} tra JSON {\"answer\":\"...\"}. "
        "Da kiem app song (curl GET / = 200, body co '<h1>RAG Chatbot</h1>'; POST /chat tra {\"answer\":\"Paris la thu do Phap\"}). "
        "GIO hay goi verify_webapp NGAY voi journey day du de chung minh chatbot tra loi DUNG (khong chi co UI).",
        scripted={"shell_exec": "<h1>RAG Chatbot</h1> ... {\"answer\":\"Paris la thu do Phap\"}",
                  "read_file": "app.py: @app.post('/chat')", "think": "OK"},
    )
    if inp:
        j = inp.get("journey", [])
        if isinstance(j, str):
            try: j = json.loads(j)
            except: j = []
        has_content = any(s.get("assert_contains") or s.get("assert_json") or s.get("assert_not_contains")
                          for s in j if isinstance(s, dict))
        print(f"  >> {len(j)} step(s); assert NOI DUNG: {'CO -> DUNG' if has_content else 'KHONG -> chi status (yeu)'}")

asyncio.run(main())
