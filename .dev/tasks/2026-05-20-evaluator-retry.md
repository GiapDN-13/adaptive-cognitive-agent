# Task: Evaluator + Smart Retry

## 1. Task chuẩn bị làm là gì
Implement 2 nodes:
- **Evaluator** — chấm điểm output trên 4 tiêu chí (Relevance, Completeness, Accuracy, Actionability) + kiểm tra ngôn ngữ
- **Smart Retry** — phân loại lý do fail → đổi strategy → retry (max 3 lần)

## 2. Làm như thế nào
- Viết evaluator prompt (structured JSON scoring)
- Implement evaluator node: gọi LLM Flash, chấm điểm, quyết định pass/fail
- Implement retry node: phân loại failure reason, inject feedback vào context
- Wire retry loop trong graph (evaluator → pass? → output / retry → executor)
- Giữ track best_output + best_score qua các attempts

## 3. Ảnh hưởng ra sao
- Thêm 2 nodes mới vào graph
- Thay đổi flow: executor → evaluator → (pass → END / fail → retry → executor)
- Output cuối cùng sẽ là best_output (score cao nhất trong các attempts)
- Tăng latency (thêm 1-2 LLM calls per attempt) nhưng tăng quality

## 4. Triển khai như thế nào
- Step 1: Viết prompts/evaluator.py
- Step 2: Viết nodes/evaluator.py
- Step 3: Viết nodes/retry.py
- Step 4: Update graph/builder.py (wire evaluator + retry loop)
- Step 5: Update main.py để hiển thị eval scores
- Step 6: Test e2e

## 5. Kiểm thử ra sao
- Task chất lượng cao → pass ngay lần 1 (score >= 6.0)
- Task có output yếu → retry và improve
- Max 3 attempts rồi trả best output
- Kiểm tra feedback specific (thiếu data vs sai hướng vs thiếu depth)

## 6. Kết quả như thế nào
- [x] Evaluator chấm điểm đúng 4 tiêu chí (10/10 cho lãi kép, 6.2 cho React vs Vue, 0.2 cho output kém)
- [x] Pass/fail logic chính xác (>= 6.0 pass, < 6.0 fail)
- [x] Retry phân loại đúng lý do fail (insufficient_depth cho output shallow)
- [x] Retry inject feedback vào user_input (augmented input with retry instruction)
- [x] Best output tracking hoạt động (best_score cập nhật đúng)
- [x] Graph loop đúng (evaluator → pass → format_output → END / fail → retry → executor)
- [x] Full pipeline e2e tested: trivial + simple + complex, evaluator pass lần 1
