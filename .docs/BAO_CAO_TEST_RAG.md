# Báo Cáo Kiểm Thử SmartAgent — Tác Vụ Xây Dựng RAG Chatbot

**Ngày:** 2026-05-31
**Mục đích:** Chứng minh cách SmartAgent **suy nghĩ và làm việc** qua một tác vụ phát triển phần mềm thực tế
**Model:** AWS Bedrock — Claude Sonnet 4.6
**Kết quả:** ✅ Hoàn thành — 10 iterations, 10 tool calls, ~3 phút

---

## 1. Tóm Tắt Cho Lãnh Đạo

SmartAgent được giao một tác vụ phát triển hoàn chỉnh: *"Xây dựng một Chatbot RAG bằng Python, tự tạo knowledge base, implement retrieval, và chạy demo chứng minh kết quả."*

Agent đã **tự động hoàn thành toàn bộ** mà không cần can thiệp thủ công:
- Tự kiểm tra môi trường, phát hiện thiếu thư viện, tự cài đặt
- Tự thiết kế kiến trúc 3 tầng (knowledge base → retrieval → generation)
- Viết code production-quality (TF-IDF + cosine similarity + extractive generation)
- **Chạy demo thực tế** và chứng minh chatbot trả lời đúng
- Tự viết tài liệu README

**Điểm quan trọng:** Agent không "bịa" kết quả — mọi câu trả lời đều dựa trên output thực tế từ việc chạy code trong sandbox.

---

## 2. Cách Agent Suy Nghĩ — Phân Tích Từng Bước

### Iteration 1 — TƯ DUY TRƯỚC KHI HÀNH ĐỘNG (Think)

Agent **không lao vào code ngay**. Bước đầu tiên, nó dừng lại và lập kế hoạch (hiển thị qua "Thinking Stream"):

```
🧠 THINKING:
The user wants a simple RAG chatbot in Python. Let me plan this:
1. Knowledge base: 3-4 text documents about AI/ML topics
2. Retrieval: TF-IDF with sklearn (no external API needed)
3. Chatbot function: takes question, retrieves relevant docs, generates answer
4. Demo with 2-3 sample questions
```

> **Nhận xét:** Đây là nguyên tắc "Think Before Coding" (tích hợp từ Karpathy guidelines). Agent xác định rõ phạm vi, chọn cách tiếp cận đơn giản nhất (TF-IDF thay vì gọi API ngoài) — thể hiện tư duy "Simplicity First".

### Iteration 2 — KIỂM CHỨNG MÔI TRƯỜNG (không giả định)

Thay vì giả định thư viện có sẵn, agent **kiểm tra thực tế**:

```bash
python3 -c "import sklearn; import numpy; ..."
# → ModuleNotFoundError: No module named 'sklearn'
```

> **Nhận xét:** Agent phát hiện vấn đề TRƯỚC khi viết code phụ thuộc vào nó — tránh lỗi về sau. Đây là tư duy "verify, don't assume".

### Iteration 3 — TỰ KHẮC PHỤC (self-healing)

Phát hiện thiếu thư viện → tự cài đặt (qua cơ chế phê duyệt an toàn):

```bash
pip install scikit-learn numpy -q
# → OK sklearn 1.9.0
python3 --version  # → Python 3.11.15
pip show numpy     # → Version: 2.4.6
```

> **Nhận xét:** Agent không bỏ cuộc khi gặp lỗi. Nó tự sửa và xác nhận môi trường đã sẵn sàng (kiểm tra version cụ thể).

### Iterations 4-6 — XÂY DỰNG CÓ CẤU TRÚC

Agent chia code thành 3 module riêng biệt, mỗi file một nhiệm vụ:

| File | Nội dung | Kích thước |
|------|----------|-----------|
| `knowledge_base.py` | 4 documents về AI/ML | 3,849 bytes |
| `rag_chatbot.py` | TFIDFIndex + generate_answer + RAGChatbot | 4,571 bytes |
| `demo.py` | Demo 3 câu hỏi + interactive mode | 1,146 bytes |

> **Nhận xét:** Tách module rõ ràng (separation of concerns) — không viết tất cả vào 1 file. Code chất lượng cao: TF-IDF dùng unigram+bigram, sublinear TF scaling, cosine similarity.

### Iteration 7 — CHẠY THỬ THỰC TẾ (proof, not claim)

Agent **thực sự chạy** demo, không chỉ nói "code sẽ hoạt động":

```bash
cd /workspace/rag_chatbot && echo "quit" | python3 demo.py
# → RAG CHATBOT DEMO chạy thành công
```

### Iteration 8 — TÀI LIỆU HÓA

Tự viết `README.md` với sơ đồ kiến trúc, hướng dẫn chạy, và đề xuất mở rộng.

### Iterations 9-10 — XÁC NHẬN & BÁO CÁO

Liệt kê file đã tạo, tổng hợp kết quả cho người dùng — chỉ báo cáo những gì **thực sự đã làm**.

---

## 3. Bằng Chứng Hoạt Động Thực Tế

Demo chạy với câu hỏi thật, cho thấy retrieval + generation hoạt động chính xác:

```
❓ Câu hỏi: Deep Learning và mạng nơ-ron là gì?
🔍 Tài liệu được truy xuất:
   • [0.309] Deep Learning và Neural Networks    ← relevance score cao nhất
   • [0.077] Machine Learning là gì?
💬 Trả lời:
Deep Learning là một kỹ thuật trong Machine Learning sử dụng mạng nơ-ron
nhân tạo (Artificial Neural Networks) với nhiều lớp ẩn (hidden layers)...
📚 Nguồn: "Deep Learning và Neural Networks"
```

> Hệ thống chấm điểm độ liên quan (cosine similarity), chọn đúng tài liệu, trích xuất câu trả lời chính xác, và **trích dẫn nguồn** — đầy đủ đặc trưng của một RAG system thật.

---

## 4. Các Cơ Chế An Toàn Đã Hoạt Động

Trong quá trình test, các guardrail của hệ thống đều kích hoạt đúng:

| Cơ chế | Biểu hiện trong test |
|--------|---------------------|
| **Approval Gate** | Lệnh `pip install` yêu cầu phê duyệt trước khi chạy |
| **Audit Logging** | Mọi tool call được ghi log đầy đủ (input + result) |
| **Hook Pipeline** | Tất cả 10 tool calls đều qua pre/post hooks |
| **Anti-Hallucination** | Agent chỉ báo cáo output thực tế từ sandbox |

---

## 5. Đặc Điểm Nổi Bật Về Tư Duy Của Agent

```
┌─────────────────────────────────────────────────────────┐
│  QUY TRÌNH TƯ DUY CỦA SMARTAGENT                        │
│                                                         │
│  1. THINK    → Lập kế hoạch trước, chọn cách đơn giản  │
│       ↓                                                 │
│  2. VERIFY   → Kiểm tra môi trường, không giả định     │
│       ↓                                                 │
│  3. SELF-HEAL → Gặp lỗi thì tự sửa, không bỏ cuộc      │
│       ↓                                                 │
│  4. BUILD    → Code có cấu trúc, tách module rõ ràng   │
│       ↓                                                 │
│  5. PROVE    → Chạy thật để chứng minh, không bịa      │
│       ↓                                                 │
│  6. DOCUMENT → Tự viết tài liệu                         │
│       ↓                                                 │
│  7. REPORT   → Báo cáo trung thực kết quả thực tế      │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Kết Luận

Bài test chứng minh SmartAgent là một **agent phát triển tự chủ thực thụ**, không phải chatbot trả lời câu hỏi:

- ✅ **Tự chủ hoàn toàn** — từ nhận yêu cầu đến sản phẩm hoàn chỉnh, không cần hướng dẫn từng bước
- ✅ **Tư duy có kỷ luật** — think trước, verify môi trường, xử lý lỗi
- ✅ **Bằng chứng thực tế** — chạy code thật, không hallucinate
- ✅ **Chất lượng production** — code sạch, có cấu trúc, có tài liệu
- ✅ **An toàn** — qua approval gate và audit logging

Đây mới chỉ là **một bài test dev**. Cùng kiến trúc này, agent có thể tự mở rộng (tạo tools/skills mới) cho các tác vụ phức tạp hơn như security audit, CVE research, hay penetration testing.

---

## Phụ Lục: Thông Số Kỹ Thuật

| Chỉ số | Giá trị |
|--------|---------|
| Tổng iterations | 10 |
| Tổng tool calls | 10 |
| Tools sử dụng | think, shell_exec, write_file |
| File tạo ra | 4 (knowledge_base.py, rag_chatbot.py, demo.py, README.md) |
| Thời gian | ~3 phút |
| Lỗi gặp phải | 1 (thiếu sklearn — tự khắc phục) |
| Can thiệp thủ công | 0 |
