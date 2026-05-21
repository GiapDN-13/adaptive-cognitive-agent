import asyncio
import json
from dataclasses import dataclass
from typing import AsyncGenerator

from app.config import settings


@dataclass
class LLMResponse:
    text: str
    parsed: dict | None = None
    tokens_used: int = 0
    stop_reason: str = ""
    content_blocks: list = None

    def __post_init__(self):
        if self.content_blocks is None:
            self.content_blocks = []


class BedrockClient:
    def __init__(self):
        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "bedrock-runtime",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
            config=Config(read_timeout=60, connect_timeout=10),
        )

    async def converse(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 32000,
    ) -> dict:
        kwargs = {
            "modelId": settings.bedrock_light_model,
            "system": [{"text": system}],
            "messages": messages,
            "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
        }
        if tools:
            kwargs["toolConfig"] = {"tools": tools}

        response = await asyncio.to_thread(self._client.converse, **kwargs)
        return response

    async def converse_stream(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 32000,
    ) -> AsyncGenerator[dict, None]:
        kwargs = {
            "modelId": settings.bedrock_light_model,
            "system": [{"text": system}],
            "messages": messages,
            "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
        }
        if tools:
            kwargs["toolConfig"] = {"tools": tools}

        def _call():
            return self._client.converse_stream(**kwargs)

        response = await asyncio.to_thread(_call)
        stream = response.get("stream")
        if not stream:
            return

        def _next_event(it):
            try:
                return next(it)
            except StopIteration:
                return None

        it = iter(stream)
        while True:
            event = await asyncio.to_thread(_next_event, it)
            if event is None:
                break
            yield event

    async def converse_stream_collect(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 32000,
        on_text_chunk: callable = None,
    ) -> dict:
        """Stream response, collect into full response structure, optionally callback on text chunks."""
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

        return {
            "stopReason": stop_reason,
            "output": {"message": {"content": content_blocks}},
            "usage": usage,
        }


def create_llm_client() -> BedrockClient:
    return BedrockClient()
