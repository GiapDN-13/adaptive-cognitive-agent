"""
Meta-tools — enable the agent to extend itself at runtime.

Three tools:
  - create_tool: Write Python handler + JSON schema → register → immediately available
  - create_skill: Write SKILL.md → reload skill catalog
  - create_hook: Write Python hook → register pre/post hook
"""

import ast
import json
import logging
from pathlib import Path

from app.agent.tool_safety import validate_handler_code, validate_hook_code, CodeSafetyError

logger = logging.getLogger(__name__)

EXTENSIONS_DIR = Path("./data/extensions")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

CREATE_TOOL_SCHEMA = {
    "name": "create_tool",
    "description": "Create a new tool that becomes immediately available in subsequent iterations. The handler runs in the backend process — delegate heavy work to docker_manager.exec_command_simple(session.container_id, cmd). Use this when no existing tool fits the task.",
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Snake_case name (e.g. 'parse_csv', 'analyze_logs'). Must be unique.",
                },
                "description": {
                    "type": "string",
                    "description": "What the tool does — shown to the LLM for tool selection.",
                },
                "parameters": {
                    "type": "object",
                    "description": "JSON Schema for the tool's input parameters (properties + required).",
                },
                "handler_code": {
                    "type": "string",
                    "description": "Python code defining: async def handler(session, tool_input, ws_send, cancel_event) -> str. Available in namespace: docker_manager, json, re, Path.",
                },
                "category": {
                    "type": "string",
                    "enum": ["intelligence", "action", "meta"],
                    "description": "Tool category: intelligence (read-only queries), action (side effects), meta (self-modification).",
                },
            },
            "required": ["tool_name", "description", "parameters", "handler_code"],
        }
    },
}

CREATE_SKILL_SCHEMA = {
    "name": "create_skill",
    "description": "Create a new reusable skill (instruction set). The skill becomes available in the skills catalog and can be loaded with load_skill. Use for capturing domain knowledge, workflows, or project-specific patterns.",
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "Kebab-case ID (e.g. 'data-pipeline-setup', 'react-patterns')",
                },
                "skill_name": {
                    "type": "string",
                    "description": "Human-readable name",
                },
                "description": {
                    "type": "string",
                    "description": "One-line description — shown in skills catalog",
                },
                "content": {
                    "type": "string",
                    "description": "Full markdown instructions for the skill. Include: When to Use, Workflow steps, Checklist, Examples.",
                },
            },
            "required": ["skill_id", "skill_name", "description", "content"],
        }
    },
}

CREATE_HOOK_SCHEMA = {
    "name": "create_hook",
    "description": "Create a new pre-execution or post-execution hook. Pre-hooks can block tool execution; post-hooks transform output. Hooks run on every tool call.",
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "hook_name": {
                    "type": "string",
                    "description": "Snake_case name (e.g. 'validate_json_output', 'log_api_calls')",
                },
                "hook_type": {
                    "type": "string",
                    "enum": ["pre", "post"],
                    "description": "pre = can block execution (return False, reason), post = can transform result string",
                },
                "hook_code": {
                    "type": "string",
                    "description": "Python code. Pre: async def pre_hook(tool_name, tool_input, session_id) -> tuple[bool, str|None]. Post: async def post_hook(tool_name, tool_input, result, session_id) -> str.",
                },
                "description": {
                    "type": "string",
                    "description": "What this hook checks or enforces",
                },
            },
            "required": ["hook_name", "hook_type", "hook_code"],
        }
    },
}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_create_tool(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.tool_registry import tool_registry

    tool_name = tool_input.get("tool_name", "").strip()
    description = tool_input.get("description", "")
    parameters = tool_input.get("parameters", {})
    handler_code = tool_input.get("handler_code", "")
    category = tool_input.get("category", "action")

    if not tool_name or not tool_name.replace("_", "").isalnum():
        return "Error: tool_name must be non-empty and contain only letters, digits, and underscores."

    if tool_registry.has_tool(tool_name):
        info = tool_registry.get_tool_info(tool_name)
        if info and info["builtin"]:
            return f"Error: Cannot overwrite builtin tool '{tool_name}'."

    try:
        validate_handler_code(handler_code)
    except CodeSafetyError as e:
        return f"Safety validation failed: {e}"

    # Persist to disk
    tool_dir = EXTENSIONS_DIR / "tools" / tool_name
    tool_dir.mkdir(parents=True, exist_ok=True)

    schema = {
        "name": tool_name,
        "description": description,
        "inputSchema": {"json": parameters},
    }
    (tool_dir / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    (tool_dir / "handler.py").write_text(handler_code, encoding="utf-8")

    # Compile and verify
    try:
        handler = _compile_handler(handler_code)
    except Exception as e:
        # Cleanup on failure
        (tool_dir / "handler.py").unlink(missing_ok=True)
        (tool_dir / "schema.json").unlink(missing_ok=True)
        tool_dir.rmdir()
        return f"Compilation failed: {e}"

    # Register
    tool_registry.register(
        name=tool_name,
        schema=schema,
        handler=handler,
        builtin=False,
        category=category,
    )

    logger.info(f"Runtime tool created: {tool_name}")
    return f"Tool '{tool_name}' created and registered successfully. It is now available for use."


async def handle_create_skill(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.skill_manager import skill_manager

    skill_id = tool_input.get("skill_id", "").strip()
    skill_name = tool_input.get("skill_name", "")
    description = tool_input.get("description", "")
    content = tool_input.get("content", "")

    if not skill_id or not skill_id.replace("-", "").isalnum():
        return "Error: skill_id must be non-empty kebab-case (letters, digits, hyphens)."

    # Build SKILL.md with frontmatter
    skill_md = f"""---
name: {skill_name}
description: {description}
origin: runtime
---

{content}
"""

    # Persist
    skill_dir = EXTENSIONS_DIR / "skills" / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(skill_md, encoding="utf-8")

    # Register in skill_manager
    skill_manager.skills[skill_id] = {
        "id": skill_id,
        "name": skill_name,
        "description": description,
        "path": str(skill_path),
    }

    logger.info(f"Runtime skill created: {skill_id}")
    return f"Skill '{skill_id}' created. Use load_skill('{skill_id}') to load its full instructions."


async def handle_create_hook(session, tool_input, ws_send, cancel_event) -> str:
    from app.agent.hook_manager import hook_manager

    hook_name = tool_input.get("hook_name", "").strip()
    hook_type = tool_input.get("hook_type", "")
    hook_code = tool_input.get("hook_code", "")
    description = tool_input.get("description", "")

    if not hook_name or not hook_name.replace("_", "").isalnum():
        return "Error: hook_name must be non-empty and contain only letters, digits, and underscores."

    try:
        validate_hook_code(hook_code, hook_type)
    except CodeSafetyError as e:
        return f"Safety validation failed: {e}"

    # Persist
    hooks_dir = EXTENSIONS_DIR / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / f"{hook_name}.py"

    # Add metadata comment
    full_code = f'"""{description}"""\n\n{hook_code}\n'
    hook_path.write_text(full_code, encoding="utf-8")

    # Compile and register
    try:
        namespace = _build_hook_namespace()
        exec(compile(ast.parse(hook_code), str(hook_path), "exec"), namespace)

        if hook_type == "pre":
            func = namespace.get("pre_hook")
            if func:
                hook_manager.register_pre_hook(func)
        elif hook_type == "post":
            func = namespace.get("post_hook")
            if func:
                hook_manager.register_post_hook(func)
    except Exception as e:
        hook_path.unlink(missing_ok=True)
        return f"Hook compilation failed: {e}"

    logger.info(f"Runtime hook created: {hook_name} (type={hook_type})")
    return f"Hook '{hook_name}' ({hook_type}) created and registered. It will run on all subsequent tool calls."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compile_handler(code: str):
    """Compile handler code into an async callable."""
    namespace = _build_handler_namespace()
    tree = ast.parse(code)
    exec(compile(tree, "<runtime-tool>", "exec"), namespace)
    handler = namespace.get("handler")
    if handler is None:
        raise ValueError("handler.py must define 'async def handler(...)'")
    if not asyncio.iscoroutinefunction(handler):
        raise ValueError("handler must be an async function")
    return handler


def _build_handler_namespace() -> dict:
    """Namespace available to runtime tool handlers."""
    import json as json_mod
    import re as re_mod
    from pathlib import Path as PathCls
    from app.deps import _docker_manager

    return {
        "__builtins__": __builtins__,
        "json": json_mod,
        "re": re_mod,
        "Path": PathCls,
        "docker_manager": _docker_manager,
        "asyncio": __import__("asyncio"),
    }


def _build_hook_namespace() -> dict:
    """Namespace available to runtime hooks."""
    import json as json_mod
    import re as re_mod
    import logging as logging_mod

    return {
        "__builtins__": __builtins__,
        "json": json_mod,
        "re": re_mod,
        "logging": logging_mod,
    }


# Need asyncio import at module level for _compile_handler
import asyncio


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_meta_tools(registry) -> None:
    """Register the 3 meta-tools into the ToolRegistry."""
    registry.register(
        "create_tool", CREATE_TOOL_SCHEMA, handle_create_tool,
        builtin=True, category="meta",
    )
    registry.register(
        "create_skill", CREATE_SKILL_SCHEMA, handle_create_skill,
        builtin=True, category="meta",
    )
    registry.register(
        "create_hook", CREATE_HOOK_SCHEMA, handle_create_hook,
        builtin=True, category="meta",
    )
