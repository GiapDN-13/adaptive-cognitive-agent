# SmartAgent V2 — Platform Overview

**For:** Executive / Technical Leadership
**Date:** 2026-05-31
**Version:** 2.0.0

---

## What is SmartAgent?

SmartAgent là nền tảng AI Agent tự động hóa chuyên sâu, có khả năng **tự mở rộng** (self-extending) để thích ứng với mọi loại tác vụ — từ security research, penetration testing đến code audit và data analysis.

**Điểm khác biệt:** Agent không chỉ thực thi lệnh — nó **tự tạo công cụ mới** khi gặp bài toán phức tạp, lưu lại phương pháp luận, và cải thiện qua mỗi session.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  User (Web Dashboard)                                        │
│  ┌─────────────────────────┬───────────────────────────┐    │
│  │  Chat + Thinking Stream │  Activity + Pipeline + Ext │    │
│  └─────────────────────────┴───────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  WebSocket (real-time bidirectional)                          │
├─────────────────────────────────────────────────────────────┤
│  FastAPI Backend                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Agent Loop (ReACT: Think → Act → Observe → Repeat)  │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────┐   │   │
│  │  │ToolRegistry│  │ HookManager│  │SkillManager  │   │   │
│  │  │  14+ tools │  │ pre/post   │  │ 247+ skills  │   │   │
│  │  └────────────┘  └────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  LLM Provider: AWS Bedrock (Claude Sonnet 4.6)               │
├─────────────────────────────────────────────────────────────┤
│  Docker Sandbox (isolated per session)                        │
│  - Full Linux environment (Python 3.11, bash, gcc, curl)     │
│  - Network access for research                               │
│  - File system isolation                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Capabilities

### 1. Self-Extending Agent
Agent tự động nhận biết khi nào cần công cụ mới và tự tạo:

| Trigger | Agent Action |
|---------|-------------|
| Scan nhiều targets | Tự tạo `scanner` tool |
| Parse format lặp lại | Tự tạo `parser` tool |
| Multi-phase complex task | Tự dùng `execute_pipeline` |
| Phát hiện methodology hay | Tự tạo `skill` để nhớ |
| User yêu cầu safety rule | Tự tạo `hook` enforcement |

### 2. Structured Pipeline Execution
Thay vì free-form, agent tổ chức công việc thành stages:
```
Recon → Analysis → Exploitation → Reporting
```
Mỗi stage là subagent riêng biệt, findings tự động flow sang stage sau.

### 3. Safety & Quality Guardrails
- **GateGuard**: Block tạo/viết file nếu chưa research
- **Planning Loop**: Nhắc agent think trước khi act
- **AST Validation**: Runtime tools được validate syntax + security
- **Hook Pipeline**: Mọi tool call đều qua pre/post hooks
- **Karpathy Rules**: Think before coding, simplicity first, surgical changes

### 4. Real-time Dashboard
- **Activity Timeline**: Xem real-time từng action agent đang làm
- **Thinking Stream**: Xem agent reasoning (purple bubble)
- **Pipeline Progress**: Visual stages [●●●○○]
- **Extensions Panel**: Theo dõi tools/skills được tạo runtime

---

## Tool Registry (14 built-in + N runtime)

| Category | Tools |
|----------|-------|
| **Action** | shell_exec, write_file, read_file, web_search, think, ask_user, propose_plan, load_skill, load_agent |
| **Meta** | execute_pipeline, spawn_subagent, create_tool, create_skill, create_hook |
| **Runtime** | Agent tự tạo theo nhu cầu (scanner, parser, analyzer, tester...) |

---

## Security Research Workflow (Example)

```
User: "Phân tích CVE-2026-XXXXX, tìm RCE vector"

Agent:
  1. [think] Đánh giá yêu cầu — cần research + lab + exploit analysis
  2. [create_tool: cve_researcher] Tool tự động fetch NVD, advisories
  3. [create_tool: vuln_analyzer] Tool phân tích source code patches
  4. [execute_pipeline]
     Stage 1: RECON — thu thập public facts, advisories, patches
     Stage 2: ROOT CAUSE — phân tích diff, xác định bug primitive
     Stage 3: EXPLOITABILITY — đánh giá điều kiện RCE
     Stage 4: LAB — dựng environment, reproduce crash
     Stage 5: REPORT — tạo báo cáo chuyên nghiệp
  5. [create_skill: cve-analysis-methodology] Lưu lại phương pháp

Output: Full report tại /workspace/reports/ với:
  - Executive Summary
  - Technical Root Cause
  - Primitive Ladder (bug → primitive → condition → impact)
  - Prerequisite Graph (C1, C2, C3...)
  - Lab PoC Plan
  - Detection & Mitigation
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Tailwind + Zustand |
| Backend | FastAPI + uvicorn (Python 3.11) |
| LLM | AWS Bedrock — Claude Sonnet 4.6 |
| Sandbox | Docker container per session |
| State | File-based persistence + in-memory registry |
| Knowledge | 247 skills (ECC) + 61 agent definitions |

---

## Key Differentiators vs. ChatGPT/Claude.ai

| Feature | ChatGPT/Claude | SmartAgent |
|---------|---------------|------------|
| Code execution | Limited sandbox | Full Docker + network |
| Tool creation | No | Agent tự tạo tools runtime |
| Multi-stage pipeline | No | execute_pipeline với subagents |
| Memory across sessions | Basic | Skills persist methodology |
| Security research | Refuses | Fully authorized (pentest/audit) |
| Real-time visibility | Token stream only | Activity + Pipeline + Thinking |
| Quality enforcement | None | GateGuard + hooks + Karpathy rules |

---

## Deployment

```bash
# One command to start everything:
cd v2/ && docker compose up --build -d

# Services:
# - Frontend:  http://localhost:5173
# - Backend:   http://localhost:8000
# - Sandbox:   Auto-created per session
```

---

## Roadmap (Next)

- [ ] Multi-agent orchestration (Queen + Workers topology)
- [ ] Browser automation (Playwright/DevTools)
- [ ] GitNexus code intelligence integration
- [ ] Model routing (Sonnet for light tasks, Opus for complex)
- [ ] Authentication + multi-user support
- [ ] Persistent cross-session learning
