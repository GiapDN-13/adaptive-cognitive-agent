"""Test handle_write_file hardening (P1.1): no path injection, byte-faithful
round-trip, nested dirs, size cap. Run in backend container; skips w/o Docker.
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
        from app.agent.builtin_tools import handle_write_file, _MAX_WRITE_BYTES
        dm = DockerManager()
        deps._docker_manager = dm
    except Exception as e:
        print(f"SKIP — no Docker daemon: {e}")
        return 0

    failures = []
    cid = None
    try:
        cid, _ = await dm.create_container("test-write-file", ContainerConfig())
        session = types.SimpleNamespace(container_id=cid, id="test-write-file")

        # Case 1: PATH INJECTION — a path containing $(...) must NOT execute.
        evil_path = "/workspace/$(touch /tmp/PWNED).txt"
        res1 = await handle_write_file(session, {"path": evil_path, "content": "x"}, _noop_ws, None)
        ec, _ = await dm.exec_command_simple(cid, "test -f /tmp/PWNED && echo YES || echo NO")
        pwned = "YES" in (await dm.exec_command_simple(cid, "ls /tmp/PWNED 2>/dev/null && echo YES || echo NO"))[1]
        if pwned:
            failures.append("Case1 INJECTION: /tmp/PWNED was created — shell injection still possible!")
        else:
            print("[1] path injection blocked (no /tmp/PWNED): PASS")

        # Case 2: byte-faithful round-trip with quotes / $() / newlines / unicode
        tricky = "line1 'single' \"double\"\n$(echo nope) `backtick`\nTiếng Việt: xin chào\n"
        res2 = await handle_write_file(session, {"path": "/workspace/rt.txt", "content": tricky}, _noop_ws, None)
        back = await dm.copy_file_from(cid, "/workspace/rt.txt")
        got = back.decode("utf-8") if isinstance(back, (bytes, bytearray)) else str(back)
        if got != tricky:
            failures.append(f"Case2 round-trip mismatch: wrote {tricky!r} got {got!r}")
        elif "verified" not in res2:
            failures.append(f"Case2 not verified: {res2}")
        else:
            print("[2] round-trip (quotes/$()/newline/unicode) + verified: PASS")

        # Case 3: nested dirs auto-created
        res3 = await handle_write_file(session, {"path": "/workspace/a/b/c/deep.txt", "content": "deep"}, _noop_ws, None)
        ec, out = await dm.exec_command_simple(cid, "cat /workspace/a/b/c/deep.txt")
        if out.strip() != "deep":
            failures.append(f"Case3 nested dir: got {out!r} / res {res3}")
        else:
            print("[3] nested dirs auto-created: PASS")

        # Case 4: oversize rejected
        big = "A" * (_MAX_WRITE_BYTES + 1)
        res4 = await handle_write_file(session, {"path": "/workspace/big.txt", "content": big}, _noop_ws, None)
        if "WRITE FAILED" not in res4 or "limit" not in res4:
            failures.append(f"Case4 oversize not rejected: {res4[:120]}")
        else:
            print("[4] oversize content rejected: PASS")

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
