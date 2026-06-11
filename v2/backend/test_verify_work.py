"""Test handle_verify_work hardening (P1.2): exit code is ground truth, assert
modes, timeout. Run in backend container; skips w/o Docker.
"""
import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def _noop_ws(_m):
    pass


async def run():
    try:
        from app.core.docker_manager import DockerManager
        from app.models.session import ContainerConfig
        import app.deps as deps
        from app.agent.builtin_tools import handle_verify_work
        dm = DockerManager()
        deps._docker_manager = dm
    except Exception as e:
        print(f"SKIP — no Docker daemon: {e}")
        return 0

    failures = []
    cid = None
    try:
        cid, _ = await dm.create_container("test-verify-work", ContainerConfig())
        session = types.SimpleNamespace(container_id=cid, id="test-verify-work")

        async def vw(ti):
            return await handle_verify_work(session, ti, _noop_ws, None)

        # Case 1: exit 0 but output contains "error" → PASS (exit code dominates)
        r = await vw({"criterion": "c1", "test_command": "echo 'this is an error message'; exit 0"})
        if "PASS" not in r.split("\n")[0]:
            failures.append(f"Case1 (exit0+error word): expected PASS, got: {r.splitlines()[0]}")
        else:
            print("[1] exit 0 + 'error' word → PASS (exit code is ground truth): PASS")

        # Case 2: exit 1, no error keyword → FAIL
        r = await vw({"criterion": "c2", "test_command": "echo all good; exit 1"})
        if "FAIL" not in r.split("\n")[0]:
            failures.append(f"Case2 (exit1): expected FAIL, got: {r.splitlines()[0]}")
        else:
            print("[2] exit 1 → FAIL: PASS")

        # Case 3: assert_mode=contains
        r = await vw({"criterion": "c3", "test_command": "echo HELLO_WORLD", "assert_mode": "contains", "expected": "HELLO_WORLD"})
        if "PASS" not in r.split("\n")[0]:
            failures.append(f"Case3 contains: expected PASS, got: {r.splitlines()[0]}")
        else:
            print("[3] assert_mode=contains match → PASS: PASS")

        # Case 4: timeout
        r = await vw({"criterion": "c4", "test_command": "sleep 5", "timeout": 1})
        if "FAIL" not in r.split("\n")[0] or "TIMED OUT" not in r:
            failures.append(f"Case4 timeout: expected FAIL+TIMED OUT, got: {r.splitlines()[0]}")
        else:
            print("[4] sleep 5 / timeout 1 → FAIL (timeout): PASS")

        # Case 5: assert_mode=regex
        r = await vw({"criterion": "c5", "test_command": "echo 'version 1.2.3'", "assert_mode": "regex", "expected": r"version \d+\.\d+\.\d+"})
        if "PASS" not in r.split("\n")[0]:
            failures.append(f"Case5 regex: expected PASS, got: {r.splitlines()[0]}")
        else:
            print("[5] assert_mode=regex match → PASS: PASS")

        # Case 6: expected exit code (non-zero target)
        r = await vw({"criterion": "c6", "test_command": "exit 2", "expected": "2"})
        if "PASS" not in r.split("\n")[0]:
            failures.append(f"Case6 expected-exit-2: expected PASS, got: {r.splitlines()[0]}")
        else:
            print("[6] exit 2 with expected='2' → PASS: PASS")

        # Case 7: contains with EMPTY expected → must be ERROR (not a false PASS)
        r = await vw({"criterion": "c7", "test_command": "echo x", "assert_mode": "contains", "expected": ""})
        if "ERROR" not in r.split("\n")[0]:
            failures.append(f"Case7 contains+empty: expected ERROR, got: {r.splitlines()[0]}")
        else:
            print("[7] contains + empty expected → ERROR: PASS")

        # Case 8: invalid regex → ERROR (config mistake, not FAIL)
        r = await vw({"criterion": "c8", "test_command": "echo x", "assert_mode": "regex", "expected": "[unclosed"})
        if "ERROR" not in r.split("\n")[0]:
            failures.append(f"Case8 invalid-regex: expected ERROR, got: {r.splitlines()[0]}")
        else:
            print("[8] invalid regex → ERROR: PASS")

        # Case 9: unknown assert_mode → ERROR
        r = await vw({"criterion": "c9", "test_command": "true", "assert_mode": "foo"})
        if "ERROR" not in r.split("\n")[0]:
            failures.append(f"Case9 unknown-mode: expected ERROR, got: {r.splitlines()[0]}")
        else:
            print("[9] unknown assert_mode → ERROR: PASS")

    finally:
        if cid:
            await dm.destroy_container(cid)

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
