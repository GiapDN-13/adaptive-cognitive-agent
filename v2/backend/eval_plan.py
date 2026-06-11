"""BEFORE (A): soi dong tong ket 'completed/total' cua _execute_plan_steps.
Nghi van bug loop.py:866 — dem 'completed' tim chuoi '[FAILED]' nhung tag that la
'[FAILED exit_code=N]' -> step FAIL bi dem nham la completed."""
import asyncio, sys, types
sys.path.insert(0, '/app')


async def _ws(_m): pass


async def main():
    import app.agent.loop as loop
    loop._cancel_flags.clear()
    session = types.SimpleNamespace(container_id="x", id="splan")

    class FakeDM:
        scripted = {}
        async def exec_command_capture(self, cid, cmd, timeout=900):
            return self.scripted.get(cmd, (0, f"ran: {cmd}", False))
    loop._docker_manager = FakeDM()
    loop.requires_approval = lambda c: False

    FakeDM.scripted = {"true": (0, "ok", False), "false": (1, "boom", False)}
    steps = [
        {"id": "step_0", "command": "true", "description": "s0 ok"},
        {"id": "step_1", "command": "false", "description": "s1 fail"},
        {"id": "step_2", "command": "true", "description": "s2 never"},
    ]
    r = await loop._execute_plan_steps(session, "p", steps, _ws)
    head = r.split(chr(10))[0]
    print("SUMMARY LINE:", head)
    print("  >> co '[FAILED exit_code=1]' trong output:", "[FAILED exit_code=1]" in r)
    print("  >> dem literal '[FAILED]':", "[FAILED]" in r, "(neu False -> bug: fail khong bi tru)")


asyncio.run(main())
