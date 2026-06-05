"""Integration tests for the agent loop — full flow with a mocked LLM.

These test the ReACT loop wiring (tool dispatch, continuation, end_turn handling,
hook pipeline) WITHOUT calling a real LLM or Docker. We patch _call_llm to return
scripted responses.
"""
from unittest.mock import AsyncMock

import pytest

from app.agent import loop as agent_loop
from app.agent.tool_registry import ToolRegistry


class FakeSession:
    def __init__(self, sid="testsess1"):
        self.id = sid
        self.container_id = "fake_container"
        self.messages = []


def _llm_text_response(text):
    """Simulate an end_turn text response from the LLM."""
    return {
        "stopReason": "end_turn",
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {},
    }


def _llm_tool_response(tool_name, tool_input, tool_id="t1"):
    """Simulate a tool_use response from the LLM."""
    return {
        "stopReason": "tool_use",
        "output": {"message": {"content": [
            {"toolUse": {"toolUseId": tool_id, "name": tool_name, "input": tool_input}}
        ]}},
        "usage": {},
    }


@pytest.fixture
def isolated_registry(monkeypatch):
    """Provide a clean registry with a couple of safe fake tools."""
    reg = ToolRegistry()

    async def echo_handler(session, tool_input, ws_send, cancel_event):
        return f"echo: {tool_input.get('msg', '')}"

    reg.register(
        "echo_tool",
        {"name": "echo_tool", "description": "echo", "inputSchema": {"json": {"type": "object", "properties": {}}}},
        echo_handler,
        builtin=True,
    )
    monkeypatch.setattr("app.agent.loop.tool_registry", reg)
    return reg


@pytest.mark.asyncio
async def test_loop_end_turn_sends_message(isolated_registry, monkeypatch):
    """A single end_turn response should produce one agent_message and stop."""
    session = FakeSession()
    sent = []

    async def ws_send(msg):
        sent.append(msg)

    # Mock _call_llm to return end_turn immediately
    mock_llm = AsyncMock(return_value=_llm_text_response("Hello, done."))
    monkeypatch.setattr(agent_loop, "_call_llm", mock_llm)
    # Ensure not stale
    agent_loop._session_generation[session.id] = 1

    messages = [{"role": "user", "content": [{"text": "hi"}]}]
    await agent_loop._run_loop(
        session, messages, "system", isolated_registry.get_tool_specs(),
        ws_send, gen=1, cancel_event=None,
    )

    # Should have an agent_message with the text
    msgs = [m for m in sent if m.get("type") == "agent_message"]
    assert any("Hello, done." in m.get("content", "") for m in msgs)


@pytest.mark.asyncio
async def test_loop_tool_use_then_end_turn(isolated_registry, monkeypatch):
    """Loop should execute a tool, feed result back, then end_turn."""
    session = FakeSession()
    sent = []

    async def ws_send(msg):
        sent.append(msg)

    # First call → tool_use, second call → end_turn
    responses = [
        _llm_tool_response("echo_tool", {"msg": "ping"}),
        _llm_text_response("Tool said pong, finishing."),
    ]
    call_count = {"n": 0}

    async def fake_call_llm(*args, **kwargs):
        r = responses[call_count["n"]]
        call_count["n"] += 1
        return r

    monkeypatch.setattr(agent_loop, "_call_llm", fake_call_llm)
    agent_loop._session_generation[session.id] = 1

    messages = [{"role": "user", "content": [{"text": "echo ping"}]}]
    await agent_loop._run_loop(
        session, messages, "system", isolated_registry.get_tool_specs(),
        ws_send, gen=1, cancel_event=None,
    )

    # LLM called twice (tool_use then end_turn)
    assert call_count["n"] == 2
    # Final message present
    final = [m for m in sent if m.get("type") == "agent_message"]
    assert any("finishing" in m.get("content", "") for m in final)


@pytest.mark.asyncio
async def test_loop_respects_cancel_flag(isolated_registry, monkeypatch):
    """If cancel flag is set, loop should not call the LLM."""
    session = FakeSession("cancelsess")
    sent = []

    async def ws_send(msg):
        sent.append(msg)

    mock_llm = AsyncMock(return_value=_llm_text_response("should not happen"))
    monkeypatch.setattr(agent_loop, "_call_llm", mock_llm)

    agent_loop._session_generation[session.id] = 1
    agent_loop._cancel_flags[session.id] = True  # cancelled before start

    messages = [{"role": "user", "content": [{"text": "hi"}]}]
    await agent_loop._run_loop(
        session, messages, "system", isolated_registry.get_tool_specs(),
        ws_send, gen=1, cancel_event=None,
    )

    mock_llm.assert_not_called()
    agent_loop._cancel_flags[session.id] = False  # cleanup


@pytest.mark.asyncio
async def test_loop_stale_generation_stops(isolated_registry, monkeypatch):
    """If generation is stale (newer gen exists), loop should stop early."""
    session = FakeSession("stalesess")
    sent = []

    async def ws_send(msg):
        sent.append(msg)

    mock_llm = AsyncMock(return_value=_llm_text_response("x"))
    monkeypatch.setattr(agent_loop, "_call_llm", mock_llm)

    # Current generation is 5, but we run with gen=1 → stale
    agent_loop._session_generation[session.id] = 5

    messages = [{"role": "user", "content": [{"text": "hi"}]}]
    await agent_loop._run_loop(
        session, messages, "system", isolated_registry.get_tool_specs(),
        ws_send, gen=1, cancel_event=None,
    )

    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(isolated_registry, monkeypatch):
    """Dispatching an unregistered tool returns a clear 'Unknown tool' message."""
    session = FakeSession()

    async def ws_send(msg):
        pass

    result = await agent_loop._do_execute_tool(
        session, "nonexistent_tool", {}, ws_send, None
    )
    assert "Unknown tool" in result


@pytest.mark.asyncio
async def test_select_model_off_by_default(monkeypatch):
    """Model routing is opt-in; default returns None (fast light model)."""
    from app.config import settings
    monkeypatch.setattr(settings, "enable_model_routing", False, raising=False)
    monkeypatch.setattr(settings, "bedrock_heavy_model", "us.anthropic.claude-opus-4-7", raising=False)

    msgs = [{"role": "user", "content": [{"text": "synthesize final comprehensive final report"}]}]
    assert agent_loop._select_model(msgs) is None


@pytest.mark.asyncio
async def test_select_model_routes_heavy_when_enabled(monkeypatch):
    """When routing enabled, narrow heavy signals in the LAST message pick Opus."""
    from app.config import settings
    monkeypatch.setattr(settings, "enable_model_routing", True, raising=False)
    monkeypatch.setattr(settings, "bedrock_heavy_model", "us.anthropic.claude-opus-4-7", raising=False)

    heavy_msgs = [{"role": "user", "content": [{"text": "Now synthesize final comprehensive final report"}]}]
    assert agent_loop._select_model(heavy_msgs) == "us.anthropic.claude-opus-4-7"

    light_msgs = [{"role": "user", "content": [{"text": "ls the directory"}]}]
    assert agent_loop._select_model(light_msgs) is None
