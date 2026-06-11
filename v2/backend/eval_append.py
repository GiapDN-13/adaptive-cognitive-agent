import asyncio, types, sys
sys.path.insert(0, '/app')
from app.core.docker_manager import DockerManager
from app.models.session import ContainerConfig
import app.deps as deps
from app.agent.builtin_tools import handle_write_file


async def main():
    dm = DockerManager(); deps._docker_manager = dm
    cid, _ = await dm.create_container('eval-append', ContainerConfig())
    s = types.SimpleNamespace(container_id=cid, id='x')
    async def ws(m): pass

    async def w(label, ti):
        r = await handle_write_file(s, ti, ws, None)
        # đọc lại bytes thật + size
        try:
            raw = await dm.copy_file_from(cid, ti['path'] if ti['path'].startswith('/') else '/workspace/'+ti['path'])
            raw = bytes(raw) if isinstance(raw,(bytes,bytearray)) else b''
        except Exception:
            raw = b'<missing>'
        print(f"\n=== {label} ===")
        print(f"  RETURN: {r[:120]}")
        print(f"  FILE BYTES: {raw!r}  (len={len(raw) if isinstance(raw,bytes) else '?'})")

    p = "/workspace/log.txt"
    # 1. file cũ KHÔNG có newline cuối → append → nối SÁT nhau?
    await w("1. Ghi 'AAA' (không newline cuối)", {"path": p, "content": "AAA"})
    await w("2. Append 'BBB' → nối ra sao?", {"path": p, "content": "BBB", "mode": "append"})
    # 3. append tiếp với newline
    await w("3. Append '\\nCCC'", {"path": p, "content": "\nCCC", "mode": "append"})
    # 4. append nhiều lần liên tiếp (build file tăng dần)
    p2 = "/workspace/findings.md"
    await w("4a. append vào file MỚI '## A\\n'", {"path": p2, "content": "## A\n", "mode": "append"})
    await w("4b. append '## B\\n'", {"path": p2, "content": "## B\n", "mode": "append"})
    await w("4c. append '## C\\n'", {"path": p2, "content": "## C\n", "mode": "append"})
    # 5. append file nhị phân/unicode — byte có nguyên vẹn?
    await w("5a. ghi 'Tiếng '", {"path": "/workspace/u.txt", "content": "Tiếng "})
    await w("5b. append 'Việt 🇻🇳'", {"path": "/workspace/u.txt", "content": "Việt 🇻🇳", "mode": "append"})

    await dm.destroy_container(cid)


asyncio.run(main())
