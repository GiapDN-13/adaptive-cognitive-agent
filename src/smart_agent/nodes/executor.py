import json

from smart_agent.config import settings
from smart_agent.graph.state import AgentState
from smart_agent.prompts.executor import build_executor_system_prompt
from smart_agent.tools.calculator import calculator
from smart_agent.tools.code_executor import code_executor
from smart_agent.tools.datetime_tool import get_datetime
from smart_agent.tools.read_url import read_url
from smart_agent.tools.think import think
from smart_agent.tools.web_search import web_search

TOOL_DEFINITIONS = [
    {
        "toolSpec": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression. Use Python math syntax. Examples: '100000000 * (1 + 0.08)**5', 'math.sqrt(144)', '(500 * 12) / 365'",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate",
                        }
                    },
                    "required": ["expression"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "think",
            "description": "Use this to organize complex thoughts before giving a final answer. Write down your reasoning, analysis, or intermediate conclusions.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "thought": {
                            "type": "string",
                            "description": "Your reasoning or analysis to organize",
                        }
                    },
                    "required": ["thought"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "web_search",
            "description": "Search the web for real information. ALWAYS use this when the user mentions a specific company, product, person, or entity to get REAL facts. Also use for current data, statistics, or any info not in your training data. Search BEFORE writing content about specific entities.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        }
                    },
                    "required": ["query"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "read_url",
            "description": "Fetch and extract text content from a URL. Use after web_search to get full details from a specific page, or when user provides a URL directly.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to fetch and read",
                        }
                    },
                    "required": ["url"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "code_executor",
            "description": "Execute Python code and return the output. Use for data processing, generating content programmatically, testing algorithms, or any task that benefits from running actual code.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute",
                        }
                    },
                    "required": ["code"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_datetime",
            "description": "Get the current date, time, and day of week. Use when the user asks about today's date, current time, or when you need to reference the current date in your response.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "timezone_offset": {
                            "type": "number",
                            "description": "UTC offset in hours (default: 7 for Vietnam)",
                        }
                    },
                    "required": [],
                }
            },
        }
    },
]

TOOL_DISPATCH = {
    "calculator": lambda params: calculator(params["expression"]),
    "think": lambda params: think(params["thought"]),
    "web_search": lambda params: web_search(params["query"]),
    "read_url": lambda params: read_url(params["url"]),
    "code_executor": lambda params: code_executor(params["code"]),
    "get_datetime": lambda params: get_datetime(params.get("timezone_offset", 7)),
}


def _is_incomplete(text: str) -> bool:
    """Detect if output was cut off mid-generation."""
    if not text or len(text) < 200:
        return False
    text_lower = text.lower().strip()
    # HTML that didn't close
    if "<html" in text_lower and "</html>" not in text_lower:
        return True
    if "<body" in text_lower and "</body>" not in text_lower:
        return True
    # Markdown code block not closed
    if text.count("```") % 2 != 0:
        return True
    # Ends mid-sentence (no terminal punctuation in last 100 chars)
    last_chunk = text[-100:]
    if not any(last_chunk.rstrip().endswith(c) for c in [".", "!", "?", "`", ">", "}", ")", "]", ";"]):
        return True
    return False


def _get_max_iterations(depth: int) -> int:
    if depth <= 2:
        return 4
    if depth == 3:
        return 6
    return 8


def _get_max_tokens(depth: int) -> int:
    if depth <= 2:
        return 16384
    if depth == 3:
        return 32000
    return 64000


def executor_node(state: AgentState) -> dict:
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
        config=Config(read_timeout=600, connect_timeout=15),
    )

    system_prompt = build_executor_system_prompt(
        persona=state.get("persona", "Generalist"),
        language=state.get("language", "vi"),
        domain_rules=state.get("domain_rules", []),
        anti_patterns=state.get("anti_patterns", []),
        quality_gates=state.get("quality_gates", []),
        cognitive_output=state.get("cognitive_output"),
    )

    depth = state.get("thinking_depth", 3)
    max_iterations = _get_max_iterations(depth)
    max_tokens = _get_max_tokens(depth)

    # Build user message with conversation context
    user_text = state["user_input"]
    history = state.get("conversation_history", [])
    if history:
        recent = history[-10:]
        max_chars_per_msg = 4000 if depth >= 3 else 2000
        context_lines = []
        for m in recent:
            role = "User" if m["role"] == "user" else "Assistant"
            context_lines.append(f"{role}: {m['content'][:max_chars_per_msg]}")
        context = "\n".join(context_lines)
        user_text = f"[Conversation context]\n{context}\n\n[Current request]\n{user_text}"

    messages = [{"role": "user", "content": [{"text": user_text}]}]

    tool_calls_log = []
    iterations = 0
    accumulated_text = ""

    for i in range(max_iterations):
        iterations += 1
        is_last_iteration = i == max_iterations - 1

        if is_last_iteration and not accumulated_text:
            messages.append({
                "role": "user",
                "content": [{"text": "You have used all available iterations. Provide your final comprehensive answer NOW based on everything you've gathered so far. Do NOT call any more tools — respond with text only."}],
            })

        response = client.converse(
            modelId=settings.bedrock_light_model,
            system=[{"text": system_prompt}],
            messages=messages,
            toolConfig={"tools": TOOL_DEFINITIONS},
            inferenceConfig={"temperature": 0.4, "maxTokens": max_tokens},
        )

        stop_reason = response.get("stopReason", "")
        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])

        messages.append({"role": "assistant", "content": content_blocks})

        if stop_reason == "end_turn":
            final_text = ""
            for block in content_blocks:
                if "text" in block:
                    final_text += block["text"]
            combined = accumulated_text + final_text

            if _is_incomplete(combined) and i < max_iterations - 1:
                accumulated_text = combined
                messages.append({
                    "role": "user",
                    "content": [{"text": "Your output is incomplete — it appears to be cut off mid-way. Continue EXACTLY where you stopped. Do not repeat anything already written."}],
                })
                continue

            return {
                "final_output": combined,
                "tool_calls": tool_calls_log,
                "react_iterations": iterations,
            }

        if stop_reason == "max_tokens":
            for block in content_blocks:
                if "text" in block:
                    accumulated_text += block["text"]
            messages.append({
                "role": "user",
                "content": [{"text": "Continue exactly where you left off. Do not repeat what you already wrote."}],
            })
            continue

        if stop_reason == "tool_use":
            tool_results = []
            for block in content_blocks:
                if "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_name = tool_use["name"]
                    tool_input = tool_use.get("input", {})
                    tool_id = tool_use["toolUseId"]

                    dispatch_fn = TOOL_DISPATCH.get(tool_name)
                    if dispatch_fn:
                        result = dispatch_fn(tool_input)
                    else:
                        result = f"Unknown tool: {tool_name}"

                    tool_calls_log.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "output": result,
                        "iteration": iterations,
                    })

                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_id,
                            "content": [{"text": result}],
                        }
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = ""
            for block in content_blocks:
                if "text" in block:
                    final_text += block["text"]
            return {
                "final_output": accumulated_text + final_text or "[No output generated]",
                "tool_calls": tool_calls_log,
                "react_iterations": iterations,
            }

    last_text = ""
    for block in content_blocks:
        if "text" in block:
            last_text += block["text"]

    return {
        "final_output": accumulated_text + last_text or "[Max iterations reached]",
        "tool_calls": tool_calls_log,
        "react_iterations": iterations,
    }
