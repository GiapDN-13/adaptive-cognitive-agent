"""Test _retry_after_stall — the fix for the 9-iteration timeout (Bedrock stalls on a
SMALL context). The old code retried the identical request once and gave up; the new
code backs off and retries several times, and does NOT mangle small contexts."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import app.agent.loop as loop  # noqa: E402


async def noop_ws(_msg):
    pass


def small_ctx():
    # ~39K-style small context (like the failing session), 21 messages
    msgs = [{"role": "user", "content": [{"text": "rebuild frontend"}]}]
    for i in range(10):
        msgs.append({"role": "assistant", "content": [{"text": "x" * 1000}]})
        msgs.append({"role": "user", "content": [{"text": "y" * 1000}]})
    return msgs


async def run():
    failures = []
    orig_call = loop._call_llm
    orig_sleep = asyncio.sleep

    # make backoff instant so the test is fast
    async def fast_sleep(_s):
        await orig_sleep(0)
    asyncio.sleep = fast_sleep  # type: ignore
    loop.asyncio.sleep = fast_sleep  # patch the name the module uses

    try:
        # --- Case 1: stalls twice then succeeds ---
        calls = {"n": 0}

        async def stall_then_ok(*a, **k):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("LLM stream stalled: no data for 120s")
            return {"stopReason": "end_turn", "output": {"message": {"content": [{"text": "done"}]}}}

        loop._call_llm = stall_then_ok
        loop._cancel_flags.clear()
        resp = await loop._retry_after_stall(small_ctx(), "sys", [], noop_ws, None, "testsess", max_retries=3)
        if resp is None:
            failures.append("Case1: should have succeeded on 3rd attempt, got None")
        elif resp["stopReason"] != "end_turn":
            failures.append(f"Case1: wrong response {resp}")
        else:
            print(f"[1] stall x2 then success: PASS (took {calls['n']} attempts)")

        # --- Case 2: stalls forever → returns None (not crash) ---
        async def always_stall(*a, **k):
            raise RuntimeError("LLM stream stalled: no data for 120s")

        loop._call_llm = always_stall
        resp = await loop._retry_after_stall(small_ctx(), "sys", [], noop_ws, None, "testsess", max_retries=3)
        if resp is not None:
            failures.append("Case2: should return None after exhausting retries")
        else:
            print("[2] stall forever -> None (graceful): PASS")

        # --- Case 3: small context is NOT trimmed (the old bug) ---
        captured = {}

        async def capture_ctx(messages, *a, **k):
            captured["len"] = len(messages)
            return {"stopReason": "end_turn", "output": {"message": {"content": [{"text": "ok"}]}}}

        loop._call_llm = capture_ctx
        ctx = small_ctx()
        await loop._retry_after_stall(ctx, "sys", [], noop_ws, None, "testsess", max_retries=3)
        if captured.get("len") != len(ctx):
            failures.append(f"Case3: small context was trimmed {len(ctx)} -> {captured.get('len')}")
        else:
            print(f"[3] small context NOT trimmed: PASS ({len(ctx)} msgs preserved)")

        # --- Case 4: cancel flag aborts retries immediately ---
        loop._call_llm = always_stall
        loop._cancel_flags["cancelsess"] = True
        resp = await loop._retry_after_stall(small_ctx(), "sys", [], noop_ws, None, "cancelsess", max_retries=3)
        if resp is not None:
            failures.append("Case4: cancelled session should return None")
        else:
            print("[4] cancel aborts retries: PASS")

    finally:
        loop._call_llm = orig_call
        asyncio.sleep = orig_sleep  # type: ignore
        loop.asyncio.sleep = orig_sleep
        loop._cancel_flags.clear()

    print()
    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("RESULT: ALL PASS")


if __name__ == "__main__":
    asyncio.run(run())
