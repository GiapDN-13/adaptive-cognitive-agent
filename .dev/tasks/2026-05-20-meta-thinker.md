# Task: Meta-Thinker Node

## 1. Task chuẩn bị làm là gì
Implement Meta-Thinker node — bộ não quyết định CÁCH agent suy nghĩ:
- Chọn persona (CTO/PM/TechLead/Analyst/Creative/Generalist)
- Chọn thinking depth (1-5)
- Sinh domain rules (3-5 constraints cụ thể)
- Sinh anti-patterns (2-3 lỗi cần tránh)
- Sinh quality gates (2-3 tiêu chí output phải đạt)
- Quyết định có cần full cognitive framework không

## 2. Làm như thế nào
- Viết prompt template cho Meta-Thinker (structured JSON output)
- Implement node function nhận AgentState, gọi LLM, trả về partial state
- Adaptive: 1 LLM call cho depth ≤3, nhiều calls cho depth 4-5 (đơn giản hóa cho MVP: 1 call trước)
- Wire vào graph thay thế placeholder

## 3. Ảnh hưởng ra sao
- Thay thế placeholder_node trong graph/builder.py
- Output của Meta-Thinker sẽ là input cho Executor (chưa implement)
- Quyết định needs_full_framework ảnh hưởng routing (skip/trigger Cognitive Framework)

## 4. Triển khai như thế nào
- Step 1: Viết prompts/meta_thinker.py (prompt template)
- Step 2: Viết nodes/meta_thinker.py (node logic)
- Step 3: Update graph/builder.py (wire real node)
- Step 4: Update main.py test cases nếu cần

## 5. Kiểm thử ra sao
- Test "Phân tích thị trường AI VN" → Analyst persona, depth 4, needs_full_framework=True
- Test "Debug lỗi CORS" → TechLead persona, depth 2, needs_full_framework=False
- Test "Kế hoạch marketing Q3" → PM persona, depth 3-4
- Domain rules phải SPECIFIC cho task (không generic)

## 6. Kết quả như thế nào
- [x] Meta-Thinker chọn đúng persona (Analyst cho market research, TechLead cho so sánh tech, Creative cho pitch)
- [x] Depth hợp lý theo complexity (7→depth 4, 3→depth 3, high-stakes→depth 5)
- [x] Domain rules specific, không generic (VN-specific data, SSR benchmarks, ARR metrics)
- [x] Anti-patterns relevant (đừng lấy số global cho VN, đừng ignore team familiarity)
- [x] Quality gates testable (phải có số liệu %, phải có 3+ recommendations, CTA cụ thể)
- [x] needs_full_framework đúng logic (depth 4,5 → True, depth 3 → False)
