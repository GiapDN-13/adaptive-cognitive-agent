from pydantic import BaseModel

from smart_agent.graph.state import AgentState
from smart_agent.llm import llm_client
from smart_agent.prompts.meta_thinker import META_THINKER_PROMPT


class MetaThinkerOutput(BaseModel):
    persona: str
    thinking_depth: int
    domain_rules: list[str]
    anti_patterns: list[str]
    quality_gates: list[str]
    needs_full_framework: bool


def meta_thinker_node(state: AgentState) -> dict:
    prompt = META_THINKER_PROMPT.format(
        user_input=state["user_input"],
        language=state.get("language", "vi"),
        domains=state.get("domains", ["general"]),
        complexity_score=state.get("complexity_score", 3),
        needs_search=state.get("needs_search", False),
    )

    response = llm_client.call_flash(
        prompt,
        response_schema=MetaThinkerOutput,
        system_instruction="You are a meta-cognitive planner. Return only valid JSON.",
    )

    if response.parsed:
        data = response.parsed
        depth = data.get("thinking_depth", 3)
        return {
            "persona": data.get("persona", "Generalist"),
            "thinking_depth": depth,
            "domain_rules": data.get("domain_rules", []),
            "anti_patterns": data.get("anti_patterns", []),
            "quality_gates": data.get("quality_gates", []),
            "needs_full_framework": depth >= 4,
        }

    return {
        "persona": "Generalist",
        "thinking_depth": 3,
        "domain_rules": [],
        "anti_patterns": [],
        "quality_gates": [],
        "needs_full_framework": False,
    }
