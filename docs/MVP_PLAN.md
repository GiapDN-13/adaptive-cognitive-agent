# SmartAgent MVP — Implementation Plan

## Context

MekongAI cần xây dựng SmartAgent — "bộ não" trung tâm có khả năng adaptive thinking (tự điều chỉnh mức độ suy nghĩ theo complexity của task). MVP scope: 1 agent chạy full pipeline end-to-end. Timeline: 2-4 tuần, 1 developer (AI/ML expert, quen Gemini).

**Mục tiêu MVP:** Chứng minh pipeline Perceive → MetaThink → Execute → Evaluate hoạt động, và visible khác biệt so với chatbot thường.

---

## Project Structure

```
mekongai-smart-agent/
├── pyproject.toml
├── Makefile
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── src/
│   └── smart_agent/
│       ├── __init__.py
│       ├── config.py               # pydantic-settings
│       ├── models.py               # Pydantic data models
│       ├── llm.py                  # Gemini Flash/Pro client wrapper
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── builder.py          # LangGraph graph construction
│       │   └── state.py            # AgentState TypedDict
│       ├── nodes/
│       │   ├── __init__.py
│       │   ├── perceiver.py
│       │   ├── trivial.py
│       │   ├── clarifier.py
│       │   ├── meta_thinker.py
│       │   ├── cognitive.py        # 5-step framework (depth 4-5)
│       │   ├── executor.py         # ReACT loop
│       │   ├── evaluator.py
│       │   ├── retry.py
│       │   └── self_update.py      # Stub for MVP
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── web_search.py
│       │   ├── read_url.py
│       │   ├── calculator.py
│       │   └── think.py
│       ├── prompts/
│       │   ├── __init__.py
│       │   ├── perceiver.py
│       │   ├── meta_thinker.py
│       │   ├── cognitive.py
│       │   ├── executor.py
│       │   ├── evaluator.py
│       │   └── persona.py
│       ├── memory/
│       │   └── store.py            # In-memory dict (MVP placeholder)
│       └── ui/
│           └── app.py              # Streamlit
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── evals/
│       ├── eval_runner.py
│       └── cases/
└── docs/
```

---

## LangGraph Graph Design

### State Schema

```python
class AgentState(TypedDict):
    user_input: str
    conversation_history: list[dict]
    language: str                    # "vi" | "en"
    domains: list[str]
    complexity_score: int            # 0-10
    needs_search: bool
    needs_clarification: bool
    is_trivial: bool
    trivial_response: str | None
    clarification_questions: list[str] | None
    persona: str
    thinking_depth: int              # 1-5
    domain_rules: list[str]
    anti_patterns: list[str]
    quality_gates: list[str]
    needs_full_framework: bool
    cognitive_output: dict | None
    final_output: str
    tool_calls: list[dict]
    react_iterations: int
    eval_scores: dict | None
    eval_passed: bool
    eval_feedback: str | None
    attempt_number: int
    retry_strategy: str | None
    best_output: str
    best_score: float
```

### Graph Topology

```
START → [perceiver]
  → (is_trivial?) → YES → [trivial_respond] → END
  → (needs_clarification?) → YES → [clarifier] → END
  → [meta_thinker]
    → (needs_full_framework?) → YES → [cognitive_framework]
    → [executor] (ReACT loop)
      → [evaluator]
        → (passed OR attempt >= 3?) → [format_output] → END
        → [retry_strategist] → [executor] (loop back)
```

### Conditional Routing

```python
def route_after_perceiver(state: AgentState) -> str:
    if state["is_trivial"]:
        return "trivial_respond"
    if state["needs_clarification"]:
        return "clarifier"
    return "meta_thinker"

def route_after_meta_thinker(state: AgentState) -> str:
    if state["needs_full_framework"]:
        return "cognitive_framework"
    return "executor"

def route_after_evaluator(state: AgentState) -> str:
    if state["eval_passed"] or state["attempt_number"] >= 3:
        return "format_output"
    return "retry_strategist"
```

---

## Week-by-Week Plan

### Week 1: Foundation + Core Pipeline

| Day | Task | Milestone |
|-----|------|-----------|
| 1-2 | Project setup + LLM client + Perceiver + Trivial + first 3-node graph | "Xin chào" instant response, complex input classified correctly |
| 3-4 | Meta-Thinker node (persona, depth, rules, anti-patterns, quality gates) | Any input → picks correct persona + depth + relevant rules |
| 5-7 | Executor (ReACT loop + tools: web_search, calculator, think) | Agent reasons, calls tools, produces output for medium task |

### Week 2: Evaluation + Cognitive Framework

| Day | Task | Milestone |
|-----|------|-----------|
| 8-9 | Evaluator + Smart Retry | Agent retries and improves when score < 6.0 |
| 10-12 | Cognitive Framework (5 sequential steps, depth 4-5 only) | "Chiến lược AI cho ngân hàng" triggers full 5-step framework |
| 13-14 | Clarifier + full graph wiring + e2e testing | Full pipeline works: trivial, medium, complex |

### Week 3: UI + Testing

| Day | Task | Milestone |
|-----|------|-----------|
| 15-17 | Streamlit UI (show thinking process, ReACT steps, eval scores) | Demo-ready UI showing "this is not a chatbot" |
| 18-19 | Unit tests + integration tests + eval suite (10-15 cases) | Test suite passes, eval > 80% |
| 20-21 | Self-Update stub + in-memory pattern store | Agent "remembers" within session |

### Week 4: Docker + Hardening

| Day | Task | Milestone |
|-----|------|-----------|
| 22-23 | Docker + docker-compose | `docker-compose up` runs full app |
| 24-25 | Error handling, token budget, timeout, edge cases | Robust against LLM failures |
| 26-28 | Buffer: bug fixes, prompt tuning, demo prep | Polished MVP |

---

## Day 1 Starter (Chi tiết)

1. `uv init` + install deps: `langgraph`, `google-genai`, `pydantic`, `pydantic-settings`, `python-dotenv`
2. `config.py` — Settings class (GOOGLE_API_KEY, model names)
3. `llm.py` — `call_flash()` + `call_pro()` wrappers with structured output support
4. `graph/state.py` — AgentState TypedDict (minimal fields first)
5. `nodes/perceiver.py` — 1 Flash call, returns classification
6. `nodes/trivial.py` — instant friendly response
7. `graph/builder.py` — 3-node graph: perceiver → trivial/placeholder
8. `main.py` — invoke graph, print state

**End of Day 1:** Graph chạy, "Xin chào" → instant, "Phân tích thị trường" → classified but TODO.

---

## Prompt Architecture

### Perceiver Prompt (Gemini Flash, structured JSON output)

```
ROLE: Input classifier for an AI cognitive engine.
TASK: Analyze user input and return structured classification.

Return JSON:
- language: "vi" | "en"
- domains: list from [tech, business, marketing, data, security, finance, creative, general]
- complexity_score: 0-10
- is_trivial: boolean
- needs_clarification: boolean
- needs_search: boolean
```

### Meta-Thinker Prompt (Gemini Flash, structured JSON output)

```
ROLE: Meta-cognitive planner deciding HOW the agent should think.

Return JSON:
- persona: one of [CTO, PM, TechLead, Analyst, Creative, Generalist]
- thinking_depth: 1-5
- domain_rules: 3-5 specific constraints for THIS task
- anti_patterns: 2-3 common mistakes to avoid
- quality_gates: 2-3 testable output criteria
- needs_full_framework: boolean (true if depth >= 4)
```

### Evaluator Prompt (Gemini Flash, structured JSON output)

```
ROLE: Impartial quality evaluator.

Score 0-10 on:
- relevance: answers the actual question?
- completeness: sufficient detail?
- accuracy: facts correct?
- actionability: user can act on this?

Also: language_correct (boolean), feedback (improvement suggestions)
```

### Executor System Prompt (assembled dynamically)

```
You are {persona_name}, expert AI assistant by MekongAI.
{mekong_personality}
{persona_expertise}

MUST FOLLOW: {domain_rules}
MUST AVOID: {anti_patterns}
OUTPUT MUST SATISFY: {quality_gates}
{cognitive_framework_output_if_exists}

Respond in {language}. Use tools when needed.
```

---

## Key Dependencies

```toml
[project.dependencies]
langgraph = ">=0.2"
google-genai = ">=1.0"
pydantic = ">=2.0"
pydantic-settings = ">=2.0"
python-dotenv = ">=1.0"
streamlit = ">=1.35"
httpx = ">=0.27"

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "ruff"]
```

---

## google-genai SDK Pattern

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=YourPydanticModel,
        temperature=0.2,
    )
)
```

---

## Token Budget (ước tính)

| Component | Model | Tokens/call |
|-----------|-------|-------------|
| Perceiver | Flash | ~300 total |
| Meta-Thinker | Flash | ~700 total |
| Cognitive (x5) | Flash/Pro | ~1400 each |
| Executor (per iter) | Pro | ~3000 each |
| Evaluator | Flash | ~1700 total |

Depth 5 complex task: ~15,000-20,000 tokens total. Cost: ~$0.02-0.05/request.

---

## Risk Mitigation (Nếu trễ deadline)

| Ưu tiên cắt | Cái gì | Impact |
|-------------|--------|--------|
| 1 | Self-Update → stub (log only) | Thấp |
| 2 | Cognitive Framework: 5 bước → 3 bước | Trung bình |
| 3 | Clarifier → skip (luôn proceed) | Thấp |
| 4 | Evaluator: 4 criteria → 2 | Thấp |
| 5 | Smart Retry → dumb retry | Trung bình |
| 6 | Streamlit → CLI-only | Trung bình |

---

## Verification Plan

1. **Unit tests:** Mock LLM responses, test each node independently
2. **Integration tests:** 3 scenarios (trivial / medium / complex)
3. **Eval suite:** 10-15 JSON test cases with expected behaviors
4. **Streamlit demo:** Visual inspection of thinking process display
5. **Docker:** `docker-compose up` → app at localhost:8501
