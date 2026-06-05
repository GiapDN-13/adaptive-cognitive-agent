"""Unit tests for hook_manager — pre/post hooks, GateGuard, dangerous command detection."""
import pytest

from app.agent.hook_manager import (
    HookManager,
    _record_tool_call,
    clear_session_history,
    dangerous_command_pre_hook,
    gateguard_pre_hook,
    secret_detection_pre_hook,
)


@pytest.mark.asyncio
async def test_dangerous_command_blocks_rm_rf_root():
    allowed, reason = await dangerous_command_pre_hook(
        "shell_exec", {"command": "rm -rf /"}, "sess1"
    )
    assert allowed is False
    assert reason is not None


@pytest.mark.asyncio
async def test_dangerous_command_blocks_fork_bomb():
    allowed, _ = await dangerous_command_pre_hook(
        "shell_exec", {"command": ":(){ :|:& };:"}, "sess1"
    )
    assert allowed is False


@pytest.mark.asyncio
async def test_dangerous_command_allows_safe():
    allowed, reason = await dangerous_command_pre_hook(
        "shell_exec", {"command": "ls -la /workspace"}, "sess1"
    )
    assert allowed is True
    assert reason is None


@pytest.mark.asyncio
async def test_dangerous_command_ignores_non_shell():
    allowed, _ = await dangerous_command_pre_hook(
        "write_file", {"path": "/tmp/x", "content": "rm -rf /"}, "sess1"
    )
    assert allowed is True  # not shell_exec, so not checked


@pytest.mark.asyncio
async def test_gateguard_blocks_create_without_research():
    sid = "gg_test_1"
    clear_session_history(sid)
    # No research done yet → create_tool should be blocked
    allowed, reason = await gateguard_pre_hook(
        "create_tool", {"tool_name": "x"}, sid
    )
    assert allowed is False
    assert "research" in reason.lower()


@pytest.mark.asyncio
async def test_gateguard_allows_create_after_research():
    sid = "gg_test_2"
    clear_session_history(sid)
    _record_tool_call(sid, "web_search")  # simulate research
    allowed, reason = await gateguard_pre_hook(
        "create_tool", {"tool_name": "x"}, sid
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_gateguard_ignores_non_write_tools():
    sid = "gg_test_3"
    clear_session_history(sid)
    allowed, _ = await gateguard_pre_hook("shell_exec", {"command": "ls"}, sid)
    assert allowed is True


@pytest.mark.asyncio
async def test_secret_detection_blocks_aws_key():
    content = 'aws_key = "AKIAIOSFODNN7EXAMPLE"'
    allowed, reason = await secret_detection_pre_hook(
        "write_file", {"path": "/tmp/config.py", "content": content}, "sess1"
    )
    assert allowed is False


@pytest.mark.asyncio
async def test_secret_detection_allows_clean_code():
    content = 'def hello():\n    return "world"'
    allowed, _ = await secret_detection_pre_hook(
        "write_file", {"path": "/tmp/x.py", "content": content}, "sess1"
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_hook_manager_pre_blocks_on_first_fail():
    hm = HookManager()

    async def blocker(tool, inp, sid):
        return False, "blocked"

    async def allower(tool, inp, sid):
        return True, None

    hm.register_pre_hook(allower)
    hm.register_pre_hook(blocker)
    allowed, reason = await hm.execute_pre_hooks("x", {}, "s")
    assert allowed is False
    assert reason == "blocked"


@pytest.mark.asyncio
async def test_hook_manager_fail_open_on_exception():
    hm = HookManager()

    async def crasher(tool, inp, sid):
        raise RuntimeError("boom")

    hm.register_pre_hook(crasher)
    # Fail-open: exception in hook should not block execution
    allowed, _ = await hm.execute_pre_hooks("x", {}, "s")
    assert allowed is True


@pytest.mark.asyncio
async def test_post_hooks_chain_result():
    hm = HookManager()

    async def append_a(tool, inp, result, sid):
        return result + "A"

    async def append_b(tool, inp, result, sid):
        return result + "B"

    hm.register_post_hook(append_a)
    hm.register_post_hook(append_b)
    result = await hm.execute_post_hooks("x", {}, "start", "s")
    assert result == "startAB"
