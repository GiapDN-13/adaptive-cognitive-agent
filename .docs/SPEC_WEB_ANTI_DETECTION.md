# SPEC — Web Access chống Anti-Detection (cho red/blue team + research)

> **Trạng thái:** Thiết kế, chờ user chọn tier + cấp key → code. (2026-06-10)
> **Bối cảnh:** `web_search` hiện dùng DuckDuckGo HTML + DDG Lite + fetch URL trực tiếp (UA rotation). Đủ cho research thường, NHƯNG **không vượt được** Cloudflare / captcha / JS-wall — đúng những nguồn red/blue team & research hay cần.

## Sự thật cốt lõi (không hứa suông)
Không có cách **free** vượt captcha/Cloudflare. Có 3 tầng, chi phí tăng dần:

| Tầng | Vượt được | Không vượt | Chi phí |
|------|-----------|------------|---------|
| 1. HTTP + UA rotation (ĐÃ CÓ) | bot-block đơn giản | JS, captcha, Cloudflare | Free |
| 2. Headless browser + stealth | JS-wall, bot-detect cơ bản, giữ session | captcha cứng, IP-block residential | ~Free (tốn RAM) |
| 3. Proxy/captcha service | Cloudflare, captcha, IP-block | — (đắt) | Trả phí |

---

## Tier 2 — Playwright Stealth Browser (khuyến nghị làm trước)

**Giải quyết:** JS-rendered sites, bot-detection cơ bản (navigator.webdriver, fingerprint), giữ cookie/session đa bước. Đây là ~80% nhu cầu thực tế của research/recon.

**Tool mới đề xuất:** `browser_fetch`
```
Input: url, wait_for (selector/timeout), screenshot (bool), actions (click/type/scroll list), session_id (giữ cookie)
Output: rendered HTML/text + (optional) screenshot path + console errors
```

**Cơ chế:**
- `playwright` + `playwright-stealth` (patch navigator.webdriver, plugins, WebGL fingerprint...).
- Chromium headless, `--no-sandbox` trong container.
- Persistent context per session_id → giữ login/cookie qua nhiều call (quan trọng cho recon sau auth).

**⚠️ Ràng buộc RAM:** Chromium ~300-400MB > sandbox 512MB hiện tại. 2 cách:
- (A) Nâng `container_default_mem` lên 1.5-2GB cho session cần browser (config.py:40 + update_resources API đã có).
- (B) Chạy 1 Chromium ở HOST, container connect qua CDP (port 9222). Nhẹ cho sandbox nhưng phức tạp hơn.
- → **Khuyến nghị (A)**: đơn giản, agent tự bật khi cần.

**Pre-bake:** thêm `playwright` + `playwright-stealth` + `chromium` vào `Dockerfile.sandbox` (image to ~1.5GB) HOẶC cài on-demand (chậm lần đầu). Khuyến nghị pre-bake vì browser dùng nhiều.

**Hiệu quả đo được (acceptance):** fetch 1 trang JS-rendered (vd SPA React) → trả text thật (không phải "enable JS"); giữ session login qua 2 call.

---

## ⭐ Tier 2.5 — Firecrawl SELF-HOST (ĐÃ CHỐT — làm khi user sẵn sàng build)

> User đã chọn: self-host Firecrawl (không cần API key) + thêm tool `/map` + `/crawl` cho red/blue team recon. Đây là lựa chọn CHÍNH cho anti-detection vì: mạnh như tier 3 (rotating proxy + JS render + anti-bot, phủ 96% web) nhưng FREE như tier 2 (self-host).

**Firecrawl là gì:** API open-source (AGPL) biến web → markdown sạch / JSON, tự xử lý JS render + proxy rotation + anti-bot. Repo: github.com/firecrawl/firecrawl. Endpoints: `/scrape`, `/search`, `/map`, `/crawl`, `/batch`, `/extract`.

**⚠️ Thực tế self-host (đọc kỹ trước khi build):** Firecrawl KHÔNG phải 1 container. Stack gồm ~4-5 service: Redis + API + worker + playwright-service. Image vài GB, build lâu. Đây là thay đổi hạ tầng lớn → build lúc tỉnh táo, không lúc khuya.

**Tích hợp vào SmartAgent (sẵn-sàng-code):**

1. **docker-compose** — thêm Firecrawl services (lấy từ `docker-compose.yaml` repo Firecrawl), cùng network với `backend`. SmartAgent gọi `http://firecrawl-api:3002`.

2. **config.py** — thêm `firecrawl_url: str = "http://firecrawl-api:3002"` + `firecrawl_api_key: str = ""`.

3. **builtin_tools.py — engine-list (đã có structure):** thêm `_firecrawl_search` + `_firecrawl_scrape`, ưu tiên TRƯỚC DDG; fallback DDG free nếu Firecrawl down:
```python
engines = []
if settings.firecrawl_url: engines.append(("firecrawl", _firecrawl_search))
engines += [("duckduckgo", _ddg_search), ("ddg-lite", _ddg_lite_search)]
```
   - `web_search` mode `url`: gọi Firecrawl `/scrape` (render JS) thay `requests.get` thô → đọc được SPA/JS-wall.

4. **2 tool recon MỚI:**
   - `site_map(url, limit)` → Firecrawl `/map` → liệt kê mọi URL của site (attack surface cho red team).
   - `crawl_site(url, limit, max_depth)` → Firecrawl `/crawl` → cào nội dung nhiều trang (research/blue team). Async job → poll status.
   - Đăng ký tool_registry (category "intelligence").

**Acceptance đo được:**
- `web_search url=<trang JS-heavy>` → nội dung thật (Firecrawl render JS).
- `site_map url=<site>` → danh sách URL > 1.
- Firecrawl down → tự fallback DDG, không crash.
- 1 trang sau Cloudflare nhẹ → scrape được.

**Rủi ro:** RAM/CPU nặng; build lâu; AGPL (self-host nội bộ OK). ROE: recon/scrape cho red/blue team được ủy quyền.

---

## Tier 3 — Commercial APIs (khi cần vượt Cloudflare/captcha cứng nhất)

Code đã cấu trúc **engine-list** trong `handle_web_search` → thêm engine = thêm 1 async fn. Bật theo key có trong `.env`:

| Service | Mạnh | Key env | Ghi chú |
|---------|------|---------|---------|
| **Exa** | Neural search, nội dung sạch, research-grade | `EXA_API_KEY` | ⭐ Claude Code môi trường này CÓ MCP exa → tổ chức có thể đã có key. Ưu tiên thử. |
| **Brave Search API** | Index độc lập, rẻ, ổn định | `BRAVE_API_KEY` | Tốt cho search tổng quát |
| **Firecrawl** | Render JS + anti-bot + crawl | `FIRECRAWL_API_KEY` | Tốt cho scrape trang khó |
| **ScraperAPI / Bright Data / Zyte** | Rotating residential proxy + giải captcha | (mỗi hãng) | DUY NHẤT vượt Cloudflare/captcha cứng. Đắt nhất. |

**Pattern tích hợp (đã sẵn structure):**
```python
engines = []
if settings.exa_api_key: engines.append(("exa", _exa_search))
if settings.brave_api_key: engines.append(("brave", _brave_search))
engines += [("duckduckgo", _ddg_search), ("ddg-lite", _ddg_lite_search)]  # fallback free
# thử lần lượt, engine cao cấp trước, free fallback sau
```
→ Có key thì tự dùng engine xịn; không có thì free fallback. User chỉ cần thêm key vào `.env`, không đổi code.

---

## MCP option (thay vì tự code engine)
Claude Code môi trường này có sẵn các MCP: `exa` (web_search_exa, web_fetch_exa), `chrome-devtools` (browser thật), `playwright`. NHƯNG đây là MCP của **harness Claude Code**, KHÔNG phải của SmartAgent runtime. Để SmartAgent dùng MCP cần: (a) SmartAgent tự làm MCP client, hoặc (b) đơn giản hơn — gọi thẳng Exa/Brave REST API như tier 3 (không cần MCP layer). → **Khuyến nghị gọi REST trực tiếp**, nhẹ hơn dựng MCP client.

---

## Lộ trình đề xuất (mai)
1. **Hỏi user có key Exa/Brave không** (môi trường có MCP exa → khả năng cao có). Nếu có → tier 3 Exa trước (nhanh nhất, chất lượng cao nhất, ~30 phút code + test).
2. Nếu cần JS-wall/session → tier 2 Playwright (nâng RAM + pre-bake, ~nửa ngày).
3. Tier 3 proxy/captcha (Firecrawl/ScraperAPI) chỉ khi gặp Cloudflare cứng thực tế.

**ROE:** anti-detection cho red/blue team được ủy quyền + research là chính đáng. Giữ quyền tự do, không tự ý dùng cho mục đích ngoài phạm vi user giao.

## Files sẽ đụng
- `app/agent/builtin_tools.py` — thêm engine fn (tier 3) / tool `browser_fetch` (tier 2)
- `app/agent/tools.py` — schema
- `app/config.py` — `exa_api_key`/`brave_api_key`/... (đọc từ .env)
- `v2/sandbox/Dockerfile.sandbox` — pre-bake playwright (tier 2)
- `docker_manager.py` / `config.py:40` — RAM bump cho session browser (tier 2)
