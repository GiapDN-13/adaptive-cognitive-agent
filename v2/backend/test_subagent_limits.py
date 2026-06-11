"""Test P3.1: subagent depth cap, robust result extraction, pipeline exclusion.
Pure unit — monkeypatches _run_loop, no Docker needed.
"""
import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def _noop_ws(_m):
    pass


async def run():
    import app.agent.loop as loop
    from app.agent.builtin_tools import handle_spawn_subagent, handle_spawn_critic
    from app.agent.tool_registry import tool_registry
    from app.agent.builtin_tools import register_all_builtins
    from app.agent.meta_tools import register_meta_tools

    failures = []
    session = types.SimpleNamespace(container_id="x", id="ssub")
    loop._subagent_depth.clear()

    # 1) extract_last_agent_text: last msg is a toolResult (no assistant text) →
    #    must still return the earlier assistant text, not "".
    msgs = [
        {"role": "user", "content": [{"text": "task"}]},
        {"role": "assistant", "content": [{"text": "the real answer"}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "t", "content": [{"text": "tool output"}]}}]},
    ]
    got = loop.extract_last_agent_text(msgs)
    if got != "the real answer":
        failures.append(f"extract: expected 'the real answer', got {got!r}")
    else:
        print("[1] extract_last_agent_text skips trailing toolResult → assistant text: PASS")

    # 2) pipeline excluded for subagents
    if not tool_registry.has_tool("execute_pipeline"):
        register_all_builtins(tool_registry)
        register_meta_tools(tool_registry)
    sub_specs = tool_registry.get_tool_specs(is_subagent=True)
    sub_names = {s["toolSpec"]["name"] for s in sub_specs}
    if "execute_pipeline" in sub_names:
        failures.append("execute_pipeline should be excluded for subagents")
    elif "spawn_subagent" in sub_names or "spawn_critic" in sub_names:
        failures.append("spawn_* should be excluded for subagents")
    else:
        print("[2] subagent tool specs exclude execute_pipeline + spawn_*: PASS")

    # 3) depth cap: simulate depth already at max → refuse
    orig_runloop = loop._run_loop

    async def fake_runloop(**kw):
        # populate a trailing assistant message so extraction works
        kw["messages"].append({"role": "assistant", "content": [{"text": "done"}]})

    loop._run_loop = fake_runloop
    try:
        loop._subagent_depth[session.id] = loop._MAX_SUBAGENT_DEPTH
        r = await handle_spawn_subagent(session, {"role_name": "X", "task": "t"}, _noop_ws, None)
        if "NOT SPAWNED" not in r:
            failures.append(f"depth cap subagent: {r!r}")
        else:
            print("[3] subagent at max depth → refused: PASS")

        r = await handle_spawn_critic(session, {"subject": "s", "context": "c"}, _noop_ws, None)
        if "NOT SPAWNED" not in r:
            failures.append(f"depth cap critic: {r!r}")
        else:
            print("[4] critic at max depth → refused: PASS")

        # 4) depth resets after a normal spawn (depth 0 → runs → back to 0)
        loop._subagent_depth[session.id] = 0
        r = await handle_spawn_subagent(session, {"role_name": "Y", "task": "t"}, _noop_ws, None)
        if loop._subagent_depth.get(session.id) != 0:
            failures.append(f"depth not restored: {loop._subagent_depth.get(session.id)}")
        elif "done" not in r:
            failures.append(f"normal spawn extraction: {r!r}")
        else:
            print("[5] normal spawn runs + depth restored to 0: PASS")
    finally:
        loop._run_loop = orig_runloop
        loop._subagent_depth.clear()

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
