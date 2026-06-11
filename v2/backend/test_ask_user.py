"""Test handle_ask_user hardening (P2.2): option matching + timeout sentinel.
Pure unit — monkeypatches _wait_for_user_response, no Docker needed.
"""
import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def _noop_ws(_m):
    pass


async def run():
    import app.agent.loop as loop
    from app.agent.builtin_tools import handle_ask_user

    failures = []
    session = types.SimpleNamespace(container_id="x", id="s1")
    orig = loop._wait_for_user_response

    async def fake_response(_sid, *a, **k):
        return fake_response.value

    loop._wait_for_user_response = fake_response

    try:
        # Case 1: response matches an option
        fake_response.value = "Qdrant"
        r = await handle_ask_user(session, {"question": "DB?", "options": ["PostgreSQL", "Qdrant"]}, _noop_ws, None)
        if "selected option: Qdrant" not in r:
            failures.append(f"Case1 match: {r!r}")
        else:
            print("[1] matching option → 'selected option': PASS")

        # Case 2: free-text not in options → flagged as free-text
        fake_response.value = "dùng cái nào nhẹ nhất"
        r = await handle_ask_user(session, {"question": "DB?", "options": ["PostgreSQL", "Qdrant"]}, _noop_ws, None)
        if "free-text" not in r:
            failures.append(f"Case2 free-text: {r!r}")
        else:
            print("[2] non-option answer → flagged free-text: PASS")

        # Case 3: timeout sentinel → no-answer instruction (NOT a plausible answer)
        fake_response.value = "(no response - timeout)"
        r = await handle_ask_user(session, {"question": "DB?", "options": ["A", "B"]}, _noop_ws, None)
        if "no answer received" not in r or "Do NOT assume" not in r:
            failures.append(f"Case3 timeout: {r!r}")
        else:
            print("[3] timeout → explicit no-answer (no loop): PASS")

        # Case 4: cancelled sentinel
        fake_response.value = "(cancelled)"
        r = await handle_ask_user(session, {"question": "DB?"}, _noop_ws, None)
        if "no answer received" not in r:
            failures.append(f"Case4 cancelled: {r!r}")
        else:
            print("[4] cancelled → no-answer: PASS")

        # Case 5: no options, normal answer
        fake_response.value = "yes do it"
        r = await handle_ask_user(session, {"question": "ok?"}, _noop_ws, None)
        if "User responded: yes do it" not in r:
            failures.append(f"Case5 no-options: {r!r}")
        else:
            print("[5] no options → plain response: PASS")

    finally:
        loop._wait_for_user_response = orig

    print()
    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
