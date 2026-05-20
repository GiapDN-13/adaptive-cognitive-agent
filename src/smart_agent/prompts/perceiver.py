PERCEIVER_PROMPT = """Analyze the user input and classify it.

CONVERSATION HISTORY (recent):
{conversation_history}

CURRENT INPUT: "{user_input}"

CLASSIFICATION RULES (follow strictly):

1. FOLLOW-UP DETECTION: If conversation history shows the assistant previously generated a detailed response (code, content, analysis) AND the current input references that output (e.g. "bị thiếu", "cung cấp lại", "sửa lại", "thêm phần", "expand", "more detail", "not enough", "tiếp tục", "làm lại"), then:
   - is_trivial = false
   - needs_clarification = false
   - complexity_score = same as or higher than the previous task

2. POST-CLARIFICATION: If the user previously received clarification questions and is now answering them or saying "OK do it" / "thực hiện đi", this is NOT trivial.

3. TRIVIAL: is_trivial = true ONLY for standalone greetings/thanks/farewells with NO reference to prior conversation AND no actionable request. Examples: "Xin chào" (empty history), "Cảm ơn", "Hi". NOT trivial: any math, any create/write/explain/compare/analyze request, any follow-up to prior output.

Return JSON with these fields:
- language: "vi" or "en" (detect from input)
- domains: list of relevant domains from ["tech", "business", "marketing", "data", "security", "finance", "creative", "general"]
- complexity_score: integer 0-10. Scoring guide:
  - Base 2 for any non-trivial request
  - +2 for each domain beyond the first
  - +2 if involves production/security/payment
  - +1 if needs current/external information
  - +1 if creative/brainstorm required
  - -1 if output format is clear and simple
  - For follow-ups: match or exceed original task complexity
- is_trivial: see rule 3 above
- needs_clarification: true if input has action verb + generic subject + few details AND no prior clarification was already done AND this is NOT a follow-up
- needs_search: true if answering requires current/external information not in general knowledge"""
