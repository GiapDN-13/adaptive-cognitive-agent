"""Test handle_shell_exec hardening (P1.3): exit code reported, timeout honored,
safe overflow file (no heredoc), cancel_event. Run in backend container; skips w/o Docker.
"""
import asyncio
import sys
import threading
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
        from app.agent.builtin_tools import handle_shell_exec
        dm = DockerManager()
        deps._docker_manager = dm
    except Exception as e:
        print(f"SKIP — no Docker daemon: {e}")
        return 0

    failures = []
    cid = None
    try:
        cid, _ = await dm.create_container("test-shell-exec", ContainerConfig())
        session = types.SimpleNamespace(container_id=cid, id="test-shell-exec")

        async def sh(ti, cancel=None):
            return await handle_shell_exec(session, ti, _noop_ws, cancel)

        # Case 1: success exit code reported
        r = await sh({"command": "echo hi"})
        if "[exit_code=0]" not in r or "hi" not in r:
            failures.append(f"Case1 echo: {r!r}")
        else:
            print("[1] echo hi → [exit_code=0] + output: PASS")

        # Case 2: non-zero exit code reported
        r = await sh({"command": "exit 7"})
        if "[exit_code=7]" not in r:
            failures.append(f"Case2 exit7: {r!r}")
        else:
            print("[2] exit 7 → [exit_code=7]: PASS")

        # Case 3: timeout honored
        r = await sh({"command": "sleep 5", "timeout": 1})
        if "TIMED OUT" not in r:
            failures.append(f"Case3 timeout: {r!r}")
        else:
            print("[3] sleep 5 / timeout 1 → TIMED OUT: PASS")

        # Case 4: large output containing the literal old heredoc marker → overflow
        # file must round-trip correctly (proves heredoc bug is gone).
        big_cmd = "for i in $(seq 1 400); do echo \"HEREDOC_EOF line $i with some padding text xxxxxxxxxxxxxxxxxxxxxxxxxxxx\"; done"
        r = await sh({"command": big_cmd, "timeout": 30})
        if "saved to /tmp/output_" not in r:
            failures.append(f"Case4 overflow not saved: {r[:160]!r}")
        else:
            # extract path and read it back
            import re
            m = re.search(r"saved to (/tmp/output_\w+\.txt)", r)
            ok = False
            if m:
                back = await dm.copy_file_from(cid, m.group(1))
                txt = back.decode("utf-8") if isinstance(back, (bytes, bytearray)) else str(back)
                ok = "HEREDOC_EOF line 400" in txt
            if not ok:
                failures.append("Case4 overflow round-trip failed (heredoc marker broke it?)")
            else:
                print("[4] large output w/ 'HEREDOC_EOF' → overflow file round-trips: PASS")

        # Case 5: cancel_event set → returns quickly without finishing a long cmd
        ev = threading.Event()
        ev.set()
        r = await sh({"command": "sleep 30", "timeout": 60}, cancel=ev)
        if "CANCELLED" not in r:
            failures.append(f"Case5 cancel: expected CANCELLED, got {r!r}")
        else:
            print("[5] cancel_event set → CANCELLED quickly: PASS")

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
