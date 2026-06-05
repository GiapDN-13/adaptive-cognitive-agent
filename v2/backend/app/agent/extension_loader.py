"""
Extension Loader — loads runtime-created tools, skills, and hooks from disk on startup.

Scans data/extensions/ and registers everything into the appropriate managers.
Called once during app initialization (after builtin + meta tools are registered).
"""

import ast
import json
import logging
from pathlib import Path

from app.agent.hook_manager import hook_manager
from app.agent.tool_registry import tool_registry
from app.agent.tool_safety import CodeSafetyError, validate_handler_code

logger = logging.getLogger(__name__)

EXTENSIONS_DIR = Path("./data/extensions")


def load_all_extensions() -> dict:
    """Load all persisted extensions from disk. Returns summary counts."""
    EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
    (EXTENSIONS_DIR / "tools").mkdir(exist_ok=True)
    (EXTENSIONS_DIR / "skills").mkdir(exist_ok=True)
    (EXTENSIONS_DIR / "hooks").mkdir(exist_ok=True)

    tools_loaded = _load_runtime_tools()
    skills_loaded = _load_runtime_skills()
    hooks_loaded = _load_runtime_hooks()

    logger.info(
        f"Extensions loaded: {tools_loaded} tools, {skills_loaded} skills, {hooks_loaded} hooks"
    )
    return {"tools": tools_loaded, "skills": skills_loaded, "hooks": hooks_loaded}


def _load_runtime_tools() -> int:
    tools_dir = EXTENSIONS_DIR / "tools"
    if not tools_dir.exists():
        return 0

    count = 0
    for tool_dir in tools_dir.iterdir():
        if not tool_dir.is_dir():
            continue
        schema_path = tool_dir / "schema.json"
        handler_path = tool_dir / "handler.py"
        if not schema_path.exists() or not handler_path.exists():
            continue

        tool_name = tool_dir.name
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            code = handler_path.read_text(encoding="utf-8")

            validate_handler_code(code)
            handler = _compile_handler(code)

            tool_registry.register(
                name=tool_name,
                schema=schema,
                handler=handler,
                builtin=False,
                category="action",
            )
            count += 1
            logger.info(f"Loaded runtime tool: {tool_name}")
        except (CodeSafetyError, Exception) as e:
            logger.error(f"Failed to load runtime tool '{tool_name}': {e}")

    return count


def _load_runtime_skills() -> int:
    from app.agent.skill_manager import _parse_frontmatter, skill_manager

    skills_dir = EXTENSIONS_DIR / "skills"
    if not skills_dir.exists():
        return 0

    count = 0
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        skill_id = skill_dir.name
        try:
            content = skill_file.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            skill_manager.skills[skill_id] = {
                "id": skill_id,
                "name": fm.get("name", skill_id),
                "description": fm.get("description", "Runtime-created skill"),
                "path": str(skill_file),
            }
            count += 1
            logger.info(f"Loaded runtime skill: {skill_id}")
        except Exception as e:
            logger.error(f"Failed to load runtime skill '{skill_id}': {e}")

    return count


def _load_runtime_hooks() -> int:
    hooks_dir = EXTENSIONS_DIR / "hooks"
    if not hooks_dir.exists():
        return 0

    count = 0
    for hook_file in hooks_dir.glob("*.py"):
        hook_name = hook_file.stem
        try:
            code = hook_file.read_text(encoding="utf-8")

            # Strip docstring wrapper if present
            clean_code = code
            try:
                tree = ast.parse(code)
                if (tree.body and isinstance(tree.body[0], ast.Expr)
                        and isinstance(tree.body[0].value, ast.Constant)):
                    # First statement is a docstring, extract the rest
                    lines = code.split("\n")
                    # Find end of docstring
                    in_docstring = False
                    rest_start = 0
                    for i, line in enumerate(lines):
                        if '"""' in line or "'''" in line:
                            if in_docstring:
                                rest_start = i + 1
                                break
                            else:
                                if line.count('"""') >= 2 or line.count("'''") >= 2:
                                    rest_start = i + 1
                                    break
                                in_docstring = True
                    clean_code = "\n".join(lines[rest_start:]).strip()
            except Exception:
                pass

            namespace = _build_hook_namespace()
            exec(compile(ast.parse(clean_code), str(hook_file), "exec"), namespace)

            registered = False
            if "pre_hook" in namespace and callable(namespace["pre_hook"]):
                hook_manager.register_pre_hook(namespace["pre_hook"])
                registered = True
            if "post_hook" in namespace and callable(namespace["post_hook"]):
                hook_manager.register_post_hook(namespace["post_hook"])
                registered = True

            if registered:
                count += 1
                logger.info(f"Loaded runtime hook: {hook_name}")
            else:
                logger.warning(f"Hook file '{hook_name}' has no pre_hook or post_hook function")

        except Exception as e:
            logger.error(f"Failed to load runtime hook '{hook_name}': {e}")

    return count


def _compile_handler(code: str):
    """Compile a handler string into an async callable."""
    import asyncio

    namespace = _build_handler_namespace()
    tree = ast.parse(code)
    exec(compile(tree, "<runtime-tool>", "exec"), namespace)
    handler = namespace.get("handler")
    if handler is None:
        raise ValueError("Code must define 'async def handler(...)'")
    if not asyncio.iscoroutinefunction(handler):
        raise ValueError("handler must be an async function")
    return handler


def _build_handler_namespace() -> dict:
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
    import json as json_mod
    import logging as logging_mod
    import re as re_mod

    return {
        "__builtins__": __builtins__,
        "json": json_mod,
        "re": re_mod,
        "logging": logging_mod,
    }
