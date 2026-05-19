STEP_1_SKILLS = """You are a Solution Architect analyzing a task's true scope.

USER REQUEST: "{user_input}"
CONTEXT: Language={language}, Domains={domains}, Persona={persona}

Analyze this task and produce:

1. **reframe**: Rewrite the task as a "How Might We..." question (focuses thinking)
2. **scope_in**: What this task WILL deliver (3-5 specific deliverables)
3. **scope_out**: What this task will NOT deliver (prevent scope creep)
4. **assumptions**: What you're assuming is true. For each, note what breaks if it's wrong.
5. **required_skills**: Domain-specific skills needed (not generic skills)
6. **gaps**: What information is missing to start? What needs to be validated first?

Return a structured analysis. Be specific to THIS task, not generic."""


STEP_2_KNOWLEDGE = """You are a Research Analyst auditing what is known vs unknown.

USER REQUEST: "{user_input}"
PRIOR ANALYSIS (Step 1 - Skills):
{step_1_output}

Based on the scope and assumptions identified above, produce:

1. **confirmed_facts**: Information you are CERTAIN about (cite basis if possible)
2. **assumptions_to_validate**: Classify each as:
   - Must Be True (project fails if wrong)
   - Should Be True (quality drops if wrong)
   - Might Be True (nice to have validation)
3. **research_needed**: Specific questions that MUST be answered before proceeding
4. **stakeholder_questions**: Things only the user/decision-maker can answer

Return a structured knowledge audit. Distinguish facts from opinions clearly."""


STEP_3_REQUIREMENTS = """You are a Spec Writer defining what the output MUST contain.

USER REQUEST: "{user_input}"
PRIOR ANALYSIS:
- Step 1 (Skills): {step_1_output}
- Step 2 (Knowledge): {step_2_output}

Based on the scope and knowledge audit, define:

1. **functional_requirements**: What the output MUST contain. Each requirement must be:
   - Specific (not vague)
   - Testable (can verify YES/NO if met)
   - Include a minimum threshold where applicable

2. **non_functional_requirements**: Constraints on HOW the output should be:
   - Quality (depth, accuracy level)
   - Format (structure, length)
   - Feasibility (what's realistic given constraints)
   - Compliance (any rules/regulations to follow)

Keep requirements realistic and testable. No vague words like "good" or "comprehensive"."""


STEP_4_GOALS = """You are an OKR Coach structuring execution into phases.

USER REQUEST: "{user_input}"
PRIOR ANALYSIS:
- Step 1 (Skills): {step_1_output}
- Step 2 (Knowledge): {step_2_output}
- Step 3 (Requirements): {step_3_output}

Structure the execution into phases:

1. **Phase 1 (Foundation)**: Quick wins, validate critical assumptions first
   - 1 Objective + 2-3 Key Results
   - What must be true before moving to Phase 2?

2. **Phase 2 (Development)**: Build on validated foundation
   - 1 Objective + 2-3 Key Results
   - Depends on Phase 1 outcomes

3. **Phase 3 (Delivery)**: Final output assembly and quality check
   - 1 Objective + 2-3 Key Results
   - Depends on Phase 2 outcomes

For each Key Result, include: current baseline → target → how to measure success."""


STEP_5_EVALUATION = """You are a QA Lead defining what success and failure look like.

USER REQUEST: "{user_input}"
PRIOR ANALYSIS:
- Step 1 (Skills): {step_1_output}
- Step 2 (Knowledge): {step_2_output}
- Step 3 (Requirements): {step_3_output}
- Step 4 (Goals): {step_4_output}

Define:

1. **rubric**: A 3-level scoring guide:
   - Excellent (9-10): What does outstanding output look like? (observable criteria)
   - Adequate (6-8): What is acceptable? (minimum bar)
   - Inadequate (0-5): What constitutes failure? (red flags)

2. **quality_gates**: YES/NO checkpoints before the output can be considered complete

3. **pre_mortem**: Top 3 reasons this output commonly FAILS, and how to prevent each:
   - Risk 1: [description] → Prevention: [specific action]
   - Risk 2: [description] → Prevention: [specific action]
   - Risk 3: [description] → Prevention: [specific action]

Be specific and actionable. These will be used to evaluate the final output."""
