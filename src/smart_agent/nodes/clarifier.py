from smart_agent.graph.state import AgentState
from smart_agent.llm import llm_client
from smart_agent.prompts.clarifier import CLARIFIER_PROMPT


def clarifier_node(state: AgentState) -> dict:
    language = state.get("language", "vi")
    language_name = "Vietnamese" if language == "vi" else "English"

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
    }
