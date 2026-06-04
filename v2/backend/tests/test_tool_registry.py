"""Unit tests for ToolRegistry — dispatch, registration, subagent filtering."""
import pytest
from app.agent.tool_registry import ToolRegistry


async def _dummy(session, tool_input, ws_send, cancel_event):
    return "ok"


def _schema(name):
    return {"name": name, "description": f"{name} tool", "inputSchema": {"json": {"type": "object", "properties": {}}}}


def test_register_and_lookup():
    reg = ToolRegistry()
    reg.register("foo", _schema("foo"), _dummy, builtin=True)
    assert reg.has_tool("foo")
    assert reg.count == 1
    assert reg.get_handler("foo") is _dummy


def test_get_handler_missing_returns_none():
    reg = ToolRegistry()
    assert reg.get_handler("nope") is None


def test_cannot_overwrite_builtin_with_runtime():
    reg = ToolRegistry()
    reg.register("foo", _schema("foo"), _dummy, builtin=True)
    with pytest.raises(ValueError):
        reg.register("foo", _schema("foo"), _dummy, builtin=False)


def test_unregister_runtime_succeeds():
    reg = ToolRegistry()
    reg.register("bar", _schema("bar"), _dummy, builtin=False)
    assert reg.unregister("bar") is True
    assert not reg.has_tool("bar")


def test_unregister_builtin_blocked():
    reg = ToolRegistry()
    reg.register("foo", _schema("foo"), _dummy, builtin=True)
    assert reg.unregister("foo") is False
    assert reg.has_tool("foo")


def test_list_runtime_tools():
    reg = ToolRegistry()
    reg.register("builtin1", _schema("builtin1"), _dummy, builtin=True)
    reg.register("runtime1", _schema("runtime1"), _dummy, builtin=False)
    assert reg.list_runtime_tools() == ["runtime1"]


def test_get_tool_specs_format():
    reg = ToolRegistry()
    reg.register("foo", _schema("foo"), _dummy, builtin=True)
    specs = reg.get_tool_specs()
    assert len(specs) == 1
    assert specs[0] == {"toolSpec": _schema("foo")}


def test_subagent_excludes_meta_tools():
    reg = ToolRegistry()
    reg.register("shell_exec", _schema("shell_exec"), _dummy, builtin=True)
    reg.register("spawn_subagent", _schema("spawn_subagent"), _dummy, builtin=True)
    reg.register("create_tool", _schema("create_tool"), _dummy, builtin=True)

    sub_specs = reg.get_tool_specs(is_subagent=True)
    names = [s["toolSpec"]["name"] for s in sub_specs]
    assert "shell_exec" in names
    assert "spawn_subagent" not in names
    assert "create_tool" not in names


def test_get_tool_info():
    reg = ToolRegistry()
    reg.register("foo", _schema("foo"), _dummy, builtin=False, category="intelligence")
    info = reg.get_tool_info("foo")
    assert info["name"] == "foo"
    assert info["builtin"] is False
    assert info["category"] == "intelligence"
