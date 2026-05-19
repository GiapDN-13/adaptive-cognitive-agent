from typing import TypedDict


class AgentState(TypedDict, total=False):
    user_input: str
    conversation_history: list[dict]

    # Perceiver output
    language: str
    domains: list[str]
    complexity_score: int
    needs_search: bool
    needs_clarification: bool
    is_trivial: bool

    # Trivial
    trivial_response: str

    # Clarification
    clarification_questions: list[str]

    # Meta-Thinker output
    persona: str
    thinking_depth: int
    domain_rules: list[str]
    anti_patterns: list[str]
    quality_gates: list[str]
    needs_full_framework: bool

    # Cognitive Framework output
    cognitive_output: dict

    # Executor
    final_output: str
    tool_calls: list[dict]
    react_iterations: int

    # Evaluator
    eval_scores: dict
    eval_passed: bool
    eval_feedback: str

    # Retry
    attempt_number: int
    retry_strategy: str
    best_output: str
    best_score: float
