import asyncio, time, types, sys
sys.path.insert(0, '/app')
from app.core.docker_manager import DockerManager
from app.models.session import ContainerConfig
import app.deps as deps
from app.agent.builtin_tools import handle_shell_exec


async def main():
    dm = DockerManager(); deps._docker_manager = dm
    cid, _ = await dm.create_container('eval-shell', ContainerConfig())
    s = types.SimpleNamespace(container_id=cid, id='eval-shell')

    t0 = [0.0]
    chunks_log = []
    async def ws(m):
        # record WHEN each live chunk arrives → proves streaming vs batch
        if m.get("type") == "terminal_output" and m.get("content") and not m.get("done"):
            chunks_log.append((round(time.monotonic() - t0[0], 1), m["content"].strip()[:40]))

    async def run(label, ti, cancel=None):
        chunks_log.clear(); t0[0] = time.monotonic()
        r = await handle_shell_exec(s, ti, ws, cancel)
        print(f"\n=== {label} ===")
        print(f"INPUT: {ti}")
        if chunks_log:
            print("LIVE CHUNKS (giây khi đến → nội dung):")
            for t, c in chunks_log:
                print(f"   t+{t}s: {c}")
        print(f"RETURN:\n{r[:500]}")

    # 1. PROOF OF LIVE STREAMING: in 1 dòng mỗi giây trong 4s — chunks phải đến RẢI theo thời gian
    await run("1. Stream LIVE (1 dòng/giây x4)",
              {"command": "for i in 1 2 3 4; do echo \"dong $i luc $(date +%S)s\"; sleep 1; done"})

    # 2. TIMEOUT GIỮ OUTPUT: in 3 dòng rồi treo — timeout phải giữ 3 dòng đã in (trước đây mất sạch)
    await run("2. Timeout GIỮ output đã in (in 3 dòng rồi sleep 30, timeout=4)",
              {"command": "echo A; echo B; echo C; sleep 30", "timeout": 4})

    # 3. exit code vẫn đúng khi stream
    await run("3. Exit code khi fail", {"command": "echo truoc-loi; ls /khong-co; echo sau-loi"})

    # 4. cancel giữa chừng
    import threading
    ev = threading.Event()
    async def cancel_after():
        await asyncio.sleep(2); ev.set()
    asyncio.create_task(cancel_after())
    await run("4. Cancel giữa chừng (sleep 20, cancel sau 2s)",
              {"command": "echo start; sleep 20; echo end"}, cancel=ev)

    await dm.destroy_container(cid)


asyncio.run(main())
