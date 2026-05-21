from typing import Callable

from app.llm.client import BedrockClient


async def stream_agent_response(
    client: BedrockClient,
    messages: list[dict],
    system: str,
    tools: list[dict],
    ws_send: Callable,
    temperature: float = 0.4,
    max_tokens: int = 32000,
) -> dict:
    """Call LLM with streaming, sending text chunks to WebSocket in real-time."""

    async def on_chunk(chunk: str):
        await ws_send({
            "type": "agent_chunk",
            "content": chunk,
            "done": False,
        })

    response = await client.converse_stream_collect(
        messages=messages,
        system=system,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        on_text_chunk=on_chunk,
    )

    content_blocks = response.get("output", {}).get("message", {}).get("content", [])
    has_text = any("text" in b for b in content_blocks)
    if has_text:
        await ws_send({"type": "agent_chunk", "content": "", "done": True})

    return response
