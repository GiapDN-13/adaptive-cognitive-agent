"""
ToolRegistry — Central registry for all tools (builtin + runtime-created).

Replaces the hard-coded if-chain dispatch in loop.py with a unified
register/dispatch pattern. Runtime-created tools are registered alongside
builtins and automatically included in LLM toolConfig.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class ToolEntry:
    name: str
    schema: dict
    handler: Callable
    builtin: bool = True
    category: str = "action"
    dependencies: list[str] = field(default_factory=list)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        schema: dict,
        handler: Callable,
        builtin: bool = True,
        category: str = "action",
        dependencies: list[str] | None = None,
    ) -> None:
        if name in self._tools and self._tools[name].builtin and not builtin:
            raise ValueError(f"Cannot overwrite builtin tool '{name}' with runtime tool")
        self._tools[name] = ToolEntry(
            name=name,
            schema=schema,
            handler=handler,
            builtin=builtin,
            category=category,
            dependencies=dependencies or [],
        )
        logger.info(f"Registered tool: {name} (builtin={builtin}, category={category})")

    def unregister(self, name: str) -> bool:
        entry = self._tools.get(name)
        if not entry:
            return False
        if entry.builtin:
            return False
        del self._tools[name]
        logger.info(f"Unregistered runtime tool: {name}")
        return True

    def get_tool_specs(self, is_subagent: bool = False) -> list[dict]:
        specs = []
        for entry in self._tools.values():
            if is_subagent and entry.name in ("spawn_subagent", "create_tool", "create_skill", "create_hook"):
                continue
            specs.append({"toolSpec": entry.schema})
        return specs

    def get_handler(self, name: str) -> Callable | None:
        entry = self._tools.get(name)
        return entry.handler if entry else None

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def list_runtime_tools(self) -> list[str]:
        return [name for name, entry in self._tools.items() if not entry.builtin]

    def get_tool_info(self, name: str) -> dict | None:
        entry = self._tools.get(name)
        if not entry:
            return None
        return {
            "name": entry.name,
            "builtin": entry.builtin,
            "category": entry.category,
            "dependencies": entry.dependencies,
        }

    @property
    def count(self) -> int:
        return len(self._tools)


tool_registry = ToolRegistry()
