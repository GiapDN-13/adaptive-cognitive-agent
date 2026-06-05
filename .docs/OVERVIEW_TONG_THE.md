# SmartAgent V2 — Báo Cáo Tổng Thể

**Ngày:** 2026-05-31
**Phiên bản:** 2.0.0
**Đối tượng:** Lãnh đạo / Đánh giá kỹ thuật
**Model:** AWS Bedrock — Claude Sonnet 4.6

---

## 1. SmartAgent Là Gì?

SmartAgent là nền tảng **AI Agent tự chủ và tự mở rộng**, có khả năng hoàn thành các tác vụ phức tạp end-to-end mà không cần can thiệp thủ công — từ phát triển phần mềm, security audit, đến nghiên cứu và phân tích dữ liệu.

**3 đặc tính cốt lõi phân biệt với chatbot thông thường:**

| Đặc tính | Ý nghĩa |
|----------|---------|
| **Tự chủ (Autonomous)** | Nhận yêu cầu → tự lập kế hoạch → thực thi → kiểm chứng → báo cáo |
| **Tự mở rộng (Self-Extending)** | Tự tạo công cụ/kỹ năng mới tại runtime khi gặp bài toán chưa có sẵn tool |
| **Cầu toàn (Quality-First)** | Không báo cáo "xong" cho đến khi tự kiểm chứng đạt chuẩn + tự bắt lỗi mình |

---

## 2. Kiến Trúc Hệ Thống

```
┌──────────────────────────────────────────────────────────────────┐
│  FRONTEND — React Dashboard (localhost:5173)                       │
│  ┌────────────────────────────┬──────────────────────────────┐    │
│  │  Chat + Thinking Stream    │  Right Panel:                │    │
│  │  (hội thoại + suy nghĩ)    │  • Activity Timeline         │    │
│  │                            │  • Pipeline Progress         │    │
│  │  Terminal Output           │  • Extensions (tools/skills) │    │
│  └────────────────────────────┴──────────────────────────────┘    │
├──────────────────────────────────────────────────────────────────┤
│  WebSocket (real-time, 2 chiều)                                    │
├──────────────────────────────────────────────────────────────────┤
│  BACKEND — FastAPI (localhost:8000)                                │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │  AGENT LOOP (ReACT: Think → Act → Observe → Repeat)       │     │
│  │  ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐    │     │
│  │  │ToolRegistry │ │ HookManager │ │ SkillManager     │    │     │
│  │  │ 15 tools    │ │ 4 pre+4 post│ │ 246 skills       │    │     │
│  │  └─────────────┘ └─────────────┘ └──────────────────┘    │     │
│  └──────────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────┤
│  LLM: AWS Bedrock — Claude Sonnet 4.6 (native tool_use)            │
├──────────────────────────────────────────────────────────────────┤
│  DOCKER SANDBOX (mỗi session = 1 container cô lập)                 │
│  Python 3.11, bash, gcc, curl, network access                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Bộ Công Cụ (15 Tools)

### Action Tools (9) — Thực thi tác vụ
| Tool | Chức năng |
|------|-----------|
| `shell_exec` | Chạy lệnh bash trong sandbox, stream output |
| `write_file` / `read_file` | Đọc/ghi file trong container |
| `web_search` | Tìm kiếm web (async, không block) |
| `think` | Lập luận nội bộ (hiển thị thinking stream) |
| `ask_user` | Hỏi người dùng khi cần làm rõ |
| `propose_plan` | Đề xuất kế hoạch nhiều bước để duyệt |
| `load_skill` / `load_agent` | Nạp kiến thức/vai trò chuyên biệt |

### Meta Tools (6) — Tự mở rộng & kiểm chứng
| Tool | Chức năng |
|------|-----------|
| `create_tool` | **Tự tạo tool mới** tại runtime (Python handler + schema) |
| `create_skill` | **Tự tạo kỹ năng** ghi lại phương pháp luận |
| `create_hook` | **Tự tạo guard** kiểm soát execution |
| `verify_work` | **Tự kiểm chứng** kết quả theo tiêu chí (chạy test thực) |
| `execute_pipeline` | Thực thi tác vụ nhiều giai đoạn (mỗi stage = subagent) |
| `spawn_subagent` | Tạo agent con cho sub-task (vd: QA reviewer) |

---

## 4. Cơ Chế Đảm Bảo Chất Lượng (Quality-First Loop)

Đây là điểm mạnh nhất của hệ thống. Mỗi tác vụ tuân theo vòng lặp:

```
1. DEFINITION OF DONE — Tự định nghĩa tiêu chí thành công ĐO ĐƯỢC
       ↓
2. BUILD — Tạo tools cần thiết + thực thi
       ↓
3. SELF-VERIFY — Chạy verify_work cho TỪNG tiêu chí
       ↓ (fail?) → FIX → quay lại bước 3
4. ADVERSARIAL REVIEW — Spawn QA agent cố bắt lỗi mình
       ↓ (tìm thấy lỗi?) → FIX → quay lại bước 3
       ↓ (2 vòng sạch liên tiếp)
5. REPORT — Báo cáo có số liệu + bằng chứng, trung thực phần chưa đạt
```

**Nguyên tắc vàng:**
- KHÔNG báo cáo "hoàn thành" nếu chưa `verify_work` mọi tiêu chí
- KHÔNG nói "hoạt động tốt" mà không có số liệu chứng minh
- Tự bắt lỗi mình TRƯỚC khi user phát hiện
- Trung thực về phần chưa đạt > giả vờ hoàn hảo

---

## 5. Các Lớp Bảo Vệ (Guardrails)

### Pre-Hooks (chạy TRƯỚC mỗi tool — có thể chặn)
| Hook | Tác dụng |
|------|----------|
| `dangerous_command` | Chặn `rm -rf /`, fork bomb, mkfs, reverse shell |
| `gateguard` | Bắt agent research TRƯỚC khi tạo/ghi (chống hallucinate) |
| `secret_detection` | Chặn hardcode AWS key, token, password |
| `config_protection` | Bảo vệ file cấu hình linter |

### Post-Hooks (chạy SAU mỗi tool)
| Hook | Tác dụng |
|------|----------|
| `audit_log` | Ghi log mọi tool call (input + result) |
| `quality_gate` | Cảnh báo file lớn, thiếu test |
| `planning_nudge` | Nhắc `think` nếu agent chưa lập kế hoạch |
| `debug_statement` | Phát hiện console.log/print sót lại |

> **Lưu ý cho Redteam:** Hệ thống KHÔNG chặn command execution, exploit, payload — agent được phép thực hiện offensive security tasks. Guardrails chỉ chặn lệnh tự hủy hệ thống (rm -rf /) và hardcode secrets, không cản trở công việc pentest.

---

## 6. Bảo Mật & Cô Lập

| Lớp | Cơ chế |
|-----|--------|
| **Sandbox** | Mỗi session = 1 Docker container riêng, cô lập file system |
| **AST Validation** | Code runtime tools được kiểm tra: chặn `os`, `subprocess`, `eval`, `exec` |
| **Import whitelist** | Runtime tools chỉ dùng: json, re, csv, hashlib, datetime... |
| **Secret protection** | `.env` trong .gitignore. ⚠️ Lưu ý: hiện còn fallback key hardcoded trong `config.py` — chấp nhận được cho dùng nội bộ, cần xóa nếu public repo |
| **Approval gate** | Lệnh nguy hiểm (pip install, rm) yêu cầu phê duyệt |

---

## 7. Độ Ổn Định (Reliability)

| Cơ chế | Mô tả |
|--------|-------|
| Stream timeout 120s + auto-retry | Phát hiện LLM stall, tự thử lại với context nhỏ hơn |
| Context windowing | Trim khi context > 80K chars, tránh tràn token |
| Memory cleanup | Xóa global state khi session destroy (chống memory leak) |
| Graceful degradation | 1 stage pipeline fail không crash toàn bộ |
| Error boundary | Mọi exception → message thân thiện, UI không kẹt |
| Generation counter | Hủy loop cũ khi user gửi tin mới |

---

## 8. Kiểm Thử & CI/CD

| Hạng mục | Trạng thái |
|----------|-----------|
| Unit tests | **35 tests** (tool_registry, tool_safety, hook_manager) — all passing |
| Test framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Linting | ruff |
| CI Pipeline | GitHub Actions — lint + test on push/PR |

---

## 9. Giao Diện Người Dùng (Dashboard)

Layout dashboard chuyên nghiệp giúp user theo dõi real-time:

- **Chat + Thinking Stream**: Xem agent suy nghĩ (bong bóng tím) trước khi hành động
- **Activity Timeline**: Feed real-time mọi tool call với timestamp + icon màu
- **Pipeline Progress**: Thanh tiến trình các giai đoạn `[●●●○○]`
- **Extensions Panel**: Danh sách tools/skills được tạo, xóa được runtime tools
- **Terminal**: Output lệnh shell trực tiếp

---

## 10. Nền Tảng Kiến Thức

| Nguồn | Số lượng |
|-------|----------|
| Skills (ECC vendored) | 246 |
| Agent definitions | 61 |
| Rules (common) | identity, behavior, format, security, quality, verification, reporting |

Tích hợp pattern từ 6 dự án nghiên cứu: ECC (hooks/skills), Ruflo (orchestration), Superpowers (planning discipline), Shannon (pipeline), GitNexus (categorization), Karpathy (code quality).

---

## 11. Triển Khai

```bash
cd v2/ && docker compose up --build -d
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
```

---

## 12. So Sánh Với ChatGPT / Claude.ai

| Tính năng | ChatGPT/Claude | SmartAgent |
|-----------|---------------|------------|
| Thực thi code | Sandbox hạn chế | Full Docker + network |
| Tự tạo tool | ❌ | ✅ Runtime |
| Pipeline nhiều stage | ❌ | ✅ |
| Tự kiểm chứng (verify) | ❌ | ✅ verify_work loop |
| Adversarial self-review | ❌ | ✅ QA subagent |
| Security/offensive tasks | Từ chối | ✅ Được phép (redteam) |
| Theo dõi real-time | Token stream | Activity + Pipeline + Thinking |
| Nhớ cross-session | Cơ bản | Skills lưu phương pháp |

---

## 13. Kết Luận

SmartAgent V2 là một **agent kỹ sư tự chủ**, không phải máy sinh văn bản:

- Làm việc có kỷ luật: lập kế hoạch → thực thi → kiểm chứng → phản biện → báo cáo
- Tự mở rộng năng lực khi gặp bài toán mới
- Đảm bảo chất lượng bằng verification thực tế, không nói suông
- Ổn định, có test bảo vệ, minh bạch hoàn toàn

Phù hợp cho: security research/pentest, phát triển phần mềm tự động, code audit, data analysis, và các tác vụ cần độ tin cậy + khả năng kiểm chứng cao.
