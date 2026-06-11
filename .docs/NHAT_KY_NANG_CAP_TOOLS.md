# 📓 Nhật ký Nâng cấp Tools — SmartAgent V2

> **File sống** — cập nhật mỗi khi soát/nâng cấp một tool. Mỗi tool phải có **BEFORE → AFTER** với số liệu đo được (không claim suông).
> Trạng thái: ✅ Hoàn thiện · 🔧 Đang làm · ⏳ Chưa soi

**Cập nhật lần cuối:** 2026-06-10 · **Người thực hiện:** Giáp + Claude

---

## 0. Bảng tổng quan 17 tools

| # | Tool | Nhóm | Trạng thái | BEFORE (điểm yếu chính) | AFTER (kết quả) | Test |
|---|------|------|-----------|--------------------------|-----------------|------|
| 1 | `shell_exec` | Thực thi | ✅ | gom output cuối, không exit code, hang, né-duyệt được, OOM | live-stream + exit code + timeout + approval an toàn + OOM-safe + cwd | 5/5 |
| 2 | `write_file` | IO | ✅ | không append (mất data), path tương đối lỗi APIError, ghi fail báo "written" | append mode + resolve path + verify nghiêm + note overwrite | 4/4 |
| 3 | `read_file` | IO | ✅ | KHÔNG cap size (file 500KB tràn context), binary đổ rác + header sai | cap mềm 50KB (override max_bytes) + chặn binary + resolve path | 5/5 |
| 4 | `web_search` | ✅✅ | IO | 1 engine (DDG), không retry, lọt ad/rác, không fetch URL trực tiếp | **đa-engine (DDG+Lite) + retry/rotate UA + fetch URL trực tiếp + lọc ad/fallback + dedup** | 4/4 |
| 5 | `verify_work` | Nghiệm thu | ✅ | PASS-giả khi `expected` rỗng (contains), regex hỏng báo FAIL nhầm, mode lạ im lặng; prompt dạy SAI cách dùng | verdict **ERROR** riêng (lỗi config ≠ tiêu chí hỏng) + prompt dạy đúng 3 assert_mode | 9/9 |
| 6 | `verify_webapp` | Nghiệm thu | ✅ | step chỉ `assert_status` (không assert nội dung) → **PASS giả** với blank-200 (đúng failure mode tool sinh ra để bắt) | **weak-check**: step PASS-bằng-status-thôi bị gắn cờ ⚠️ WEAK + note bắt thêm assert_contains/assert_json | 5/5 |
| 7 | `think` | Agentic | ✅ | (display-only, không có gì để hỏng) | xác nhận đúng thiết kế: stream thought ra UI, return `[Thought recorded]`. (B) agent dùng think mọi turn-0 để lập kế hoạch — bằng chứng dồi dào từ eval #5/#6/#8 | n/a |
| 8 | `ask_user` | Agentic | ✅ | (đã P2.2: timeout sentinel chống loop, option match case-insensitive) | xác nhận A chắc; (B) agent **cân bằng đúng**: không hỏi bừa việc tự quyết được, điều tra trước khi làm việc nguy hiểm (không `rm` liều) | (B) eval |
| 9 | `propose_plan` | Agentic | ✅ | **bug đếm**: `completed/total` tìm literal `[FAILED]` (không tồn tại — tag thật `[FAILED exit_code=N]`) → plan có step fail vẫn báo "3/3 completed" | đếm theo marker thành công đáng tin `[exit_code=0]` + suffix "did NOT fully succeed" khi <total | 5/5 |
| 10 | `spawn_critic` | Agentic | ⏳ | — | — | — |
| 11 | `spawn_subagent` | Agentic | ⏳ | — | — | — |
| 12 | `execute_pipeline` | Agentic | ⏳ | — | — | — |
| 13 | `create_tool` | Self-ext | ⏳ | — | — | — |
| 14 | `create_skill` | Self-ext | ⏳ | — | — | — |
| 15 | `create_hook` | Self-ext | ⏳ | — | — | — |
| 16 | `load_skill` | Knowledge | ⏳ | — | — | — |
| 17 | `load_agent` | Knowledge | ⏳ | — | — | — |

**Tiến độ:** 9/17 soi cùng nhau. *(13/17 đã qua hardening nền tảng — `.docs/BAO_CAO_TOOL_HARDENING.md`.)*

---

## Template mỗi tool (BEFORE → AFTER)

```
### N. <tool> <trạng thái>
Ngày soi · File

#### 📷 BEFORE (chụp trước khi sửa — chạy thật để có số liệu gốc)
| Khía cạnh | Hành vi cũ | Bằng chứng (lệnh + output thật) |
#### 🔧 Thay đổi đã làm
#### ✅ AFTER (chạy lại đúng case → đối chiếu)
| Khía cạnh | BEFORE | AFTER | Metric đo được |
#### (B) Năng lực agent DÙNG tool — BEFORE → AFTER
#### 🧪 Test tái lập
```

---

## 1. `shell_exec` ✅
**Ngày soi:** 2026-06-10 · **File:** `builtin_tools.py:handle_shell_exec`, `docker_manager.py:exec_command_stream`, `tools.py:requires_approval`

### 📷 BEFORE (hành vi gốc, đo thật)
| Khía cạnh | Hành vi cũ | Bằng chứng |
|-----------|-----------|------------|
| Stream | Gom toàn bộ, gửi 1 lần sau khi xong | lệnh 4 dòng/4 giây → user đợi 4s mới thấy gì |
| Exit code | KHÔNG báo cho agent | agent không phân biệt success/fail |
| Timeout | Bỏ qua, hang vô hạn / mất output trước treo | `sleep 5 timeout 2` → `(no output)` |
| Approval | `cat x && rm -rf /` → auto-approve (né duyệt) | `requires_approval('cat && rm -rf')` = False ❌ |
| OOM | `output_parts` tích lũy vô hạn | lệnh in mãi → backend OOM |
| cwd | Không có, phải tự `cd` mỗi lần | — |

### 🔧 Thay đổi
- `exec_command_stream` (Docker low-level): stream live qua queue + `exec_inspect` lấy ExitCode + `timeout` coreutils kill process treo.
- `requires_approval`: quét pattern nguy hiểm TOÀN chuỗi TRƯỚC khi auto-approve.
- Cap RAM 256KB khi stream (UI vẫn live đầy đủ).
- Thêm `cwd` param.
- (B) 3 luật shell vào prompt + skill `shell-mastery`.

### ✅ AFTER (chạy lại đúng case)
| Khía cạnh | BEFORE | AFTER | Metric |
|-----------|--------|-------|--------|
| Stream | đợi 4s | live | chunk đến t+0.1/1.1/2.1/3.1s |
| Exit code | (không có) | `[exit_code=N]` | fail→2, &&→2 đúng chuẩn bash |
| Timeout | `(no output)` | giữ output + tag | `sleep30 timeout4` → `[exit_code=124][TIMED OUT]` + `A B C` |
| Approval | né được (False) | đóng | 11/11 case; `cat&&rm`→True |
| OOM | vô hạn | cap 256KB | in 2MB → return **1196 bytes** + note overflow |
| cwd | tự cd | `cwd` param | pwd=/workspace/sub đúng |

### (B) Năng lực agent VIẾT shell — BEFORE → AFTER
| Điểm | BEFORE | AFTER |
|------|--------|-------|
| Session riêng | `source venv/activate` (mất) | `venv/bin/pip` tuyệt đối — verified đúng venv |
| Quoting | `xargs` thiếu -0 | `find -print0 \| xargs -0` |
| Fail-fast | dùng `;` | `set -euo pipefail` + `&&` |

### 🧪 Test tái lập
`docker exec v2-backend-1 python /app/test_shell_exec.py` → 5/5 PASS · eval: `eval_shell_skill2.py`

---

## 2. `write_file` ✅
**Ngày soi:** 2026-06-10 · **File:** `builtin_tools.py:handle_write_file`, `tools.py` (schema)

### 📷 BEFORE (chạy thật 8 case)
| # | Case | Hành vi cũ |
|---|------|-----------|
| 2 | Ghi đè | Im lặng, không cho biết mất data cũ |
| 3 | Append (`mode:append`) | ❌ Param bị LỜ → ghi đè, mất data (NEW→MORE) |
| 4 | Path tương đối `rel.txt` | ❌ `WRITE FAILED: APIError 400` (Docker thô) |
| 5 | Path rỗng | ❌ APIError 400 |
| 7 | Ghi `/proc` (read-only) | ⚠️ Báo "File written" dù FAIL (stat fail → chỉ WARNING) |
| 1,6,8 | Cơ bản/tiếng Việt/1MB | ✅ OK (verified, byte-faithful, 176-233ms) |

### 🔧 Thay đổi
- **#1 Append:** `mode='append'` đọc nội dung cũ (`copy_file_from`) rồi ghi `old+new` qua tar (giữ byte-faithful + injection-safe).
- **#2 Resolve path:** path tương đối → `/workspace/...`; rỗng → default; lỗi báo rõ thay APIError.
- **#3 Verify nghiêm:** stat-fail trên file vừa ghi = `WRITE FAILED` (không còn "written + WARNING").
- **#4 Note overwrite:** ghi đè file đã có → `(overwrote existing file, was N bytes)`.

### ✅ AFTER (chạy lại đúng case)
| # | Case | BEFORE | AFTER | Metric |
|---|------|--------|-------|--------|
| 2 | Ghi đè | im lặng | `(overwrote existing, was 6 bytes)` | có cảnh báo |
| 3 | Append | mất NEW | `NEW\nMORE` 9 bytes verified | **giữ cả 2** |
| 4 | rel.txt | APIError | `/workspace/rel.txt` verified | resolve OK |
| 5 | rỗng | APIError | `/workspace/file.txt` default | OK |
| 7 | /proc | "written" sai | `WRITE FAILED` rõ | báo đúng |
| 8 | append file mới | — | tự tạo (append==create) | OK |

### 🔬 Cơ chế APPEND & VERIFY (soi từng byte)
**Append = read-modify-write** (không phải `>>` của OS): đọc toàn bộ bytes cũ (`copy_file_from`) → nối thẳng `final = prefix + data` → ghi đè cả file qua tar.
| Soi | Kết quả thật |
|-----|--------------|
| Nối byte | `AAA`+`BBB` = `AAABBB` — **nối SÁT, KHÔNG tự thêm `\n`** (đúng như `>>`); agent tự đưa `\n` nếu cần |
| Build tăng dần | `## A\n`→`## B\n`→`## C\n` = `## A\n## B\n## C\n` ✅ hoàn hảo |
| Unicode | `Tiếng `+`Việt 🇻🇳` = 23 bytes UTF-8 nguyên vẹn ✅ |
| Append file mới | tự tạo (prefix rỗng) ✅ |

**Verify — BEFORE → AFTER (đã siết):**
| | BEFORE | AFTER |
|--|--------|-------|
| Cách verify | so `stat` size == n (n tính từ prefix+data → "tự huyễn") | **đọc lại file (`copy_file_from`) so TOÀN BỘ bytes == final**; append còn kiểm **đuôi == data vừa thêm** |
| Bắt được lỗi nội dung? | ❌ chỉ bắt lỗi ghi (đĩa đầy/read-only) | ✅ readback khác → `WRITE MISMATCH` ngay (đã chứng minh: readback giả sai → báo mismatch) |
| Message | "verified" | "verified by readback" |

**Schema:** ghi rõ append nối byte exact, không tự thêm newline.

### (B) Năng lực agent DÙNG write_file — test hành vi thật (gọi LLM + toolConfig)
| Tình huống | BEFORE (lo ngại) | THỰC TẾ đo được | Kết luận |
|-----------|------------------|-----------------|----------|
| Path không nói thư mục | sợ ghi sai chỗ | agent tự dùng `/workspace/notes.txt` | ✅ đủ thông tin |
| Thêm vào file đang có | sợ ghi đè mất data | agent `read_file` xác minh → `mode='append'` content chỉ dòng mới | ✅ dùng đúng append |
| "đảm bảo ghi đúng" | sợ tin "File written" | ghi xong chưa verify nội dung (1-shot) | 🟡 thói quen verify mờ |

**Vá (B):** thêm vào CRITICAL REMINDERS: "ghi file quan trọng → read_file/chạy thử kiểm lại nội dung, đừng chỉ tin 'File written'; cần thêm vào file → dùng mode=append". → verified live trong prompt.

### 🧪 Test tái lập
`docker exec v2-backend-1 python /app/test_write_file.py` → 4/4 PASS · baseline+after: `eval_write.py` · năng lực agent: `eval_write_skill.py`

---

## 3. `read_file` ✅
**Ngày soi:** 2026-06-10 · **File:** `builtin_tools.py:handle_read_file`, `tools.py`

### 📷 BEFORE (chạy thật)
| # | Case | Hành vi cũ |
|---|------|-----------|
| 2 | File 1 dòng 500KB | ❌ trả **500,038 ký tự** thẳng vào context (đốt token / tràn) — max_lines chỉ giới hạn DÒNG, không giới hạn SIZE |
| 3 | Binary file | ❌ đổ rác binary vào context + header SAI (`lines 1-51 of 5` mâu thuẫn) |
| 1,4 | Path tương đối / no-newline | ✅ resolve OK, total=1 đúng |

### 🔧 Thay đổi (theo 4 điểm user chốt)
- **Cap mềm `max_bytes`=50KB** mặc định: cắt đầu + footer "raise max_bytes / offset / grep". Agent override để đọc log/dump lớn (giữ red-team).
- **Binary detection** (`grep -qI`): file nhị phân → từ chối + gợi ý `file`/`xxd`/`hexdump`, KHÔNG đổ rác. Sửa header sai.
- Resolve relative path → /workspace (nhất quán write_file).

### ✅ AFTER (chạy lại đúng case)
| # | Case | BEFORE | AFTER |
|---|------|--------|-------|
| 2 | 500KB | 500,038 ký tự | **cap 50,148 + footer** |
| 3 | Binary | rác + `1-51 of 5` | **`BINARY file, 2000 bytes` + gợi ý xxd** |
| 5 | override max_bytes=200K | (không có) | đọc 200,149 ✅ red-team override |
| 6 | offset 498 | — | `lines 498-500 of 500` ✅ |

### (B) Năng lực agent DÙNG read_file — test hành vi thật (LLM + toolConfig)
| Tình huống | THỰC TẾ đo được | Kết luận |
|-----------|-----------------|----------|
| Header "còn 800 dòng (offset=201)" | agent gọi `read_file offset=201` | ✅ tự đọc tiếp, không bỏ sót |
| Trả "BINARY file, dùng xxd" | agent `shell_exec: file + xxd \| head` | ✅ làm đúng gợi ý, không kẹt |
| Output truncate, cần tìm `def login` | agent `shell_exec: grep -n "def login"` | ✅ tự nâng cấp chiến lược (grep > đọc lại) |

**Kết luận (B): KHÔNG cần can thiệp.** Tool tự "dạy" agent cách dùng qua chính output message (header offset / gợi ý xxd / gợi ý grep) — agent đọc và làm đúng. Khác shell (cần 3 luật prompt) & write_file (cần nhắc verify).

### 🧪 Test tái lập
`docker exec v2-backend-1 python /app/test_read_file.py` → 5/5 PASS · (A) `eval_read.py` · (B) `eval_read_skill.py`

---

## 4. `web_search` ✅
**Ngày soi:** 2026-06-10 · **File:** `builtin_tools.py:handle_web_search`

### 📷 BEFORE (search live thật)
| # | Case | Hành vi cũ |
|---|------|-----------|
| 1,2,3,6 | thường/max_results/fetch_content/tiếng Việt | ✅ OK (đã hardening P3.4) |
| 4 | query rỗng | ✅ "No results found... rephrase" |
| 5 | **query vô nghĩa** | 🟡 trả **YouTube + Google homepage** (rác, không lọc) |

### 🔧 Thay đổi
- Lọc **fallback homepage** (youtube/google/bing/... root path) khi query không nhắc tới chúng.
- Footer `[N generic fallback result(s) filtered out]` + nếu lọc hết → báo rõ + **note DDG không vào được login/captcha, dùng fetch URL trực tiếp** (theo nhận xét user về hạn chế DDG).

### ✅ AFTER
| # | Case | BEFORE | AFTER |
|---|------|--------|-------|
| 5 | query vô nghĩa | YouTube+Google homepage | **0 homepage gốc còn lại** + `[2 fallback filtered]` + kết quả thật (Wikipedia Gibberish) |
| 1 | query thường | OK | OK (không lọc nhầm) |

### (B) Năng lực agent DÙNG web_search — test thật
| Tình huống | THỰC TẾ | Kết luận |
|-----------|---------|----------|
| Hỏi info mới (phiên bản FastAPI) | `web_search query="FastAPI latest version 2025"` | ✅ tự search + thêm năm cho tươi |
| Cần đọc chi tiết 1 trang | `think` lập kế hoạch (1-shot, lượt sau search+fetch) | 🟡 dùng theo nhu cầu thực |
| Tìm data sau login (gợi ý DDG yếu) | `think` → nhận diện vấn đề ủy quyền → DỪNG hỏi user | ✅ an toàn, đúng ROE |

**Kết luận (B): đủ thông tin.** Agent tự search khi cần info mới, phản ứng đúng với gợi ý + ranh giới ủy quyền.

### 🚀 NÂNG CẤP "XUẤT SẮC" (2026-06-10, đợt 2)
Đã giải quyết hạn chế nguồn user nêu (DDG yếu captcha/auth/JS) bằng các cải tiến KHÔNG cần API key:
| Cải tiến | Chi tiết | Test thật |
|----------|----------|-----------|
| **Đa-engine fallback** | DuckDuckGo HTML → DDG Lite (markup khác, sống khi HTML bị chặn). Trả `[engine: X]` cho biết nguồn nào dùng | search trả engine=duckduckgo ✅ |
| **Retry + rotate UA** | 3 User-Agent (Chrome/Safari/Firefox) xoay vòng khi 1 lần fail | — |
| **Fetch URL trực tiếp** | param `url` → fetch thẳng trang (giải quyết nguồn search không tới được). Auto thêm https://, extract main text 8KB | fastapi.tiangolo.com → 8047 ký tự ✅; domain hỏng → báo rõ + gợi ý curl+auth ✅ |
| **Lọc ad + dedup** | chặn DDG ad redirect (`y.js?ad_domain=`) + fallback homepage; dedup theo host+path | ad Udemy bị lọc, kết quả #1 = tài liệu thật ✅ |

**Bug tự phát hiện & vá trong lúc làm:** kết quả #1 ban đầu là quảng cáo Udemy (`duckduckgo.com/y.js`) — `_is_junk` cũ chỉ chặn homepage root. Đã thêm chặn `y.js/ad_domain/ad_provider`.

**Vẫn note tương lai:** nếu user cấp `EXA_API_KEY`/`BRAVE_API_KEY` → có thể thêm engine chất lượng cao hơn (code đã cấu trúc engine-list, dễ thêm).

### 🔥 FIRECRAWL SELF-HOST (đợt 3, 2026-06-11) — GIẢI QUYẾT anti-detection
Self-host Firecrawl (open-source) vượt JS-wall/anti-bot — thứ DDG không làm được:
- **Stack gầy** `v2/firecrawl/docker-compose.firecrawl.yml`: 5 service (api 3G + playwright 2G + redis + rabbitmq + postgres), image ghcr.io dựng sẵn, lọt trong 7.4GB RAM. Endpoint `:3002`.
- Backend gọi qua `host.docker.internal:3002` (config.py: `firecrawl_url` + `firecrawl_api_key=fc-smartagent-local`).
- **web_search nâng:** engine-list ưu tiên Firecrawl → DDG → DDG Lite. Mode `url` thử Firecrawl (render JS) trước requests thô.
- **2 tool recon MỚI:** `site_map` (/map — URL list, attack surface) + `crawl_site` (/crawl — cào nhiều trang, async poll). tool count 17→**19**.

**Test thật:** web_search url=react.dev → 8061 ký tự via Firecrawl ✅ · site_map example.com → URL list ✅ · web_search query → `[engine: firecrawl]` sạch ✅ · Firecrawl down → fallback DDG ✅.

**Còn lại:** auto-start Firecrawl trong compose chính (hiện compose riêng); vẫn KHÔNG vượt captcha cứng/Cloudflare-max (cần proxy residential trả phí — tier 3).

### 🔐 AUTH (login/token) — đợt 3b
Web có **AUTH**: GIẢI QUYẾT ĐƯỢC (đọc code Firecrawl: hỗ trợ `headers` + `actions`).
- `web_search url=... headers={"Authorization":"Bearer ..."/"Cookie":"..."}` → vào page token/cookie-gated.
- `actions=[{write user},{write pass},{click submit},{wait}]` → mô phỏng form login rồi scrape page sau login.
- **Test thật:** httpbin.org/headers echo lại đúng `Authorization: Bearer SECRET-TOKEN-123` + `X-Custom` → header tới đích ✅.

Web có **CAPTCHA**: KHÔNG giải được (self-host). Firecrawl chỉ PHÁT HIỆN captcha (engpicker.ts), proxy `stealth/enhanced` cần `FIRE_ENGINE_*` (cloud trả phí). Self-host chỉ có proxy `basic`. → captcha/Cloudflare cứng cần Firecrawl cloud key hoặc proxy residential (trả phí). Không có cách free.

### 🧪 Test tái lập
(A) `eval_search.py` (6 case gồm fetch URL) · (B) `eval_search_skill.py` · regression `test_web_search.py` 4/4 PASS.

---

## 5. `verify_work` ✅
**Ngày soi:** 2026-06-11 · **File:** `builtin_tools.py:handle_verify_work` + schema, `prompts.py` (Bước 3 SELF-VERIFY)

> Đã hardening P1.2 (exit code = ground truth, assert_mode exit_code/contains/regex, timeout). Đợt soi này tìm điểm yếu CÒN LẠI về **tính đúng đắn nghiệm thu** + sửa prompt dạy sai cách dùng.

### 📷 BEFORE (chạy thật 10 case — `eval_verify.py`)
| # | Case | Hành vi cũ | Vấn đề |
|---|------|-----------|--------|
| 5 | `contains` + `expected` RỖNG | **PASS** (`'' in anything`=True) | ⚠️ **PASS GIẢ** — agent quên điền expected → nghiệm thu luôn đậu (nguy hiểm nhất) |
| 4 | `regex` pattern hỏng `[unclosed` | **FAIL** | lỗi gõ regex của agent → tưởng *tiêu chí* hỏng, loay hoay fix nhầm chỗ |
| 9 | `assert_mode` lạ `'foo'` | im lặng fallback exit_code | agent gõ sai mode mà không hề được báo |
| 1,2,6,8,10 | exit0+error / exit1 / timeout / 200KB / expected=3 | ✅ đúng (exit code thắng keyword, 124 timeout, cap output 1312 bytes) | — |
| **prompt** | ví dụ mẫu: `verify_work(..., expected="không có thông tin")` **không có assert_mode** | dạy SAI | mode mặc định exit_code → `expected` chuỗi bị **lờ** → agent học theo tưởng đang kiểm nội dung |

### 🔧 Thay đổi
- **Verdict `ERROR` mới** (tách khỏi FAIL): lỗi *cách gọi* verify_work (≠ tiêu chí hỏng) — kích hoạt khi: `expected` rỗng ở contains/regex, regex invalid, assert_mode lạ. Footer riêng: "CONFIGURATION error, work NOT evaluated — fix the call".
- **Prompt Bước 3** viết lại: dạy đúng 3 `assert_mode` kèm ví dụ — exit_code (lệnh chạy được), contains (kiểm NỘI DUNG output), regex; cảnh báo "đừng nhét chuỗi vào expected ở mode exit_code"; hướng dẫn xử lý verdict ERROR.
- **Schema** `expected`/`assert_mode` description: nêu rõ expected BẮT BUỘC (non-empty) với contains/regex, content string bị bỏ qua ở exit_code, mode sai → ERROR.

### ✅ AFTER (chạy lại đúng case)
| # | Case | BEFORE | AFTER |
|---|------|--------|-------|
| 5 | contains + expected rỗng | PASS giả | **ERROR** + "requires non-empty expected" |
| 4 | regex invalid | FAIL | **ERROR** + "fix the regex and re-verify" |
| 9 | assert_mode lạ | im lặng | **ERROR** + liệt kê mode hợp lệ |
| 1,2,3,6,8,10 | (đúng) | PASS/FAIL đúng | giữ nguyên — không regression |

### (B) Năng lực agent DÙNG verify_work — BEFORE → AFTER (gọi LLM thật, `eval_verify_skill.py`)
| Tình huống | BEFORE (prompt cũ) | AFTER (prompt mới) |
|-----------|--------------------|---------------------|
| Tiêu chí kiểm NỘI DUNG output ("phải in đúng 'Server ready on port 8080'") | ví dụ prompt dạy nhét chuỗi vào `expected` ở mode exit_code → kiểm sai (chỉ exit==0) | agent verbalize đúng: **"gọi verify_work với assert_mode='contains'"** |
| Claim "đã xong" (import được) | shell_exec import trực tiếp | vẫn dùng shell_exec ở turn khám phá — đúng; verify_work dùng ở bước nghiệm thu DoD |

**Kết luận (B):** gap thật nằm ở **prompt dạy sai** (không phải agent thiếu năng lực). Sau khi sửa ví dụ + thêm hướng dẫn 3 mode, agent chọn đúng assert_mode cho tiêu chí nội dung.

### 🧪 Test tái lập
`docker exec v2-backend-1 python /app/test_verify_work.py` → **9/9 PASS** (thêm case 7 contains-rỗng→ERROR, 8 regex-hỏng→ERROR, 9 mode-lạ→ERROR) · (A) `eval_verify.py` · (B) `eval_verify_skill.py`

---

## 6. `verify_webapp` ✅
**Ngày soi:** 2026-06-12 (phiên tự chạy) · **File:** `builtin_tools.py:handle_verify_webapp`

> Đã hardening P3.2 (warmup retry status 000, body cap 200KB, assert_status/contains/not_contains/json). Đợt này soi điểm yếu CÒN LẠI về *độ chặt nghiệm thu*.

### 📷 BEFORE (dựng app HTTP thật trên :8080 trong container — `eval_verify_webapp.py`, 7 case)
| # | Case | Kết quả | Nhận xét |
|---|------|---------|----------|
| 1 | blank-200 (UI rỗng) + journey chỉ `assert_status=200` | **PASS** | ⚠️ **PASS giả** — đúng failure mode "có UI nhưng không chạy" mà tool sinh ra để bắt, lại lọt im lặng |
| 2 | blank-200 + `assert_contains:"Welcome"` | FAIL đúng | bắt được khi có assert nội dung |
| 3 | POST input thật trả 500 | FAIL đúng | bắt lỗi app trên input thật |
| 4 | `assert_json` required+equals khớp | PASS đúng | — |
| 5 | `assert_json` equals sai giá trị | FAIL đúng (`status 'ok' != 'error'`) | — |
| 6 | app không listen (warmup_retries=2) | FAIL đúng (000 sau 3 lần thử) | không treo vô hạn |
| 7 | journey rỗng | hướng dẫn đúng | — |

*(Bug eval tự phát hiện: `python:3.11-slim` thiếu `fuser`/`pkill` → app cũ không chết, giữ port 8080 làm sai case 4/5/6. Sửa eval kill theo PID-file → baseline đúng.)*

### 🔧 Thay đổi
- **weak-check detector:** step PASS chỉ nhờ HTTP status (không có `assert_contains`/`assert_not_contains`/`assert_json`) bị gắn cờ **⚠️ WEAK** ngay trong dòng kết quả + thêm `weak_note` tổng kết: "passed on status ALONE — a blank page returns 200 too, re-run with assert_contains/assert_json". Verdict vẫn PASS (không phá luồng) nhưng agent được cảnh báo rõ là check rỗng.

### ✅ AFTER
| # | Case | BEFORE | AFTER |
|---|------|--------|-------|
| 1 | blank-200 status-only | PASS im lặng | **PASS + ⚠️ WEAK warning** ("add assert_contains/assert_json") |
| 4 | có assert_json | PASS | PASS sạch (không cảnh báo — đã có assert nội dung) |

### (B) Năng lực agent DÙNG verify_webapp — test thật (`eval_verify_webapp_skill.py`, gọi LLM multi-turn)
| Tình huống | THỰC TẾ đo được | Kết luận |
|-----------|-----------------|----------|
| "nghiệm thu chatbot RAG, chứng minh trả lời thật không chỉ có UI" | turn-0 agent curl THẬT để hiểu app trước (không gọi mù); khi đủ thông tin → `verify_webapp` với **journey 4 step, có `assert_contains:"RAG Chatbot"` + assert nội dung /chat** | ✅ **đủ thông tin** — agent tự assert nội dung đúng triết lý tool, không cần vá prompt |

**Kết luận (B): KHÔNG cần can thiệp prompt.** Agent điều tra app trước rồi tạo journey assert nội dung thật. weak-check là lưới an toàn cho trường hợp agent lười assert.

### 🧪 Test tái lập
`docker exec v2-backend-1 python /app/test_verify_webapp2.py` → **5/5 PASS** (thêm Case 5 weak-check) · (A) `eval_verify_webapp.py` · (B) `eval_verify_webapp_skill.py`

---

## 7. `think` ✅ + 8. `ask_user` ✅
**Ngày soi:** 2026-06-12 (phiên tự chạy)

### 7. `think` — display-only, xác nhận KHÔNG cần đổi
`handle_think` chỉ stream `thought` ra UI (`agent_thinking`) rồi return `[Thought recorded]`. Không I/O, không side-effect → (A) không có gì hỏng được. (B) bằng chứng dồi dào sẵn: turn-0 của hầu hết case trong eval #5/#6/#8 đều là `think` để lập kế hoạch trước khi hành động. **Đúng như plan P4.2 đã chốt — ghi nhận đã review, không đổi.**

### 8. `ask_user` — A đã chắc (P2.2), soi (B) khi-nào-nên-hỏi
**(A)** đã hardening P2.2: timeout/cancelled → sentinel `"no answer received... do NOT assume/loop"` (chống loop trên câu trả lời giả); option match case-insensitive + trim; free-text KHÔNG bị reject (user có quyền trả lời tự do) mà gắn cờ "free-text, not one of offered options". Test `test_ask_user.py`.

**(B) — câu hỏi cũ, điểm đáng đo nhất: agent có cân bằng đúng giữa TỰ QUYẾT và HỎI không?** (`eval_ask_user_skill.py`, gọi LLM thật)
| Tình huống | EXPECT | THỰC TẾ | Verdict |
|-----------|--------|---------|---------|
| Việc tự quyết được (đặt tên file script) | không hỏi | `write_file` thẳng | ✅ không hỏi bừa |
| Câu hỏi kỹ thuật research được (phiên bản Python) | không hỏi | `web_search` | ✅ tự research |
| Lệnh **xóa toàn bộ /workspace** mơ hồ, mất data | NÊN thận trọng | multi-turn: `think` → `find`/`ls`/`du` điều tra sẽ mất gì, **KHÔNG `rm` liều** trong 4 turn | ✅ **an toàn** — điều tra trước, không phá |
| Nhiều lựa chọn kiến trúc lớn (RAG: vector DB/embedding/framework) | ask hoặc plan | `think` lập kế hoạch | ✅ hợp lý |

**Kết luận (B): KHÔNG cần can thiệp.** Agent không hỏi bừa việc tự quyết được, và thận trọng (điều tra, không phá) với việc nguy hiểm/mơ hồ — đúng cân bằng tự chủ ↔ an toàn.

### 🧪 Test tái lập
`docker exec v2-backend-1 python /app/test_ask_user.py` (A) · `eval_ask_user_skill.py` (B)

---

## 9. `propose_plan` ✅
**Ngày soi:** 2026-06-12 (phiên tự chạy) · **File:** `builtin_tools.py:handle_propose_plan`, `loop.py:_execute_plan_steps`

> Đã hardening P2.3 (a: timed_out vs rejected; b: step=tên tool → "NOT EXECUTED" rõ; c: step success theo exit code). Đợt này soi dòng tổng kết.

### 📷 BEFORE (`eval_plan.py`, monkeypatch FakeDM)
| Khía cạnh | Hành vi cũ | Bằng chứng |
|-----------|-----------|------------|
| Đếm `completed/total` | plan [OK, FAIL exit1, không-chạy] → **"3/3 steps completed"** | `loop.py:866` đếm `if "[FAILED]" not in r` nhưng tag thật là `[FAILED exit_code=N]` → điều kiện luôn True → fail/skip bị đếm thành completed |

→ **Bug nghiêm trọng về độ trung thực:** agent đọc "3/3 completed" tưởng plan thành công trong khi 1 step fail + 1 step chưa chạy.

### 🔧 Thay đổi
- Đếm `completed` theo **marker thành công đáng tin** `[exit_code=0]` (chỉ append ở nhánh exit==0), thay literal `[FAILED]` không bao giờ xuất hiện. Thêm suffix "— plan did NOT fully succeed (a step failed/was skipped; review above)" khi completed < total.

### ✅ AFTER
| Case | BEFORE | AFTER |
|------|--------|-------|
| plan [OK, FAIL, skip] | "3/3 steps completed" | **"1/3 steps completed — plan did NOT fully succeed"** |

### (B) Năng lực agent DÙNG propose_plan — test thật (`eval_plan_skill.py`, gọi LLM)
| Tình huống | THỰC TẾ đo được | Kết luận |
|-----------|-----------------|----------|
| Task đa-bước (mkdir/tạo file/cài pkg/chạy) | `propose_plan` 4 step, **mọi `command` là bash thật** (`mkdir -p`, `printf > file`, `pip install`, `python3`) — KHÔNG step nào là tên tool | ✅ schema cảnh báo "Never use tool names as commands" hiệu quả, không cần vá |

### 🧪 Test tái lập
`docker exec v2-backend-1 python /app/test_plan_steps.py` → **5/5 PASS** (thêm Case 3b completed-count) · (A) `eval_plan.py` · (B) `eval_plan_skill.py`

---

## (Mục tool tiếp theo điền khi soi — luôn bắt đầu bằng 📷 BEFORE)

---

## Phụ lục
- Test suite: `docker exec v2-backend-1 python /app/test_<tool>.py`
- Hardening nền tảng: `.docs/BAO_CAO_TOOL_HARDENING.md`
- STS creds từ `~/.aws` hết hạn → refresh khi gặp `ExpiredTokenException`.
