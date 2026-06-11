"""Test verify_webapp hardening (P3.2): warmup/retry, assert_json, body cap.
Run in backend container; skips w/o Docker.
"""
import asyncio
import base64
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def _noop_ws(_m):
    pass


APP = '''
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
class H(BaseHTTPRequestHandler):
    def do_GET(s):
        if s.path == "/":
            s.send_response(200); s.send_header("Content-Type","text/html"); s.end_headers()
            s.wfile.write(b"<div id=chat>MekongAI RAG</div>")
        elif s.path == "/health":
            s.send_response(200); s.send_header("Content-Type","application/json"); s.end_headers()
            s.wfile.write(json.dumps({"status":"ok","ready":True}).encode())
        else:
            s.send_response(404); s.end_headers(); s.wfile.write(b"not found")
    def log_message(s,*a): pass
HTTPServer(("0.0.0.0",8080),H).serve_forever()
'''


async def run():
    try:
        from app.core.docker_manager import DockerManager
        from app.models.session import ContainerConfig
        import app.deps as deps
        from app.agent.builtin_tools import handle_verify_webapp
        dm = DockerManager()
        deps._docker_manager = dm
    except Exception as e:
        print(f"SKIP — no Docker daemon: {e}")
        return 0

    failures = []
    cid = None
    try:
        cid, _ = await dm.create_container("test-vwa2", ContainerConfig())
        session = types.SimpleNamespace(container_id=cid, id="test-vwa2")
        b64 = base64.b64encode(APP.encode()).decode()
        await dm.exec_command_simple(cid, f"echo {b64} | base64 -d > /app.py")

        async def vw(ti):
            return await handle_verify_webapp(session, ti, _noop_ws, None)

        # Case 1: warmup — start server with a delay, verify_webapp should retry past 000
        await dm.exec_command_simple(cid, "nohup sh -c 'sleep 4 && python3 /app.py' >/tmp/s.log 2>&1 &")
        r = await vw({"journey": [
            {"name": "home", "path": "/", "assert_status": 200, "assert_contains": "MekongAI RAG"}
        ], "warmup_retries": 8})
        if "VERIFY_WEBAPP: PASS" not in r:
            failures.append(f"Case1 warmup: {r[:300]!r}")
        else:
            print("[1] warmup retry past 000 (delayed server) → PASS: PASS")

        # Case 2: assert_json on /health
        r = await vw({"journey": [
            {"name": "health", "path": "/health", "assert_status": 200,
             "assert_json": {"required": ["status"], "equals": {"status": "ok"}}}
        ]})
        if "VERIFY_WEBAPP: PASS" not in r:
            failures.append(f"Case2 assert_json: {r[:300]!r}")
        else:
            print("[2] assert_json (required + equals) → PASS: PASS")

        # Case 3: assert_json mismatch → FAIL
        r = await vw({"journey": [
            {"name": "health", "path": "/health", "assert_json": {"equals": {"status": "DOWN"}}}
        ]})
        if "VERIFY_WEBAPP: FAIL" not in r:
            failures.append(f"Case3 json mismatch: {r[:300]!r}")
        else:
            print("[3] assert_json wrong value → FAIL: PASS")

        # Case 4: status mismatch (404 path with assert 200) → FAIL
        r = await vw({"journey": [
            {"name": "missing", "path": "/nope", "assert_status": 200}
        ]})
        if "VERIFY_WEBAPP: FAIL" not in r:
            failures.append(f"Case4 status: {r[:300]!r}")
        else:
            print("[4] 404 vs assert 200 → FAIL: PASS")

        # Case 5: status-only PASS (no content assert) → PASS but flagged WEAK
        r = await vw({"journey": [
            {"name": "home", "path": "/", "assert_status": 200}
        ]})
        if "VERIFY_WEBAPP: PASS" not in r or "WEAK" not in r:
            failures.append(f"Case5 weak-check (expected PASS+WEAK warning): {r[:300]!r}")
        else:
            print("[5] status-only step → PASS + WEAK warning: PASS")

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
