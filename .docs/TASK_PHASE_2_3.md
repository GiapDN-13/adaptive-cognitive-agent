# Báo Cáo: Phase 2 (Độ Ổn Định) + Phase 3 (Test & CI/CD)

**Ngày:** 2026-05-31
**Trạng thái:** ✅ Hoàn thành
**Test:** 35 unit tests passed, backend rebuild OK

---

## Phase 2 — Độ Ổn Định (Reliability)

| # | Task | Thay đổi | File |
|---|------|----------|------|
| 2.1 | Stream timeout + retry | ✅ Đã có từ trước (120s + auto-retry) | client.py, loop.py |
| 2.2 | Context window trim | ✅ Đã có (80K threshold) | loop.py |
| 2.6 | **Memory leak fix** | `cleanup_session_state()` xóa global dicts khi session destroy | loop.py, session_manager.py |
| 2.7 | **Async web_search** | `asyncio.to_thread(requests.post)` — không block event loop | builtin_tools.py |
| 2.4 | **Graceful pipeline** | Stage fail không crash pipeline, báo rõ phần fail | builtin_tools.py |
| 2.5 | **Error boundary** | Exception → message tiếng Việt thân thiện + đóng stream để UI không kẹt | loop.py |

### Chi tiết Memory Leak Fix
Trước: `_cancel_flags`, `_session_generation`, `_cancel_events`, `_session_pending_ids`, hook history — tích lũy vô tận, không bao giờ xóa.

Sau: Khi session destroy → `cleanup_session_state()` xóa toàn bộ. Ngăn memory growth khi chạy nhiều session.

### Chi tiết Async web_search
Trước: `requests.post(timeout=10)` block event loop 10s — đơ tất cả WebSocket khác.

Sau: chạy trong thread pool qua `asyncio.to_thread` — event loop tự do.

---

## Phase 3 — Test & CI/CD (Engineering)

| # | Task | Kết quả |
|---|------|---------|
| 3.1 | **Dọn test rác** | Xóa 11 test scripts nháp (test_bing, test_ddg, test_cursor...) + 7 file rác (fix_prompts, find_endpoints...) |
| 3.2 | **Unit tests core** | 35 tests cho tool_registry, tool_safety, hook_manager |
| 3.4 | **pytest config** | asyncio_mode=auto, testpaths, ruff lint config |
| 3.5 | **CI workflow** | `.github/workflows/ci.yml` — lint + test on push/PR |

### Test Coverage
```
tests/
├── test_tool_registry.py   (9 tests)  — dispatch, register, subagent filter
├── test_tool_safety.py     (14 tests) — AST validation, forbidden imports/calls
└── test_hook_manager.py    (12 tests) — pre/post hooks, GateGuard, dangerous cmd, secret detection
```

**Kết quả:** `35 passed in 0.08s`

### Các test quan trọng
- `test_cannot_overwrite_builtin_with_runtime` — bảo vệ builtin tools
- `test_subagent_excludes_meta_tools` — subagent không có create_tool/spawn
- `test_forbidden_import_os/subprocess` — chặn code nguy hiểm
- `test_gateguard_blocks_create_without_research` — bắt research trước khi tạo
- `test_dangerous_command_blocks_rm_rf_root` — chặn lệnh phá hoại
- `test_hook_manager_fail_open_on_exception` — hook lỗi không chặn execution

### CI Pipeline
```yaml
on push/PR (v2/backend/**):
  → setup Python 3.11
  → install pytest + ruff
  → ruff check (warn-only ban đầu)
  → pytest tests/ -v
```

---

## Lưu ý: Phase 4 (Security) — Quyết định giữ tự do redteam

Theo yêu cầu, KHÔNG lock down để redteam làm việc:
- ❌ KHÔNG thêm auth/rate-limit (nội bộ)
- ❌ KHÔNG chặn command execution (cần cho exploit)
- ✅ Chỉ fix hardcoded keys (Phase 4 — sẽ làm riêng nếu cần)

Hiện tại agent vẫn chạy được mọi lệnh exploit/payload/command injection — đúng nhu cầu redteam.

---

## Tổng Kết

| Hạng mục | Trước | Sau |
|----------|-------|-----|
| Memory leak | Có (global dicts tích lũy) | ✅ Fixed |
| web_search blocking | Block event loop 10s | ✅ Async |
| Pipeline fail | Có thể crash | ✅ Graceful |
| Error handling | Crash, UI kẹt | ✅ Friendly message |
| Test suite | 0 test thật (toàn script nháp) | ✅ 35 unit tests |
| CI/CD | Không có | ✅ GitHub Actions |
| Junk files | 18 file rác | ✅ Đã dọn |

Hệ thống giờ ổn định hơn, có test bảo vệ regression, và CI tự động kiểm tra mỗi commit.
