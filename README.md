# 🧠 SmartAgent — Adaptive Cognitive Engine

> **MekongAI SmartAgent** — Bộ não trung tâm có khả năng tự điều chỉnh mức độ suy nghĩ theo complexity của task. Không phải chatbot thông thường.

---

## Tổng quan

SmartAgent là một AI Agent pipeline sử dụng kiến trúc **adaptive thinking** — tự động phân tích độ phức tạp của input và điều chỉnh chiến lược xử lý phù hợp:

- **Task đơn giản** ("Xin chào") → trả lời ngay, không qua pipeline
- **Task trung bình** ("Viết function Python") → ReACT loop với tools
- **Task phức tạp** ("Chiến lược AI cho ngân hàng") → 5-step cognitive framework + ReACT + evaluation + retry

---

## Kiến trúc Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INPUT                                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     PERCEIVER       │
                    │  • Ngôn ngữ (vi/en) │
                    │  • Domains          │
                    │  • Complexity 0-10  │
                    │  • Trivial?         │
                    │  • Cần clarify?     │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
     ┌──────────────┐  ┌────────────┐  ┌──────────────┐
     │   TRIVIAL    │  │ CLARIFIER  │  │ META-THINKER │
     │  Trả lời    │  │ Hỏi thêm   │  │ • Persona    │
     │  ngay lập   │  │ 2-4 câu    │  │ • Depth 1-5  │
     │  tức        │  │ (max 2     │  │ • Rules      │
     │             │  │  rounds)   │  │ • Gates      │
     └──────┬───────┘  └─────┬──────┘  └──────┬───────┘
            │                │                 │
            ▼                ▼                 │
           END              END                │
                                              │
                               ┌──────────────┴──────────────┐
                               │      depth >= 4?            │
                               └──────┬──────────────┬───────┘
                                      │              │
                                      ▼              │
                          ┌────────────────────┐     │
                          │ COGNITIVE FRAMEWORK │     │
                          │ 5 bước tư duy:     │     │
                          │ 1. Skills          │     │
                          │ 2. Knowledge       │     │
                          │ 3. Requirements    │     │
                          │ 4. Goals           │     │
                          │ 5. Evaluation      │     │
                          └─────────┬──────────┘     │
                                    │                │
                                    ▼                ▼
                          ┌─────────────────────────────┐
                          │         EXECUTOR            │
                          │   ReACT Loop (3-6 iters)    │
                          │   + 6 Tools available       │
                          └──────────────┬──────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────┐
                          │        EVALUATOR            │
                          │  4 criteria (0-10 each):    │
                          │  Relevance | Completeness   │
                          │  Accuracy  | Actionability  │
                          │  + Hallucination detection  │
                          └──────────────┬──────────────┘
                                         │
                              ┌──────────┴──────────┐
                              │   Score >= 6.0?     │
                              └───┬─────────────┬───┘
                                  │             │
                              YES ▼          NO ▼ (max 3 attempts)
                          ┌───────────┐  ┌──────────────┐
                          │  OUTPUT   │  │    RETRY     │
                          │  FINAL    │  │ Đổi strategy │
                          └───────────┘  └──────┬───────┘
                                                │
                                                └──→ EXECUTOR (loop)
```

---

## Tools (6 công cụ)

| Tool | Chức năng | Ví dụ sử dụng |
|------|-----------|---------------|
| `web_search` | Tìm kiếm web (DuckDuckGo) | Search thông tin công ty, data mới nhất |
| `read_url` | Đọc nội dung từ URL | Fetch chi tiết từ link search results |
| `calculator` | Tính toán toán học | `15% * 2500000`, `math.sqrt(144)` |
| `code_executor` | Chạy Python code | Test algorithm, xử lý data |
| `think` | Tổ chức reasoning | Phân tích trước khi trả lời |
| `get_datetime` | Lấy ngày/giờ hiện tại | Timezone Vietnam (UTC+7) |

---

## Cấu trúc dự án

```
mekongai-smart-agent/
├── src/smart_agent/
│   ├── config.py                # Cấu hình (Pydantic Settings)
│   ├── llm.py                   # LLM client (Bedrock + Gemini)
│   ├── graph/
│   │   ├── builder.py           # LangGraph orchestration
│   │   └── state.py             # AgentState schema
│   ├── nodes/
│   │   ├── perceiver.py         # Phân loại input
│   │   ├── trivial.py           # Trả lời nhanh
│   │   ├── clarifier.py         # Hỏi thêm (multi-round)
│   │   ├── meta_thinker.py      # Chọn persona + depth
│   │   ├── cognitive.py         # 5-step strategic thinking
│   │   ├── executor.py          # ReACT loop + tools
│   │   ├── evaluator.py         # Chấm điểm output
│   │   └── retry.py             # Đổi chiến lược retry
│   ├── tools/
│   │   ├── web_search.py        # DuckDuckGo search
│   │   ├── read_url.py          # HTTP fetch + extract text
│   │   ├── calculator.py        # Math eval (safe)
│   │   ├── code_executor.py     # Python exec sandbox
│   │   ├── think.py             # Reasoning buffer
│   │   └── datetime_tool.py     # Current date/time
│   ├── prompts/
│   │   ├── perceiver.py         # Classification rules
│   │   ├── clarifier.py         # Clarification templates
│   │   ├── meta_thinker.py      # Persona/depth selection
│   │   ├── cognitive.py         # 5-step framework prompts
│   │   ├── executor.py          # System prompt builder
│   │   ├── evaluator.py         # Quality assessment rubric
│   │   └── persona.py           # Personality + persona prompts
│   └── ui/
│       └── app.py               # Streamlit demo UI
├── .dev/tasks/                  # Task logs (6 bước mỗi task)
├── pyproject.toml               # Dependencies + build config
└── .env.example                 # Environment variables template
```

---

## Adaptive Thinking — Chi tiết

### Perceiver phân loại input:

| Loại | Điều kiện | Hành động |
|------|-----------|-----------|
| **Trivial** | Chào hỏi, cảm ơn, không action verb | Trả lời ngay (1 LLM call) |
| **Cần clarify** | Action verb + chủ đề chung, thiếu detail | Hỏi 2-4 câu (max 2 rounds) |
| **Medium** | Complexity 2-6, depth 1-3 | Meta-Think → Execute → Evaluate |
| **Complex** | Complexity 7-10, depth 4-5 | Meta-Think → Cognitive 5-step → Execute → Evaluate |

### Meta-Thinker chọn chiến lược:

| Persona | Khi nào | Focus |
|---------|---------|-------|
| **Analyst** | Data, research, phân tích | Structured, evidence-based |
| **Engineer** | Code, system design, tech | Implementation-focused |
| **Advisor** | Strategy, business, planning | High-level, ROI-oriented |
| **Creative** | Content, marketing, ideation | Original, engaging |
| **Generalist** | Mọi thứ khác | Balanced approach |

### Token Budget theo depth:

| Depth | Max Tokens | Max Iterations | Use case |
|-------|-----------|----------------|----------|
| 1-2 | 8,192 | 3 | Simple tasks |
| 3 | 16,384 | 4 | Medium content |
| 4-5 | 32,000 | 6 | Full pages, strategies |

---

## Anti-Hallucination System

SmartAgent có 3 lớp chống bịa thông tin:

1. **Executor rules**: Không được bịa tên, SĐT, địa chỉ, stats, testimonials. Phải dùng placeholder `[TÊN CÔNG TY]` hoặc search trước.

2. **Evaluator detection**: Phát hiện fabrication → trừ 3 điểm, accuracy cap 3/10 → trigger retry.

3. **Multi-round clarification**: Nếu thiếu info quan trọng sau round 1 → hỏi thêm round 2 (max 2 rounds).

---

## Cài đặt & Chạy

### 1. Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- AWS credentials (cho Bedrock) hoặc Google API key (cho Gemini)

### 2. Setup

```bash
# Clone
git clone <repo-url>
cd mekongai-smart-agent

# Install dependencies
uv sync

# Cấu hình environment
cp .env.example .env
# Sửa .env với credentials thật
```

### 3. Chạy UI

```bash
uv run streamlit run src/smart_agent/ui/app.py
```

Mở browser: http://localhost:8501

### 4. Chạy CLI test

```bash
uv run python main.py
```

---

## Environment Variables

```bash
# Provider: "bedrock" hoặc "gemini"
LLM_PROVIDER=bedrock

# AWS Bedrock
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
BEDROCK_LIGHT_MODEL=us.anthropic.claude-sonnet-4-6-v1
BEDROCK_HEAVY_MODEL=us.anthropic.claude-opus-4-6-v1

# Google Gemini (alternative)
GOOGLE_API_KEY=...
GEMINI_FLASH_MODEL=gemini-2.0-flash
GEMINI_PRO_MODEL=gemini-2.5-pro
```

---

## Evaluation Criteria

Output được chấm trên 4 tiêu chí (0-10):

| Tiêu chí | Mô tả | Penalty |
|-----------|--------|---------|
| **Relevance** | Có đúng ý user không? | — |
| **Completeness** | Đủ chi tiết không? | — |
| **Accuracy** | Chính xác không? Có bịa không? | Fabrication → cap 3/10 |
| **Actionability** | User có thể dùng ngay không? | — |

**Pass threshold**: Average >= 6.0
**Penalties**: Wrong language -2, Fabrication -3
**Max retry**: 3 attempts, chọn output score cao nhất

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | LangGraph |
| LLM (light) | Claude Sonnet 4.6 via Bedrock |
| LLM (heavy) | Claude Opus 4.6 via Bedrock |
| Web Search | DuckDuckGo (free, no API key) |
| UI | Streamlit |
| Config | Pydantic Settings |
| Package Manager | uv |
| Build System | Hatchling |

---

## Roadmap

- [x] Core pipeline (Perceive → Think → Execute → Evaluate)
- [x] Adaptive thinking depth (1-5)
- [x] Cognitive Framework (5-step strategic thinking)
- [x] ReACT loop với 6 tools
- [x] Smart retry với failure classification
- [x] Multi-round clarification
- [x] Anti-hallucination system
- [x] Streamlit UI với visible thinking process
- [ ] Docker + docker-compose
- [ ] Unit tests + eval suite
- [ ] Session memory (cross-conversation)
- [ ] Multi-agent orchestration

---

## License

Private — MekongAI Internal

---

*Built by MekongAI — "Không phải chatbot thông thường."*
