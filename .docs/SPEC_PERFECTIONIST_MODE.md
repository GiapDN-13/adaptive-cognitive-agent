# SPEC: Perfectionist Mode — Tối ưu cho chuẩn cao nhất

**Mục tiêu:** Mọi task SmartAgent làm đều đạt chuẩn — tự kiểm chứng, có số liệu, ổn định, nhất quán.
**Date:** 2026-05-31

---

## 4 Trụ Cột

### Trụ cột 1: Self-Verification Loop (Tự kiểm chứng + tự sửa)

**Vấn đề:** Agent làm xong → báo cáo ngay, không tự kiểm tra. Lỗi (như out-of-scope RAG) lọt qua.

**Giải pháp:** Thêm tool `verify_work` + bắt buộc trong workflow:
```
Build → Self-Test → Phát hiện lỗi → Fix → Re-test → (loop tối đa 3 lần) → Report
```

- Tool mới `verify_work(criteria, test_command)`: chạy test, so với success criteria, trả pass/fail + lý do
- Nếu fail → agent tự sửa, chạy lại
- Chỉ báo cáo "hoàn thành" khi verify PASS hoặc đã loop hết 3 lần (báo cáo trung thực phần chưa đạt)

### Trụ cột 2: Definition of Done (Số liệu chứng minh)

**Vấn đề:** "Tạo RAG" mơ hồ → không biết khi nào xong, không có số đo.

**Giải pháp:** Agent phải định nghĩa success criteria ĐO ĐƯỢC trước khi làm:
```
Task: "Tạo RAG"
→ Agent tự đặt DoD:
   - Code chạy không lỗi
   - Có ≥ 3 test cases pass
   - Retrieval Hit Rate ≥ 80% trên test set
   - Xử lý được câu hỏi out-of-scope
→ Cuối cùng báo cáo: đạt mấy/mấy tiêu chí
```

- Thêm vào system prompt: bắt buộc state DoD trước khi execute
- Cuối task: bảng "Tiêu chí → Đạt/Chưa → Bằng chứng"

### Trụ cột 3: Stability (Ổn định, không crash)

**Vấn đề:** Timeout, stream stall, context overflow → agent dừng giữa chừng.

**Giải pháp:** (một phần đã làm) + bổ sung:
- ✅ Stream timeout 120s + auto-retry (đã có)
- ✅ Context window 80K + trim (đã có)
- 🔲 Checkpoint: lưu progress sau mỗi stage, resume được nếu fail
- 🔲 Graceful degradation: nếu 1 stage fail, các stage khác vẫn chạy + báo cáo rõ phần nào fail
- 🔲 Heartbeat rõ ràng: user luôn biết agent đang làm gì, không "đơ"

### Trụ cột 4: Consistency (Nhất quán, chuyên nghiệp)

**Vấn đề:** Output mỗi lần một format, đôi khi thiếu phần.

**Giải pháp:** Report template chuẩn:
- Thêm skill `report-template` định nghĩa cấu trúc báo cáo chuẩn
- Mọi báo cáo: Executive Summary → Method → Results (số liệu) → Evidence → Limitations → Recommendations
- Hook post-process: kiểm tra báo cáo có đủ sections không

---

## Implementation Plan

| # | Component | File | Trụ cột |
|---|-----------|------|---------|
| 1 | Tool `verify_work` | builtin_tools.py | 1 |
| 2 | Workflow DoD enforcement | prompts.py | 1, 2 |
| 3 | Verification rule | rules/common/verification.md | 1, 2 |
| 4 | Pipeline checkpoint + graceful fail | builtin_tools.py (execute_pipeline) | 3 |
| 5 | Report template skill | rules/common/reporting.md | 4 |
| 6 | Report completeness post-hook | hook_manager.py | 4 |

---

## Workflow Mới (Perfectionist)

```
1. RECEIVE task
2. DEFINE Done — state success criteria đo được (DoD)
3. PLAN — think, xác định tools cần tạo
4. BUILD — tạo tools, execute
5. SELF-VERIFY — chạy verify_work với DoD criteria
   ├── PASS → bước 7
   └── FAIL → FIX → quay lại 5 (tối đa 3 lần)
6. (nếu vẫn fail sau 3 lần) → báo cáo trung thực phần chưa đạt
7. REPORT — theo template chuẩn, kèm số liệu + bằng chứng
```

---

## Ví Dụ: RAG Task Với Perfectionist Mode

```
Task: "Tạo RAG chatbot"

Agent:
[DoD] Tôi định nghĩa hoàn thành = {
   ✓ Code chạy không lỗi
   ✓ ≥3 test cases pass
   ✓ Hit Rate ≥ 80%
   ✓ Out-of-scope trả về "không có thông tin"
}
[BUILD] tạo knowledge_base, rag_chatbot, demo
[VERIFY] chạy eval → Hit Rate 100% ✓, nhưng out-of-scope FAIL ✗
[FIX] thêm score threshold < 0.12 → "không có thông tin"
[RE-VERIFY] chạy lại eval → out-of-scope PASS ✓
[REPORT] Bảng: 4/4 tiêu chí đạt, kèm số liệu eval
```

→ Khác biệt: agent **tự phát hiện lỗi out-of-scope và tự sửa** trước khi báo cáo. Đúng tinh thần cầu toàn.

---

## Verification (cách test SPEC này)

1. Giao lại task RAG → agent phải tự định nghĩa DoD
2. Agent phải tự chạy verify, phát hiện out-of-scope fail, tự sửa
3. Báo cáo cuối phải có bảng tiêu chí + số liệu
4. Test stability: task dài → không crash, có checkpoint
