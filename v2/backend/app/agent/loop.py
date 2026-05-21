import asyncio
import json
import uuid
from typing import Callable

from app.config import settings
from app.models.session import Session
from app.agent.tools import (
    TOOL_DEFINITIONS,
    requires_approval,
    truncate_output,
)
from app.agent.prompts import SYSTEM_PROMPT
from app.llm.client import BedrockClient, create_llm_client
from app.llm.streaming import stream_agent_response
from app.core.persistence import save_session_messages
from app.deps import _docker_manager

MAX_ITERATIONS = 15
_llm_client: BedrockClient | None = None


def _get_llm() -> BedrockClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = create_llm_client()
    return _llm_client

# Pending approvals/responses keyed by request_id (not session_id)
_pending_approvals: dict[str, asyncio.Event] = {}
_approval_results: dict[str, dict] = {}
_pending_responses: dict[str, asyncio.Event] = {}
_response_results: dict[str, str] = {}
_cancel_flags: dict[str, bool] = {}
_session_pending_ids: dict[str, list[str]] = {}


async def run_agent_loop(
    session: Session,
    user_message: str,
    ws_send: Callable,
):
    _cancel_flags[session.id] = False

    session.messages.append({"role": "user", "content": user_message})
    await save_session_messages(session.id, session.messages)

    messages = _build_messages(session)

    try:
        await _run_loop(session, messages, ws_send)
    except Exception as e:
        error_msg = f"Agent error: {type(e).__name__}: {str(e)[:200]}"
        await ws_send({"type": "error", "message": error_msg, "recoverable": True})
        session.messages.append({"role": "assistant", "content": f"[Error] {error_msg}"})
        await save_session_messages(session.id, session.messages)


async def _run_loop(
    session: Session,
    messages: list[dict],
    ws_send: Callable,
):

    for iteration in range(MAX_ITERATIONS):
        if _cancel_flags.get(session.id):
            await ws_send({"type": "agent_message", "content": "Da huy thao tac.", "metadata": None})
            break

        response = await _call_llm(messages, ws_send=ws_send)

        stop_reason = response.get("stopReason", "")
        content_blocks = response.get("output", {}).get("message", {}).get("content", [])

        messages.append({"role": "assistant", "content": content_blocks})

        if stop_reason == "end_turn":
            text = _extract_text(content_blocks)
            if text:
                session.messages.append({"role": "assistant", "content": text})
                await save_session_messages(session.id, session.messages)
                await ws_send({"type": "agent_message", "content": text, "metadata": {"iterations": iteration + 1, "streamed": True}})
            break

        if stop_reason == "tool_use":
            tool_results = []
            for block in content_blocks:
                if "toolUse" not in block:
                    continue

                tool_use = block["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                tool_id = tool_use["toolUseId"]

                result = await _execute_tool(
                    session, tool_name, tool_input, ws_send
                )

                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_id,
                        "content": [{"text": result}],
                    }
                })

            messages.append({"role": "user", "content": tool_results})

        else:
            text = _extract_text(content_blocks)
            if text:
                session.messages.append({"role": "assistant", "content": text})
                await ws_send({"type": "agent_message", "content": text, "metadata": None})
            break


async def _execute_tool(
    session: Session,
    tool_name: str,
    tool_input: dict,
    ws_send: Callable,
) -> str:
    if tool_name == "think":
        return f"[Thought recorded: {tool_input.get('thought', '')[:100]}...]"

    if tool_name == "web_search":
        from duckduckgo_search import DDGS
        query = tool_input.get("query", "")
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
            if not results:
                return "No results found."
            formatted = []
            for r in results:
                formatted.append(f"**{r['title']}**\n{r['body']}\nURL: {r['href']}")
            return "\n\n---\n\n".join(formatted)
        except Exception as e:
            return f"Search error: {e}"

    if tool_name == "ask_user":
        question = tool_input.get("question", "")
        options = tool_input.get("options")
        await ws_send({
            "type": "agent_question",
            "question": question,
            "options": options,
        })
        response = await _wait_for_user_response(session.id)
        return f"User responded: {response}"

    if tool_name == "propose_plan":
        plan_id = uuid.uuid4().hex[:8]
        steps = tool_input.get("steps", [])
        for i, step in enumerate(steps):
            step["id"] = f"step_{i}"
        await ws_send({
            "type": "plan_proposal",
            "plan_id": plan_id,
            "title": tool_input.get("title", "Plan"),
            "steps": steps,
        })
        approval = await _wait_for_approval(plan_id)
        if approval.get("approved"):
            return "Plan approved. Proceeding with execution."
        return "Plan rejected by user."

    if tool_name == "shell_exec":
        command = tool_input.get("command", "")
        if requires_approval(command):
            request_id = uuid.uuid4().hex[:8]
            await ws_send({
                "type": "approval_request",
                "request_id": request_id,
                "action": "shell_exec",
                "command": command,
                "risk_level": "medium",
            })
            approval = await _wait_for_approval(request_id)
            if not approval.get("approved"):
                return "Command rejected by user."
            command = approval.get("modified_command") or command

        exec_id = uuid.uuid4().hex[:8]
        output_parts = []

        async for chunk in _docker_manager.exec_command(session.container_id, command):
            stream_type, content = chunk.split(":", 1)
            output_parts.append(content)
            await ws_send({
                "type": "terminal_output",
                "exec_id": exec_id,
                "content": content,
                "stream": stream_type,
                "done": False,
            })

        await ws_send({
            "type": "terminal_output",
            "exec_id": exec_id,
            "content": "",
            "stream": "stdout",
            "done": True,
        })

        full_output = "".join(output_parts)
        truncated, was_truncated = truncate_output(full_output)

        if was_truncated:
            output_path = f"/tmp/output_{exec_id}.txt"
            await _docker_manager.exec_command_simple(
                session.container_id,
                f"cat << 'HEREDOC_EOF' > {output_path}\n{full_output}\nHEREDOC_EOF"
            )
            await ws_send({
                "type": "file_ready",
                "path": output_path,
                "download_url": f"/api/sessions/{session.id}/files{output_path}",
                "size_bytes": len(full_output.encode()),
            })
            return f"{truncated}\n\n[Full output ({len(full_output.splitlines())} lines) saved to {output_path}]"

        return full_output or "(no output)"

    if tool_name == "write_file":
        path = tool_input.get("path", "/workspace/file.txt")
        content = tool_input.get("content", "")
        escaped_content = content.replace("'", "'\\''")
        await _docker_manager.exec_command_simple(
            session.container_id,
            f"mkdir -p $(dirname '{path}') && printf '%s' '{escaped_content}' > '{path}'"
        )
        return f"File written: {path} ({len(content)} bytes)"

    if tool_name == "read_file":
        path = tool_input.get("path", "")
        max_lines = tool_input.get("max_lines", 200)
        _, output = await _docker_manager.exec_command_simple(
            session.container_id,
            f"head -n {max_lines} '{path}'"
        )
        return output or "(empty file)"

    return f"Unknown tool: {tool_name}"


def _build_messages(session: Session) -> list[dict]:
    messages = []
    for msg in session.messages[-20:]:
        role = msg["role"]
        content = msg["content"]
        if isinstance(content, str):
            messages.append({"role": role, "content": [{"text": content}]})
        else:
            messages.append({"role": role, "content": content})
    return messages


def _extract_text(content_blocks: list) -> str:
    text = ""
    for block in content_blocks:
        if "text" in block:
            text += block["text"]
    return text


async def _call_llm(messages: list[dict], ws_send: Callable = None) -> dict:
    client = _get_llm()
    if ws_send:
        return await stream_agent_response(
            client=client,
            messages=messages,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            ws_send=ws_send,
        )
    return await client.converse(
        messages=messages,
        system=SYSTEM_PROMPT,
        tools=TOOL_DEFINITIONS,
    )


async def _wait_for_approval(request_id: str, timeout: int = 300) -> dict:
    event = asyncio.Event()
    _pending_approvals[request_id] = event
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return _approval_results.pop(request_id, {"approved": False})
    except asyncio.TimeoutError:
        return {"approved": False}
    finally:
        _pending_approvals.pop(request_id, None)


async def _wait_for_user_response(session_id: str, timeout: int = 300) -> str:
    event = asyncio.Event()
    _pending_responses[session_id] = event
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return _response_results.pop(session_id, "")
    except asyncio.TimeoutError:
        return "(no response - timeout)"
    finally:
        _pending_responses.pop(session_id, None)


async def handle_approval(session_id: str, message: dict):
    request_id = message.get("request_id", session_id)
    _approval_results[request_id] = message
    event = _pending_approvals.get(request_id)
    if event:
        event.set()


async def handle_user_response(session_id: str, content: str):
    _response_results[session_id] = content
    event = _pending_responses.get(session_id)
    if event:
        event.set()


async def handle_cancel(session_id: str):
    _cancel_flags[session_id] = True
    for req_id, event in list(_pending_approvals.items()):
        _approval_results[req_id] = {"approved": False}
        event.set()
    for req_id, event in list(_pending_responses.items()):
        _response_results[req_id] = "(cancelled)"
        event.set()
