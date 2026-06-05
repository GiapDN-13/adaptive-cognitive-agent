import json
import logging
import threading
import uuid
from typing import AsyncGenerator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def map_tools_to_openai(bedrock_tools: list[dict] | None) -> list[dict] | None:
    if not bedrock_tools:
        return None
    openai_tools = []
    for tool in bedrock_tools:
        spec = tool.get("toolSpec", {})
        openai_tools.append({
            "type": "function",
            "function": {
                "name": spec.get("name"),
                "description": spec.get("description"),
                "parameters": spec.get("inputSchema", {}).get("json", {})
            }
        })
    return openai_tools


def map_messages_to_openai(bedrock_messages: list[dict], system_prompt: str | None = None) -> list[dict]:
    openai_messages = []
    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})

    for msg in bedrock_messages:
        role = msg.get("role")
        content = msg.get("content", [])

        # If content is already a string
        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
            continue

        text_parts = []
        tool_calls = []
        tool_results = []

        for block in content:
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolUse" in block:
                tu = block["toolUse"]
                tool_calls.append({
                    "id": tu.get("toolUseId"),
                    "type": "function",
                    "function": {
                        "name": tu.get("name"),
                        "arguments": json.dumps(tu.get("input", {}))
                    }
                })
            elif "toolResult" in block:
                tr = block["toolResult"]
                tr_content = tr.get("content", [])
                tr_text = ""
                for tr_block in tr_content:
                    if "text" in tr_block:
                        val = tr_block["text"]
                        tr_text += val if isinstance(val, str) else str(val)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tr.get("toolUseId"),
                    "content": tr_text
                })

        if tool_results:
            # Under OpenAI schema, each toolResult must be its own message with role 'tool'
            for tr_msg in tool_results:
                openai_messages.append(tr_msg)
        else:
            openai_msg = {"role": role}
            if text_parts:
                openai_msg["content"] = "\n".join(text_parts)
            else:
                openai_msg["content"] = None

            if tool_calls:
                openai_msg["tool_calls"] = tool_calls

            openai_messages.append(openai_msg)

    return openai_messages


def map_openai_response_to_bedrock(openai_resp: dict) -> dict:
    choices = openai_resp.get("choices", [])
    if not choices:
        return {
            "stopReason": "end_turn",
            "output": {"message": {"role": "assistant", "content": []}},
            "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}
        }

    choice = choices[0]
    finish_reason = choice.get("finish_reason", "stop")

    stop_reason = "end_turn"
    if finish_reason == "tool_calls":
        stop_reason = "tool_use"
    elif finish_reason == "length":
        stop_reason = "max_tokens"

    message = choice.get("message", {})
    content_blocks = []

    text = message.get("content")
    if text:
        content_blocks.append({"text": text})

    tool_calls = message.get("tool_calls", [])
    for tc in tool_calls:
        func = tc.get("function", {})
        args_str = func.get("arguments", "{}")
        try:
            inputs = json.loads(args_str)
        except Exception:
            inputs = {"raw": args_str}
        content_blocks.append({
            "toolUse": {
                "toolUseId": tc.get("id"),
                "name": func.get("name"),
                "input": inputs
            }
        })

    usage = openai_resp.get("usage", {})

    return {
        "stopReason": stop_reason,
        "output": {
            "message": {
                "role": "assistant",
                "content": content_blocks
            }
        },
        "usage": {
            "inputTokens": usage.get("prompt_tokens", 0),
            "outputTokens": usage.get("completion_tokens", 0),
            "totalTokens": usage.get("total_tokens", 0)
        }
    }


class AzureOpenAIClient:
    def __init__(self):
        self.endpoint = settings.azure_openai_endpoint
        self.api_key = settings.azure_openai_api_key
        self.headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        logger.info(f"Initialized AzureOpenAIClient with endpoint: {self.endpoint}")

    async def converse(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> dict:
        openai_messages = map_messages_to_openai(messages, system)
        openai_tools = map_tools_to_openai(tools)

        # Build payload using max_completion_tokens (required by GPT-5.4 Azure)
        payload = {
            "messages": openai_messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens
        }
        if openai_tools:
            payload["tools"] = openai_tools

        logger.info(f"Calling Azure OpenAI: {self.endpoint} (converse)")
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self.endpoint, headers=self.headers, json=payload)
            if response.status_code != 200:
                err_body = response.text
                logger.error(f"Azure OpenAI Error {response.status_code}: {err_body}")
                raise RuntimeError(f"Azure OpenAI HTTP {response.status_code}: {err_body}")

            resp_json = response.json()
            return map_openai_response_to_bedrock(resp_json)

    async def converse_stream(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        cancel_event: threading.Event | None = None,
        model: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        openai_messages = map_messages_to_openai(messages, system)
        openai_tools = map_tools_to_openai(tools)

        payload = {
            "messages": openai_messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
            "stream": True
        }
        if openai_tools:
            payload["tools"] = openai_tools

        logger.info(f"Calling Azure OpenAI: {self.endpoint} (converse_stream)")

        # Keep track of delta emission states
        started_text = False
        active_tool_calls = {}  # key: index -> {"id": ..., "name": ...}

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", self.endpoint, headers=self.headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    logger.error(f"Azure OpenAI stream error {response.status_code}: {err_body.decode('utf-8')}")
                    raise RuntimeError(f"Azure OpenAI Stream HTTP {response.status_code}: {err_body.decode('utf-8')}")

                async for line in response.aiter_lines():
                    if cancel_event and cancel_event.is_set():
                        break
                    line = line.strip()
                    if not line:
                        continue
                    if line == "data: [DONE]":
                        break
                    if line.startswith("data: "):
                        data_str = line[len("data: "):]
                        try:
                            chunk = json.loads(data_str)
                        except Exception:
                            continue

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue

                        choice = choices[0]
                        delta = choice.get("delta", {})
                        content = delta.get("content")
                        tool_calls = delta.get("tool_calls", [])
                        finish_reason = choice.get("finish_reason")

                        # 1. Text chunk delta
                        if content:
                            if not started_text:
                                yield {"contentBlockStart": {"start": {"text": ""}}}
                                started_text = True
                            yield {"contentBlockDelta": {"delta": {"text": content}}}

                        # 2. Tool calls delta
                        if tool_calls:
                            for tc in tool_calls:
                                idx = tc.get("index", 0)
                                func = tc.get("function", {})
                                tc_id = tc.get("id")
                                tc_name = func.get("name")
                                tc_args = func.get("arguments", "")

                                if idx not in active_tool_calls:
                                    # Stop text block if it was active
                                    if started_text:
                                        yield {"contentBlockStop": {}}
                                        started_text = False

                                    active_tool_calls[idx] = {
                                        "id": tc_id or f"call_{uuid.uuid4().hex[:8]}",
                                        "name": tc_name or "unknown"
                                    }

                                    yield {
                                        "contentBlockStart": {
                                            "start": {
                                                "toolUse": {
                                                    "toolUseId": active_tool_calls[idx]["id"],
                                                    "name": active_tool_calls[idx]["name"]
                                                }
                                            }
                                        }
                                    }

                                if tc_args:
                                    yield {
                                        "contentBlockDelta": {
                                            "delta": {
                                                "toolUse": {
                                                    "input": tc_args
                                                }
                                            }
                                        }
                                    }

                        # 3. Finish reason / message stop
                        if finish_reason is not None:
                            if started_text:
                                yield {"contentBlockStop": {}}
                                started_text = False

                            for idx in list(active_tool_calls.keys()):
                                yield {"contentBlockStop": {}}
                                del active_tool_calls[idx]

                            stop_reason = "end_turn"
                            if finish_reason == "tool_calls":
                                stop_reason = "tool_use"
                            elif finish_reason == "length":
                                stop_reason = "max_tokens"

                            yield {"messageStop": {"stopReason": stop_reason}}

                            usage = chunk.get("usage", {})
                            if usage:
                                yield {
                                    "metadata": {
                                        "usage": {
                                            "inputTokens": usage.get("prompt_tokens", 0),
                                            "outputTokens": usage.get("completion_tokens", 0),
                                            "totalTokens": usage.get("total_tokens", 0)
                                        }
                                    }
                                }
                            else:
                                yield {"metadata": {"usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}}}

    async def converse_stream_collect(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        on_text_chunk: callable = None,
        cancel_event: threading.Event | None = None,
        model: str | None = None,
    ) -> dict:
        content_blocks = []
        current_text = ""
        current_tool_use = None
        current_tool_input_str = ""
        stop_reason = ""
        usage = {}

        async for event in self.converse_stream(
            messages=messages,
            system=system,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            cancel_event=cancel_event,
        ):
            if "contentBlockStart" in event:
                start = event["contentBlockStart"].get("start", {})
                if "text" in start:
                    current_text = start.get("text", "")
                elif "toolUse" in start:
                    current_tool_use = start["toolUse"]
                    current_tool_input_str = ""

            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    chunk = delta["text"]
                    current_text += chunk
                    if on_text_chunk:
                        await on_text_chunk(chunk)
                elif "toolUse" in delta:
                    current_tool_input_str += delta["toolUse"].get("input", "")

            elif "contentBlockStop" in event:
                if current_tool_use:
                    try:
                        parsed_input = json.loads(current_tool_input_str)
                    except json.JSONDecodeError:
                        parsed_input = {"raw": current_tool_input_str}
                    content_blocks.append({
                        "toolUse": {
                            "toolUseId": current_tool_use.get("toolUseId", ""),
                            "name": current_tool_use.get("name", ""),
                            "input": parsed_input,
                        }
                    })
                    current_tool_use = None
                    current_tool_input_str = ""
                elif current_text:
                    content_blocks.append({"text": current_text})
                    current_text = ""

            elif "messageStop" in event:
                stop_reason = event["messageStop"].get("stopReason", "end_turn")

            elif "metadata" in event:
                usage = event["metadata"].get("usage", {})

        # Flush any trailing text just in case
        if current_text:
            content_blocks.append({"text": current_text})

        return {
            "stopReason": stop_reason,
            "output": {"message": {"content": content_blocks}},
            "usage": usage,
        }
