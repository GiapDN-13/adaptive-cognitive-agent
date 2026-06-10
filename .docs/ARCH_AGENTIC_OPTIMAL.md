# Kiến trúc Agentic Tối ưu — SmartAgent V2

**Phiên bản:** 1.0 — 2026-06-08
**Mục tiêu:** Phát triển SmartAgent V2 thành **agent tự chủ** — gặp task lạ thì TỰ nghiên cứu cách làm đúng, tự dựng môi trường, tự kiểm chứng dùng được, tự đúc kết để lần sau khá hơn. 

> **Nguyên tắc xương sống:** Mọi cơ chế trong tài liệu này phải **tổng quát** (áp cho mọi task), không "dạy để thi" (teaching to the test). Nếu một cải tiến chỉ giúp qua đúng bài RAG → đó là chống chế, bị loại.

---

## 1. Tóm tắt điều hành (cho sếp)

SmartAgent V2 đã có bộ khung agentic đúng hướng (vòng ReACT + quality loop + self-extension). Tuy nhiên qua quan sát thực tế, nó còn các lỗ hổng khiến kết quả "có giao diện nhưng không dùng được", phản xạ **"đập đi xây lại" khi gặp lỗi**, và quan trọng nhất — **đẻ ra giải pháp yếu vì dựa vào trí nhớ thay vì tự nghiên cứu**.

Tài liệu này đề xuất kiến trúc tối ưu bằng **6 trụ cột tổng quát** (không trụ nào gắn cứng vào RAG):

| Trụ cột | Trạng thái | Năng lực tổng quát nó tạo ra |
|---------|-----------|-------------------|
| 1. ReACT loop + Quality-First gate (+ test-first, two-stage review) | ✅ Đã có, nâng | Khung thực thi + nghiệm thu theo tiêu chí đo được |
| 2. **Debug-before-rewrite discipline** | 🆕 Mới | Agent debug trước, chỉ hỏi khi muốn rewrite lớn |
| 3. **Usable-acceptance gate (`verify_webapp`)** | 🆕 Mới | Chứng minh MỌI web app dùng được bằng HTTP thật, không chỉ "200 OK" |
| 4. **Research-First Capability discipline** | 🆕 Mới | Task lạ → tự research SOTA + đối chiếu requirement, TỰ suy ra thiết kế đúng |
| 5. **Cài đặt đáng tin cậy + Self-extension thật** | 🔧🆕 | Agent tự cài bất kỳ deps nào; tự đúc kết skill sau khi giải |
| 6. **UI Blueprint Skill** | 🆕 Mới | MỌI UI agent build đều sạch/dùng được — 12 rule encode được |

**Bằng chứng nghiệm thu (phép thử):** giao SmartAgent task RAG chatbot mà KHÔNG hand-feed gì — agent tự research, tự chọn stack, tự build, tự kiểm chứng dùng được (`verify_webapp` + Hit Rate@4 ≥ 0.8), tự đúc kết blueprint. Nếu agent làm được task nó **chưa từng được dạy** → kiến trúc đạt.

---

## 2. Bối cảnh & Vấn đề (root cause — đã verify trong code)

### 2.1 Lỗ hổng 1 — Nghiệm thu hời hợt
`handle_verify_work` (`v2/backend/app/agent/builtin_tools.py:220-231`) tự đánh giá bằng heuristic yếu: chỉ quét output tìm từ khóa lỗi (`error`, `traceback`, `exception`, `failed`). Nếu không có từ khóa lỗi → verdict `LIKELY_PASS`.

> **Hệ quả:** Một web server trả về trang trắng HTTP 200 KHÔNG có từ khóa lỗi → được coi là PASS. Agent báo "hoàn thành" trong khi app không dùng được. Đây chính là hiện tượng "có giao diện nhưng không dùng được".

### 2.2 Lỗ hổng 2 — Phản xạ "đập đi xây lại"
`build_system_prompt` (`v2/backend/app/agent/prompts.py`) có quy trình DoD → build → verify → review, nhưng **không có luật nào** buộc agent debug trước khi rewrite, cũng không buộc hỏi ý kiến user trước khi đổi kiến trúc.

> **Hệ quả:** Gặp lỗi CSS/layout, agent tuyên bố "rebuild hoàn toàn frontend với kiến trúc mới" — đốt thời gian, không sửa đúng gốc, và không hỏi user (dù user là chuyên gia đang giám sát).

### 2.3 Lỗ hổng 3 — Đẻ ra giải pháp yếu (root cause TỔNG QUÁT)
Lần build RAG trước, agent tự chế **TF-IDF** (báo cáo cũ tự kết luận là demo-only) thay vì embeddings ngữ nghĩa. Đây KHÔNG phải vì "thiếu blueprint RAG" — mà là **2 root cause tổng quát**, áp cho mọi domain:
1. **Dựa vào trí nhớ thay vì nghiên cứu** cách làm tốt nhất → chọn giải pháp dễ-nhớ thay vì đúng.
2. **`pip install` chậm/flaky → timeout** (`Dockerfile.sandbox` chỉ có python bare) → agent đi đường tắt, chọn thứ cài nhanh (TF-IDF không cần tải model).

> **Sửa đúng gốc, KHÔNG chống chế:** không pre-bake deps RAG (chỉ giúp qua bài RAG). Thay vào đó: (a) bắt agent **tự research** trước khi build — Trụ 4; (b) làm việc **tự cài deps đáng tin cậy** cho mọi thư viện — Trụ 5.

### 2.4 Lỗ hổng 4 — UI nhìn dở / chưa hoàn thiện (dạng "không dùng được" thứ 2)
"Có giao diện nhưng không dùng được" có **2 dạng**: (a) hỏng chức năng — Trụ 3 `verify_webapp` bắt; (b) **UI xấu/thiếu trạng thái/khó dùng** — chưa cơ chế nào xử lý. Agent không có chuẩn thiết kế nên ra UI thiếu loading/empty/error state, màu lộn xộn, spacing tùy tiện → "trông như chưa làm xong".

### 2.5 Ràng buộc cứng (là THÔNG TIN để agent tự đối chiếu, không phải để ta chọn thay nó)
- Container: **512MB RAM** (`v2/backend/app/config.py:40`) → agent phải tự cân nhắc khi chọn model/lib.
- Chỉ **port 8080** map ra host (`docker_manager.py`) → web app phải serve trên `0.0.0.0:8080`.
- Vòng lặp: **MAX_ITERATIONS = 150** (`loop.py:25`).
- Skill catalog: tối đa **30 skill** hiển thị trong prompt (`skill_manager.py:80`), ưu tiên theo `priority_skill_ids`.

Các ràng buộc này được đưa vào prompt như **bối cảnh môi trường** để agent đối chiếu ở Trụ 4 bước 2 — không phải để ta hardcode lựa chọn stack thay agent.

---

## 3. Kiến trúc Agentic Tối ưu

### 3.1 Sơ đồ tổng thể

```
                            ┌─────────────────────────────────────────┐
   user task                │           SmartAgent Core               │
      │                     │                                         │
      ▼                     │  ┌───────────────────────────────────┐  │
┌───────────┐   WebSocket   │  │   ReACT Loop (max 150 iter)        │  │
│  Frontend │◄─────────────►│  │   Think → Act → Observe → Repeat   │  │
│  (React)  │   streaming   │  └───────────────┬───────────────────┘  │
└───────────┘               │                  │ tool_use               │
      ▲                     │      ┌───────────▼────────────┐          │
      │ "Open App" :8080     │      │   Tool Registry         │          │
      │                     │      │   + Pre/Post Hooks      │          │
      │                     │      └───────────┬────────────┘          │
      │                     │                  │                        │
      │      ┌──────────────┼──────────────────┼────────────────────┐  │
      │      ▼              ▼                  ▼                    ▼  │
      │  ┌────────┐  ┌─────────────┐  ┌──────────────┐  ┌────────────┐│
      │  │ Quality│  │ Debug-first  │  │ Usable gate  │  │ Knowledge  ││
      │  │ gate   │  │ discipline   │  │ verify_webapp│  │ as Skill   ││
      │  │ (DoD)  │  │ (Trụ 2 🆕)   │  │ (Trụ 3 🆕)   │  │ (Trụ 4 🆕) ││
      │  └────────┘  └─────────────┘  └──────┬───────┘  └────────────┘│
      │                                       │ HTTP thật             │
      │                                       ▼                        │
      │                            ┌─────────────────────┐             │
      └────────────────────────────│  Docker Sandbox     │             │
                                   │  512MB, port 8080   │             │
                                   │  Pre-baked RAG deps │ (Trụ 5 🔧)   │
                                   │  (FAISS+fastembed)  │             │
                                   └─────────────────────┘             │
                                    └─────────────────────────────────┘
```

### 3.2 Trụ cột 1 — ReACT Loop + Quality-First Gate (đã có, giữ nguyên)

Vòng lặp Think→Act→Observe (tối đa 150 iteration), mỗi quyết định lớn đi qua:
**DoD (tiêu chí đo được) → Build → `verify_work` từng tiêu chí → Adversarial review (`spawn_subagent`) → Report có số liệu.**

Đã có cơ chế ổn định: stall-retry backoff (2/4/8s), max_tokens continuation, context windowing. (Xem `.docs/SPEC_FIX_TIMEOUT_UI.md`.)

**Nâng cấp từ research (superpowers — xem §9):**
- **Test-First / "watch it fail"**: với code có thể test, viết test (hoặc repro) và **xác nhận nó FAIL đúng lý do** TRƯỚC khi implement. "Nếu chưa thấy test fail, bạn không biết nó kiểm đúng thứ cần kiểm." Khớp với reproduce-before-fix (Trụ 2).
- **Two-stage review**: tách review thành **(1) spec-compliance** (code có đúng yêu cầu không — không thừa, không thiếu) → CHỈ khi pass mới tới **(2) code-quality**. Mỗi stage có vòng fix→review-lại; KHÔNG sang task mới khi còn issue mở.
- **No-placeholder**: cấm `TODO/TBD/"add error handling later"` trong plan/code coi-như-xong.

### 3.3 Trụ cột 2 — Debug-before-Rewrite Discipline 🆕

**Nguyên tắc:** Khi gặp lỗi, **fix tối thiểu là mặc định**. Lỗi là bằng chứng của một defect *cụ thể*, không phải bằng chứng kiến trúc sai.

Quy trình bắt buộc khi gặp bug (mô phỏng pattern production-grade từ `oh-my-pi/.omp/commands/fix-issues.md` — xem §9):

1. **Reproduce TRƯỚC** — tái hiện lỗi bằng lệnh/test tối thiểu, xác nhận nó *thực sự* fail. Chưa reproduce được thì KHÔNG sửa.
2. **Phân loại 3-nhánh** trước khi đụng vào code:
   - `Reproduced` → tiếp tục sửa.
   - `Not-reproduced` → DỪNG, báo "không tái hiện được + thiếu thông tin gì".
   - `Out-of-scope / không phải bug` → DỪNG, báo giải thích.
3. **Isolate** — đọc đúng file/dòng lỗi, thêm log/print, nêu **root cause 1 câu**.
4. **Fix at source, not symptom** — sửa đúng gốc, KHÔNG vá triệu chứng; **KHÔNG mở rộng phạm vi** (chỉ sửa bug đang báo, không refactor code lân cận "cho đẹp"). Ưu tiên edit file hiện có thay vì regenerate.
5. **Re-verify** — chạy lại `verify_work`/repro đúng tiêu chí đó: RED → GREEN. Cấm câu "chắc chạy được rồi".

**Plateau detection (chống retry mù):** nếu cùng một *lớp lỗi* lặp lại ≥3 lần trong một task → DỪNG retry, escalate: `spawn_critic`/high-reasoning hoặc `ask_user`. (Đúng tinh thần "chỉ hỏi khi cần" — không hỏi vặt, nhưng bế tắc lặp thì phải hỏi.)

**Khi nào được rewrite lớn / đổi kiến trúc / đổi công nghệ:** CHỈ khi có bằng chứng thiết kế là root cause, và **PHẢI `ask_user` trước** (kèm 2-4 options: "Debug bản hiện tại (khuyến nghị)", "Rewrite module X", "Để tôi tự quyết") rồi DỪNG chờ trả lời.

> ⚠️ **Giữ nguyên quyền red-team:** kỷ luật này chỉ áp cho *thay đổi kỹ thuật trên chính bản build của agent*. KHÔNG hạn chế thực thi lệnh, sinh exploit/payload, command injection, security testing (ROE giữ nguyên).

### 3.4 Trụ cột 3 — Usable-Acceptance Gate: `verify_webapp` 🆕

Tool mới chạy **HTTP thật** vào app đang chạy ở `localhost:8080` *bên trong container* (cùng network namespace — không phụ thuộc host-port), kiểm tra theo **journey người dùng**:

```
journey = [
  { GET  /        → assert status 200, assert_contains "<chat markup>" },
  { POST /chat    body={question: <câu in-corpus>}
                  → assert_contains <fact CHỈ có trong corpus> },
  { POST /chat    body={question: <câu out-of-scope>}
                  → assert_contains "<câu từ chối>",
                    assert_not_contains <fact bịa> },
]
```

**Khác biệt cốt lõi:** assert trên **response body + luồng thật**, không chỉ status code. Một app "200 OK trang trắng" sẽ **FAIL** ở bước assert_contains → buộc agent sửa cho đến khi dùng được thật.

**Vì sao KHÔNG dùng browser thật** (kết luận từ research dev-browser + chrome-devtools-mcp, §9): headless Chromium ~300MB+ → **không lọt 512MB**. HTTP+body assertion là lựa chọn đúng cho ràng buộc này. Bổ sung 2 nâng cấp nhẹ:
- App build ra **tự expose `/health`** trả JSON `{"hasContent": true, "apiReachable": true}` để bắt sớm lỗi "200 nhưng rỗng/JS chết" mà không cần browser.
- *(Tùy chọn, tương lai)* nếu cần kiểm tra render DOM thật: chạy browser ở **host** qua port 9222 (`dev-browser --connect`), KHÔNG nhét vào sandbox. Không bắt buộc cho demo FastAPI (UI server-rendered, không phụ thuộc JS nặng).

### 3.5 Trụ cột 4 — Research-First Capability Discipline 🆕

> **Nguyên tắc chỉ đạo:** SmartAgent phải **TỰ SINH** giải pháp đúng cho task lạ — KHÔNG hand-feed lời giải sẵn. Đây là khác biệt giữa "agent tự chủ" và "chống chế qua bài test".

Root cause vì sao agent đẻ ra giải pháp yếu (vd TF-IDF cho RAG) là **tổng quát**, không phải thiếu blueprint RAG: nó **dựa vào trí nhớ thay vì nghiên cứu cách làm tốt nhất**. Khắc phục bằng kỷ luật áp cho MỌI domain:

**Trước khi build bất kỳ thứ gì cho task lạ, BẮT BUỘC:**
1. **Research SOTA** — `web_search` cách tiếp cận tốt nhất hiện tại cho loại task này (không dựa trí nhớ). Đối chiếu ≥2 lựa chọn.
2. **Khớp requirement bằng số** — đối chiếu lựa chọn với con số thực (vd 1000 user, 512MB RAM, 10GB data). Công cụ này có chịu được không?
3. **`spawn_critic` phản biện** thiết kế TRƯỚC khi build, nếu là quyết định quan trọng.
4. **Ghi rõ "đây là giả định cần verify"** cho mọi claim chưa có bằng chứng.

Cơ chế này **tổng quát hóa** critical-thinking đã có (`prompts.py` Bước 1.5) thành gate bắt buộc cho task lạ. Ship 1 **meta-skill `research-first-design`** (tổng quát, KHÔNG gắn RAG) mô tả quy trình "gặp task lạ → nghiên cứu → đối chiếu → phản biện → build → đo". Đăng ký vào `priority_skill_ids`.

> **Domain blueprint do AGENT tự sinh:** sau khi giải xong một task (vd RAG), agent dùng `create_skill` **tự đúc kết** thành blueprint cho lần sau (Trụ 5). Mình KHÔNG ship sẵn `rag-blueprint` — đó là chống chế. (Các kỹ thuật cụ thể như Hybrid Search + RRF, embeddings nhẹ... là thứ agent **tự research ra**, không phải mình bơm vào.)

### 3.6 Trụ cột 5 — Môi trường cài đặt đáng tin cậy + Self-Extension thật 🔧🆕

Đổi mục tiêu từ "pre-bake deps RAG để qua bài test" (chống chế) sang **"làm cho việc agent TỰ cài bất kỳ deps nào trở nên đáng tin cậy"** (tổng quát):

**A. Cài đặt đáng tin cậy (sửa root cause timeout, áp cho mọi deps):**
- **pip cache bền** giữa các session (mount cache dir) → cài lần 2 nhanh, không tải lại.
- **Retry + timeout dài hơn** cho `pip install`/tải model — đây chính là nguồn timeout khiến agent đi đường tắt (tự chế bản yếu).
- *(Tùy chọn)* mirror/index nội bộ nếu mạng chậm.
- Kết quả: agent tự cài `fastembed`, `faiss`, hay bất kỳ thư viện nào nó **tự research ra là đúng** — không cần mình đoán trước nó sẽ dùng gì.

**B. Self-extension thật sự (agent tự khá lên):**
- Sau khi giải xong task, agent `create_skill` đúc kết phương pháp (blueprint do **chính nó** sinh) → lần sau gặp task tương tự không phải research lại từ đầu.
- Đây là vòng học thật: research → giải → đúc kết → tái dùng. Khác hẳn việc mình hand-feed.

> **Lưu ý ràng buộc 512MB vẫn còn giá trị** như *thông tin để agent tự đối chiếu* (Trụ 4 bước 2), KHÔNG phải để mình chọn stack thay nó.

### 3.7 Trụ cột 6 — UI Blueprint Skill 🆕 (trị "UI nhìn dở")

Giải quyết Lỗ hổng 4. Ship một skill `ui-blueprint` mã hóa **12 rule UI cụ thể, encode được** (rút từ DESIGN.md production thật của Claude/Airtable/Cal/Apple + open-design — xem §9). Tóm tắt:

1. **1 accent color** duy nhất + neutral grays (#f5f5f5/#e5e7eb/#6b7280); không thêm màu nhấn thứ 2.
2. **Canvas warm/off-white** (#faf9f5 hoặc #f8fafc), KHÔNG pure white #fff.
3. **Typography**: 1 display (28-48px, letter-spacing âm) + 1 body (14-16px, line-height 1.5) + monospace cho code.
4. **Button** ≥40px cao, radius 8-12px, primary/secondary rõ ràng.
5. **Chat bubble**: user phải-align + agent trái-align, radius 12px, padding 12-16px, max-width 85%.
6. **Spacing theo grid 8px**: 96px giữa section lớn, 24px giữa card, 16-32px trong card.
7. **Input** ≥44px, hairline border, focus ring rõ.
8. **LUÔN có loading / empty / error states** (đây là thứ agent hay quên → "trông chưa xong").
9. **Card** radius nhất quán, độ nổi bằng màu/border chứ không shadow nặng.
10. **Dark mode**: chọn 1 (full hoặc light-only), không nửa vời.
11. **Responsive**: mobile 1 cột, code cho scroll ngang.
12. **Transition** 150-250ms ease-out.

Skill này áp cho MỌI web app agent build (không chỉ RAG). UI blueprint là **rule thiết kế tổng quát** (không gắn domain), nên ship sẵn là hợp lệ — khác với domain blueprint (RAG) phải để agent tự sinh. Đăng ký vào `priority_skill_ids`.

---

## 4. Phép thử nghiệm thu — RAG chatbot agent TỰ tạo

> Đây là **bài test năng lực tự chủ**, không phải tính năng hardcode. Giao task, KHÔNG hand-feed cách làm. Quan sát agent có **tự** đi qua các trụ không.

SmartAgent nhận task "build RAG chatbot cho corpus X, dùng được trên web" và phải **tự**:
- **Research** (Trụ 4): tự `web_search` cách làm RAG tốt nhất, tự chọn embeddings/vector store/retrieval phù hợp 512MB — KHÔNG được phát sẵn stack. (Ta kỳ vọng nó tự ra embeddings thật thay vì TF-IDF, nhưng đó là *kết quả nó tự đạt*, không phải ta ép.)
- **Tự cài deps** (Trụ 5A) nó research ra, đáng tin cậy không timeout.
- **Build** serve `0.0.0.0:8080`: ingestion → index → retrieval → grounded answer → chat UI (theo Trụ 6).
- **Tự kiểm chứng** (Trụ 3): `verify_webapp` luồng người dùng thật + tự viết `eval.py` đo Hit Rate/MRR.
- **Tự đúc kết** (Trụ 5B): `create_skill` thành blueprint cho lần sau.

**Tiêu chí ĐẠT của kiến trúc:** agent hoàn thành task **chưa từng được dạy** này, các trụ tự kích hoạt. Chất lượng RAG (Hit Rate) là thước đo phụ; thước đo chính là **agent có tự chủ thật không**.

---

## 5. Tiêu chí nghiệm thu (Definition of Done)

| # | Tiêu chí | Cách đo |
|---|----------|---------|
| C0 | **Agent tự research trước khi build** | Log có `web_search` về cách làm + `think`/`spawn_critic` đối chiếu requirement TRƯỚC khi viết code |
| C1 | Eval chạy không crash | `python eval.py` in metrics, exit 0 |
| C2 | Retrieval đạt ngưỡng | Hit Rate@4 ≥ 0.8 (assert số in ra) |
| C3 | **App dùng được thật** | `verify_webapp`: GET / có UI; in-corpus → answer grounded; out-of-scope → từ chối |
| C4 | Bền với input hiểm | Adversarial review: input rỗng/dài/malformed không crash |
| C5 | **Agent tự đúc kết** | Sau khi xong, agent `create_skill` lưu phương pháp (self-extension thật) |
| C6 | Trung thực | Báo cáo có số liệu thật + nêu rõ limitations |

---

## 6. Lộ trình & Deadline

> **Chiến lược đã chốt: PORT PATTERN TỪ NEXUS** (không tự sáng chế). SmartAgent giữ là sản phẩm riêng, nhưng mỗi phase port skill/pattern đã kiểm chứng của Nexus (`F:\MekongAI\_nexus_ref`). Nhanh hơn và chắc hơn tự viết.

| Phase | Nội dung | Nguồn port từ Nexus | Hạn |
|-------|----------|---------------------|-----|
| **P0** | Tài liệu kiến trúc (tài liệu này) — **Mốc 1, sếp duyệt** | — | **2026-06-09 (T3)** |
| P1 | Debug-before-rewrite — Trụ 2 | `skills/systematic-debugging/SKILL.md` (Iron Law, 4 phase, fail-closed) | 2026-06-10 (T4) |
| P2 | `verify_webapp` (usable gate) — Trụ 3 | `app/project_builder/dev_server.py::_wait_for_ready` + `pipeline.py::verify_project_runnable` | 2026-06-10 (T4) |
| P3 | Research-first + meta-skills — Trụ 4 | `skills/research/SKILL.md` + `skills/plan/SKILL.md` + `docs/SKILL.md` (llm-guidelines) | 2026-06-11 (T5) |
| P4 | Deps đáng tin cậy + self-extension — Trụ 5 | `app/sandbox/manager.py` (process fallback) + `app/xskill/skill_builder.py` (tự học, relevance threshold) | 2026-06-11 (T5) |
| P4b | UI blueprint skill (12 rule — Trụ 6) | `app/project_builder/visual_qa.py` (chấm UI) + awesome-design-md | 2026-06-11 (T5) |
| P6 | **(MỚI) Quality-based exit + metacognition** — sửa gốc timeout | `app/orchestration/nexus_orchestrator.py` + `metacognition.py` | 2026-06-12 (T6) |
| P5 | Phép thử: agent TỰ build RAG (không hand-feed) + báo cáo | đối chứng RAG production `app/rag/` của Nexus | **2026-06-12 (T6) — Mốc 2** |

**Đệm rủi ro:** nếu P5/P6 lòi lỗi cần sửa sâu → trượt tối đa **2026-06-15 (T2)**.

> **Lưu ý chỉnh hướng:**
> - P3/P4 đã đổi từ "pre-bake deps RAG + ship RAG blueprint" (chống chế) sang "research-first + cài đặt đáng tin cậy + self-extension" (tổng quát). KHÔNG còn `rag-blueprint` ship sẵn — agent tự sinh (mô hình theo `xskill/skill_builder.py` của Nexus).
> - **P6 mới**: quality-based exit thay `MAX_ITERATIONS=150` → sửa tận gốc vấn đề timeout (trước chỉ fix tạm bằng retry/backoff). Port từ orchestrator Nexus.

---

## 7. Rủi ro & Giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|--------|-----|-----------|
| Agent vẫn dựa trí nhớ, bỏ qua research | Cao | Trụ 4 là gate bắt buộc; C0 trong DoD kiểm log có `web_search` trước khi build; gateguard hook đã chặn write_file nếu chưa research |
| `pip install` deps nặng vẫn timeout | Cao | Trụ 5A: pip cache bền + retry + timeout dài; agent tự chọn lib nhẹ qua research (đối chiếu 512MB) |
| Agent tự research ra giải pháp vẫn yếu | TB | `spawn_critic` phản biện thiết kế trước build; `verify_webapp` + eval bắt kết quả kém → buộc lặp lại |
| `verify_webapp` journey assert giả (luôn đúng) | TB | Bắt buộc expected là fact CHỈ có trong corpus + bước out-of-scope refusal |
| Trụ 2 làm agent rụt rè, ngại refactor hợp lý | TB | Phrasing "minimal-fix-FIRST; rewrite khi có bằng chứng + hỏi trước" — chỉnh ở prompt, không hard-code |
| Agent không tự `create_skill` đúc kết | Thấp | C5 trong DoD + nhắc trong prompt Bước cuối; không chặn nghiệm thu nếu thiếu (nice-to-have) |

---

## 8. Phụ lục — Files thay đổi

| File | Phase | Thay đổi |
|------|-------|----------|
| `.docs/ARCH_AGENTIC_OPTIMAL.md` | P0 | Tài liệu này (mới) |
| `v2/backend/app/agent/prompts.py` | P1,P2,P3,P4 | Bước 3.5 debug-first + wiring verify_webapp + research-first gate + nhắc self-extension |
| `v2/backend/app/agent/builtin_tools.py` | P2 | `handle_verify_webapp` + đăng ký (~line 607) |
| `v2/sandbox/Dockerfile.sandbox` + `docker_manager.py` | P4 | **KHÔNG** pre-bake deps RAG. Thêm pip cache mount + retry/timeout dài cho cài đặt đáng tin cậy (tổng quát) |
| `v2/backend/vendor/ecc/skills/research-first-design/SKILL.md` | P3 | Meta-skill tổng quát (mới) — KHÔNG gắn RAG |
| `v2/backend/vendor/ecc/skills/ui-blueprint/SKILL.md` | P4b | UI blueprint skill, 12 rule (mới) — rule thiết kế tổng quát |
| `v2/backend/app/agent/skill_manager.py` | P3, P4b | Thêm `research-first-design` + `ui-blueprint` vào `priority_skill_ids` |

*(KHÔNG còn `rag-blueprint` ship sẵn — agent tự sinh qua `create_skill` sau khi giải task.)*
