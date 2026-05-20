from pydantic import BaseModel

from smart_agent.graph.state import AgentState
from smart_agent.llm import llm_client
from smart_agent.prompts.perceiver import PERCEIVER_PROMPT


class PerceiverOutput(BaseModel):
    language: str
    domains: list[str]
    complexity_score: int
    is_trivial: bool
    needs_clarification: bool
    needs_search: bool


def perceiver_node(state: AgentState) -> dict:
    history = state.get("conversation_history", [])
    history_context = ""
    if history:
        recent = history[-10:]
        history_context = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:1000]}"
            for m in recent
        )

    prompt = PERCEIVER_PROMPT.format(
        user_input=state["user_input"],
        conversation_history=history_context,
    )

    response = llm_client.call_flash(
        prompt,
        response_schema=PerceiverOutput,
        system_instruction="You are an input classifier. Return only valid JSON.",
    )

    if response.parsed:
        data = response.parsed
    else:
        data = {
            "language": "vi",
            "domains": ["general"],
            "complexity_score": 3,
            "is_trivial": False,
            "needs_clarification": False,
            "needs_search": False,
        }

    return {
        "language": data["language"],
        "domains": data["domains"],
        "complexity_score": data["complexity_score"],
        "is_trivial": data["is_trivial"],
        "needs_clarification": data["needs_clarification"],
        "needs_search": data["needs_search"],
    }
