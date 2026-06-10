"""
Built-in tool handlers — extracted from loop.py's _do_execute_tool().

Each handler follows the uniform signature:
    async def handler(session, tool_input, ws_send, cancel_event) -> str

Registration function at the bottom wires all handlers + schemas into ToolRegistry.
"""

import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------

async def handle_shell_exec(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.tools import requires_approval, truncate_output
    from app.deps import _docker_manager

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
        from app.agent.loop import _wait_for_approval
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


async def handle_write_file(session, tool_input, ws_send, cancel_event) -> str:
    from app.deps import _docker_manager

    path = tool_input.get("path", "/workspace/file.txt")
    content = tool_input.get("content", "")
    escaped_content = content.replace("'", "'\\''")
    await _docker_manager.exec_command_simple(
        session.container_id,
        f"mkdir -p $(dirname '{path}') && printf '%s' '{escaped_content}' > '{path}'"
    )
    return f"File written: {path} ({len(content)} bytes)"


async def handle_read_file(session, tool_input, ws_send, cancel_event) -> str:
    from app.deps import _docker_manager

    path = tool_input.get("path", "")
    max_lines = tool_input.get("max_lines", 200)
    _, output = await _docker_manager.exec_command_simple(
        session.container_id,
        f"head -n {max_lines} '{path}'"
    )
    return output or "(empty file)"


async def handle_web_search(session, tool_input, ws_send, cancel_event) -> str:
    import urllib.parse

    import requests
    from lxml import html

    query = tool_input.get("query", "")
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        # Run blocking requests.post in a thread so the event loop isn't blocked
        resp = await asyncio.to_thread(
            requests.post, url, headers=headers, data={'q': query}, timeout=10
        )
        tree = html.fromstring(resp.text)

        results = []          # text blocks for LLM context
        structured = []       # structured results for UI transparency
        for result in tree.xpath('//div[contains(@class, "result ")]'):
            title_elem = result.xpath('.//h2[@class="result__title"]/a')
            snippet_elem = result.xpath('.//a[@class="result__snippet"]')

            if not title_elem or not snippet_elem:
                continue

            title = "".join(title_elem[0].itertext()).strip()
            link = title_elem[0].get('href')
            snippet = "".join(snippet_elem[0].itertext()).strip()

            if link and link.startswith('//duckduckgo.com/l/?uddg='):
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                link = qs.get('uddg', [link])[0]

            results.append(f"**{title}**\n{snippet}\nURL: {link}")
            structured.append({"title": title, "url": link, "snippet": snippet[:200]})
            if len(results) >= 3:
                break

        # Emit retrieval transparency event — UI shows what was searched + found
        await ws_send({
            "type": "agent_retrieval",
            "query": query,
            "results": structured,
            "count": len(structured),
        })

        if not results:
            return "No results found."
        return "\n\n---\n\n".join(results)
    except Exception as e:
        await ws_send({"type": "agent_retrieval", "query": query, "results": [], "count": 0, "error": str(e)})
        return f"Search error: {e}"


async def handle_think(session, tool_input, ws_send, cancel_event) -> str:
    thought = tool_input.get("thought", "")
    # Stream thinking content to frontend for real-time display
    await ws_send({
        "type": "agent_thinking",
        "content": thought,
        "done": False,
    })
    await ws_send({
        "type": "agent_thinking",
        "content": "",
        "done": True,
    })
    return "[Thought recorded]"


async def handle_verify_work(session, tool_input, ws_send, cancel_event) -> str:
    """Run a verification test against success criteria. Returns structured pass/fail."""
    from app.agent.tools import truncate_output
    from app.deps import _docker_manager

    criterion = tool_input.get("criterion", "")
    test_command = tool_input.get("test_command", "")
    expected = tool_input.get("expected", "")

    await ws_send({
        "type": "agent_status",
        "tool": "verify_work",
        "detail": f"Verifying: {criterion[:60]}",
    })

    if not test_command:
        return (
            f"VERIFY [{criterion}]: NO TEST COMMAND PROVIDED. "
            f"You must provide a concrete test_command (shell command that proves the criterion)."
        )

    # Run the test command in sandbox
    exec_id = uuid.uuid4().hex[:8]
    output_parts = []
    try:
        async for chunk in _docker_manager.exec_command(session.container_id, test_command):
            stream_type, content = chunk.split(":", 1)
            output_parts.append(content)
            await ws_send({
                "type": "terminal_output",
                "exec_id": exec_id,
                "content": content,
                "stream": stream_type,
                "done": False,
            })
        await ws_send({"type": "terminal_output", "exec_id": exec_id, "content": "", "stream": "stdout", "done": True})
    except Exception as e:
        return f"VERIFY [{criterion}]: ERROR running test — {e}"

    full_output = "".join(output_parts)
    truncated, _ = truncate_output(full_output)

    # Heuristic auto-assessment
    out_lower = full_output.lower()
    has_error = any(m in out_lower for m in ["error", "traceback", "exception", "failed", "assertionerror"])
    expected_met = (expected.lower() in out_lower) if expected else None

    if expected:
        verdict = "PASS" if expected_met and not has_error else "FAIL"
        detail = f"Expected '{expected}' {'FOUND' if expected_met else 'NOT FOUND'}; errors {'present' if has_error else 'none'}"
    else:
        verdict = "FAIL" if has_error else "LIKELY_PASS"
        detail = f"Errors {'detected' if has_error else 'none detected'} (no explicit expected value given)"

    return (
        f"VERIFY [{criterion}]: {verdict}\n"
        f"Assessment: {detail}\n"
        f"--- Test Output ---\n{truncated}\n"
        f"--- End Output ---\n"
        f"NOTE: Review the output yourself. If this criterion is NOT genuinely met, fix the issue and re-verify. "
        f"Do NOT report completion until all criteria genuinely PASS."
    )


async def handle_verify_webapp(session, tool_input, ws_send, cancel_event) -> str:
    """Prove a running web app is genuinely USABLE by issuing real HTTP requests
    against localhost:8080 INSIDE the container and asserting on the RESPONSE BODY
    (not just status 200). Ported from Nexus dev_server._wait_for_ready pattern.

    A blank-200 page or a server that returns errors on real user input will FAIL,
    which is exactly the "has a UI but doesn't work" failure mode we must catch.
    """
    import json as _json
    from app.agent.tools import truncate_output
    from app.deps import _docker_manager

    base_url = tool_input.get("app_url", "http://localhost:8080").rstrip("/")
    journey = tool_input.get("journey", [])
    if isinstance(journey, str):
        try:
            journey = _json.loads(journey)
        except Exception:
            return "VERIFY_WEBAPP: 'journey' must be a JSON array of steps. Got an unparseable string."
    if not isinstance(journey, list) or not journey:
        return (
            "VERIFY_WEBAPP: provide a non-empty 'journey' (list of steps). Each step: "
            "{name, method?, path?, body?, assert_status?, assert_contains?, assert_not_contains?}. "
            "Include at least one real user action and assert on the RESPONSE BODY, not just status."
        )

    await ws_send({"type": "agent_status", "tool": "verify_webapp", "detail": f"E2E {len(journey)} steps @ {base_url}"})

    def _shq(s: str) -> str:
        # safe single-quote for shell
        return "'" + str(s).replace("'", "'\\''") + "'"

    results = []
    all_pass = True
    for i, step in enumerate(journey):
        if not isinstance(step, dict):
            results.append(f"[step {i}] SKIP — not an object")
            all_pass = False
            continue
        name = step.get("name", f"step {i}")
        method = (step.get("method") or "GET").upper()
        path = step.get("path", "/")
        url = base_url + ("" if path.startswith("/") else "/") + path
        body = step.get("body")

        # Build curl: print body, then a marker + HTTP status on its own line.
        curl = f"curl -s -m 15 -X {method} {_shq(url)}"
        if body is not None:
            payload = body if isinstance(body, str) else _json.dumps(body, ensure_ascii=False)
            curl += f" -H 'Content-Type: application/json' -d {_shq(payload)}"
        curl += " -w '\\n__HTTP_STATUS__:%{http_code}'"

        try:
            output_parts = []
            async for chunk in _docker_manager.exec_command(session.container_id, curl):
                _, content = chunk.split(":", 1)
                output_parts.append(content)
            raw = "".join(output_parts)
        except Exception as e:
            results.append(f"[{name}] FAIL — curl error: {e}")
            all_pass = False
            continue

        # Split body vs status marker
        status_code = ""
        body_text = raw
        if "__HTTP_STATUS__:" in raw:
            body_text, _, status_part = raw.rpartition("__HTTP_STATUS__:")
            status_code = status_part.strip()

        step_pass = True
        reasons = []

        # Server not listening / no HTTP response
        if status_code in ("", "000"):
            step_pass = False
            reasons.append("app not responding (status 000 — server not listening?)")

        exp_status = step.get("assert_status")
        if exp_status is not None and str(exp_status) != status_code:
            step_pass = False
            reasons.append(f"status {status_code} != expected {exp_status}")

        ac = step.get("assert_contains")
        if ac:
            for needle in ([ac] if isinstance(ac, str) else ac):
                if needle not in body_text:
                    step_pass = False
                    reasons.append(f"body missing expected text: {needle!r}")

        anc = step.get("assert_not_contains")
        if anc:
            for needle in ([anc] if isinstance(anc, str) else anc):
                if needle in body_text:
                    step_pass = False
                    reasons.append(f"body contains forbidden text: {needle!r}")

        all_pass = all_pass and step_pass
        body_preview = body_text.strip()[:300].replace("\n", " ")
        verdict = "PASS" if step_pass else "FAIL"
        detail = "ok" if step_pass else "; ".join(reasons)
        results.append(f"[{name}] {verdict} (HTTP {status_code or 'n/a'}) — {detail}\n    body: {body_preview}")

    summary = "\n".join(results)
    overall = "PASS" if all_pass else "FAIL"
    return (
        f"VERIFY_WEBAPP: {overall} ({sum('] PASS' in r for r in results)}/{len(journey)} steps passed)\n"
        f"{summary}\n"
        f"NOTE: This asserts on the actual RESPONSE BODY + user journey. "
        f"If FAIL, the app is NOT genuinely usable yet — fix the real defect (use systematic-debugging skill) and re-verify. "
        f"Do NOT report the app as done until verify_webapp PASSES."
    )


async def handle_spawn_critic(session, tool_input, ws_send, cancel_event) -> str:
    """Spawn a dedicated Critic subagent that adversarially reviews a decision/design/claim.
    Works for ANY domain — the critic auto-detects the domain and researches to verify."""
    from app.agent.loop import _run_loop, _session_generation, _extract_text
    from app.agent.prompts import build_critic_prompt
    from app.agent.tool_registry import tool_registry

    subject = tool_input.get("subject", "")        # what to critique
    context = tool_input.get("context", "")        # requirement / constraints / numbers
    claims = tool_input.get("claims", "")          # specific claims to verify

    await ws_send({
        "type": "agent_message",
        "content": f"🔬 **Critic Agent** — phản biện: {subject[:80]}",
        "metadata": None,
    })

    critic_task = (
        f"## Đối tượng phản biện\n{subject}\n\n"
        f"## Bối cảnh / Yêu cầu (con số cụ thể)\n{context}\n\n"
    )
    if claims:
        critic_task += f"## Các claim cần kiểm chứng\n{claims}\n\n"
    critic_task += (
        "Hãy phản biện nghiêm khắc. Với MỖI claim/lựa chọn: research (web_search) để verify, "
        "đưa verdict VALID / QUESTIONABLE / WRONG kèm bằng chứng và đề xuất sửa. "
        "Kết thúc bằng tổng kết: những gì cần thay đổi TRƯỚC khi triển khai."
    )

    critic_prompt = build_critic_prompt()
    critic_tools = tool_registry.get_tool_specs(is_subagent=True)
    sub_messages = [{"role": "user", "content": [{"text": critic_task}]}]

    await _run_loop(
        session=session,
        messages=sub_messages,
        system_prompt=critic_prompt,
        tools_list=critic_tools,
        ws_send=ws_send,
        gen=_session_generation.get(session.id, 0),
        cancel_event=cancel_event,
        is_subagent=True,
    )

    verdict = "(no critique)"
    if sub_messages and sub_messages[-1].get("role") == "assistant":
        verdict = _extract_text(sub_messages[-1].get("content", []))

    # Emit structured critique event for UI
    await ws_send({
        "type": "agent_critique",
        "finding": f"Critic review: {subject[:100]}",
        "resolved": False,
    })
    await ws_send({
        "type": "agent_message",
        "content": f"🔬 **Critic hoàn thành**. Áp dụng phản biện vào thiết kế trước khi build.",
        "metadata": None,
    })
    return f"CRITIC REVIEW of '{subject}':\n{verdict}\n\n[Hãy SỬA thiết kế theo phản biện trên TRƯỚC khi tiếp tục build.]"


async def handle_ask_user(session, tool_input, ws_send, cancel_event) -> str:
    question = tool_input.get("question", "")
    options = tool_input.get("options")
    await ws_send({
        "type": "agent_question",
        "question": question,
        "options": options,
    })
    from app.agent.loop import _wait_for_user_response
    response = await _wait_for_user_response(session.id)
    return f"User responded: {response}"


async def handle_propose_plan(session, tool_input, ws_send, cancel_event) -> str:
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
    from app.agent.loop import _execute_plan_steps, _wait_for_approval
    approval = await _wait_for_approval(plan_id)
    if not approval.get("approved"):
        return "Plan rejected by user."

    results = await _execute_plan_steps(session, plan_id, steps, ws_send)
    return results


async def handle_load_skill(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.skill_manager import skill_manager
    skill_id = tool_input.get("skill_id", "")
    return skill_manager.load_skill_content(skill_id)


async def handle_load_agent(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.agent_manager import agent_manager
    agent_id = tool_input.get("agent_id", "")
    return agent_manager.load_agent_content(agent_id)


async def handle_spawn_subagent(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.loop import _run_loop, _session_generation
    from app.agent.prompts import build_system_prompt
    from app.agent.tool_registry import tool_registry

    role_name = tool_input.get("role_name", "Subagent")
    system_prompt = tool_input.get("system_prompt", "")
    task = tool_input.get("task", "")

    await ws_send({"type": "agent_message", "content": f"\U0001f528 **Khởi tạo Sub-Agent**: `{role_name}`\n*Nhiệm vụ*: {task}", "metadata": None})

    sub_system_prompt = build_system_prompt(is_subagent=True, custom_system_prompt=system_prompt)
    sub_tools = tool_registry.get_tool_specs(is_subagent=True)

    sub_messages = [
        {"role": "user", "content": [{"text": task}]}
    ]

    await _run_loop(
        session=session,
        messages=sub_messages,
        system_prompt=sub_system_prompt,
        tools_list=sub_tools,
        ws_send=ws_send,
        gen=_session_generation.get(session.id, 0),
        cancel_event=cancel_event,
        is_subagent=True,
    )

    final_answer = "(No response)"
    if sub_messages and sub_messages[-1].get("role") == "assistant":
        from app.agent.loop import _extract_text
        final_answer = _extract_text(sub_messages[-1].get("content", []))

    await ws_send({"type": "agent_message", "content": f"✅ **Sub-Agent `{role_name}` Hoàn thành**.", "metadata": None})
    return f"Sub-Agent '{role_name}' completed. Final response:\n{final_answer}"


def _pipeline_checkpoint_path(session_id: str, pipeline_name: str):
    import re
    from pathlib import Path
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", pipeline_name)[:40]
    d = Path("./data/checkpoints")
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{session_id}_{safe}.json"


def _load_pipeline_checkpoint(session_id: str, pipeline_name: str) -> dict:
    import json
    path = _pipeline_checkpoint_path(session_id, pipeline_name)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_pipeline_checkpoint(session_id: str, pipeline_name: str, state: dict):
    import json
    path = _pipeline_checkpoint_path(session_id, pipeline_name)
    try:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Checkpoint save failed: {e}")


def _clear_pipeline_checkpoint(session_id: str, pipeline_name: str):
    path = _pipeline_checkpoint_path(session_id, pipeline_name)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


async def handle_execute_pipeline(session, tool_input, ws_send, cancel_event) -> str:
    """Execute a structured pipeline of stages, each as an isolated subagent.

    Supports checkpoint/resume: progress is saved after each stage. If the same
    pipeline is re-run after a crash, completed stages are skipped.
    """
    from app.agent.loop import _cancel_flags, _extract_text, _run_loop, _session_generation
    from app.agent.prompts import build_system_prompt
    from app.agent.tool_registry import tool_registry

    pipeline_name = tool_input.get("name", "Pipeline")
    stages = tool_input.get("stages", [])
    shared_context = tool_input.get("context", "")

    if not stages:
        return "Error: Pipeline must have at least one stage."

    # Load checkpoint — resume from where we left off
    checkpoint = _load_pipeline_checkpoint(session.id, pipeline_name)
    completed_stages = checkpoint.get("completed", {})  # {stage_index: result}
    resumed = len(completed_stages) > 0

    intro = f"🔄 **Pipeline `{pipeline_name}`** — {len(stages)} stages"
    if resumed:
        intro += f" (resume: bỏ qua {len(completed_stages)} stage đã hoàn thành)"
    await ws_send({"type": "agent_message", "content": intro, "metadata": None})

    results = []
    accumulated_findings = ""
    # Restore prior results into context
    for idx_str in sorted(completed_stages.keys(), key=lambda x: int(x)):
        prior = completed_stages[idx_str]
        results.append(prior["result_block"])
        accumulated_findings += f"\n### {prior['name']}\n{prior['summary']}\n"

    for i, stage in enumerate(stages):
        # Skip stages already completed in a prior run (checkpoint resume)
        if str(i) in completed_stages:
            continue

        if _cancel_flags.get(session.id):
            results.append(f"Stage {i+1}: CANCELLED")
            break

        stage_name = stage.get("name", f"Stage {i+1}")
        stage_goal = stage.get("goal", "")
        stage_tools_hint = stage.get("tools_hint", "")

        await ws_send({
            "type": "agent_status",
            "tool": "pipeline",
            "detail": f"[{i+1}/{len(stages)}] {stage_name}",
        })
        await ws_send({
            "type": "agent_message",
            "content": f"▶️ **Stage {i+1}/{len(stages)}**: `{stage_name}`",
            "metadata": None,
        })

        stage_prompt = (
            f"You are executing stage '{stage_name}' of pipeline '{pipeline_name}'.\n\n"
            f"## Stage Goal\n{stage_goal}\n\n"
            f"## Shared Context\n{shared_context}\n\n"
        )
        if accumulated_findings:
            stage_prompt += f"## Findings from Previous Stages\n{accumulated_findings}\n\n"
        if stage_tools_hint:
            stage_prompt += f"## Tools Hint\n{stage_tools_hint}\n\n"
        stage_prompt += (
            "Execute this stage thoroughly. Return your findings as structured text. "
            "Be concise but comprehensive."
        )

        sub_system_prompt = build_system_prompt(is_subagent=True, custom_system_prompt=f"Pipeline stage executor: {stage_name}")
        sub_tools = tool_registry.get_tool_specs(is_subagent=True)
        sub_messages = [{"role": "user", "content": [{"text": stage_prompt}]}]

        try:
            await _run_loop(
                session=session,
                messages=sub_messages,
                system_prompt=sub_system_prompt,
                tools_list=sub_tools,
                ws_send=ws_send,
                gen=_session_generation.get(session.id, 0),
                cancel_event=cancel_event,
                is_subagent=True,
            )

            stage_result = "(No output)"
            if sub_messages and sub_messages[-1].get("role") == "assistant":
                stage_result = _extract_text(sub_messages[-1].get("content", []))

            result_block = f"## Stage {i+1}: {stage_name}\n{stage_result}"
            results.append(result_block)
            accumulated_findings += f"\n### {stage_name}\n{stage_result[:2000]}\n"

            # Save checkpoint after successful stage
            completed_stages[str(i)] = {
                "name": stage_name,
                "result_block": result_block,
                "summary": stage_result[:2000],
            }
            _save_pipeline_checkpoint(session.id, pipeline_name, {"completed": completed_stages})

            await ws_send({
                "type": "agent_message",
                "content": f"✅ **Stage `{stage_name}` complete**",
                "metadata": None,
            })

        except Exception as e:
            error_msg = f"Stage '{stage_name}' failed: {e}"
            results.append(f"## Stage {i+1}: {stage_name}\n❌ {error_msg}")
            logger.error(f"Pipeline stage error: {error_msg}")

    # Pipeline fully done → clear checkpoint
    all_done = len(completed_stages) == len(stages)
    if all_done:
        _clear_pipeline_checkpoint(session.id, pipeline_name)

    summary = f"Pipeline '{pipeline_name}' completed: {len(completed_stages)}/{len(stages)} stages.\n\n"
    summary += "\n\n---\n\n".join(results)
    return summary


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_all_builtins(registry) -> None:
    """Register all built-in tools into the given ToolRegistry."""
    from app.agent.tools import TOOL_DEFINITIONS

    handler_map = {
        "shell_exec": handle_shell_exec,
        "write_file": handle_write_file,
        "read_file": handle_read_file,
        "web_search": handle_web_search,
        "think": handle_think,
        "ask_user": handle_ask_user,
        "propose_plan": handle_propose_plan,
        "load_skill": handle_load_skill,
        "load_agent": handle_load_agent,
    }

    for tool_def in TOOL_DEFINITIONS:
        spec = tool_def["toolSpec"]
        name = spec["name"]
        handler = handler_map.get(name)
        if handler:
            registry.register(name, spec, handler, builtin=True, category="action")

    # execute_pipeline — structured multi-stage execution
    pipeline_spec = {
        "name": "execute_pipeline",
        "description": "Execute a structured pipeline of stages. Each stage runs as an isolated subagent with its own context. Use for complex multi-phase tasks (audit, research, development). Previous stage findings automatically flow to next stage.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Pipeline name (e.g. 'API Security Audit')"},
                    "context": {"type": "string", "description": "Shared context for all stages (target info, credentials, scope)"},
                    "stages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Stage name (e.g. 'Reconnaissance')"},
                                "goal": {"type": "string", "description": "What this stage must accomplish"},
                                "tools_hint": {"type": "string", "description": "Hint about which tools to use or create"},
                            },
                            "required": ["name", "goal"],
                        },
                        "description": "Ordered list of stages to execute",
                    },
                },
                "required": ["name", "stages"],
            }
        },
    }
    registry.register("execute_pipeline", pipeline_spec, handle_execute_pipeline, builtin=True, category="meta")

    # verify_work — self-verification against success criteria
    verify_spec = {
        "name": "verify_work",
        "description": "Verify that your work meets a specific success criterion by running an actual test. Use this AFTER building something and BEFORE reporting completion. Run it for EACH criterion in your Definition of Done. If a criterion fails, fix the issue and verify again.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string", "description": "The success criterion being checked (e.g. 'RAG returns no-info for out-of-scope questions')"},
                    "test_command": {"type": "string", "description": "A concrete shell command that tests this criterion (e.g. 'cd /workspace && python3 test_oos.py')"},
                    "expected": {"type": "string", "description": "Optional: expected substring in output that proves PASS (e.g. 'không có thông tin')"},
                },
                "required": ["criterion", "test_command"],
            }
        },
    }
    registry.register("verify_work", verify_spec, handle_verify_work, builtin=True, category="meta")

    # verify_webapp — prove a running web app is genuinely usable (real HTTP, assert body)
    verify_webapp_spec = {
        "name": "verify_webapp",
        "description": (
            "Prove a web app you built is GENUINELY USABLE — not just returning HTTP 200. "
            "Issues real HTTP requests to the running app (default http://localhost:8080) INSIDE the "
            "container and asserts on the RESPONSE BODY + a real user journey. MANDATORY after building "
            "any web app/API/chatbot UI, BEFORE reporting it done. A blank-200 page or a server that errors "
            "on real input will FAIL. Design the journey to exercise real user actions: e.g. GET / must "
            "contain the app's UI markup; POST /chat with an in-scope question must return a grounded answer "
            "containing a fact from the data; an out-of-scope question must return a refusal and NOT a fabricated fact."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "app_url": {"type": "string", "description": "Base URL of the running app (default http://localhost:8080)"},
                    "journey": {
                        "type": "array",
                        "description": "Ordered list of user-journey steps to assert.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Human label for this step"},
                                "method": {"type": "string", "description": "HTTP method (GET/POST/...). Default GET"},
                                "path": {"type": "string", "description": "Path, e.g. '/' or '/chat'. Default '/'"},
                                "body": {"description": "Optional request body (object → sent as JSON, or raw string)"},
                                "assert_status": {"type": "integer", "description": "Optional expected HTTP status code"},
                                "assert_contains": {"description": "String or list of strings that MUST appear in the response body"},
                                "assert_not_contains": {"description": "String or list of strings that must NOT appear (e.g. a hallucinated fact)"},
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": ["journey"],
            }
        },
    }
    registry.register("verify_webapp", verify_webapp_spec, handle_verify_webapp, builtin=True, category="meta")

    # spawn_critic — dedicated adversarial reviewer (any domain)
    critic_spec = {
        "name": "spawn_critic",
        "description": "Spawn a dedicated Critic agent to adversarially review an important decision, design, or technical claim BEFORE you commit to it. Works for ANY domain (web/infra/pentest/ML/data/security). The critic auto-detects the domain, researches to verify each claim, and returns VALID/QUESTIONABLE/WRONG verdicts with evidence. USE THIS before finalizing architecture/tech choices or any claim you cannot back with evidence.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "What to critique (e.g. 'choice of ChromaDB as vector DB', 'this RCE payload approach', 'using pandas for 10GB dataset')"},
                    "context": {"type": "string", "description": "Requirements with concrete numbers/constraints (e.g. '1000 concurrent users', '10GB data', 'target behind Cloudflare WAF')"},
                    "claims": {"type": "string", "description": "Specific claims to verify (e.g. 'ChromaDB scales to 1k users', 'this payload bypasses WAF')"},
                },
                "required": ["subject", "context"],
            }
        },
    }
    registry.register("spawn_critic", critic_spec, handle_spawn_critic, builtin=True, category="meta")

    # spawn_subagent — special: only for main agent
    spawn_spec = {
        "name": "spawn_subagent",
        "description": "Spawn a sub-agent to handle a specific sub-task in a separate context. Use this when a task is complex or requires deep focus.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "role_name": {"type": "string", "description": "Name of the subagent role (e.g. 'Code Reviewer')"},
                    "system_prompt": {"type": "string", "description": "Custom instructions/personality for the subagent"},
                    "task": {"type": "string", "description": "The specific task the subagent must complete"},
                },
                "required": ["role_name", "task"],
            }
        },
    }
    registry.register("spawn_subagent", spawn_spec, handle_spawn_subagent, builtin=True, category="meta")
