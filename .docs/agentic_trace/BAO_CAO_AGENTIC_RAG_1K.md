# Báo cáo Agentic — Năng lực tự tư duy & xây dựng (bài toán: Chatbot RAG ~1000 users)

> **Tóm tắt cho sếp:** Chúng tôi giao cho Agent đúng một bài toán thực tế — *"xây chatbot RAG cho ~1000 nhân viên hỏi đáp tài liệu nội bộ, đa định dạng, phân quyền theo phòng ban"* — và ghi lại **toàn bộ** quá trình nó suy nghĩ & hành động, không cắt xén, không dàn dựng. Báo cáo này trình bày 2 lần chạy THẬT để chứng minh agent: (1) **tự đào sâu bản chất** bài toán thay vì làm theo nghĩa đen, (2) **biết dừng lại hỏi** khi thiếu thứ chỉ con người cấp được, (3) khi có đủ điều kiện thì **tự build sản phẩm thật, tự kiểm thử, và tự cho một "giám khảo" độc lập nghiệm thu**.
>
> Mọi trace gốc kèm theo: `trace_report.md` (lần 1) và `trace_report_full.md` (lần 2, 1258 dòng).

---

## 1. Vì sao báo cáo này đáng tin

Đây **không phải** slide marketing. Mỗi câu dưới đây truy được về một event có thật trong log:

- **Trace 1** — `trace_report.md`: agent gặp bài toán khi sandbox **chưa** có credentials thật + tài liệu thật.
- **Trace 2** — `trace_report_full.md`: agent gặp đúng bài toán đó khi **đã** được cấp tài liệu mẫu thật (4 phòng ban) + AWS Bedrock thật.

Hai lần cho thấy 2 mặt của cùng một năng lực: **biết khi nào phải hỏi, và khi đủ điều kiện thì làm tới nơi**.

---

## 2. Trace 1 — Khi thiếu điều kiện: Agent ĐÀO SÂU rồi DỪNG LẠI HỎI (không làm ẩu)

Agent không lao vào code. Bước đầu tiên là **tự mổ xẻ bài toán** (trích nguyên văn thinking của agent):

> **"1000 users" là gì?** — Cực kỳ mơ hồ. 1000 đăng ký vs 1000 đồng thời là 2 kiến trúc khác nhau:
> - 1000 đăng ký, ~10-50 đồng thời → in-process vector DB (Chroma/FAISS) + 1 server đủ
> - 1000 đồng thời → phải dùng vector DB server-mode (Qdrant/Milvus), Redis cache, multi-worker, queue
>
> **"PDF/Word/Excel" — đây là cái BẪY chính:** … Excel KHÔNG phải document text — là dữ liệu bảng. Chunk Excel như text sẽ phá nát ngữ nghĩa hàng/cột …
>
> **"Phân quyền theo phòng ban" — cũng là bẫy:** Cách ngây thơ filter ở app layer → fail vì user vẫn truy cập qua API. Cách đúng: metadata filter **Ở VECTOR DB** …

Sau khi đào sâu, agent **gom 5 câu hỏi chốt** kèm bảng trade-off và đề xuất kiến trúc, rồi **dừng lại** — vì 2 thứ nó cần (LLM credentials thật + tài liệu thật) chỉ con người cấp được. Trích kết luận của agent:

> *"Tôi sẽ không build cho đến khi có câu trả lời cho mục LLM và file mẫu — vì đây là 2 thứ KHÔNG mock được mà vẫn ra sản phẩm thật. **Mock LLM hay mock dữ liệu = chứng minh được zero** về việc app hoạt động thật."*

**Ý nghĩa cho sếp:** đây chính là hành vi ta muốn ở một kỹ sư giỏi — không "demo cho có" bằng dữ liệu giả rồi báo cáo thành công. Agent **từ chối tự lừa mình và lừa người dùng**.

---

## 3. Trace 2 — Khi đủ điều kiện: Agent TỰ BUILD → TỰ KIỂM → GIÁM KHẢO NGHIỆM THU

Lần này chúng tôi cấp cho agent tài liệu mẫu thật của 4 phòng ban (HR/Finance/Engineering/Admin, đa định dạng) + AWS Bedrock thật, và trả lời dứt khoát 5 câu hỏi. Agent chạy **trọn vẹn không cần can thiệp**.

### Con số thực tế của lần chạy

| Chỉ số | Giá trị |
|--------|---------|
| Tổng thời gian | **~20 phút** (1213 giây) |
| Tổng sự kiện ghi nhận | **3071 events** |
| Lượt gọi công cụ | **99** |
| — Suy nghĩ (`think`) | 14 |
| — Chạy lệnh thật (`shell_exec`) | 63 |
| — Ghi file code (`write_file`) | 7 |
| — Kiểm thử web app (`verify_webapp`) | 4 |
| — **Giám khảo mù độc lập (`spawn_evaluator`)** | **2** |
| — Đọc file (`read_file`) | 9 |
| Lần phải hỏi lại người dùng | **0** (đã đủ thông tin) |

### Agent tư duy thế nào trước khi build (trích nguyên văn)

> **Bản chất:** Nhân viên hỏi tài liệu nội bộ → cần *grounded answer* (không bịa), respect ACL phòng ban, không leak chéo.
>
> **ACL phải áp ở retrieval level (filter), không chỉ ở generate level** (vì context vẫn leak qua prompt). Cũng không chỉ ở UI.
>
> **Anti-hallucination:** out-of-scope question → phải refuse, không bịa. **Citation:** phải show nguồn để user verify.

Agent tự đặt **Definition of Done đo được** (7 tiêu chí), gồm cả ca khó:
- *HR user hỏi câu chỉ có trong Finance doc → KHÔNG retrieve được → refuse* (kiểm thử phân quyền thật)
- *Hỏi câu out-of-scope → refuse "không có thông tin"* (kiểm thử chống bịa)
- *Hỏi 1 cell cụ thể trong file Excel → answer đúng* (kiểm thử chunking bảng)

### Sản phẩm agent thật sự tạo ra

Một web app RAG hoàn chỉnh, chạy được, dùng Bedrock thật (Titan Embeddings v2 + Claude):

```
/workspace/app/main.py     — FastAPI server + chat UI + auth + ACL
/workspace/app/rag.py      — pipeline: ingest đa định dạng → embed (Titan) → retrieve có filter → generate (Claude) + citation + refusal
/workspace/app/users.py    — login, session, phân quyền 4 phòng ban (Admin xem tất cả)
/workspace/app/verify.py   — script tự kiểm thử các tiêu chí DoD
/workspace/app/users.json  — user store
/workspace/app/server.log  — log chạy thật
```

### Điểm mấu chốt: Giám khảo mù độc lập (spawn_evaluator)

Trước khi được báo "hoàn thành", agent **bắt buộc** triệu một giám khảo độc lập (model Opus, **không** thấy quá trình agent làm) để tự điều tra trên sản phẩm thật và phán quyết. Giám khảo này tự mở source code, chạy thử app, kiểm các ca khó — rồi báo cáo cả **những hạn chế còn lại một cách trung thực**, ví dụ:

> - *Vector store in-memory: re-ingest mỗi lần restart; corpus lớn (>1000 chunks) nên chuyển Qdrant/pgvector.*
> - *Sessions in-memory: production multi-worker cần Redis.*
> - *Chưa có rate limit / audit log: nội bộ ~1000 user chấp nhận được, nhưng nên thêm trước khi mở rộng.*

**Ý nghĩa cho sếp:** sản phẩm không chỉ "chạy được" mà còn được một bên thứ ba độc lập soi và **nói thật về giới hạn** — đúng tinh thần không phóng đại.

---

## 4. Kết luận

Trên đúng một bài toán thực tế (RAG 1k users), Agent thể hiện đủ chuỗi năng lực agentic:

1. **Tự phát triển bài toán** — phát hiện 3 cái "bẫy" (quy mô mơ hồ, Excel ≠ text, phân quyền phải ở tầng retrieval) mà người mới dễ bỏ qua.
2. **Trung thực, không tự-mock** — thiếu điều kiện thật thì dừng lại hỏi, không demo bằng đồ giả.
3. **Tự xây sản phẩm thật** — 7 file code, dùng Bedrock thật, 63 lệnh thật, ~20 phút không cần người can thiệp.
4. **Tự kiểm thử + giám khảo độc lập** — verify theo DoD đo được + 1 giám khảo mù nghiệm thu và báo cáo giới hạn trung thực.

**Đính kèm để sếp soi chi tiết:**
- `trace_report.md` — toàn bộ trace lần 1 (tư duy + dừng hỏi).
- `trace_report_full.md` — toàn bộ trace lần 2, 1258 dòng (từng bước thinking, từng lệnh, từng file, giám khảo).
- `trace_events_full.json` — dữ liệu sự kiện thô (3071 events) để kiểm chứng độc lập.
