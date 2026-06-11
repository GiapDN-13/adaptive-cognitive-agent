"""Test execute_pipeline hardening (P3.3): name-keyed checkpoint resume, fail_fast,
bounded findings. Pure unit — monkeypatches _run_loop, no Docker needed.
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
    import app.agent.builtin_tools as bt
    from app.agent.builtin_tools import handle_execute_pipeline, _clear_pipeline_checkpoint

    failures = []
    session = types.SimpleNamespace(container_id="x", id="spipe")
    loop._cancel_flags.clear()

    # control: which stage names should raise, and recorded executions
    state = {"fail_on": set(), "ran": []}
    orig = loop._run_loop

    async def fake_runloop(**kw):
        # the prompt contains "stage '<name>'" — recover the stage by scanning
        txt = kw["messages"][0]["content"][0]["text"]
        import re
        m = re.search(r"executing stage '([^']+)'", txt)
        name = m.group(1) if m else "?"
        state["ran"].append(name)
        if name in state["fail_on"]:
            raise RuntimeError(f"boom in {name}")
        kw["messages"].append({"role": "assistant", "content": [{"text": f"result of {name}"}]})

    loop._run_loop = fake_runloop
    # also patch the symbol imported into builtin_tools' function scope is fine (it imports inside fn)

    try:
        _clear_pipeline_checkpoint(session.id, "P")

        stages = [
            {"name": "A", "goal": "ga"},
            {"name": "B", "goal": "gb"},
            {"name": "C", "goal": "gc"},
        ]

        # Case 1: fail_fast — B fails → pipeline aborts, C not run
        state["fail_on"] = {"B"}; state["ran"] = []
        r = await handle_execute_pipeline(session, {"name": "P", "stages": stages, "fail_fast": True}, _noop_ws, None)
        if "ABORTED" not in r or "C" in state["ran"]:
            failures.append(f"Case1 fail_fast: ran={state['ran']} r={r[:150]!r}")
        else:
            print(f"[1] fail_fast: B fails → ABORTED, C not run (ran={state['ran']}): PASS")

        # Case 2: resume — fix B, re-run. A should be skipped (checkpointed by name),
        # B and C run.
        state["fail_on"] = set(); state["ran"] = []
        r = await handle_execute_pipeline(session, {"name": "P", "stages": stages, "fail_fast": True}, _noop_ws, None)
        if "A" in state["ran"]:
            failures.append(f"Case2 resume: A should be skipped, ran={state['ran']}")
        elif "completed" not in r:
            failures.append(f"Case2 resume not completed: {r[:150]!r}")
        else:
            print(f"[2] resume skips checkpointed A, runs B+C → completed (ran={state['ran']}): PASS")

        # Case 3: reorder stages — checkpoint keyed by name, so completed ones still skip
        _clear_pipeline_checkpoint(session.id, "P2")
        state["fail_on"] = {"Y"}; state["ran"] = []
        s2 = [{"name": "X", "goal": "gx"}, {"name": "Y", "goal": "gy"}]
        await handle_execute_pipeline(session, {"name": "P2", "stages": s2}, _noop_ws, None)  # X ok, Y fails
        # now reorder: Y first, X second — X already done, must be skipped even though index changed
        state["fail_on"] = set(); state["ran"] = []
        s2r = [{"name": "Y", "goal": "gy"}, {"name": "X", "goal": "gx"}]
        await handle_execute_pipeline(session, {"name": "P2", "stages": s2r}, _noop_ws, None)
        if "X" in state["ran"]:
            failures.append(f"Case3 reorder: X already done should skip by name, ran={state['ran']}")
        else:
            print(f"[3] reorder stages → name-keyed checkpoint skips done X (ran={state['ran']}): PASS")

        # Case 4: duplicate stages (same name+goal) must NOT collapse into one
        # checkpoint entry → all run, reported "completed N/N" (regression for the
        # occurrence-keyed fix; name-only key reported "partial N/N-1").
        _clear_pipeline_checkpoint(session.id, "P3")
        state["fail_on"] = set(); state["ran"] = []
        s3 = [{"name": "Scan", "goal": "g"}, {"name": "Scan", "goal": "g"}, {"name": "Rep", "goal": "r"}]
        r = await handle_execute_pipeline(session, {"name": "P3", "stages": s3}, _noop_ws, None)
        if "completed: 3/3" not in r or len(state["ran"]) != 3:
            failures.append(f"Case4 dup-stage (expected completed 3/3, ran 3): ran={state['ran']} head={r.split(chr(10))[0]!r}")
        else:
            print(f"[4] duplicate stages → all run, completed 3/3 (ran={state['ran']}): PASS")
        _clear_pipeline_checkpoint(session.id, "P3")

        _clear_pipeline_checkpoint(session.id, "P")
        _clear_pipeline_checkpoint(session.id, "P2")

    finally:
        loop._run_loop = orig

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
