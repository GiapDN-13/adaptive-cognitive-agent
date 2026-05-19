PERCEIVER_PROMPT = """Analyze the user input and classify it.

CONVERSATION HISTORY (recent):
{conversation_history}

CURRENT INPUT: "{user_input}"

IMPORTANT: Consider the conversation history when classifying. If the user previously received clarification questions and is now answering them or saying "OK do it", this is NOT trivial — it's a continuation that should proceed with the full pipeline.

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
- is_trivial: true ONLY if input is a standalone greeting/thanks/farewell with NO actionable request. Examples of trivial: "Xin chào", "Cảm ơn", "Hi". Examples of NOT trivial: any math/computation, any request to create/write/explain/compare/analyze something, any question requiring reasoning. If there is conversation history with a pending task, this is NOT trivial.
- needs_clarification: true if input has action verb + generic subject + few details (e.g. "Tạo landing page" without specifics) AND no prior clarification was already done
- needs_search: true if answering requires current/external information not in general knowledge"""
