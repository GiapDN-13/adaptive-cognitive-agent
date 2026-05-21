import asyncio
import json
import logging
import uuid
from typing import Callable

from app.config import settings

logger = logging.getLogger(__name__)
from app.models.session import Session
from app.agent.tools import (
    TOOL_DEFINITIONS,
    requires_approval,
    truncate_output,
)
from app.agent.prompts import SYSTEM_PROMPT
from app.llm.client import BedrockClient, create_llm_client
from app.llm.streaming import stream_agent_response
from app.core.persistence import save_session_messages, update_session_title
from app.deps import _docker_manager

MAX_ITERATIONS = 10
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
_session_generation: dict[str, int] = {}


async def run_agent_loop(
    session: Session,
    user_message: str,
    ws_send: Callable,
):
    _cancel_flags[session.id] = False
    gen = _session_generation.get(session.id, 0) + 1
    _session_generation[session.id] = gen
    logger.info(f"[{session.id[:8]}] agent loop start, gen={gen}, msg={user_message[:50]}")

    session.messages.append({"role": "user", "content": user_message})
    await save_session_messages(session.id, session.messages)

    if len(session.messages) == 1:
        title = user_message[:60].strip()
        await update_session_title(session.id, title)

    messages = _build_messages(session)

    try:
        await _run_loop(session, messages, ws_send, gen)
    except asyncio.CancelledError:
        logger.info(f"[{session.id[:8]}] agent loop cancelled, gen={gen}")
    except Exception as e:
        logger.exception(f"[{session.id[:8]}] agent loop error, gen={gen}")
        if _session_generation.get(session.id) != gen:
            return
        error_msg = f"Agent error: {type(e).__name__}: {str(e)[:200]}"
        await ws_send({"type": "error", "message": error_msg, "recoverable": True})
        session.messages.append({"role": "assistant", "content": f"[Error] {error_msg}"})
        await save_session_messages(session.id, session.messages)


async def _run_loop(
    session: Session,
    messages: list[dict],
    ws_send: Callable,
    gen: int = 0,
):

    def _stale():
        return _session_generation.get(session.id) != gen

    search_count = 0
    max_searches = 3

    for iteration in range(MAX_ITERATIONS):
        if _cancel_flags.get(session.id) or _stale():
            break

        await ws_send({"type": "agent_status", "tool": "thinking", "detail": f"iteration {iteration + 1}"})
        response = await _call_llm(messages, ws_send=ws_send)

        if _stale():
            break

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

                tool_desc = tool_input.get("query") or tool_input.get("command") or tool_input.get("path") or ""
                await ws_send({
                    "type": "agent_status",
                    "tool": tool_name,
                    "detail": str(tool_desc)[:100],
                })

                if tool_name == "web_search":
                    search_count += 1
                    if search_count > max_searches:
                        result = "Search limit reached. Please synthesize your findings and respond."
                    else:
                        result = await _execute_tool(
                            session, tool_name, tool_input, ws_send
                        )
                else:
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
                results = list(ddgs.text(query, max_results=3))
            if not results:
                return "No results found."
            formatted = []
            for r in results:
                body = r['body'][:200]
                formatted.append(f"**{r['title']}**\n{body}\nURL: {r['href']}")
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
        if not approval.get("approved"):
            return "Plan rejected by user."

        results = await _execute_plan_steps(session, plan_id, steps, ws_send)
        return results

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
    try:
        if ws_send:
            return await asyncio.wait_for(
                stream_agent_response(
                    client=client,
                    messages=messages,
                    system=SYSTEM_PROMPT,
                    tools=TOOL_DEFINITIONS,
                    ws_send=ws_send,
                ),
                timeout=120,
            )
        return await asyncio.wait_for(
            client.converse(
                messages=messages,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
            ),
            timeout=120,
        )
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        raise RuntimeError("LLM response timeout (120s)")


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
    _session_generation[session_id] = _session_generation.get(session_id, 0) + 1
    for req_id, event in list(_pending_approvals.items()):
        _approval_results[req_id] = {"approved": False}
        event.set()
    for req_id, event in list(_pending_responses.items()):
        _response_results[req_id] = "(cancelled)"
        event.set()


async def _execute_plan_steps(
    session: Session,
    plan_id: str,
    steps: list[dict],
    ws_send: Callable,
) -> str:
    results = []

    for step in steps:
        step_id = step["id"]
        command = step.get("command")
        description = step.get("description", "")

        if _cancel_flags.get(session.id):
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "failed"})
            results.append(f"Step {step_id}: CANCELLED")
            break

        await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "running"})

        if not command or command in ("write_file", "read_file", "web_search", "think", "ask_user"):
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "done"})
            results.append(f"Step {step_id} ({description}): skipped (no executable command)")
            continue

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
                await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "failed"})
                results.append(f"Step {step_id}: REJECTED by user")
                break
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
        truncated, _ = truncate_output(full_output)

        if "error" in full_output.lower() or "traceback" in full_output.lower():
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "failed"})
            results.append(f"Step {step_id} ({description}):\n$ {command}\n[FAILED]\n{truncated}")
            results.append("Plan paused due to error. Agent will analyze and decide next action.")
            break
        else:
            await ws_send({"type": "step_progress", "plan_id": plan_id, "step_id": step_id, "status": "done"})
            results.append(f"Step {step_id} ({description}):\n$ {command}\n{truncated}")

    summary = "\n\n---\n\n".join(results)
    completed = sum(1 for r in results if "[FAILED]" not in r and "CANCELLED" not in r and "REJECTED" not in r)
    total = len(steps)

    return f"Plan execution: {completed}/{total} steps completed.\n\n{summary}"
