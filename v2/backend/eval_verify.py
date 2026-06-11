import asyncio, types, sys
sys.path.insert(0, '/app')
from app.core.docker_manager import DockerManager
from app.models.session import ContainerConfig
import app.deps as deps
from app.agent.builtin_tools import handle_verify_work


async def main():
    dm = DockerManager(); deps._docker_manager = dm
    cid, _ = await dm.create_container('eval-verify', ContainerConfig())
    s = types.SimpleNamespace(container_id=cid, id='x')
    async def ws(m): pass

    async def r(label, ti):
        out = await handle_verify_work(s, ti, ws, None)
        first = out.split(chr(10))[0]
        assess = [l for l in out.split(chr(10)) if l.startswith('Assessment')]
        print(f"\n=== {label} ===  INPUT: {ti}")
        print(f"  {first}")
        if assess: print(f"  {assess[0]}")
        print(f"  [out_len={len(out)}]")

    await r("1. exit0 + output 'error'", {"criterion": "c1", "test_command": "echo 'an error occurred'; true"})
    await r("2. exit1", {"criterion": "c2", "test_command": "false"})
    await r("3. contains khop", {"criterion": "c3", "test_command": "echo HELLO", "assert_mode": "contains", "expected": "HELLO"})
    await r("4. regex INVALID", {"criterion": "c4", "test_command": "echo x", "assert_mode": "regex", "expected": "[unclosed"})
    await r("5. contains expected rong", {"criterion": "c5", "test_command": "echo x", "assert_mode": "contains", "expected": ""})
    await r("6. timeout (sleep 5, to=1)", {"criterion": "c6", "test_command": "sleep 5", "timeout": 1})
    await r("7. thieu test_command", {"criterion": "c7"})
    await r("8. output 200KB", {"criterion": "c8", "test_command": "yes ABCDEFGH | head -c 200000; true"})
    await r("9. assert_mode la 'foo'", {"criterion": "c9", "test_command": "true", "assert_mode": "foo"})
    await r("10. exit_code expected=3, lenh exit 3", {"criterion": "c10", "test_command": "exit 3", "expected": "3"})

    await dm.destroy_container(cid)


asyncio.run(main())
