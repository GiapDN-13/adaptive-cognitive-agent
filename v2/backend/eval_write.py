import asyncio, types, sys
sys.path.insert(0, '/app')
from app.core.docker_manager import DockerManager
from app.models.session import ContainerConfig
import app.deps as deps
from app.agent.builtin_tools import handle_write_file


async def main():
    dm = DockerManager(); deps._docker_manager = dm
    cid, _ = await dm.create_container('eval-write', ContainerConfig())
    s = types.SimpleNamespace(container_id=cid, id='eval-write')
    async def ws(m): pass

    async def run(label, ti, verify_cmd=None):
        r = await handle_write_file(s, ti, ws, None)
        print(f"\n=== {label} ===")
        print(f"INPUT: path={ti.get('path')!r} mode={ti.get('mode','overwrite')} len={len(ti.get('content',''))}")
        print(f"RETURN: {r[:160]}")
        if verify_cmd:
            _, out = await dm.exec_command_simple(cid, verify_cmd)
            print(f"VERIFY: {out.strip()[:160]!r}")

    # 1. cơ bản
    await run("1. Ghi cơ bản", {"path": "/workspace/a.txt", "content": "hello\n"}, "cat /workspace/a.txt")
    # 2. ghi đè → phải có note overwrite
    await run("2. Ghi ĐÈ (note?)", {"path": "/workspace/a.txt", "content": "NEW\n"}, "cat /workspace/a.txt")
    # 3. APPEND → phải nối, giữ NEW
    await run("3. APPEND (giữ NEW + thêm MORE)", {"path": "/workspace/a.txt", "content": "MORE\n", "mode": "append"}, "cat /workspace/a.txt")
    # 4. relative path → resolve về /workspace
    await run("4. Path TƯƠNG ĐỐI rel.txt", {"path": "rel.txt", "content": "x\n"}, "cat /workspace/rel.txt")
    # 5. path rỗng → default
    await run("5. Path RỖNG → default", {"path": "", "content": "y\n"}, "cat /workspace/file.txt")
    # 6. tiếng việt
    await run("6. Tiếng Việt", {"path": "/workspace/vn.txt", "content": "Xin chào 🇻🇳\n"}, "cat /workspace/vn.txt")
    # 7. /proc → phải WRITE FAILED
    await run("7. Ghi /proc (phải FAILED)", {"path": "/proc/test.txt", "content": "z\n"})
    # 8. append vào file chưa tồn tại → tạo mới
    await run("8. APPEND file mới", {"path": "/workspace/new.txt", "content": "first\n", "mode": "append"}, "cat /workspace/new.txt")

    await dm.destroy_container(cid)


asyncio.run(main())
