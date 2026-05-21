import json
import asyncio
from typing import Callable

from app.config import settings
from app.llm.client import BedrockClient, create_llm_client
from app.agent.prompts import TASK_CLASSIFIER_PROMPT, PLAN_GENERATION_PROMPT


async def classify_task(user_message: str, history_context: str = "") -> bool:
    """Returns True if task needs a multi-step plan."""
    client = create_llm_client()

    prompt = f"{TASK_CLASSIFIER_PROMPT}\n\nConversation context:\n{history_context}\n\nUser request: {user_message}"

    response = await client.converse(
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        system="You are a task classifier. Respond with JSON only.",
        temperature=0.1,
        max_tokens=256,
    )

    content = response.get("output", {}).get("message", {}).get("content", [])
    text = ""
    for block in content:
        if "text" in block:
            text += block["text"]

    try:
        result = json.loads(text)
        return result.get("needs_plan", False)
    except json.JSONDecodeError:
        return len(user_message.split()) > 20


async def generate_plan(
    user_message: str,
    history_context: str = "",
) -> dict:
    """Generate an execution plan for a complex task."""
    client = create_llm_client()

    prompt = (
        f"{PLAN_GENERATION_PROMPT}\n\n"
        f"Context:\n{history_context}\n\n"
        f"User request: {user_message}\n\n"
        f"Generate plan as JSON:"
    )

    response = await client.converse(
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        system="You are a planning agent. Return only valid JSON with title and steps.",
        temperature=0.3,
        max_tokens=2048,
    )

    content = response.get("output", {}).get("message", {}).get("content", [])
    text = ""
    for block in content:
        if "text" in block:
            text += block["text"]

    try:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        plan = json.loads(clean)
        return plan
    except json.JSONDecodeError:
        return {
            "title": "Execution Plan",
            "steps": [{"description": user_message, "command": None}],
        }
