"""BEFORE baseline (A): verify_webapp chong app that tren :8080 trong container.
Soi: blank-200 PASS gia? app loi tren input that bi bat? warmup boot? assert_json? app khong listen?"""
import asyncio, types, sys
sys.path.insert(0, '/app')
from app.core.docker_manager import DockerManager
from app.models.session import ContainerConfig
import app.deps as deps
from app.agent.builtin_tools import handle_verify_webapp


async def main():
    dm = DockerManager(); deps._docker_manager = dm
    cid, _ = await dm.create_container('eval-vwebapp', ContainerConfig())
    s = types.SimpleNamespace(container_id=cid, id='x')
    async def ws(m): pass

    async def r(label, ti):
        out = await handle_verify_webapp(s, ti, ws, None)
        print(f"\n=== {label} ===")
        print("  " + out.split(chr(10))[0])
        for ln in out.split(chr(10))[1:]:
            if ln.startswith('['): print("  " + ln[:160])

    app_blank = (
        "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
        "class H(BaseHTTPRequestHandler):\n"
        "    def log_message(self,*a): pass\n"
        "    def do_GET(self):\n"
        "        self.send_response(200); self.end_headers(); self.wfile.write(b'<html><body></body></html>')\n"
        "    def do_POST(self):\n"
        "        self.send_response(500); self.end_headers(); self.wfile.write(b'Internal Server Error')\n"
        "HTTPServer(('0.0.0.0',8080),H).serve_forever()\n"
    )
    await dm.copy_file_to(cid, app_blank.encode(), "/workspace/blank.py")
    await dm.exec_command_simple(cid, "nohup python3 /workspace/blank.py >/tmp/b.log 2>&1 & echo $! >/tmp/b.pid; sleep 1")

    await r("1. blank-200 chi assert_status=200 (PASS gia?)",
            {"app_url": "http://localhost:8080", "journey": [{"name": "home", "assert_status": 200}]})
    await r("2. blank-200 assert_contains 'Welcome' -> FAIL dung",
            {"journey": [{"name": "home", "assert_contains": "Welcome"}]})
    await r("3. POST input that tra 500 -> FAIL",
            {"journey": [{"name": "submit", "method": "POST", "path": "/api", "body": {"q": "hi"}, "assert_status": 200}]})

    await dm.exec_command_simple(cid, "kill $(cat /tmp/b.pid) 2>/dev/null; sleep 2")

    app_json = (
        "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
        "import json\n"
        "class H(BaseHTTPRequestHandler):\n"
        "    def log_message(self,*a): pass\n"
        "    def do_POST(self):\n"
        "        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()\n"
        "        self.wfile.write(json.dumps({'answer':'42','status':'ok'}).encode())\n"
        "HTTPServer(('0.0.0.0',8080),H).serve_forever()\n"
    )
    await dm.copy_file_to(cid, app_json.encode(), "/workspace/api.py")
    await dm.exec_command_simple(cid, "nohup python3 /workspace/api.py >/tmp/a.log 2>&1 & echo $! >/tmp/a.pid; sleep 1")
    await r("4. assert_json required+equals -> PASS",
            {"journey": [{"name": "ask", "method": "POST", "path": "/q", "body": {"q": "x"},
                          "assert_status": 200, "assert_json": {"required": ["answer"], "equals": {"status": "ok"}}}]})
    await r("5. assert_json equals sai -> FAIL",
            {"journey": [{"name": "ask", "method": "POST", "path": "/q", "body": {"q": "x"},
                          "assert_json": {"equals": {"status": "error"}}}]})
    await dm.exec_command_simple(cid, "kill $(cat /tmp/a.pid) 2>/dev/null; sleep 2")

    await r("6. app khong listen (warmup_retries=2) -> FAIL 000",
            {"journey": [{"name": "home", "assert_status": 200}], "warmup_retries": 2})

    await r("7. journey rong -> huong dan", {"journey": []})

    await dm.destroy_container(cid)


asyncio.run(main())
