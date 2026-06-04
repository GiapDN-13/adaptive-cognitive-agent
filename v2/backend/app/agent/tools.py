import re
import uuid

from app.core.docker_manager import DockerManager


TOOL_DEFINITIONS = [
    {
        "toolSpec": {
            "name": "shell_exec",
            "description": "Execute a bash command in the sandbox container. Output is streamed live to the user.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Bash command to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)"},
                    },
                    "required": ["command"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "write_file",
            "description": "Write content to a file in the container.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path in container"},
                        "content": {"type": "string", "description": "File content to write"},
                    },
                    "required": ["path", "content"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "read_file",
            "description": "Read file content from the container.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path in container"},
                        "max_lines": {"type": "integer", "description": "Max lines to read (default 200)"},
                    },
                    "required": ["path"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "web_search",
            "description": "Search the web for information. Use for current data, documentation, or research.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
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
    for pattern in AUTO_APPROVE_PATTERNS:
        if re.match(pattern, command.strip()):
            return False

    for pattern in APPROVAL_REQUIRED_PATTERNS:
        if re.search(pattern, command.strip()):
            return True

    return False


def truncate_output(output: str, max_lines: int = 150, max_chars: int = 12000) -> tuple[str, bool]:
    if len(output) <= max_chars:
        lines = output.split("\n")
        if len(lines) <= max_lines:
            return output, False

    lines = output.split("\n")
    if len(lines) > max_lines:
        head = "\n".join(lines[:80])
        tail = "\n".join(lines[-30:])
        truncated = f"{head}\n\n... [{len(lines) - 110} lines hidden] ...\n\n{tail}"
    else:
        truncated = output

    if len(truncated) > max_chars:
        truncated = truncated[:max_chars] + f"\n... [truncated at {max_chars} chars, total {len(output)} chars]"
        return truncated, True

    return truncated, len(lines) > max_lines

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


