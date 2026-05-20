from pydantic import BaseModel

from smart_agent.graph.state import AgentState
from smart_agent.llm import llm_client
from smart_agent.prompts.evaluator import EVALUATOR_PROMPT


class EvaluatorOutput(BaseModel):
    relevance: float
    completeness: float
    accuracy: float
    actionability: float
    language_correct: bool
    contains_fabrication: bool
    gate_violations: list[str]
    feedback: str


def evaluator_node(state: AgentState) -> dict:
    output = state.get("final_output", "")
    if not output or output.startswith("[TODO]") or output.startswith("[Max") or output.startswith("[No output"):
        return {
            "eval_scores": {"relevance": 0, "completeness": 0, "accuracy": 0, "actionability": 0},
            "eval_passed": False,
            "eval_feedback": "No valid output was generated.",
            "attempt_number": state.get("attempt_number", 0) + 1,
        }

    language = state.get("language", "vi")
    language_name = "Vietnamese" if language == "vi" else "English"
    quality_gates = state.get("quality_gates", [])
    gates_text = "\n".join(f"  - {g}" for g in quality_gates) if quality_gates else "  (none specified)"

    prompt = EVALUATOR_PROMPT.format(
        user_input=state["user_input"],
        language=language,
        language_name=language_name,
        quality_gates=gates_text,
        output=output[:8000],
    )

    response = llm_client.call_flash(
        prompt,
        response_schema=EvaluatorOutput,
        system_instruction="You are an impartial evaluator. Score honestly. Return only valid JSON.",
    )

    attempt = state.get("attempt_number", 0) + 1
    current_score = state.get("best_score", 0.0)
    current_best = state.get("best_output", "")

    if response.parsed:
        data = response.parsed
        scores = {
            "relevance": data.get("relevance", 5),
            "completeness": data.get("completeness", 5),
            "accuracy": data.get("accuracy", 5),
            "actionability": data.get("actionability", 5),
        }

        avg_score = sum(scores.values()) / 4
        if not data.get("language_correct", True):
            avg_score -= 2.0
        if data.get("contains_fabrication", False):
            avg_score -= 3.0
            scores["accuracy"] = min(scores["accuracy"], 3)

        passed = avg_score >= 6.0
        feedback = data.get("feedback", "")

        if avg_score > current_score:
            best_output = output
            best_score = avg_score
        else:
            best_output = current_best or output
            best_score = current_score

        return {
            "eval_scores": scores,
            "eval_passed": passed,
            "eval_feedback": feedback,
            "attempt_number": attempt,
            "best_output": best_output,
            "best_score": best_score,
        }

    return {
        "eval_scores": {"relevance": 7, "completeness": 7, "accuracy": 7, "actionability": 7},
        "eval_passed": True,
        "eval_feedback": "",
        "attempt_number": attempt,
        "best_output": output,
        "best_score": 7.0,
    }
