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
        f"## CRITICAL: Landing Page / Website Generation\n"
        f"When the user asks to create a landing page, website, or web page:\n"
        f"1. Use think() to plan what content to include\n"
        f"2. If user mentions a company/entity → use web_search to get REAL info first\n"
        f"3. Use generate_landing_page() tool with a JSON config string containing:\n"
        f"   - company_name, tagline, description, primary_color, accent_color\n"
        f"   - services: [{{name, description, icon}}]\n"
        f"   - features: [string list]\n"
        f"   - stats: [{{value, label}}]\n"
        f"   - testimonials: [{{quote, author, role}}]\n"
        f"   - contact: {{phone, email, address}}\n"
        f"   - cta_text, nav_links, hero_subtitle, footer_text\n"
        f"4. The tool returns COMPLETE HTML — just pass it to the user\n"
        f"5. ONLY include data you actually have. Use placeholders for missing info.\n\n"
        f"NEVER write raw HTML manually for landing pages — ALWAYS use generate_landing_page tool.\n\n"
        f"## Long Content Generation (non-landing-page)\n"
        f"For other long content (documents, long code), use code_executor to build in parts:\n"
        f"1. Use think() to plan the structure\n"
        f"2. Use code_executor() to generate each section\n"
        f"3. Combine all sections in your final response"
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
