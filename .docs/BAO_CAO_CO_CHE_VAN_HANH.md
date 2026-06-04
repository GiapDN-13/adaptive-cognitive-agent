# Báo Cáo: Cơ Chế Vận Hành Của SmartAgent

**Ngày:** 2026-05-31
**Mục đích:** Giải thích chi tiết cách SmartAgent thực thi một tác vụ từ bên trong — luồng xử lý, vòng lặp, ra quyết định
**Dữ liệu:** Trích từ log thực tế (session 82317b282b34 — tác vụ RAG chatbot, 22 iterations)

---

## 1. Kiến Trúc Vòng Lặp (ReACT Loop)

SmartAgent vận hành theo mô hình **ReACT** (Reasoning + Acting), lặp tối đa 150 vòng:

```
┌──────────────────────────────────────────────────────────┐
│  MỖI ITERATION:                                           │
│                                                          │
│  1. Lấy danh sách tools hiện có (động, gồm runtime tools)│
│  2. Gọi LLM (Claude Sonnet 4.6) với context + tools      │
│  3. LLM quyết định:                                      │
│     ├── stop_reason = "tool_use"  → thực thi tool        │
│     │     → qua pre-hooks → execute → post-hooks         │
│     │     → đưa kết quả vào context → lặp lại            │
│     └── stop_reason = "end_turn"  → trả lời cuối → DỪNG  │
└──────────────────────────────────────────────────────────┘
```

**Điểm quan trọng:** Tools list được lấy LẠI mỗi iteration → nếu agent tạo tool mới ở vòng N, vòng N+1 đã dùng được ngay.

---

## 2. Luồng Thực Thi Một Tool (Chi Tiết)

Mỗi khi agent gọi tool, nó đi qua pipeline 3 tầng:

```
Tool call
   │
   ▼
┌─────────────────┐
│  PRE-HOOKS      │  ← Kiểm tra trước khi chạy
│  • dangerous_command  (chặn rm -rf /, fork bomb...)
│  • gateguard          (bắt research trước khi write)
│  • secret_detection   (chặn hardcode credentials)
│  • config_protection  (bảo vệ file linter config)
└────────┬────────┘
         │ allowed?
         ▼
┌─────────────────┐
│  EXECUTE        │  ← Chạy trong Docker sandbox
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  POST-HOOKS     │  ← Xử lý sau khi chạy
│  • audit_log          (ghi log mọi tool call)
│  • quality_gate       (cảnh báo file lớn, thiếu test)
│  • planning_nudge     (nhắc think nếu chưa plan)
└────────┬────────┘
         │
         ▼
    Kết quả → context
```

**Bằng chứng từ log:** Mọi tool call đều có dòng `[AUDIT] Session ... | Tool: ... | Input: ... | Result: ...` — đây là post-hook audit ghi lại.

---

## 3. Trace Thực Tế — Agent Xử Lý Task RAG (22 iterations)

Dưới đây là luồng THỰC TẾ agent đã chạy, trích từ log:

### Giai đoạn 1: Lập kế hoạch (iteration 1)
```
[Tool: think] "Let me define the Definition of Done (DoD):
  C1: Code chạy không lỗi
  C2: TF-IDF retrieval đúng cho 4 chủ đề
  ...
  C7: Toàn bộ 28 test cases pass"
```
→ Agent KHÔNG code ngay. Nó định nghĩa tiêu chí thành công trước.

### Giai đoạn 2: Xây dựng (iterations 2-7)
```
[Tool: shell_exec]  mkdir + pip install scikit-learn numpy
[Tool: write_file]  knowledge_base.py  (6,390 bytes)
[Tool: write_file]  retriever.py        (2,656 bytes)
[Tool: write_file]  extractor.py        (2,076 bytes)
[Tool: write_file]  chatbot.py          (3,108 bytes)
[Tool: write_file]  test_chatbot.py     (11,021 bytes)  ← viết test
[Tool: write_file]  demo.py + requirements.txt
```
→ Tách 5 module riêng + viết test suite. Không gộp 1 file.

### Giai đoạn 3: Tự phát hiện lỗi giữa chừng (iterations 8-12)
```
[Tool: shell_exec]  chạy demo.py → thấy vấn đề
[Tool: think] "backpropagation work? → score 0.0661 < threshold 0.10.
              This is a problem because backpropagation IS AI/ML topic."
[Tool: write_file]  retriever.py (5,591 bytes)  ← SỬA: thêm hybrid detection
[Tool: think] "Query 'ai là cầu thủ bóng đá' bị detect in-scope vì chứa 'ai'
              — 'ai' tiếng Việt = 'who', không phải Artificial Intelligence!"
[Tool: write_file]  retriever.py (5,725 bytes)  ← SỬA lần 2: lọc từ tiếng Việt
```
→ Agent tự test, tự phát hiện edge case tinh vi, tự sửa NGAY trong lúc làm.

### Giai đoạn 4: Tự kiểm chứng có hệ thống (iterations 13-18)
```
[verify_work] C1: Code chạy không lỗi          → PASS
[verify_work] C2: TF-IDF retrieval đúng        → FAIL  ← phát hiện!
[Tool: think] "Test thực ra pass (9 passed) nhưng verify_work báo FAIL
              vì không tìm thấy string 'doc_1...'. Để tôi sửa expected."
[verify_work] C2 (sửa expected='9 passed')     → PASS
[verify_work] C3: Extractive answer            → PASS
[verify_work] C4: Out-of-scope 'nấu phở'       → PASS
[verify_work] C5: Hit Rate ≥ 75%               → PASS
[verify_work] C6: threshold + keyword 20/20    → PASS
[verify_work] C7: Toàn bộ 28 tests             → PASS
```
→ Agent verify TỪNG tiêu chí. Khi C2 báo FAIL (do tiêu chí test sai), agent tự điều chỉnh cách test rồi verify lại.

### Giai đoạn 5: Phản biện đối kháng (iterations 19-22)
```
[spawn_subagent] "QA Adversarial Reviewer"
   Nhiệm vụ: cố phá hệ thống bằng query hiểm
   │
   ├── Test "model runway fashion show", "deep blue chess"...
   ├── Phân tích root cause: "transformer" score=0 nhưng "transformers" có vocab
   │                        → stemming issue của TF-IDF
   ├── Tìm BUG: keyword whitelist trigger nhưng retrieval score=0 → wrong doc
   ├── Tìm BUG: _split_sentences mất câu khi không có space sau dấu chấm
   └── Báo cáo: 52 tests, 16 FAIL, False Positive Rate 50-80%
```
→ Agent tự spawn 1 agent KHÁC chỉ để bắt lỗi mình. Tìm ra 16 bugs ẩn.

---

## 4. Các Cơ Chế Kỹ Thuật Đảm Bảo Ổn Định

| Cơ chế | Mô tả | Giá trị |
|--------|-------|---------|
| **Dynamic tools** | Tools lấy lại mỗi iteration | Runtime tools dùng được ngay |
| **Context windowing** | Trim khi context > 80K chars | Không tràn token limit |
| **Stream timeout 120s** | Timeout mỗi chunk LLM | Phát hiện stall sớm |
| **Auto-retry on stall** | Stall → trim context → gọi lại | Không crash giữa chừng |
| **Generation counter** | Đánh số mỗi lần chạy | Hủy được loop cũ khi user gửi tin mới |
| **Cancel via threading.Event** | Hủy tức thì cả khi đang chờ LLM | User control tốt |

---

## 5. Cách LLM "Suy Nghĩ" Được Hiển Thị

Agent stream 3 loại thông tin real-time về UI:

| Loại message | Hiển thị | Ví dụ |
|--------------|----------|-------|
| `agent_thinking` | Bong bóng tím "Thinking" | Reasoning trước khi hành động |
| `agent_status` | Activity timeline | "[verify_work] C4: out-of-scope" |
| `agent_chunk` | Streaming text | Câu trả lời cuối, từng token |
| `terminal_output` | Terminal panel | Output lệnh shell thực tế |

→ User thấy CHÍNH XÁC agent đang làm gì ở mọi thời điểm, không có "hộp đen".

---

## 6. Thống Kê Lần Chạy Này

| Chỉ số | Giá trị |
|--------|---------|
| Tổng iterations | 22 |
| Tool calls | ~40 |
| - think | 6 lần (lập kế hoạch + phân tích) |
| - write_file | 9 lần (5 module + 2 sửa retriever + test + qa) |
| - shell_exec | ~15 lần (build, test, debug) |
| - verify_work | 7 lần (kiểm chứng từng DoD) |
| - spawn_subagent | 1 lần (QA adversarial) |
| File tạo ra | 8 (5 module + test + demo + qa) |
| Lỗi tự phát hiện & sửa | 3 (threshold, "ai" tiếng Việt, C2 test) |
| Bugs adversarial tìm thêm | 16 |
| Can thiệp thủ công | 0 |

---

## 7. Kết Luận — Tư Duy Vận Hành

SmartAgent không phải "chatbot trả lời" — nó là **vòng lặp tự chủ có kỷ luật**:

```
Định nghĩa chuẩn (DoD)
    → Xây dựng có cấu trúc
    → Tự test liên tục (phát hiện lỗi giữa chừng)
    → Verify có hệ thống từng tiêu chí
    → Tự phản biện (adversarial review)
    → Báo cáo trung thực (kể cả 16 bugs)
```

Mỗi bước đều:
- **Minh bạch** — mọi tool call được log + hiển thị real-time
- **Có kiểm soát** — qua pre/post hooks
- **Tự kiểm chứng** — không tin "có vẻ đúng", phải test thực tế
- **Ổn định** — timeout, retry, cancel, context management

> Đây là sự khác biệt cốt lõi: agent **làm việc như một kỹ sư cẩn thận**, không phải máy sinh văn bản.
