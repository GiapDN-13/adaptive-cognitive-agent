import asyncio, types, sys
sys.path.insert(0, '/app')
from app.core.docker_manager import DockerManager
from app.models.session import ContainerConfig
import app.deps as deps
from app.agent.builtin_tools import handle_read_file


async def main():
    dm = DockerManager(); deps._docker_manager = dm
    cid, _ = await dm.create_container('eval-read', ContainerConfig())
    s = types.SimpleNamespace(container_id=cid, id='x')
    async def ws(m): pass

    async def r(label, ti):
        out = await handle_read_file(s, ti, ws, None)
        print(f"\n=== {label} ===  INPUT: {ti}")
        print(f"RETURN (len={len(out)}): {out[:220]}" + ("...[CẮT]" if len(out) > 220 else ""))

    await dm.exec_command_simple(cid, "seq 1 500 > /workspace/big.txt")
    await dm.exec_command_simple(cid, "printf 'one line no newline' > /workspace/oneline.txt")
    await dm.exec_command_simple(cid, "python3 -c \"open('/workspace/huge.txt','w').write('X'*500000)\"")
    await dm.exec_command_simple(cid, "head -c 2000 /dev/urandom > /workspace/bin.dat")

    await r("1. Path tương đối 'big.txt'", {"path": "big.txt", "max_lines": 3})
    await r("2. File 1 dòng 500KB (phải CAP ~50KB)", {"path": "/workspace/huge.txt"})
    await r("3. Binary (phải TỪ CHỐI + gợi ý)", {"path": "/workspace/bin.dat"})
    await r("4. 1 dòng không newline (total=1)", {"path": "/workspace/oneline.txt"})
    await r("5. Override max_bytes=200000 đọc huge", {"path": "/workspace/huge.txt", "max_bytes": 200000})
    await r("6. big.txt offset=498 (cuối file)", {"path": "/workspace/big.txt", "offset": 498})

    await dm.destroy_container(cid)


asyncio.run(main())
