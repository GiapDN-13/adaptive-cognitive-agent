import re

TOOL_DEFINITIONS = [
    {
        "toolSpec": {
            "name": "shell_exec",
            "description": "Execute a bash command in the sandbox container. Output is streamed live and the return value is prefixed with [exit_code=N]. NOTE: each call is a SEPARATE shell — cd/venv/export do NOT persist between calls; chain dependent steps with && in one command, or set `cwd`.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Bash command to execute"},
                        "timeout": {"type": "integer", "description": "Max seconds before the command is killed (default 900). Use a small value for quick checks."},
                        "cwd": {"type": "string", "description": "Optional working directory to run the command in (e.g. '/workspace/proj'). Saves prefixing with cd."},
                    },
                    "required": ["command"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "write_file",
            "description": "Write content to a file in the container. Relative paths resolve under /workspace. Overwrites by default; use mode='append' to add to an existing file. The write is verified on disk (returns WRITE FAILED if it didn't land).",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path (absolute, or relative to /workspace)"},
                        "content": {"type": "string", "description": "File content to write"},
                        "mode": {"type": "string", "enum": ["overwrite", "append"], "description": "overwrite (default) replaces the file; append adds content to the end. NOTE: append joins bytes EXACTLY — it does NOT insert a newline, so include a leading '\\n' in content if you want the appended text on a new line."},
                    },
                    "required": ["path", "content"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "read_file",
            "description": "Read file content from the container. Returns a header with the line range and total line count, so you know if more remains. Use `offset` to paginate large files. Reports 'FILE NOT FOUND' distinctly from an empty file.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path in container"},
                        "max_lines": {"type": "integer", "description": "Max lines to read (default 200)"},
                        "offset": {"type": "integer", "description": "1-based line number to start from (default 1). Use to read the next page, e.g. offset=201."},
                        "max_bytes": {"type": "integer", "description": "Soft cap on returned text size in chars (default 50000) to protect context. Output is truncated past this; raise it to read large logs/dumps."},
                        "line_numbers": {"type": "boolean", "description": "If true, prefix each line with its absolute line number (default false)."},
                    },
                    "required": ["path"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "web_search",
            "description": "Search the web (multi-engine: DuckDuckGo + Lite fallback, retry + UA rotation), OR fetch a specific URL directly via `url`. Distinguishes network error from zero-results. For login/captcha/JS sources, pass `url` to fetch a known page directly.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query. Multi-engine with retry."},
                        "url": {"type": "string", "description": "Instead of searching, fetch THIS URL directly and return its main text. For known/important pages search can't surface."},
                        "headers": {"type": "object", "description": "AUTH: HTTP headers sent to the target page when using `url`, e.g. {\"Authorization\":\"Bearer <token>\"} or {\"Cookie\":\"session=<id>\"} — to access token/cookie-gated pages."},
                        "actions": {"type": "array", "description": "AUTH/login flow when using `url`: ordered browser actions for Firecrawl, e.g. [{\"type\":\"write\",\"selector\":\"#user\",\"text\":\"...\"},{\"type\":\"click\",\"selector\":\"button[type=submit]\"},{\"type\":\"wait\",\"milliseconds\":2000}]. Then the post-login page is scraped.", "items": {"type": "object"}},
                        "max_results": {"type": "integer", "description": "Number of results to return, 1-10 (default 3)."},
                        "fetch_content": {"type": "boolean", "description": "If true, also fetch and extract the main text of the top result for deeper context (default false)."},
                    },
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "think",
            "description": "Organize your reasoning before acting. Not visible to user.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "thought": {"type": "string", "description": "Your reasoning"},
                    },
                    "required": ["thought"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "ask_user",
            "description": "Ask the user a question. Use when you need clarification or want to confirm before proceeding.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Question to ask"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of choices",
                        },
                    },
                    "required": ["question"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "propose_plan",
            "description": "Present a multi-step execution plan for the user to approve before executing. Each step's 'command' field MUST be an actual bash command (e.g. 'python main.py', 'pip install x', 'printf ... > file.py'). Never use tool names as commands.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Plan title"},
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "command": {"type": "string"},
                                },
                                "required": ["description"],
                            },
                            "description": "List of steps",
                        },
                    },
                    "required": ["title", "steps"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "load_skill",
            "description": "Load the full instructions for a specific skill. Use this when you need detailed guidance on a particular capability listed in your Available Skills.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "skill_id": {"type": "string", "description": "The ID of the skill to load (e.g. 'search-first')"},
                    },
                    "required": ["skill_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "load_agent",
            "description": "Load the full definition for a specialist agent. Use this when you need detailed guidance from a specific agent role listed in your Available Agents (e.g. 'architect', 'code-reviewer').",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "The ID of the agent to load (e.g. 'architect', 'code-reviewer')"},
                    },
                    "required": ["agent_id"],
                }
            },
        }
    },
]

# Commands that auto-approve (read-only, no side effects)
AUTO_APPROVE_PATTERNS = [
    r"^(ls|dir|pwd|whoami|echo|cat|head|tail|wc|file|stat|which|type|env|printenv)",
    r"^python[23]?\s+\S+\.py",
    r"^(grep|find|locate|awk|sed|sort|uniq|cut|tr)\s",
]

# Commands that always need approval
APPROVAL_REQUIRED_PATTERNS = [
    r"(^|\s)(rm|rmdir)\s",
    r"(^|\s)sudo\s",
    r"(pip|pip3)\s+install",
    r"(apt-get|apt)\s+(install|remove|purge)",
    r"(npm|yarn|pnpm)\s+(install|add)",
    r"(wget|curl)\s+.*\|\s*(bash|sh)",
    r"(nmap|masscan|nikto|sqlmap)",
]


def requires_approval(command: str) -> bool:
    """Decide if a command needs user approval.

    SECURITY FIX: dangerous patterns are checked FIRST and scan the WHOLE command
    (re.search), so a read-only prefix can't smuggle a dangerous command past the
    gate — e.g. `cat x && rm -rf /` previously matched the `^cat` auto-approve and
    skipped the rm check; now the rm is caught regardless of what comes before it.

    We keep the default permissive (unknown → auto) to preserve red-team freedom:
    only the explicitly dangerous/expensive patterns require a human OK.
    """
    cmd = command.strip()

    # 1. Dangerous ANYWHERE in the command → require approval (scans full string).
    for pattern in APPROVAL_REQUIRED_PATTERNS:
        if re.search(pattern, cmd):
            return True

    # 2. Otherwise safe to auto-run (preserves autonomous execution / red-team use).
    return False


def truncate_output(output: str, max_lines: int = 150, max_chars: int = 12000) -> tuple[str, bool]:
    """Return (text, was_truncated). was_truncated is True if ANY content was
    hidden — by line count OR char count — so callers (e.g. shell_exec's overflow
    file) reliably know the full output isn't present in `text`."""
    lines = output.split("\n")
    # Fast path: small enough on both axes → unchanged.
    if len(output) <= max_chars and len(lines) <= max_lines:
        return output, False

    truncated_by_lines = False
    if len(lines) > max_lines:
        head = "\n".join(lines[:80])
        tail = "\n".join(lines[-30:])
        truncated = f"{head}\n\n... [{len(lines) - 110} lines hidden] ...\n\n{tail}"
        truncated_by_lines = True
    else:
        truncated = output

    truncated_by_chars = False
    if len(truncated) > max_chars:
        truncated = truncated[:max_chars] + f"\n... [truncated at {max_chars} chars, total {len(output)} chars]"
        truncated_by_chars = True

    return truncated, (truncated_by_lines or truncated_by_chars)

def get_tools(is_subagent: bool = False):
    """Get tool specs — delegates to ToolRegistry for dynamic tool list."""
    from app.agent.tool_registry import tool_registry
    if tool_registry.count > 0:
        return tool_registry.get_tool_specs(is_subagent=is_subagent)
    # Fallback for pre-registry initialization (e.g. module-level imports)
    tools = list(TOOL_DEFINITIONS)
    if not is_subagent:
        tools.append({
            "toolSpec": {
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
        })
    return tools


