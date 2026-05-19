# Task: Cognitive Framework (5-Step Strategic Thinking)

## 1. Task chuẩn bị làm là gì
Implement Cognitive Framework — 5 bước tư duy chiến lược sequential cho tasks depth 4-5:
1. Skills (Solution Architect) — Reframe, scope, assumptions, gaps
2. Knowledge (Research Analyst) — Facts vs assumptions, cần research gì
3. Requirements (Spec Writer) — FR + NFR, testable criteria
4. Goals (OKR Coach) — Phased approach, objectives + key results
5. Evaluation (QA Lead) — Rubric, quality gates, pre-mortem

Mỗi bước = 1 LLM call, output bước trước làm input cho bước sau.

## 2. Làm như thế nào
- Viết 5 prompt templates (1 per step) trong prompts/cognitive.py
- Implement cognitive_node: gọi 5 LLM calls sequential, accumulate output
- Output tổng hợp inject vào executor system prompt qua cognitive_output field
- Chỉ trigger khi needs_full_framework=True (depth >= 4)

## 3. Ảnh hưởng ra sao
- Thay thế executor_node hiện tại ở node "cognitive_framework" trong graph
- cognitive_output sẽ được inject vào executor system prompt (đã có support)
- Tasks depth 4-5 sẽ chậm hơn (thêm 5 LLM calls) nhưng output chất lượng cao hơn

## 4. Triển khai như thế nào
- Step 1: Viết prompts/cognitive.py (5 prompt templates)
- Step 2: Viết nodes/cognitive.py (sequential 5-step pipeline)
- Step 3: Update graph/builder.py (wire cognitive → executor → evaluator)
- Step 4: Test with depth 4-5 task

## 5. Kiểm thử ra sao
- "Xây dựng chiến lược AI cho ngân hàng số" → triggers full 5 steps
- Mỗi step output coherent và builds on previous
- Cognitive output appears in executor context → influences final answer quality
- Compared to same task without framework: output should be more structured/strategic

## 6. Kết quả như thế nào
- [x] 5 steps execute sequentially (skills→knowledge→requirements→goals→evaluation)
- [x] Each step receives prior steps' output (accumulated context ~41K chars)
- [x] Cognitive output injected into executor (executor produced strategic 7.5K output)
- [x] Quality difference visible: output has executive summary, ROI analysis, risk matrix, phased roadmap
- [x] Timeout fixed (300s read_timeout in both llm.py and executor.py)
- [x] Total pipeline time: ~537s for depth 5 strategic task (acceptable)
- [x] Evaluator score: 6.2/10 PASSED (R=8, C=4, A=7, Act=6)
