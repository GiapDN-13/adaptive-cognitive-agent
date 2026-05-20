from smart_agent.prompts.persona import MEKONG_PERSONALITY, PERSONA_PROMPTS


def build_executor_system_prompt(
    persona: str,
    language: str,
    domain_rules: list[str],
    anti_patterns: list[str],
    quality_gates: list[str],
    cognitive_output: dict | None = None,
) -> str:
    persona_prompt = PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["Generalist"])

    sections = [
        MEKONG_PERSONALITY,
        f"\n## Your Expertise (Persona: {persona})\n{persona_prompt}",
    ]

    if domain_rules:
        rules_text = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(domain_rules))
        sections.append(f"\n## Domain Rules (MUST FOLLOW)\n{rules_text}")

    if anti_patterns:
        ap_text = "\n".join(f"  - {ap}" for ap in anti_patterns)
        sections.append(f"\n## Anti-Patterns (MUST AVOID)\n{ap_text}")

    if quality_gates:
        qg_text = "\n".join(f"  - {qg}" for qg in quality_gates)
        sections.append(f"\n## Quality Gates (OUTPUT MUST SATISFY)\n{qg_text}")

    if cognitive_output:
        cog_text = _format_cognitive_output(cognitive_output)
        sections.append(f"\n## Strategic Framework Analysis\n{cog_text}")

    sections.append(
        "\n## CRITICAL: Anti-Hallucination Rules\n"
        "- NEVER fabricate specific factual details the user has NOT provided: "
        "company names, phone numbers, addresses, emails, pricing, team names, "
        "testimonials, statistics, or any claim presented as fact.\n"
        "- If specific info is needed but missing, use EXPLICIT PLACEHOLDERS: "
        "[TÊN CÔNG TY], [SỐ ĐIỆN THOẠI], [ĐỊA CHỈ], [EMAIL], [DỊCH VỤ CỤ THỂ], [GIÁ].\n"
        "- At the end of your response, list missing info: "
        "'⚠️ Cần bổ sung: [list what placeholders need to be filled]'.\n"
        "- Only include specifics that: (a) user explicitly stated, "
        "(b) verifiable general knowledge, or (c) obtained via web_search.\n"
        "- It is BETTER to have placeholders than to invent convincing-sounding fake data."
    )

    lang_name = "Vietnamese" if language == "vi" else "English"
    sections.append(
        f"\n## Instructions\n"
        f"- Respond in {lang_name}\n"
        f"- Think step by step before answering\n"
        f"- Use tools when you need computation or external information\n"
        f"- Your response must satisfy ALL quality gates above\n"
        f"- Be thorough but avoid unnecessary padding"
    )

    return "\n".join(sections)


def _format_cognitive_output(cognitive_output: dict) -> str:
    parts = []
    for key, value in cognitive_output.items():
        if isinstance(value, dict):
            formatted = "\n".join(f"    - {k}: {v}" for k, v in value.items())
            parts.append(f"  **{key}:**\n{formatted}")
        elif isinstance(value, list):
            formatted = "\n".join(f"    - {item}" for item in value)
            parts.append(f"  **{key}:**\n{formatted}")
        else:
            parts.append(f"  **{key}:** {value}")
    return "\n".join(parts)
