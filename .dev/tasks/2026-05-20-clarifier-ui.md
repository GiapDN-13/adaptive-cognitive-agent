# Task: Clarifier Node + Streamlit UI

## 1. Task chuẩn bị làm là gì
Implement 2 components còn lại cho MVP:
- **Clarifier Node**: Khi input ambiguous (needs_clarification=True), generate 2-4 clarifying questions
- **Streamlit UI**: Demo UI hiển thị toàn bộ thinking process (perceiver → meta-thinker → cognitive → executor → evaluator → retry)

## 2. Làm như thế nào
- Clarifier: 1 prompt template + 1 node function, gọi Flash model, trả về numbered questions
- UI: Streamlit chat interface với `st.status()` expandable sections cho mỗi pipeline step

## 3. Ảnh hưởng ra sao
- Clarifier hoàn thành path thứ 2 trong graph (trivial đã có, full pipeline đã có)
- UI cho phép demo trực quan pipeline — key differentiator vs chatbot thường
- Không ảnh hưởng existing nodes/graph logic

## 4. Triển khai như thế nào
- Step 1: Viết `prompts/clarifier.py` (template)
- Step 2: Viết `nodes/clarifier.py` (node function)
- Step 3: Test clarifier standalone
- Step 4: Viết `ui/app.py` (full Streamlit UI)
- Step 5: Test UI running + health check

## 5. Kiểm thử ra sao
- Clarifier: Input "Viết code" → returns numbered questions asking scope/language/context
- UI: `streamlit run` → HTTP 200, `/_stcore/health` → "ok", no import errors

## 6. Kết quả như thế nào
- [x] Clarifier prompt template generates specific questions (not generic)
- [x] Clarifier node tested: "Viết code" → 4 clarifying questions in Vietnamese
- [x] Streamlit UI starts without errors (health check "ok")
- [x] UI shows all pipeline steps with expandable status sections
- [x] Chat interface with session state persistence
- [x] All 3 paths displayed: trivial (quick), clarification, full pipeline with retry loop
