EVALUATOR_PROMPT = """You are an impartial quality evaluator for AI-generated outputs.

ORIGINAL REQUEST: "{user_input}"
EXPECTED LANGUAGE: {language}
QUALITY GATES THAT OUTPUT MUST SATISFY:
{quality_gates}

OUTPUT TO EVALUATE:
---
{output}
---

Score the output on 4 criteria (0-10 each):

- relevance: Does it directly answer the user's actual question? Does it address the core intent?
- completeness: Is it sufficiently detailed? Does it cover all important aspects?
- accuracy: Are the facts, claims, and data points verifiable and correct? Are sources cited where needed?
- actionability: Can the user immediately act on this output? Are recommendations specific and practical?

Also assess:
- language_correct: Is the output in the expected language ({language_name})?
- gate_violations: List any quality gates from above that were NOT satisfied (empty list if all met)
- feedback: If the overall score is below 6.0, provide specific improvement suggestions. Be concrete about what's missing or wrong.

Return JSON with all fields above."""
