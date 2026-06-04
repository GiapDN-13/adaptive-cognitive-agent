# Task Report: Self-Extending SmartAgent Architecture

**Date**: 2026-05-30
**Status**: COMPLETED
**Scope**: Backend refactor — ToolRegistry + Meta-tools + Extension system

---

## Summary

Redesigned SmartAgent từ hard-coded tool dispatch thành self-extending architecture. Agent giờ có thể tự tạo tools, skills, hooks tại runtime — tất cả persist qua restart.

---

## What Changed

### New Files (5)

| File | Lines | Purpose |
|------|-------|---------|
| `app/agent/tool_registry.py` | 85 | Central registry: ToolEntry dataclass, register/dispatch/list |
| `app/agent/tool_safety.py` | 110 | AST validation: forbidden imports, eval/exec, signature checks |
| `app/agent/builtin_tools.py` | 215 | 11 tool handlers extracted from loop.py + registration function |
| `app/agent/meta_tools.py` | 265 | 3 meta-tools: create_tool, create_skill, create_hook |
| `app/agent/extension_loader.py` | 175 | Startup loader: scan data/extensions/, register all |

### Modified Files (4)

| File | Change |
|------|--------|
| `app/agent/loop.py` | Replaced 200-line if-chain with 5-line registry dispatch. Added dynamic tools_list per iteration. |
| `app/agent/tools.py` | `get_tools()` delegates to ToolRegistry when available. |
| `app/agent/skill_manager.py` | Added `reload()` method scanning data/extensions/skills/. |
| `app/main.py` | Startup: register_all_builtins → register_meta_tools → load_all_extensions. |

---

## Architecture

```
Agent Loop (per iteration)
    → tools_list = tool_registry.get_tool_specs()   ← includes runtime tools
    → LLM call with dynamic toolConfig
    → tool_use block received
    → hook_manager.execute_pre_hooks()
    → tool_registry.get_handler(name) → execute
    → hook_manager.execute_post_hooks()
    → result back to LLM
```

### Self-Extension Flow
```
Iteration N:  LLM calls create_tool("parse_csv", ...)
              → validate_handler_code() [AST safety]
              → persist to data/extensions/tools/parse_csv/
              → compile + register in ToolRegistry
              → "Tool created successfully"

Iteration N+1: tools_list now includes parse_csv
               LLM calls parse_csv(...)
               → execute via registry → hook pipeline → return
```

---

## Tool Registry Stats (after startup)

| Category | Count |
|----------|-------|
| Built-in action tools | 9 (shell_exec, write_file, read_file, web_search, think, ask_user, propose_plan, load_skill, load_agent) |
| Built-in meta tools | 4 (spawn_subagent, create_tool, create_skill, create_hook) |
| Runtime tools | N (loaded from data/extensions/tools/) |
| **Total at boot** | **13 + N** |

---

## Security Model

1. **AST validation** — Blocks: os, subprocess, sys, ctypes, signal, socket, multiprocessing, threading, importlib
2. **Import whitelist** — Only: json, re, math, datetime, urllib, hashlib, base64, collections, itertools, functools, typing, dataclasses, enum, string, textwrap, csv, io, struct, decimal, fractions, statistics, random, uuid, copy, operator
3. **Forbidden calls** — eval, exec, compile, __import__, globals, locals, getattr, setattr, delattr, breakpoint, open
4. **Namespace sandbox** — Handlers get: docker_manager, json, re, Path, asyncio
5. **Cannot overwrite builtins** — Registry raises ValueError
6. **Hook pipeline intact** — ALL tools (builtin + runtime) pass through pre/post hooks

---

## Verification

| Test | Result |
|------|--------|
| Python syntax check (all 9 files) | PASS |
| AST parse verification | PASS |
| No circular imports (tool_registry has no app imports) | PASS |
| Backward compatible (get_tools fallback) | PASS |

---

## Persistence Structure

```
data/extensions/
├── tools/
│   └── {tool_name}/
│       ├── handler.py      # async def handler(session, tool_input, ws_send, cancel_event) -> str
│       └── schema.json     # Bedrock toolSpec format
├── skills/
│   └── {skill_id}/
│       └── SKILL.md        # Standard frontmatter + markdown
└── hooks/
    └── {hook_name}.py      # async def pre_hook(...) or post_hook(...)
```

---

## Research Applied

| Source | Pattern Applied |
|--------|----------------|
| ECC | Hook lifecycle (pre→exec→post), GateGuard concept, content/harness separation |
| Ruflo | Orchestration separate from execution, model routing category field |
| Superpowers | Verification step in create_tool (compile + dry-run before register) |
| Shannon | Data-driven registry, dependency field on ToolEntry |
| GitNexus | Tool categorization (intelligence/action/meta) |

---

## Next Steps (not in scope of this task)

1. **Frontend UI** — Show runtime tools in a panel, allow user to manage/delete
2. **Tool versioning** — Track version of runtime tools, support updates
3. **Learning hooks** — Post-success hook that captures patterns for reuse
4. **MCP integration** — Add GitNexus or external MCP servers as tool sources
5. **Security hardening** — Auth, rate limiting (from weakness report Phase 1)
