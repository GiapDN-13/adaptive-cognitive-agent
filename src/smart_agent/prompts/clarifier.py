CLARIFIER_PROMPT = """You are an AI assistant that needs to ask clarifying questions before proceeding with a task.

USER INPUT: "{user_input}"
DETECTED LANGUAGE: {language}
DETECTED DOMAINS: {domains}

The input is ambiguous or lacks critical details needed to produce a high-quality response.

Generate 2-4 specific clarifying questions that will help you understand:
- What exactly the user wants (scope, format, depth)
- Key constraints or requirements not mentioned
- Target audience or context

Rules:
- Ask in {language_name}
- Questions must be specific to THIS request (not generic)
- Each question should unlock meaningful information
- Keep questions concise (1 sentence each)
- Number them for easy reference

Return ONLY the questions, formatted as a numbered list."""
