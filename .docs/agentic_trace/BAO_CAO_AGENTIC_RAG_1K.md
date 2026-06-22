# Agent tự tư duy & tự xây sản phẩm — Trình bày qua bài toán Chatbot RAG cho ~1000 users

## Mục tiêu của phần trình bày

Chứng minh Agent **không làm theo nghĩa đen** mà tự phát triển bài toán, tự xây sản phẩm thật, tự kiểm thử và tự nghiệm thu độc lập. Để minh chứng, chọn một bài toán thực tế — *"chatbot RAG cho ~1000 nhân viên hỏi đáp tài liệu nội bộ, tài liệu đa định dạng, phân quyền theo phòng ban"* — và ghi lại **toàn bộ** quá trình Agent suy nghĩ và hành động, nguyên trạng, không cắt xén.

Toàn bộ kết quả đến từ **2 lần chạy thật**, trace gốc kèm theo (`trace_report.md`, `trace_report_full.md` — 1258 dòng).

---

## Phần 1 — Khi thiếu điều kiện: Agent đào sâu và biết dừng lại hỏi

Khi sandbox **chưa** có credentials thật và tài liệu thật, Agent không lao vào code. Bước đầu tiên là tự mổ xẻ bài toán (trích nguyên văn dòng suy nghĩ):

> **"1000 users" là gì?** — Cực kỳ mơ hồ. 1000 đăng ký vs 1000 đồng thời là 2 kiến trúc khác nhau: 1000 đăng ký (~10-50 đồng thời) thì Chroma/FAISS in-process là đủ; 1000 đồng thời thật thì cần Qdrant server + Redis + multi-worker.
>
> **"PDF/Word/Excel" — đây là cái bẫy chính:** Excel KHÔNG phải document text mà là dữ liệu bảng. Chunk Excel như text sẽ phá nát ngữ nghĩa hàng/cột.
>
> **"Phân quyền theo phòng ban" — cũng là bẫy:** Filter ở app layer là sai vì user vẫn truy cập được qua API. Phải filter ở **vector DB metadata level**.

Sau khi đào sâu, Agent gom **5 câu hỏi chốt** kèm bảng so sánh trade-off, rồi **dừng lại** — vì hai thứ còn thiếu (credentials LLM thật + tài liệu thật) chỉ con người cấp được. Kết luận của Agent:

> *"Không build cho tới khi có LLM thật và file thật — vì đây là 2 thứ không mock được mà vẫn ra sản phẩm thật. **Mock LLM hay mock dữ liệu = chứng minh được zero.**"*

**Điểm cần lưu ý:** đây đúng là hành vi của một kỹ sư giỏi — không "demo cho có" bằng dữ liệu giả rồi báo thành công. Agent từ chối tự lừa mình và lừa người dùng.

---

## Phần 2 — Khi đủ điều kiện: Agent tự build nguyên một sản phẩm chạy được

Khi được cấp tài liệu mẫu thật của 4 phòng ban (HR / Finance / Engineering / Admin, đủ định dạng) + AWS Bedrock thật, và trả lời dứt khoát 5 câu hỏi, Agent **chạy một mạch ~20 phút, không cần can thiệp**.

### Số liệu thực tế của lần chạy

| Chỉ số | Giá trị |
|--------|---------|
| Thời gian tự chạy | **~20 phút** (1213 giây) |
| Tổng số bước ghi nhận | **3071 events** |
| Số lần gọi công cụ | **99** |
| — Tự suy nghĩ (`think`) | 14 |
| — Chạy lệnh thật trong sandbox (`shell_exec`) | 63 |
| — Tự viết file code (`write_file`) | 7 |
| — Tự kiểm thử web app (`verify_webapp`) | 4 |
| — **Tự gọi giám khảo độc lập nghiệm thu (`spawn_evaluator`)** | **2** |
| Số lần phải quay lại hỏi | **0** (đã đủ thông tin) |

### Tư duy trước khi build (trích nguyên văn)

> **Bản chất:** Nhân viên hỏi tài liệu nội bộ → cần câu trả lời *grounded* (không bịa), tôn trọng phân quyền phòng ban, không leak chéo.
>
> **Phân quyền phải áp ở tầng retrieval (filter), không chỉ ở tầng generate** — nếu chỉ chặn lúc generate thì context vẫn leak qua prompt.
>
> **Chống bịa:** câu ngoài phạm vi → phải từ chối, không bịa. **Citation:** phải chỉ rõ nguồn để người dùng kiểm chứng.

Từ đó Agent tự đặt **tiêu chí hoàn thành đo được** (7 tiêu chí), bao gồm các ca khó:
- HR hỏi câu chỉ có trong tài liệu Finance → phải **KHÔNG** lấy được → từ chối (kiểm thử phân quyền).
- Hỏi câu hoàn toàn ngoài phạm vi → từ chối "không có thông tin" (kiểm thử chống bịa).
- Hỏi đúng một ô trong file Excel → trả lời đúng (kiểm thử xử lý bảng).

### Sản phẩm Agent tự tạo ra

Một web app RAG hoàn chỉnh, chạy được, dùng Bedrock thật (Titan Embeddings v2 để embed + Claude để trả lời):

```
/workspace/app/main.py     — FastAPI server + giao diện chat + auth + phân quyền
/workspace/app/rag.py      — pipeline: đọc tài liệu đa định dạng → embed (Titan) → retrieve có filter phòng ban → trả lời (Claude) + citation + từ chối khi ngoài phạm vi
/workspace/app/users.py    — login, session, phân quyền 4 phòng ban (Admin xem tất cả)
/workspace/app/verify.py   — script tự kiểm thử theo tiêu chí
/workspace/app/users.json  — dữ liệu user
/workspace/app/server.log  — log chạy thật
```

### Điểm nổi bật: Agent tự gọi giám khảo độc lập soi lại chính nó

Cơ chế bắt buộc: trước khi được phép báo "hoàn thành", Agent phải triệu một giám khảo độc lập (model Opus, **không** thấy quá trình Agent làm) tự điều tra trên sản phẩm thật rồi phán quyết. Giám khảo này tự mở code, tự chạy thử app, tự kiểm các ca khó — và báo lại cả **những hạn chế còn lại một cách thẳng thắn**:

> - Vector store đang in-memory, restart phải ingest lại; corpus lớn nên chuyển Qdrant/pgvector.
> - Session in-memory; nếu chạy multi-worker production thì cần Redis.
> - Chưa có rate limit / audit log; nội bộ ~1000 user tạm ổn nhưng nên thêm trước khi mở rộng.

Sản phẩm không chỉ "chạy được" mà còn được một bên độc lập soi và **nói thật về giới hạn** — không phóng đại.

---

## Phần 3 — Tiếp thu feedback: nâng chiều sâu tư duy + đo được

Sau lần trình bày đầu, có feedback rằng Agent còn "chỉ nhích, chưa tư duy đủ rộng" — cụ thể: giả định quy mô cho tiện ("corpus nhỏ"), chưa đào sâu xử lý nội dung file, và chưa cân nhắc nhiều phương án. Đối chiếu với tài liệu *"Phân tích Tư duy của AI"* (cơ chế Tree-of-Thoughts: sinh nhiều nhánh giải pháp, so sánh trade-off rồi mới chọn; và tự phản chiếu "Wait/Aha"), chúng tôi đã **biến phản hồi đó thành thước đo định lượng** rồi cải tiến có kiểm chứng.

**Cách đo:** một "giám khảo" Opus độc lập chấm dòng suy nghĩ thật của Agent theo 7 tiêu chí (ánh xạ từ các cơ chế trong tài liệu):

| Mã | Tiêu chí | Nguồn (tài liệu) |
|----|----------|------------------|
| D1 | Suy luận quy mô định lượng (người × file, tách trục đồng thời/khối lượng) | mục 1 |
| D2 | Đào sâu xử lý nội dung (Excel: ngữ nghĩa hàng/cột) | mục 1 |
| D3 | Phân rã + làm phần khó nhất trước | mục 1, 5 |
| D4 | Tư duy đa nhánh (Tree-of-Thoughts) | mục 2.2 |
| D5 | Tự phản chiếu / sửa sai giữa chừng (Wait/Aha) | mục 4.1 |
| D6 | Chấm điểm có trọng số khi chọn nhánh (reward model) | mục 3.1 |
| D7 | Biết khi mình không biết (Self-RAG / ranh giới tri thức) | mục 4.2 |

**Kết quả đo NHIỀU LẦN (trung thực — đo 4 lần cùng prompt, lấy tỉ lệ pass):**

| Tiêu chí | D1 | D2 | D3 | D4 | D5 | D6 | D7 | TB |
|----------|----|----|----|----|----|----|----|----|
| Tỉ lệ pass / 4 lần | 50% | 50% | 50% | 25% | 25% | 0% | 25% | **2.2/7** |

> **Phát hiện quan trọng (đã sửa lại cho đúng):** khi đo 1 lần duy nhất, điểm dao động 0/7 → 5/7 cho **cùng một prompt** — tức kết quả 1 lần bị nhiễu nặng, không đáng tin. Đo 4 lần cho thấy năng lực tư duy hiện **CHƯA ỔN ĐỊNH**: có lần Agent đào rất sâu (5/7), có lần làm hời hợt (0/7). Đây là vấn đề lớn hơn việc "thiếu đề mục": các cơ chế tư duy đã được dạy qua prompt nhưng Agent **thực thi không nhất quán**.

**Hướng khắc phục (đang triển khai):** giống cách đã làm thành công với khâu nghiệm thu (ép `spawn_evaluator` bằng cơ chế cứng trong vòng lặp, không chỉ bằng lời nhắc) — cần một cơ chế **bắt buộc** Agent đi đủ chuỗi tư duy (đào quy mô → đa nhánh → chấm điểm) trước khi được bắt tay xây dựng. Prompt-only đã chứng minh là chưa đủ để đạt độ ổn định cần thiết cho môi trường doanh nghiệp.

**Điểm cốt lõi về phương pháp:** mỗi phản hồi về chất lượng tư duy được chuyển thành tiêu chí đo (rubric D1–D7), chấm bằng giám khảo độc lập **nhiều lần** để tách tín hiệu khỏi nhiễu — không kết luận vội từ một lần chạy may mắn.

---

## Tổng kết năng lực đã chứng minh

Trên đúng một bài toán thực tế (RAG 1k users), Agent thể hiện trọn chuỗi năng lực agentic:

1. **Tự phát triển bài toán** — tự phát hiện 3 cái bẫy (quy mô mơ hồ, Excel ≠ text, phân quyền phải ở tầng retrieval) mà người làm vội dễ bỏ qua.
2. **Trung thực, không tự-mock** — thiếu đồ thật thì dừng lại hỏi, không demo bằng đồ giả.
3. **Tự build sản phẩm thật** — 7 file code, dùng Bedrock thật, 63 lệnh thật, ~20 phút không cần can thiệp.
4. **Tự kiểm thử + giám khảo độc lập nghiệm thu** — verify theo tiêu chí đo được + một giám khảo mù phán quyết và báo cáo giới hạn trung thực.
5. **Tư duy đa nhánh (Tree-of-Thoughts) + tự phản chiếu** — đã dạy qua prompt (sinh nhiều phương án, so trade-off, tự nghi ngờ/sửa sai). Đo nhiều lần cho thấy năng lực này CÓ xuất hiện nhưng CHƯA ỔN ĐỊNH (trung bình 2.2/7, dao động 0–5/7) → đang chuyển sang cơ chế cứng để ép thực thi nhất quán (xem Phần 3).

**Tài liệu đính kèm để kiểm chứng chi tiết:**
- `trace_report.md` — toàn bộ trace lần 1 (Agent tư duy rồi dừng hỏi).
- `trace_report_full.md` — toàn bộ trace lần 2, 1258 dòng (từng bước suy nghĩ, từng lệnh, từng file, giám khảo).
- `trace_events_full.json` — 3071 sự kiện thô, phục vụ kiểm chứng độc lập.
- `trace_events_ToT.json` — trace sau khi thêm tư duy đa nhánh (đạt 5/5 chiều sâu).
- `eval_depth.py` — bộ chấm 5 tiêu chí D1–D5 (giám khảo Opus), để đo lại bất kỳ lúc nào.
