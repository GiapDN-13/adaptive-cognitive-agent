from smart_agent.graph.state import AgentState
from smart_agent.llm import llm_client
from smart_agent.prompts.clarifier import CLARIFIER_FOLLOWUP_PROMPT, CLARIFIER_PROMPT


def clarifier_node(state: AgentState) -> dict:
    language = state.get("language", "vi")
    language_name = "Vietnamese" if language == "vi" else "English"
    clarification_round = state.get("clarification_round", 0) + 1

    if clarification_round > 1 and state.get("missing_info"):
        prompt = CLARIFIER_FOLLOWUP_PROMPT.format(
            user_input=state["user_input"],
            language=language,
            language_name=language_name,
            domains=state.get("domains", ["general"]),
            missing_info=", ".join(state.get("missing_info", [])),
        )
    else:
        prompt = CLARIFIER_PROMPT.format(
            user_input=state["user_input"],
            language=language,
            language_name=language_name,
            domains=state.get("domains", ["general"]),
        )

    response = llm_client.call_flash(prompt, temperature=0.3)

    return {
        "clarification_questions": response.text.strip().split("\n"),
        "final_output": response.text.strip(),
        "clarification_round": clarification_round,
    }
