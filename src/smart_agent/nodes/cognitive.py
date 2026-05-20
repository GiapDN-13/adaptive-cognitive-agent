from smart_agent.graph.state import AgentState
from smart_agent.llm import llm_client
from smart_agent.prompts.cognitive import (
    STEP_1_SKILLS,
    STEP_2_KNOWLEDGE,
    STEP_3_REQUIREMENTS,
    STEP_4_GOALS,
    STEP_5_EVALUATION,
)


def cognitive_node(state: AgentState) -> dict:
    user_input = state["user_input"]
    language = state.get("language", "vi")
    domains = state.get("domains", ["general"])
    persona = state.get("persona", "Generalist")

    steps_output = {}

    # Step 1: Skills
    prompt_1 = STEP_1_SKILLS.format(
        user_input=user_input,
        language=language,
        domains=domains,
        persona=persona,
    )
    resp_1 = llm_client.call_flash(prompt_1, temperature=0.3)
    steps_output["skills"] = resp_1.text

    # Step 2: Knowledge
    prompt_2 = STEP_2_KNOWLEDGE.format(
        user_input=user_input,
        step_1_output=resp_1.text[:4000],
    )
    resp_2 = llm_client.call_flash(prompt_2, temperature=0.3)
    steps_output["knowledge"] = resp_2.text

    # Step 3: Requirements
    prompt_3 = STEP_3_REQUIREMENTS.format(
        user_input=user_input,
        step_1_output=resp_1.text[:3000],
        step_2_output=resp_2.text[:3000],
    )
    resp_3 = llm_client.call_flash(prompt_3, temperature=0.3)
    steps_output["requirements"] = resp_3.text

    # Step 4: Goals
    prompt_4 = STEP_4_GOALS.format(
        user_input=user_input,
        step_1_output=resp_1.text[:2000],
        step_2_output=resp_2.text[:2000],
        step_3_output=resp_3.text[:3000],
    )
    resp_4 = llm_client.call_flash(prompt_4, temperature=0.3)
    steps_output["goals"] = resp_4.text

    # Step 5: Evaluation
    prompt_5 = STEP_5_EVALUATION.format(
        user_input=user_input,
        step_1_output=resp_1.text[:2000],
        step_2_output=resp_2.text[:2000],
        step_3_output=resp_3.text[:2000],
        step_4_output=resp_4.text[:2000],
    )
    resp_5 = llm_client.call_flash(prompt_5, temperature=0.3)
    steps_output["evaluation"] = resp_5.text

    return {"cognitive_output": steps_output}
