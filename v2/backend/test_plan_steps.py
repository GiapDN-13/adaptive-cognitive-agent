"""Test propose_plan / _execute_plan_steps hardening (P2.3): exit-code step
success, tool-name step surfaced, autonomous no-approver message.
Pure unit — monkeypatches docker_manager + approval, no Docker needed.
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
    from app.agent.builtin_tools import handle_propose_plan

    failures = []
    session = types.SimpleNamespace(container_id="x", id="splan")
    loop._cancel_flags.clear()

    # Fake docker manager with scriptable exit codes
    class FakeDM:
        def __init__(self):
            self.scripted = {}
        async def exec_command_capture(self, cid, cmd, timeout=900):
            return self.scripted.get(cmd, (0, f"ran: {cmd}", False))
    fake_dm = FakeDM()
    loop._docker_manager = fake_dm

    # avoid approval prompts: make requires_approval False
    import app.agent.tools as tools_mod
    orig_req = tools_mod.requires_approval
    loop.requires_approval = lambda c: False

    try:
        # --- _execute_plan_steps directly ---
        # Case 1: a step whose command is a tool name → surfaced, not silent success
        steps = [{"id": "step_0", "command": "write_file", "description": "write a file"}]
        r = await loop._execute_plan_steps(session, "p1", steps, _noop_ws)
        if "NOT EXECUTED" not in r or "write_file" not in r:
            failures.append(f"Case1 tool-name step: {r!r}")
        else:
            print("[1] tool-name step → NOT EXECUTED warning: PASS")

        # Case 2: shell step that exits non-zero → FAILED, plan pauses
        fake_dm.scripted = {"false": (1, "", False)}
        steps = [{"id": "step_0", "command": "false", "description": "failing cmd"}]
        r = await loop._execute_plan_steps(session, "p2", steps, _noop_ws)
        if "FAILED exit_code=1" not in r:
            failures.append(f"Case2 exit1 step: {r!r}")
        else:
            print("[2] step exit 1 → FAILED (exit code): PASS")

        # Case 3: shell step exit 0 but output contains 'error' → still PASS (exit code wins)
        fake_dm.scripted = {"echo error": (0, "error word here", False)}
        steps = [{"id": "step_0", "command": "echo error", "description": "noisy ok"}]
        r = await loop._execute_plan_steps(session, "p3", steps, _noop_ws)
        if "exit_code=0" not in r or "FAILED" in r:
            failures.append(f"Case3 exit0+error word: {r!r}")
        else:
            print("[3] exit 0 + 'error' word → step OK (exit code wins): PASS")

        # Case 3b: completed/total count — a failing step must NOT inflate the count.
        # (regression: old code matched literal "[FAILED]" that never appears, so a
        # plan with a failed step reported "N/N completed".)
        fake_dm.scripted = {"true": (0, "ok", False), "false": (1, "boom", False)}
        steps = [
            {"id": "step_0", "command": "true", "description": "ok"},
            {"id": "step_1", "command": "false", "description": "fail"},
            {"id": "step_2", "command": "true", "description": "never (paused)"},
        ]
        r = await loop._execute_plan_steps(session, "p3b", steps, _noop_ws)
        head = r.split("\n")[0]
        if "1/3 steps completed" not in head or "did NOT fully succeed" not in head:
            failures.append(f"Case3b completed-count (expected '1/3 ... did NOT fully succeed'): {head!r}")
        else:
            print("[3b] failing step → '1/3 completed' + warning (no inflated count): PASS")

        # --- handle_propose_plan autonomous no-approver ---
        async def fake_wait_approval(plan_id, *a, **k):
            return {"approved": False, "timed_out": True}
        orig_wait = loop._wait_for_approval
        loop._wait_for_approval = fake_wait_approval
        try:
            r = await handle_propose_plan(session, {"title": "T", "steps": [{"command": "echo hi", "description": "d"}]}, _noop_ws, None)
            if "no approver responded" not in r:
                failures.append(f"Case4 no-approver: {r!r}")
            else:
                print("[4] autonomous (no approver) → clear message, no hang loop: PASS")
        finally:
            loop._wait_for_approval = orig_wait

    finally:
        loop.requires_approval = orig_req

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
