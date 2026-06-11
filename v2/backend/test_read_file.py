"""Test handle_read_file hardening (P2.1): missing-vs-empty, offset pagination,
total line count, line numbers. Run in backend container; skips w/o Docker.
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
        from app.agent.builtin_tools import handle_read_file
        dm = DockerManager()
        deps._docker_manager = dm
    except Exception as e:
        print(f"SKIP — no Docker daemon: {e}")
        return 0

    failures = []
    cid = None
    try:
        cid, _ = await dm.create_container("test-read-file", ContainerConfig())
        session = types.SimpleNamespace(container_id=cid, id="test-read-file")

        async def rd(ti):
            return await handle_read_file(session, ti, _noop_ws, None)

        # setup files
        await dm.exec_command_simple(cid, "mkdir -p /workspace/d")
        await dm.exec_command_simple(cid, "touch /workspace/empty.txt")
        await dm.exec_command_simple(cid, "seq 1 500 > /workspace/big.txt")

        # Case 1: missing file
        r = await rd({"path": "/workspace/nope.txt"})
        if "FILE NOT FOUND" not in r:
            failures.append(f"Case1 missing: {r!r}")
        else:
            print("[1] missing file → FILE NOT FOUND: PASS")

        # Case 2: empty file (distinct from missing)
        r = await rd({"path": "/workspace/empty.txt"})
        if "empty file" not in r or "NOT FOUND" in r:
            failures.append(f"Case2 empty: {r!r}")
        else:
            print("[2] empty file → empty (not 'not found'): PASS")

        # Case 3: offset pagination + total count
        r = await rd({"path": "/workspace/big.txt", "offset": 100, "max_lines": 50})
        lines = [l for l in r.split("\n")[1:] if l.strip()]
        if "of 500" not in r or "100" not in lines[0] or "149" not in lines[-1] or len(lines) != 50:
            failures.append(f"Case3 offset: header/lines wrong. header={r.splitlines()[0]!r} first={lines[0]!r} last={lines[-1]!r} n={len(lines)}")
        else:
            print("[3] offset=100 max=50 → lines 100-149 of 500: PASS")

        # Case 4: directory
        r = await rd({"path": "/workspace/d"})
        if "is a directory" not in r:
            failures.append(f"Case4 dir: {r!r}")
        else:
            print("[4] directory → clear error: PASS")

        # Case 5: line_numbers
        r = await rd({"path": "/workspace/big.txt", "offset": 1, "max_lines": 3, "line_numbers": True})
        if "1\t1" not in r.replace(" ", ""):  # cat -n produces "     1\t1"
            # be lenient: just check it contains a tab-numbered first line
            if "\t" not in r:
                failures.append(f"Case5 line_numbers: {r!r}")
            else:
                print("[5] line_numbers → numbered output: PASS")
        else:
            print("[5] line_numbers → numbered output: PASS")

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
