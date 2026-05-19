import json

from smart_agent.config import settings
from smart_agent.graph.state import AgentState
from smart_agent.prompts.executor import build_executor_system_prompt
from smart_agent.tools.calculator import calculator
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
            "description": "Search the web for current information. Use when you need up-to-date data, facts, or information not in your training data.",
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
]

TOOL_DISPATCH = {
    "calculator": lambda params: calculator(params["expression"]),
    "think": lambda params: think(params["thought"]),
    "web_search": lambda params: web_search(params["query"]),
}


def _get_max_iterations(depth: int) -> int:
    if depth <= 2:
        return 3
    if depth == 3:
        return 4
    return 6


def executor_node(state: AgentState) -> dict:
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
        config=Config(read_timeout=300, connect_timeout=10),
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

    # Build user message with conversation context
    user_text = state["user_input"]
    history = state.get("conversation_history", [])
    if history:
        recent = history[-6:]
        context_lines = []
        for m in recent:
            role = "User" if m["role"] == "user" else "Assistant"
            context_lines.append(f"{role}: {m['content'][:500]}")
        context = "\n".join(context_lines)
        user_text = f"[Conversation context]\n{context}\n\n[Current request]\n{user_text}"

    messages = [{"role": "user", "content": [{"text": user_text}]}]

    tool_calls_log = []
    iterations = 0

    for i in range(max_iterations):
        iterations += 1
        is_last_iteration = i == max_iterations - 1

        if is_last_iteration:
            messages.append({
                "role": "user",
                "content": [{"text": "You have used all available iterations. Provide your final comprehensive answer NOW based on everything you've gathered so far. Do NOT call any more tools — respond with text only."}],
            })

        response = client.converse(
            modelId=settings.bedrock_light_model,
            system=[{"text": system_prompt}],
            messages=messages,
            toolConfig={"tools": TOOL_DEFINITIONS},
            inferenceConfig={"temperature": 0.4, "maxTokens": 4096},
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
            return {
                "final_output": final_text,
                "tool_calls": tool_calls_log,
                "react_iterations": iterations,
            }

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
                "final_output": final_text or "[No output generated]",
                "tool_calls": tool_calls_log,
                "react_iterations": iterations,
            }

    last_text = ""
    for block in content_blocks:
        if "text" in block:
            last_text += block["text"]

    return {
        "final_output": last_text or "[Max iterations reached]",
        "tool_calls": tool_calls_log,
        "react_iterations": iterations,
    }
