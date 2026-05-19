from smart_agent.graph.state import AgentState
from smart_agent.llm import llm_client


def trivial_node(state: AgentState) -> dict:
    language = state.get("language", "vi")
    user_input = state["user_input"]

    prompt = f"""Respond naturally and briefly to this casual message.
Language: {"Vietnamese" if language == "vi" else "English"}
Message: "{user_input}"

Reply in 1-2 sentences. Be friendly, concise, have personality."""

    response = llm_client.call_flash(prompt, temperature=0.7)

    return {"trivial_response": response.text, "final_output": response.text}
