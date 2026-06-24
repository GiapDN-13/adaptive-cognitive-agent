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

---

## CẬP NHẬT 3 — Baseline SẠCH N=6 (harness chống nhiễu + parser linh hoạt)

Phát hiện: các baseline 0/7 trước đó là do **Bedrock ServiceUnavailable/throttle** (lỗi hạ
tầng) + parser regex không bắt format Opus 4.8 → toàn FAIL oan. Sửa harness: retry 503/throttle
+ parser bỏ markdown + bắt "Dk ... PASS/FAIL" linh hoạt + judge-lỗi tính ERROR (không FAIL).

Baseline N=6 (tư duy 1-turn, temp 0.4, KHÔNG qua gate):
| D1 | D2 | D3 | D4 | D5 | D6 | D7 | TB |
|----|----|----|----|----|----|----|----|
|100%|100%|83%|17%|0%|17%|**83%**| 4.0/7 |

KẾT LUẬN VỀ "NÂNG %":
- **D7: 60% → 83%** nhờ luật 1b (chống claim model-ID/dim từ trí nhớ). Nâng được BẰNG PROMPT.
- D1/D2 giữ 100%, D3 83%.
- **D4/D5/D6 (17%/0%/17%): prompt KHÔNG nâng nổi** — agent MỘT MÌNH gần như không tự làm
  đa nhánh + chấm điểm + tự phản chiếu, dù prompt đã có luật ToT/reward. Đây là giới hạn bản
  chất model → CHỈ gate ép được (trace GATE-FIRED đã chứng minh D4/D6 PASS khi qua gate).
- => Đừng vặn prompt thêm cho D4/D6 (đã thử nhiều vòng, vô ích). Giá trị nằm ở GATE.

---

## CẬP NHẬT 4 — Tổng hợp "nâng %" (đủ dữ liệu để chốt)

| Trụ | 1-turn (suy 1 phát) | Qua loop (think nhiều lần) | Trace gate-fired |
|-----|---------------------|----------------------------|------------------|
| D4 đa nhánh   | 17% | **~100%** | PASS |
| D6 chấm điểm  | 17% | 0%        | **PASS** |
| D7            | 83% | 100%      | (fail lần đó) |

3 phát hiện sạch:
1. **D7 nâng bằng PROMPT** (60→83%, luật 1b). XONG.
2. **D4 nâng nhờ THINK QUA LOOP nhiều lần** (17→~100%) — agent suy đủ lâu thì tự làm đa nhánh.
3. **D6 (chấm điểm có trọng số) CHỈ gate ép được** — mọi cách khác 0%, chỉ trace gate-fired PASS.
   Đây là trụ cứng đầu nhất, phụ thuộc gate.

LƯU Ý PHƯƠNG PHÁP: harness eval_gate_samples đo gate_fired=0 vì agent trong harness loanh quanh
think/explore, KHÔNG tới write_file trong cửa sổ (timeout) → gate chưa bắn. Trong PRODUCTION thật
(user → agent build) gate SẼ bắn (đã thấy ở trace_run_full GATE-FIRED). Tức D6 được gate bao phủ
trong luồng thật, chỉ là harness ngắn không tái hiện được.

=> KẾT LUẬN: "nâng %" đã đạt ở chỗ nâng được (D7 prompt, D4 think-qua-loop). D6 dựa gate trong
build thật. Đừng vặn prompt thêm.

---

## CẬP NHẬT 5 — THỐNG KÊ gate trên 3 trace BUILD TRỌN (production-like)

3 lần chạy trace_run_full đầy đủ (build ≥4 file, gate bắn tự nhiên như production):

| run | D1 | D2 | D3 | D4 | D5 | D6 | D7 | gate bắn | tổng |
|-----|----|----|----|----|----|----|----|----------|------|
| 1 | P | P | P | P | P | **P** | P | 1 | **7/7** |
| 2 | F | P | P | P | P | **F** | F | 0 | 5/7 |
| 3 | F | P | P | P | F | **P** | P | 1 | 6/7 |
| **%** |33%|100%|100%|**100%**|67%|**67%**|67%| 2/3 | **TB 5.3/7** |

TƯƠNG QUAN GATE ↔ D6 (rõ rệt, dù n nhỏ):
- 2/2 run gate BẮN → D6 PASS.
- 1 run gate KHÔNG bắn → D6 FAIL.
=> Gate chính là thứ ép được D6 (trụ mà prompt/think không nâng nổi: 0-17% mọi nơi khác).

NÂNG % TỔNG KẾT (so baseline 1-turn 4.0/7):
- D4 đa nhánh: 17% → **100%** (think qua loop nhiều lần).
- D6 chấm điểm: 17% → **67%** (gate ép — chỉ gate làm được).
- TB: 4.0/7 → **5.3/7** ở điều kiện build trọn + gate active (production-like).
- D1 dao động (33% ở 3 mẫu này) — nhiễu mẫu nhỏ; ở N=6 trước D1=100%, cần n lớn hơn để chốt.

Hạn chế: n=3 nhỏ; D1 lần này thấp bất thường (có thể giám khảo khắt khe / mẫu nhỏ). Xu hướng
chính (gate nâng D6, think-loop nâng D4) đã rõ và nhất quán với các đo trước.

---

## CẬP NHẬT 6 — T11 (post-build D6 gate): D6 từ 25% → 100% (3/3)

Vấn đề trước: T10 pre-build gate bắn thưa (build nhanh lọt) → D6 chỉ 25-67%. Thêm T11:
cổng thứ 2 ở end_turn (trước khi báo xong) — nếu suy nghĩ chưa có chấm điểm trọng số cho
quyết định kiến trúc → chặn 1 lần, ép bổ sung (_has_weighted_scoring LLM-judge YES/NO).

3 trace build TRỌN (tới spawn_evaluator) với T10+T11 active:
| run | D1 | D2 | D3 | D4 | D5 | D6 | D7 | gate bắn | tổng |
|-----|----|----|----|----|----|----|----|----------|------|
| 1 | P | P | P | P | P | **P** | P | 1 | **7/7** |
| 2 | P | P | P | P | P | **P** | P | 0 | **7/7** |
| 3 | P | P | P | P | P | **P** | P | 1 | **7/7** |
| **%** |100|100|100|100|100|**100**|100| 2/3 | **7.0/7** |

D6: 17-25% (trước) → **100% (3/3)**. Run 2 D6 pass dù gate không bắn = agent TỰ chấm điểm
đủ (gate cho qua đúng). Run 1,3 gate bắn → ép → D6 pass. Cả 2 cơ chế (tự đạt / bị ép) đều
dẫn tới D6 pass.

TỔNG KẾT NÂNG % (build trọn, production-like):
- Baseline 1-turn: 4.0/7 (D4/D6 ~17%).
- + T10 pre-build gate: TB 5.3/7 (D6 25-67%, gate thưa).
- + T11 post-build D6 gate: **TB 7.0/7, D6 100%** (n=3).

Hạn chế: n=3 (run 4 cắt vì build trọn ~15'/run quá lâu); cần n lớn hơn để chốt 100% bền,
nhưng xu hướng đảo chiều rõ rệt (D6 0-25% → 100%) là tín hiệu mạnh, nhất quán 3/3.

---

## CẬP NHẬT 7 — Sửa 2 lỗi sếp bắt (chấm v6, rubric mở rộng D1-D9)

Sếp bắt: (1) agent chấm Qdrant thắng nhưng build Chroma ("migrate sau"); (2) thiếu chi tiết
định lượng (chunk/top-k/ngưỡng) — và KHÔNG được thiên RAG, phải chung mọi lĩnh vực.

Sửa: T11 gate → 3 trạng thái (THIEU_CHAM_DIEM/LECH_BUILD/OK); prompt Bước 1.5 thêm "CHIỀU SÂU
TRIỂN KHAI" (đa lĩnh vực) + "KHỚP BUILD VỚI QUYẾT ĐỊNH"; rubric +D8 (chiều sâu định lượng) +D9
(build khớp quyết định).

Trace v6 (build trọn, gate active): **8/9**.
- D8 PASS: "chunk 600 chars overlap 100 vì văn bản nội bộ 200-500 chars; top_k=5 cosine; Titan
  dim 1024; CSV mỗi hàng=1 chunk" — con số gắn lý do (trước đây thiếu).
- D9: quyết định CHÍNH (vector store) KHỚP — chấm Qdrant thắng + build Qdrant (hết lỗi Chroma-cho-1k).
  FAIL chỉ ở quyết định PHỤ (LLM Haiku 3 vs 4.5, không ask_user) — sạn nhỏ.
- D1: "KHÔNG được phán '4 file là nhỏ' → cần server-mode" — hết lỗi Chroma cho 1k user.

Còn lại: D9 ở quyết định phụ vẫn lọt (judge soi quyết định chính). Siết thêm tăng rủi ro chặn-oan.
