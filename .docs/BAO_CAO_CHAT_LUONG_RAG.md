# Báo Cáo Đánh Giá Chất Lượng RAG Chatbot

**Ngày:** 2026-05-31
**Đối tượng test:** RAG Chatbot do SmartAgent tự xây dựng
**Phương pháp:** Eval suite độc lập với golden test set + phân tích chi tiết từng câu hỏi
**Knowledge Base:** 4 documents về AI/ML (ML, Deep Learning, NLP, RAG)

---

## 1. Cách RAG Này Hoạt Động (để hiểu kết quả test)

```
Câu hỏi → TF-IDF Vectorizer → Cosine Similarity với 4 docs
        → Lấy top-2 docs điểm cao nhất
        → Extractive Generation (chọn 3 câu liên quan nhất trong docs)
        → Trả lời + trích nguồn
```

**Lưu ý quan trọng:** Đây là RAG **cơ bản** — retrieval bằng TF-IDF (khớp từ khóa), generation bằng cách **trích nguyên văn câu** từ tài liệu (extractive), KHÔNG dùng LLM để diễn đạt lại. Điều này quyết định cả điểm mạnh lẫn điểm yếu dưới đây.

---

## 2. Kết Quả Chi Tiết Từng Câu Hỏi

### ✅ Case 1: "Có mấy loại học máy và là những loại nào?" — ĐÚNG

| | |
|---|---|
| **Tài liệu kỳ vọng** | doc_1 (Machine Learning là gì?) |
| **Tài liệu retrieve** | **doc_1** [score 0.168] → doc_2 [0.082] |
| **Từ khóa khớp** | "học", "loại", "máy" |

**Câu trả lời:**
> "...Có ba loại học máy chính: học có giám sát (supervised learning), học không giám sát (unsupervised learning), và học tăng cường (reinforcement learning)..."

**Phân tích:** ✅ **Hợp lý hoàn hảo.** Câu hỏi chứa từ đặc trưng "loại học máy" → khớp chính xác doc_1 vốn liệt kê 3 loại. Câu trả lời trích đúng đoạn liệt kê. Đây là case lý tưởng.

---

### ✅ Case 2: "CNN dùng để xử lý loại dữ liệu nào?" — ĐÚNG

| | |
|---|---|
| **Tài liệu kỳ vọng** | doc_2 (Deep Learning) |
| **Tài liệu retrieve** | **doc_2** [score 0.136] → doc_1 [0.133] |
| **Từ khóa khớp** | "dùng", "liệu", **"cnn"** |

**Câu trả lời:**
> "Convolutional Neural Networks (CNN) rất hiệu quả cho xử lý ảnh và nhận dạng hình ảnh. Recurrent Neural Networks (RNN) và LSTM được dùng cho dữ liệu tuần tự..."

**Phân tích:** ✅ **Hợp lý.** Từ khóa "cnn" là đặc trưng duy nhất của doc_2 → kéo nó lên top. Tuy nhiên khoảng cách điểm với doc_1 rất sát (0.136 vs 0.133) — cho thấy TF-IDF dễ nhầm khi câu hỏi có nhiều từ chung chung ("dùng", "liệu", "loại").

---

### ✅ Case 3: "RAG hoạt động qua mấy bước?" — ĐÚNG (rõ ràng nhất)

| | |
|---|---|
| **Tài liệu kỳ vọng** | doc_4 (RAG) |
| **Tài liệu retrieve** | **doc_4** [score 0.169] → doc_2 [0.026] |
| **Từ khóa khớp** | "động", **"rag"**, "bước", "qua", "hoạt" |

**Câu trả lời:**
> "RAG hoạt động theo hai bước chính: đầu tiên, hệ thống truy xuất các tài liệu liên quan từ knowledge base...; sau đó, mô hình ngôn ngữ sử dụng các tài liệu đó làm ngữ cảnh..."

**Phân tích:** ✅ **Xuất sắc.** Khoảng cách điểm rất lớn (0.169 vs 0.026) → retrieval cực kỳ tự tin. 5 từ khóa khớp, đặc biệt "rag" + "bước" là đặc trưng. Câu trả lời chính xác tuyệt đối.

---

### ✅ Case 4: "Vector database nào hay dùng cho RAG?" — ĐÚNG

| | |
|---|---|
| **Tài liệu kỳ vọng** | doc_4 (RAG) |
| **Tài liệu retrieve** | **doc_4** [score 0.155] → doc_2 [0.073] |
| **Từ khóa khớp** | **"rag"**, "dùng", **"vector"**, **"database"** |

**Câu trả lời:**
> "Vector database như Pinecone, Weaviate, hoặc FAISS thường được dùng để lưu trữ embeddings..."

**Phân tích:** ✅ **Hợp lý.** Từ khóa "vector" + "database" rất đặc trưng → khớp đúng doc_4. Câu trả lời nêu đúng 3 công cụ. Tuy nhiên câu thứ 2-3 trong answer lại lạc sang CNN/RNN (do extractive lấy thêm câu từ doc_2 thứ hạng 2) — **nhiễu nhẹ**.

---

### ❌ Case 5: "Machine learning là gì?" — SAI THỨ HẠNG

| | |
|---|---|
| **Tài liệu kỳ vọng** | doc_1 (Machine Learning là gì?) |
| **Tài liệu retrieve** | **doc_2** [score 0.152] ← SAI → doc_1 [0.117] |
| **Từ khóa khớp** | "machine", "learning" (cả 2 doc đều có) |

**Câu trả lời:**
> "Deep Learning là một kỹ thuật trong Machine Learning... Transformer là kiến trúc hiện đại nhất... Machine Learning (ML) là một nhánh của trí tuệ nhân tạo..."

**Phân tích:** ❌ **ĐÂY LÀ ĐIỂM YẾU RÕ RỆT.** Câu hỏi định nghĩa ML cơ bản, nhưng RAG lại đưa **doc_2 (Deep Learning) lên trên** doc_1 (đúng).

**Tại sao sai?** doc_2 chứa cụm "trong **Machine Learning**" nhiều lần, và do TF-IDF dùng **bigram** ("machine learning") + sublinear scaling, tần suất xuất hiện trong doc_2 làm điểm cao hơn. TF-IDF **không hiểu** rằng câu hỏi "X là gì?" nên ưu tiên document có **tiêu đề** = X.

→ Đây là hạn chế cố hữu của keyword matching: **không hiểu ý định (intent) câu hỏi**.

---

### ❌ Case 6: "Cách nấu phở bò?" (OUT-OF-SCOPE) — XỬ LÝ SAI

| | |
|---|---|
| **Tài liệu kỳ vọng** | KHÔNG có (ngoài phạm vi KB) |
| **Tài liệu retrieve** | doc_3 [score 0.090] → doc_1 [0.050] |
| **Từ khóa khớp** | "cách" (từ chung chung!) |

**Câu trả lời (SAI HOÀN TOÀN):**
> "Các mô hình Transformer như BERT và GPT đã cách mạng hóa NLP... Reinforcement learning dạy agent cách hành động..."

**Phân tích:** ❌ **LỖI NGHIÊM TRỌNG NHẤT.** Câu hỏi về nấu ăn — hoàn toàn không liên quan AI/ML — nhưng RAG vẫn trả lời bằng tài liệu Transformer/NLP, chỉ vì trùng từ "cách".

**Nguyên nhân:** Hệ thống **KHÔNG có ngưỡng (threshold)** để từ chối câu hỏi ngoài phạm vi. Bất kỳ câu nào có score > 0 đều được trả lời → nguy hiểm trong production (trả lời sai mà vẫn tự tin).

---

## 3. Bảng Tổng Hợp

| # | Câu hỏi | Loại | Doc đúng | Doc top | Kết quả |
|---|---------|------|----------|---------|---------|
| 1 | Có mấy loại học máy? | Liệt kê | doc_1 | doc_1 | ✅ |
| 2 | CNN xử lý dữ liệu nào? | Kỹ thuật | doc_2 | doc_2 | ✅ |
| 3 | RAG hoạt động mấy bước? | Quy trình | doc_4 | doc_4 | ✅ |
| 4 | Vector database cho RAG? | Công cụ | doc_4 | doc_4 | ✅ |
| 5 | Machine learning là gì? | Định nghĩa | doc_1 | **doc_2** | ❌ |
| 6 | Cách nấu phở bò? | Out-of-scope | (none) | doc_3 | ❌ |

**Trên golden set lớn hơn (14 câu):** Hit Rate@2 = **100%**, MRR = **0.929** (doc đúng gần như luôn nằm trong top-2, thường ở vị trí #1).

---

## 4. Đánh Giá Khi Nào RAG Này Phù Hợp / Không Phù Hợp

### ✅ PHÙ HỢP khi:
- Câu hỏi chứa **từ khóa đặc trưng** (tên riêng: "CNN", "RAG", "vector database")
- Knowledge base **nhỏ** (vài chục docs), nội dung **ít trùng lặp**
- User hỏi đúng phạm vi, không hỏi linh tinh
- Cần giải pháp **nhẹ, không cần GPU/API**, chạy offline

### ❌ KHÔNG PHÙ HỢP khi:
- Câu hỏi **diễn đạt khác từ ngữ** trong tài liệu (semantic gap)
- KB có nhiều docs **nội dung chồng lấn** (như doc_1 vs doc_2 đều nói "machine learning")
- Cần **từ chối** câu hỏi ngoài phạm vi (thiếu threshold)
- Cần câu trả lời **diễn đạt tự nhiên** (extractive chỉ ghép câu, đôi khi rời rạc)

---

## 5. Đề Xuất Cải Thiện (theo mức độ ưu tiên)

| Ưu tiên | Vấn đề | Giải pháp |
|---------|--------|-----------|
| 🔴 Cao | Out-of-scope trả lời sai | Thêm **score threshold** (vd < 0.12 → "Tôi không có thông tin về câu hỏi này") |
| 🔴 Cao | Không hiểu intent ("X là gì" → ưu tiên doc tiêu đề X) | Cộng điểm nếu query khớp **title** của doc |
| 🟡 TB | Keyword matching không hiểu ngữ nghĩa | Thay TF-IDF bằng **sentence-transformers** (semantic embedding) |
| 🟡 TB | Câu trả lời rời rạc | Thay extractive bằng **LLM generation** dùng context |
| 🟢 Thấp | KB nhỏ | Dùng **FAISS/ChromaDB** khi scale lên hàng nghìn docs |

---

## 6. Kết Luận

RAG do SmartAgent tạo **đạt yêu cầu cho một prototype/demo**:
- ✅ Retrieval tốt với câu hỏi có từ khóa rõ (Hit Rate 100%, MRR 0.929)
- ✅ Trích dẫn nguồn đầy đủ, có điểm số minh bạch
- ⚠️ Có 2 điểm yếu cố hữu của TF-IDF: nhầm intent ("là gì") và không lọc out-of-scope

**Giá trị của bài đánh giá này:** Không chỉ "nhìn thấy nó chạy", mà **đo được bằng số liệu** và **giải thích được vì sao** mỗi câu trả lời như vậy. Đây là cách kiểm chứng chất lượng RAG đúng chuẩn — soi từng case: hỏi gì, lấy tài liệu nào, vì sao, có hợp lý không.

> Bản thân SmartAgent cũng có thể được giao chính bài eval này để **tự phát hiện và sửa** các điểm yếu trên — minh chứng cho khả năng tự cải thiện.
