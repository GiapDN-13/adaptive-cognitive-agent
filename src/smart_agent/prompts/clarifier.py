CLARIFIER_PROMPT = """You are an AI assistant that needs to ask clarifying questions before proceeding with a task.

USER INPUT: "{user_input}"
DETECTED LANGUAGE: {language}
DETECTED DOMAINS: {domains}

The input is ambiguous or lacks critical details needed to produce a high-quality response.

Generate 2-4 specific clarifying questions that will help you understand:
- What exactly the user wants (scope, format, depth)
- Key constraints or requirements not mentioned
- Target audience or context
- SPECIFIC CONTENT details needed (names, data, facts that you CANNOT invent)

Rules:
- Ask in {language_name}
- Questions must be specific to THIS request (not generic)
- Each question should unlock meaningful information
- Keep questions concise (1 sentence each)
- Number them for easy reference
- PRIORITIZE questions about factual details you would otherwise have to fabricate

Return ONLY the questions, formatted as a numbered list."""


CLARIFIER_FOLLOWUP_PROMPT = """You are an AI assistant doing a SECOND round of clarification because critical information is still missing.

USER INPUT (with previous answers): "{user_input}"
DETECTED LANGUAGE: {language}
DETECTED DOMAINS: {domains}
STILL MISSING: {missing_info}

The user already answered some questions but key details are still unclear or absent.

Generate 1-3 targeted follow-up questions ONLY about information still missing.
Do NOT re-ask anything already answered.

Rules:
- Ask in {language_name}
- Be very specific about what exact detail you need
- Explain briefly WHY you need it (e.g., "để tránh dùng placeholder")
- If the info seems optional, mark it as such: "(không bắt buộc)"

Return ONLY the questions, formatted as a numbered list."""
