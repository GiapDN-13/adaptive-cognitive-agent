"""Test exec_command_capture — exit code + real timeout enforcement (P0.2).

Run inside the backend container (has Docker socket). Skips gracefully if no daemon.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def run():
    try:
        from app.core.docker_manager import DockerManager
        from app.models.session import ContainerConfig
        dm = DockerManager()
    except Exception as e:
        print(f"SKIP — no Docker daemon: {e}")
        return 0

    failures = []
    cid = None
    try:
        cid, _ = await dm.create_container("test-exec-capture", ContainerConfig())

        # Case 1: success → exit 0, output captured, not timed out
        ec, out, to = await dm.exec_command_capture(cid, "echo hello", timeout=10)
        if not (ec == 0 and "hello" in out and to is False):
            failures.append(f"Case1 echo: got ({ec}, {out!r}, {to})")
        else:
            print(f"[1] echo → exit {ec}, timed_out {to}: PASS")

        # Case 2: non-zero exit code surfaced
        ec, out, to = await dm.exec_command_capture(cid, "exit 3", timeout=10)
        if ec != 3:
            failures.append(f"Case2 exit3: got exit {ec}")
        else:
            print(f"[2] exit 3 → exit {ec}: PASS")

        # Case 3: real timeout — sleep 5 with timeout=1 → timed_out True
        ec, out, to = await dm.exec_command_capture(cid, "sleep 5", timeout=1)
        if not to:
            failures.append(f"Case3 timeout: got exit {ec}, timed_out {to} (expected timed_out True)")
        else:
            print(f"[3] sleep 5 / timeout 1 → timed_out {to} (exit {ec}): PASS")

        # Case 4: command with special chars not re-parsed by extra shell
        ec, out, to = await dm.exec_command_capture(cid, "echo \"a b\" && echo $((1+1))", timeout=10)
        if not ("a b" in out and "2" in out):
            failures.append(f"Case4 special: got {out!r}")
        else:
            print("[4] compound + arithmetic: PASS")

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
