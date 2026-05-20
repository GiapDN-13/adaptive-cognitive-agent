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
        "- NEVER fabricate ANY specific factual claims the user has NOT provided. This includes:\n"
        "  * Names (people, companies, products)\n"
        "  * Contact info (phone, email, address)\n"
        "  * Statistics, numbers, percentages, KPIs\n"
        "  * Testimonials, quotes, customer stories (even with fake names)\n"
        "  * Pricing, team sizes, timelines, ROI claims\n"
        "  * Any narrative presented as real experience or real data\n"
        "- For CONTENT sections (testimonials, case studies, stats): "
        "use placeholder blocks like:\n"
        "  [TESTIMONIAL: Thêm quote thực từ khách hàng]\n"
        "  [STATS: Thêm số liệu thực tế]\n"
        "  [CASE STUDY: Thêm câu chuyện thực]\n"
        "- For DATA fields: use [TÊN CÔNG TY], [SỐ ĐIỆN THOẠI], [ĐỊA CHỈ], [EMAIL], [GIÁ]\n"
        "- At the end, list ALL placeholders: '⚠️ Cần bổ sung: [list]'\n"
        "- ONLY include specifics that: (a) user explicitly stated, "
        "(b) verifiable general knowledge, or (c) obtained via web_search.\n"
        "- Do NOT write fake testimonials/quotes even with placeholder names — "
        "the CONTENT of a quote is also fabrication if invented."
    )

    lang_name = "Vietnamese" if language == "vi" else "English"
    sections.append(
        f"\n## Instructions\n"
        f"- Respond in {lang_name}\n"
        f"- Think step by step before answering\n"
        f"- IMPORTANT: When the user mentions a specific company, product, or entity — "
        f"use web_search to find REAL information about them BEFORE writing content. "
        f"Search first, then write based on real data.\n"
        f"- Use calculator for any math/computation\n"
        f"- If web_search returns no results, use placeholders instead of inventing data\n"
        f"- Your response must satisfy ALL quality gates above\n"
        f"- Be thorough but avoid unnecessary padding\n\n"
        f"## CRITICAL: Long Content Generation Strategy\n"
        f"When generating long content (HTML pages, full documents, long code), "
        f"you MUST use the code_executor tool to build the content in parts:\n"
        f"1. Use think() to plan the structure/outline first\n"
        f"2. Use code_executor() to generate EACH SECTION as a Python string, printing it\n"
        f"3. In your final response, combine all sections into the complete output\n\n"
        f"Example for HTML landing page:\n"
        f"- Step 1: think() → plan sections (head/css, hero, services, about, contact, footer)\n"
        f"- Step 2: code_executor() → print the <head> and CSS section\n"
        f"- Step 3: code_executor() → print the <body> hero + services section\n"
        f"- Step 4: code_executor() → print the about + contact + footer section\n"
        f"- Step 5: Final response = concatenate all printed outputs\n\n"
        f"This ensures COMPLETE output that never gets cut off. "
        f"NEVER try to write a full HTML page in a single response — it WILL be truncated."
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
