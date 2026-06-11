"""Test P3.5: meta_tools schema validation + overwrite guard, tool_safety
whitelist widening, hook return-type fail-open. Pure unit, no Docker.
"""
import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def _noop_ws(_m):
    pass


async def run():
    failures = []

    # --- tool_safety whitelist ---
    from app.agent.tool_safety import validate_handler_code, CodeSafetyError

    good = (
        "import requests\n"
        "async def handler(session, tool_input, ws_send, cancel_event):\n"
        "    return 'ok'\n"
    )
    try:
        validate_handler_code(good)
        print("[1] handler importing 'requests' now allowed: PASS")
    except CodeSafetyError as e:
        failures.append(f"Case1: requests should be allowed now: {e}")

    bad = (
        "import os\n"
        "async def handler(session, tool_input, ws_send, cancel_event):\n"
        "    return os.getcwd()\n"
    )
    try:
        validate_handler_code(bad)
        failures.append("Case2: 'import os' should still be rejected")
    except CodeSafetyError:
        print("[2] handler importing 'os' still rejected: PASS")

    # Case 2b: dunder sandbox-escape WITHOUT import must be rejected
    # (().__class__.__subclasses__() reaches Popen/os in the backend process).
    escape = (
        "async def handler(session, tool_input, ws_send, cancel_event):\n"
        "    return str(().__class__.__bases__[0].__subclasses__())\n"
    )
    try:
        validate_handler_code(escape)
        failures.append("Case2b: dunder sandbox-escape should be rejected")
    except CodeSafetyError:
        print("[2b] dunder __subclasses__ escape rejected: PASS")

    # --- create_tool schema validation + overwrite guard ---
    from app.agent.tool_registry import tool_registry
    from app.agent.meta_tools import handle_create_tool
    session = types.SimpleNamespace(container_id="x", id="smeta")

    # malformed parameters (not a JSON schema object)
    r = await handle_create_tool(session, {
        "tool_name": "t_bad", "description": "d", "parameters": {"foo": "bar"},
        "handler_code": good,
    }, _noop_ws, None)
    if "must be a JSON Schema object" not in r:
        failures.append(f"Case3 schema-validate: {r!r}")
    else:
        print("[3] malformed parameters rejected: PASS")

    # valid create, then overwrite guard
    valid_params = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
    r1 = await handle_create_tool(session, {
        "tool_name": "t_over", "description": "d", "parameters": valid_params, "handler_code": good,
    }, _noop_ws, None)
    r2 = await handle_create_tool(session, {
        "tool_name": "t_over", "description": "d2", "parameters": valid_params, "handler_code": good,
    }, _noop_ws, None)
    if "successfully" not in r1:
        failures.append(f"Case4a valid create failed: {r1!r}")
    elif "overwrite=true" not in r2:
        failures.append(f"Case4b overwrite not guarded: {r2!r}")
    else:
        print("[4] valid create OK; duplicate runtime tool guarded (needs overwrite): PASS")
    # cleanup
    tool_registry.unregister("t_over")

    # --- hook return-type fail-open ---
    from app.agent.hook_manager import HookManager
    hm = HookManager()

    async def bad_pre_hook(tool_name, tool_input, session_id):
        return "I should be a tuple but I'm a string"  # malformed
    hm.register_pre_hook(bad_pre_hook)
    allowed, reason = await hm.execute_pre_hooks("shell_exec", {}, "s")
    if allowed is not True:
        failures.append(f"Case5 pre-hook fail-open: blocked unexpectedly ({allowed},{reason})")
    else:
        print("[5] malformed pre-hook → fail-open (execution allowed): PASS")

    async def bad_post_hook(tool_name, tool_input, result, session_id):
        return 12345  # not a str
    hm2 = HookManager()
    hm2.register_post_hook(bad_post_hook)
    out = await hm2.execute_post_hooks("shell_exec", {}, "original", "s")
    if out != "original":
        failures.append(f"Case6 post-hook fail-open: result corrupted → {out!r}")
    else:
        print("[6] malformed post-hook → keeps prior result (str): PASS")

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
