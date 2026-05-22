import asyncio
import threading
import time
from typing import Callable

from app.llm.client import BedrockClient


async def stream_agent_response(
    client: BedrockClient,
    messages: list[dict],
    system: str,
    tools: list[dict],
    ws_send: Callable,
    temperature: float = 0.4,
    max_tokens: int = 64000,
    cancel_event: threading.Event | None = None,
) -> dict:
    last_activity = time.monotonic()

    async def on_chunk(chunk: str):
        nonlocal last_activity
        last_activity = time.monotonic()
        await ws_send({
            "type": "agent_chunk",
            "content": chunk,
            "done": False,
        })

    async def heartbeat_loop():
        try:
            while True:
                await asyncio.sleep(8)
                elapsed = int(time.monotonic() - last_activity)
                if elapsed >= 8:
                    await ws_send({
                        "type": "agent_heartbeat",
                        "elapsed_since_last_chunk": elapsed,
                    })
        except asyncio.CancelledError:
            pass

    heartbeat_task = asyncio.create_task(heartbeat_loop())
    response = None
    try:
        response = await client.converse_stream_collect(
            messages=messages,
            system=system,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            on_text_chunk=on_chunk,
            cancel_event=cancel_event,
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await ws_send({"type": "agent_chunk", "content": "", "done": True})
        raise
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    stop_reason = response.get("stopReason", "")
    content_blocks = response.get("output", {}).get("message", {}).get("content", [])
    has_text = any("text" in b for b in content_blocks)
    if has_text and stop_reason != "max_tokens":
        await ws_send({"type": "agent_chunk", "content": "", "done": True})

    return response
