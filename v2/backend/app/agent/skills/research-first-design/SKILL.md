---
name: research-first-design
description: Gặp task lạ — nghiên cứu cách làm tốt nhất TRƯỚC khi build. Tự research SOTA, đối chiếu requirement bằng số, phản biện, rồi mới code. Chống đẻ giải pháp yếu vì dựa trí nhớ.
origin: ported-from-nexus
---

# Research-First Design (Nghiên cứu trước khi làm)

## Vì sao có skill này

Lỗi phổ biến nhất khi gặp task lạ: **dựa vào trí nhớ thay vì nghiên cứu**, dẫn đến chọn giải pháp dễ-nhớ thay vì giải pháp ĐÚNG (ví dụ chọn TF-IDF cho RAG vì cài nhanh, trong khi embeddings ngữ nghĩa mới đúng). Skill này bắt buộc nghiên cứu + đối chiếu TRƯỚC khi viết dòng code đầu tiên.

## Nguyên tắc tối thượng

```
KHÔNG BUILD KHI CHƯA RESEARCH. KHÔNG CLAIM SUÔNG.
Mỗi quyết định kỹ thuật phải truy được về BẰNG CHỨNG (số liệu/doc/benchmark/test), không phải trí nhớ.
```

## Quy trình bắt buộc (trước khi build cho task lạ)

### 1. Research cách làm tốt nhất (BẮT BUỘC)
- `web_search` ít nhất 2-3 query về cách tiếp cận SOTA cho LOẠI task này (vd "best RAG architecture 2025", "production vector search small memory").
- Đối chiếu ≥2 lựa chọn khả dĩ. KHÔNG dừng ở lựa chọn đầu tiên nhớ ra.
- Ghi lại phát hiện (dùng `think`): mỗi lựa chọn — ưu/nhược, bằng chứng.

### 2. Đối chiếu requirement bằng CON SỐ
Dùng `think` trả lời: lựa chọn này có chịu được con số THỰC trong yêu cầu không?
- Ràng buộc môi trường (vd: container 512MB RAM, 1 port). Model/lib này có lọt không?
- Quy mô (vd: 1000 user, 10GB data, 100 req/s). Giới hạn thực tế là bao nhiêu?
- Nếu chưa biết → đánh dấu "giả định cần verify" → `web_search` để verify.

### 2.5. DECISION-COMMITMENT GATE (BẮT BUỘC — chống mâu thuẫn nhận-thức/hành-động)

> ⛔ **Lỗi chí mạng cần tránh:** phân tích ra "X NGUY HIỂM/không phù hợp" rồi VẪN cài/dùng X. Nhận thức đúng mà hành động sai = thất bại.

Sau khi đối chiếu, dùng `think` chốt MỘT bảng quyết định RÕ RÀNG — và hành động sau đó PHẢI khớp 100% bảng này:

```
QUYẾT ĐỊNH CÔNG NGHỆ (đã khớp ràng buộc <điền số: vd 512MB RAM>):
- <Hạng mục>: CHỌN <X> | LOẠI <Y vì lý do số>
  vd: Embedding: CHỌN TF-IDF/BM25 (RAM thấp) | LOẠI sentence-transformers (kéo torch >500MB, OOM với 512MB)
- <Hạng mục>: CHỌN ... | LOẠI ...
```

**Quy tắc sắt:**
1. Mọi thứ bị đánh dấu "NGUY HIỂM / không lọt / LOẠI" → **TUYỆT ĐỐI KHÔNG** `pip install` hay dùng nó. Không có ngoại lệ "thử xem sao".
2. Lệnh cài đặt/code TIẾP THEO phải chỉ chứa thứ trong cột CHỌN. Trước khi `shell_exec pip install`, đối chiếu lại: từng gói có nằm trong cột CHỌN không?
3. Nếu thấy mình sắp dùng thứ đã LOẠI → DỪNG, quay lại bảng. Nếu thật sự cần nó → phải đổi bảng quyết định một cách công khai (giải thích vì sao ràng buộc thay đổi), không lén dùng.
4. Nghi ngờ một lựa chọn vẫn rủi ro → `spawn_critic` trước khi cài.

### 3. Phản biện TRƯỚC khi build (quyết định quan trọng)
- Dùng `spawn_critic` cho lựa chọn kiến trúc quan trọng — nó tự research và đưa verdict VALID/QUESTIONABLE/WRONG có bằng chứng cho từng claim.
- Sửa theo phản biện TRƯỚC khi viết code.

### 4. Chỉ build sau khi 3 bước trên xong
- Khi build, mỗi quyết định phải truy được về research ở bước 1-3.

## 3 câu hỏi gốc (áp cho MỌI khẳng định kỹ thuật)
1. **BẰNG CHỨNG?** — claim "đủ nhanh/an toàn/scale được" có số liệu/doc/test không? Chưa có → đánh dấu giả định + verify.
2. **KHỚP CON SỐ REQUIREMENT?** — chịu được con số cụ thể trong yêu cầu không?
3. **CÁI GÌ CÓ THỂ SAI?** — failure mode, edge case, giả định ngầm?

## Định nghĩa "xong research"
Trước khi viết code, verify:
1. Đã `web_search` ≥2-3 lần về cách làm, so sánh ≥2 lựa chọn.
2. Đã đối chiếu lựa chọn với con số requirement + ràng buộc môi trường.
3. (Quyết định quan trọng) đã `spawn_critic` phản biện và sửa theo.

## Sau khi giải xong task — TỰ ĐÚC KẾT
Dùng `create_skill` lưu lại phương pháp đã dùng (vd "cách build RAG production") để LẦN SAU không phải research lại từ đầu. Đây là self-extension thật: research → giải → đúc kết → tái dùng.
