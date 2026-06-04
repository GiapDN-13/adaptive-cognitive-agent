# Roadmap: SmartAgent Production-Ready (Perfectionist Standard)

**Mục tiêu:** Đưa toàn bộ SmartAgent đạt chuẩn sếp cầu toàn duyệt.
**Nguyên tắc:** Hoàn hảo về chất lượng + ổn định + testable, NHƯNG giữ tự do cho redteam (không lock command execution).
**Date:** 2026-05-31

---

## Nguyên Tắc Cốt Lõi

> **"Mọi thứ agent làm phải tự kiểm chứng được, ổn định, và có bằng chứng — nhưng agent vẫn được phép làm mọi việc redteam cần (exploit, payload, command injection)."**

Security chỉ fix những gì KHÔNG cản trở redteam:
- ✅ Fix: hardcoded keys, secret leak, memory leak, crash
- ❌ KHÔNG thêm: lệnh chặn exploit, sandbox quá chặt, refuse offensive tasks

---

## PHASE 1 — Chất Lượng Agent (Core) [ưu tiên cao nhất]

Mục tiêu: Agent làm gì cũng đạt chuẩn, tự kiểm chứng, không bịa.

| # | Task | Mô tả |
|---|------|-------|
| 1.1 | Tool `verify_work` | Agent tự chạy test, so success criteria, trả pass/fail + lý do |
| 1.2 | Definition of Done | Agent bắt buộc định nghĩa success criteria đo được TRƯỚC khi làm |
| 1.3 | Self-verification loop | Build → Verify → Fix → Re-verify (max 3 lần) trước khi báo cáo |
| 1.4 | Verification rule | `rules/common/verification.md` — kỷ luật tự kiểm |
| 1.5 | Report template | Cấu trúc báo cáo chuẩn: Summary → Method → Results → Evidence → Limitations |

**Đầu ra:** Agent tự phát hiện lỗi (như out-of-scope RAG) và tự sửa trước khi báo cáo.

---

## PHASE 2 — Độ Ổn Định (Reliability)

Mục tiêu: Không crash, không timeout, demo không fail giữa chừng.

| # | Task | Trạng thái |
|---|------|-----------|
| 2.1 | Stream timeout + auto-retry | ✅ Đã làm (120s + retry) |
| 2.2 | Context window trim | ✅ Đã làm (80K threshold) |
| 2.3 | Pipeline checkpoint | 🔲 Lưu progress mỗi stage, resume nếu fail |
| 2.4 | Graceful degradation | 🔲 1 stage fail → stage khác vẫn chạy, báo rõ phần fail |
| 2.5 | Global error boundary | 🔲 Mọi exception → message thân thiện, không crash WS |
| 2.6 | Memory leak fix | 🔲 Cleanup global dicts khi session destroy |
| 2.7 | Blocking web_search fix | 🔲 Dùng httpx async thay requests sync |

---

## PHASE 3 — Test + CI/CD (Engineering)

Mục tiêu: Codebase có test thật, quality gate tự động.

| # | Task | Mô tả |
|---|------|-------|
| 3.1 | Dọn test rác | Xóa test_bing.py, test_ddg.py... (scripts nháp) |
| 3.2 | Unit tests core | Test tool_registry, tool_safety, hook_manager (logic thuần) |
| 3.3 | Integration test | Test agent loop end-to-end (mock LLM) |
| 3.4 | pytest config | Cấu hình pytest + coverage |
| 3.5 | CI workflow | GitHub Actions: lint + test on push |
| 3.6 | Pre-commit hook | ruff format + test trước commit |

---

## PHASE 4 — Bảo Mật Cơ Bản (không cản redteam)

Mục tiêu: Fix lỗ hổng nội bộ, GIỮ tự do offensive.

| # | Task | Mô tả |
|---|------|-------|
| 4.1 | Xóa hardcoded keys | config.py, docker-compose — chuyển hết sang .env |
| 4.2 | .env vào .gitignore | Đảm bảo không commit secrets |
| 4.3 | Secret scan | Kiểm tra git history có key nào leak |
| 4.4 | Memory cleanup | Session destroy → clear global state (cũng thuộc 2.6) |
| — | ~~Auth/rate limit~~ | ❌ BỎ QUA — nội bộ, redteam cần tự do |
| — | ~~Command blocking~~ | ❌ BỎ QUA — redteam cần chạy exploit |

---

## Thứ Tự Thực Hiện

```
Phase 1 (Chất lượng) → Phase 2 (Ổn định) → Phase 3 (Test) → Phase 4 (Security nhẹ)
     ↑ làm trước, ảnh hưởng demo nhiều nhất
```

Mỗi phase xong → test thực tế → báo cáo .docs/ → commit.

---

## Tiêu Chí "Sếp Cầu Toàn Duyệt"

Sau khi hoàn thành, hệ thống phải:
- [ ] Agent tự định nghĩa DoD + tự verify mọi task
- [ ] Agent tự phát hiện & sửa lỗi trước khi báo cáo
- [ ] Mọi báo cáo có số liệu + bằng chứng (không nói suông)
- [ ] Không crash/timeout trong demo (graceful mọi lỗi)
- [ ] Có test suite chạy được + CI xanh
- [ ] Không hardcoded secrets
- [ ] Redteam vẫn chạy exploit/payload tự do
