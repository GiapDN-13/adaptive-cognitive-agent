from smart_agent.graph.state import AgentState
from smart_agent.llm import llm_client


RETRY_CLASSIFICATION_PROMPT = """Analyze why this AI output failed quality evaluation and determine the best retry strategy.

ORIGINAL REQUEST: "{user_input}"
EVALUATION FEEDBACK: "{feedback}"
EVALUATION SCORES: {scores}
ATTEMPT NUMBER: {attempt}

Classify the failure into one of these categories and suggest a fix:

1. "more_data" - Output lacks specific data, examples, or evidence. Fix: search for more information before answering.
2. "wrong_direction" - Output misunderstood the intent or answered the wrong question. Fix: reframe the approach.
3. "insufficient_depth" - Output is too shallow or generic. Fix: go deeper with more analysis and structure.
4. "wrong_language" - Output is in the wrong language. Fix: respond in the correct language.

Return JSON with:
- strategy: one of ["more_data", "wrong_direction", "insufficient_depth", "wrong_language"]
- retry_instruction: A specific instruction to improve the output (1-2 sentences)"""


def retry_node(state: AgentState) -> dict:
    feedback = state.get("eval_feedback", "")
    scores = state.get("eval_scores", {})
    attempt = state.get("attempt_number", 1)

    prompt = RETRY_CLASSIFICATION_PROMPT.format(
        user_input=state["user_input"],
        feedback=feedback,
        scores=scores,
        attempt=attempt,
    )

    response = llm_client.call_flash(
        prompt,
        system_instruction="Return only valid JSON with 'strategy' and 'retry_instruction' fields.",
    )

    strategy = "insufficient_depth"
    retry_instruction = "Provide more detailed analysis with specific examples and data."

    if response.parsed:
        strategy = response.parsed.get("strategy", strategy)
        retry_instruction = response.parsed.get("retry_instruction", retry_instruction)

    augmented_input = (
        f"{state['user_input']}\n\n"
        f"[RETRY INSTRUCTION - Previous attempt scored {state.get('best_score', 0):.1f}/10. "
        f"Issue: {retry_instruction}]"
    )

    return {
        "retry_strategy": strategy,
        "user_input": augmented_input,
    }
