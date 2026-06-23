# Đo độ ổn định tư duy — ĐÚNG điều kiện production (temp 0.4, N=5)

> Sửa lỗi đo trước: bản đầu chấm ở temp 0.7 (cố tình thấy variance) → bi quan hóa,
> ra 2.2/7 với biến thiên 0→5. Đo lại ĐÚNG temp agent thật dùng (0.4), N=5:

| Trụ | Tỉ lệ pass /5 | |
|-----|---------------|---|
| D1 quy mô định lượng        | **100%** | đã vững |
| D2 xử lý nội dung Excel      | **100%** | đã vững |
| D3 phân rã + phần khó trước  | **80%**  | tốt |
| D7 biết khi mình không biết  | **60%**  | khá |
| D4 đa nhánh (ToT)            | **40%**  | chập chờn |
| D6 chấm điểm có trọng số     | **20%**  | yếu nhất |
| D5 tự phản chiếu (Wait/Aha)  | **20%**  | yếu (hành vi tự nhiên, khó ép) |
| **TB** | **4.2/7** | |

## Kết luận
- Phần lớn "biến thiên 0→5" trước kia là DO ĐO SAI (temp 0.7), KHÔNG phải agent tệ.
  D1/D2 thực ra đã 100% ổn định nhờ luật prompt "mẫu≠production" + đào nội dung.
- Điểm yếu THẬT còn lại: **D4 (40%) + D6 (20%)** = đa nhánh + chấm điểm trọng số.
- Đây CHÍNH LÀ phần cổng T10 (LLM-judge) bao phủ — nhưng phép đo này gọi LLM 1-turn
  (không qua agent loop) nên gate KHÔNG tham gia. Trong production thật (qua loop, khi
  agent write_file), gate sẽ chặn nếu D4/D6 thiếu → ép lên. Gate đặt ĐÚNG chỗ; chỉ là
  phép đo 1-turn không kích hoạt được nó (đã verify gate ở mức đơn vị: test_prebuild_judge 6/6).

## Việc còn lại để có số e2e sạch
Cần harness đo qua loop mà agent CHẮC CHẮN tới write_file trong cửa sổ (task nhỏ hơn /
seed sẵn để build nhanh), khi đó mới đo được "gate nâng D4/D6 thật bao nhiêu".

---

## CẬP NHẬT — Bằng chứng e2e: gate T10 BẮN trong build thật (trace_events_GATE_FIRED.json)

Sau nhiều harness đo e2e bị nhiễu (agent không tới write_file / Bedrock stall / gate_blocks=0),
chạy `trace_run_full.py` (đã chứng minh build tới nơi) với gate siết → quan sát trực tiếp:

- **gate fired: 1 lần** (`pre-build gate 1/2`) — gate CHẶN write_file đầu tiên vì judge thấy
  thinking chưa đủ đa nhánh/chấm điểm.
- Sau khi bị chặn: thinking xuất hiện **14 dấu hiệu đa nhánh** (vs/phương án/trade-off/Qdrant).
- Agent build trọn: **write_file × 10**, KHÔNG deadlock (chỉ chặn 1/2 lần).

=> Chuỗi nhân quả: định build → gate chặn → agent rethink (sinh đa nhánh) → judge cho qua →
build. Đây là bằng chứng gate T10 (LLM-judge siết) THỰC SỰ CAN THIỆP trong luồng production,
khác mọi lần trước (gate ngủ, gate_blocks=0). Số lượng hóa "nâng D4/D6 bao nhiêu %" vẫn cần
nhiều mẫu sạch hơn, nhưng cơ chế đã verify hoạt động end-to-end.

---

## CẬP NHẬT 2 — Chấm trace GATE-FIRED + luật D7 (1b)

**Chấm D1-D7 trên trace mà gate ĐÃ bắn (qua loop thật) = 6/7** — D4 VÀ D6 đều PASS:
- D6: agent làm BẢNG có cột "Trọng số" (Scale=3, Filter=3...), tính tổng có trọng số
  (Chroma 52 vs Qdrant 50), chọn nhánh điểm cao — đúng reward-model của tài liệu.
- Chỉ D7 FAIL: agent ghi model ID/dim "(đã test)" từ trí nhớ, không đánh dấu cần verify.

**=> Phân biệt 2 PHÉP ĐO (quan trọng, dễ nhầm):**
- `eval_depth_multi` (LLM 1-turn, KHÔNG qua gate): đo "agent TỰ suy 1 phát" → D4/D6 ~0-33%.
  Tức agent MỘT MÌNH ít khi làm đa nhánh/chấm điểm.
- Trace qua loop (gate BẮN): D4/D6 PASS. Gate ÉP được agent làm.
- Hai số không mâu thuẫn — xác nhận GATE LÀ CẦN THIẾT (agent một mình không ổn ở D4/D6).

**Luật D7 mới (1b trong prompts.py):** chi tiết kỹ thuật dễ sai từ trí nhớ (model ID/version/
dimension/tên hàm) phải đánh dấu "[GIẢ ĐỊNH — cần verify]" + chạy thử kiểm trước khi cam kết;
cấm ghi "(đã test)" nếu chưa thực chạy lệnh test trong phiên. Đo nhanh N=3 (1-turn): D7 60→67%
(nhích nhẹ, trong nhiễu — chưa đủ kết luận; cần đo qua gate/nhiều mẫu hơn).
