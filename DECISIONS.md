# SmartAgent — Design Decisions & Context

## Ngày: 19/05/2026

---

## Bối cảnh dự án

| Mục | Chi tiết |
|-----|----------|
| **Mục đích** | SmartAgent là "bộ não" trung tâm — sau này điều phối, sinh sub-agents, tools, skills, tạo mạng lưới agent chuyên trách |
| **Giai đoạn** | Mới bắt đầu (chỉ có design doc, chưa có code) |
| **Team** | 1 người, full-stack + AI/ML chuyên sâu |
| **Timeline** | MVP trong 2-4 tuần |
| **MVP scope** | Chạy được full pipeline 1 task (Perceive → MetaThink → Execute → Evaluate) |
| **Infra** | Local/Docker trước |
| **LLM Provider** | Gemini all (Flash cho nhẹ, Pro cho nặng) — đã có API access, dùng thường xuyên |
| **Điểm khó nhất** | Meta-Think + Cognitive Framework, Self-evaluation + Retry, Orchestration tổng thể |

---

## Quyết định thiết kế

### 1. Perceiver Mechanism
**Quyết định:** Dùng LLM nhẹ (Gemini Flash)
**Lý do:** Chính xác hơn keyword matching, chấp nhận thêm ~0.5-1s latency
**Note:** Cần update doc — hiện doc ghi "không gọi AI" nhưng thực tế sẽ dùng Flash

### 2. Meta-Think Calls
**Quyết định:** Adaptive — 1 call cho depth ≤3, nhiều calls cho depth 4-5
**Lý do:** Cân bằng giữa tốc độ (task đơn giản) và chất lượng (task chiến lược)

### 3. Cognitive Framework Flow
**Quyết định:** Sequential (chuỗi)
**Lý do:** Mỗi bước xây trên kết quả bước trước, đảm bảo coherent

### 4. LLM Stack
**Quyết định:** Single provider — Gemini all (Flash + Pro)
**Lý do:** Đơn giản ops, đã quen dùng, đủ cho MVP

### 5. Embedding / Memory
**Quyết định:** CHƯA QUYẾT ĐỊNH
**Note:** Cần experiment. Có thể dùng Gemini Embedding hoặc open-source multilingual (e5/bge). Qdrant cho vector store.

### 6. ReACT Loop Limit
**Quyết định:** Adaptive theo depth
- Depth 1-2: max 3 iterations
- Depth 3: max 5 iterations
- Depth 4-5: max 8 iterations

### 7. Evaluation Criteria
**Quyết định:** 4 tiêu chí
- Relevance (0-10): Có trả lời đúng câu hỏi không?
- Completeness (0-10): Có đủ chi tiết không?
- Accuracy (0-10): Facts/data có chính xác không?
- Actionability (0-10): User có thể hành động từ output không?
- Language: YES/NO

**Công thức:** Score = (R + C + A + Act) / 4. Sai ngôn ngữ: -2. Pass ≥ 6.0

### 8. Retry Strategy
**Quyết định:** Retry thông minh
- Evaluator phân loại lý do fail (thiếu data / thiếu depth / sai hướng)
- Thiếu data → force search trước khi retry
- Sai hướng → đổi persona/approach
- Không chỉ "cố gắng hơn" mà thay đổi strategy

### 9. Pattern Decay
**Quyết định:** Cả hai — time decay + counter-evidence override
- Patterns giảm confidence theo thời gian nếu không được reinforce
- 1 failure có thể override nhiều successes (penalty > reward)
- Pattern không bao giờ "vĩnh viễn"

---

---

## Tech Choices

| Mục | Quyết định |
|-----|-----------|
| **Ngôn ngữ** | Python |
| **Orchestration** | LangGraph |
| **LLM SDK** | google-genai (Gemini Flash + Pro) |
| **Code style** | Class-based OOP |
| **Testing** | Unit test (mock LLM) + Integration test e2e + Eval suite (prompt testing) |
| **UI** | Streamlit đơn giản (demo thinking process) |
| **Infra** | Local/Docker |
| **Vector DB** | Qdrant (cho memory system — sau MVP) |

---

## Ghi chú thêm
- Memory system để sau MVP (focus pipeline trước)
- Sub-agent orchestration là vision dài hạn, MVP chỉ cần 1 agent chạy full pipeline
- Cần update SMART_AGENT_COGNITIVE_CORE.md với các decisions ở trên
