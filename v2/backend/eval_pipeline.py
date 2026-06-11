"""BEFORE (A): soi edge-case execute_pipeline khi 2 stage TRUNG (name,goal).
Nghi van: completed_stages la dict keyed by hash(name,goal) -> 2 stage trung chi
1 entry -> len(completed) != len(stages) -> all_done=False -> bao 'partial' + checkpoint
khong bao gio clear, du da chay het."""
import asyncio, sys, types
sys.path.insert(0, '/app')


async def _ws(_m): pass


async def main():
    import app.agent.loop as loop
    from app.agent.builtin_tools import handle_execute_pipeline, _clear_pipeline_checkpoint
    loop._cancel_flags.clear()
    session = types.SimpleNamespace(container_id="x", id="spipe")

    async def fake_runloop(**kw):
        kw["messages"].append({"role": "assistant", "content": [{"text": "stage output ok"}]})
    loop._run_loop = fake_runloop

    _clear_pipeline_checkpoint(session.id, "DupPipe")
    ti = {"name": "DupPipe", "context": "c", "stages": [
        {"name": "Scan", "goal": "scan code"},
        {"name": "Scan", "goal": "scan code"},   # <-- trung khoa
        {"name": "Report", "goal": "write report"},
    ]}
    r = await handle_execute_pipeline(session, ti, _ws, None)
    head = r.split(chr(10))[0]
    print("SUMMARY:", head)
    print("  >> ky vong: chay het 3 stage -> 'completed'. Neu thay 'partial' / so < 3 -> BUG dup-key")
    _clear_pipeline_checkpoint(session.id, "DupPipe")


asyncio.run(main())
