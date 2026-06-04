# SPEC: UI/UX Dashboard Redesign

**Date**: 2026-05-30
**Status**: DRAFT — awaiting approval
**Style**: Minimal dark dashboard, professional

---

## Layout Design

```
┌──────────────────────────────────────────────────────────────────┐
│  TOP BAR: Session info | Status dot | CPU/MEM | Actions          │
├────────────────────────────────────┬─────────────────────────────┤
│                                    │                             │
│          MAIN CHAT                 │     RIGHT PANEL             │
│     (messages + streaming)         │  ┌─────────────────────┐   │
│                                    │  │  Activity Timeline   │   │
│                                    │  │  (real-time feed)    │   │
│                                    │  ├─────────────────────┤   │
│                                    │  │  Pipeline Progress   │   │
│                                    │  │  [●●●○○] Stage 3/5   │   │
│                                    │  ├─────────────────────┤   │
│                                    │  │  Extensions          │   │
│                                    │  │  Tools(14) Skills(3) │   │
│                                    │  └─────────────────────┘   │
│                                    │                             │
├────────────────────────────────────┼─────────────────────────────┤
│  BOTTOM: Terminal output (collapsible, shared width)             │
├────────────────────────────────────┴─────────────────────────────┤
│  INPUT BAR: [📎] [input area...........................] [Send]  │
└──────────────────────────────────────────────────────────────────┘
```

### Responsive breakdown:
- **Desktop (>1200px)**: Full layout as above — chat 60%, right panel 40%
- **Tablet (768-1200px)**: Right panel collapses to tab overlay
- **Mobile (<768px)**: Full-width chat only, panels via bottom sheet

---

## Right Panel — 3 Sections (accordion/tabs)

### 1. Activity Timeline
- Real-time feed of agent actions (like a mini log)
- Each entry: `[icon] [timestamp] [action description]`
- Color-coded: green=success, yellow=in-progress, red=error, blue=info
- Auto-scrolls, collapsible
- Shows: tool calls, pipeline stages, approvals, tool creations

### 2. Pipeline Progress
- Only visible when pipeline running
- Visual progress: stage dots/bar + current stage name
- Each stage: icon + name + status (pending/running/done/failed)
- Expandable: click stage to see its output summary
- Shows elapsed time per stage

### 3. Extensions Panel (existing, improved)
- Tabs: Tools | Skills | Hooks
- Runtime-created items highlighted with accent color
- Compact list with category badges
- Delete button for runtime items
- "Created this session" indicator

---

## Top Bar Redesign

```
[Logo] SmartAgent   ● Running   session:abc123   CPU: 2.1%   MEM: 45MB   [🕐 History] [🔧 Extensions] [📁 Files] [⬛ End]
```

- Compact, single line
- Status dot (green/yellow/red)
- Resource stats always visible when running
- Toggle buttons on right for panels

---

## Chat Area Improvements

1. **Message bubbles** — slightly rounder, better spacing
2. **Code blocks** — syntax highlighting with copy button
3. **Approval cards** — inline but with better visual hierarchy
4. **Plan viewer** — progress steps with checkmarks/spinners inline
5. **Sub-agent messages** — visually indented, different left border color
6. **Streaming** — smoother cursor animation
7. **Timestamps** — subtle, on hover

---

## Terminal Section

- Below chat, shared full width
- Collapsible (click header to expand/collapse)
- Max 3 recent executions visible
- Each execution: header with exec_id + status + clear button
- Monospace, color-coded stdout(white)/stderr(red)
- Copy button per execution

---

## Input Bar Redesign

```
[📎 files] | Write a message or paste a task...                    | [Cancel ⬛] [Send ➤]
```

- Taller (3 lines min visible)
- Attachment preview row (if files selected)
- Send button changes to Cancel when agent working
- Subtle character count
- Shift+Enter for new line, Enter to send

---

## New Components Needed

| Component | File | Purpose |
|-----------|------|---------|
| `DashboardLayout.tsx` | Layout wrapper with grid/flexbox panels |
| `RightPanel.tsx` | Accordion container for Activity/Pipeline/Extensions |
| `ActivityTimeline.tsx` | Real-time agent action feed |
| `PipelineProgress.tsx` | Visual pipeline stage tracker |
| `ImprovedTopBar.tsx` | Redesigned session bar |

---

## Color System (extended)

```css
--bg: #0a0a0a          /* Main background */
--surface: #141414      /* Panel/card background */
--surface-2: #1a1a1a   /* Elevated surface */
--border: rgba(255,255,255,0.06)  /* Subtle borders */
--border-active: rgba(255,255,255,0.12)  /* Active borders */
--primary: #0E7C6B     /* Teal accent */
--primary-glow: rgba(14,124,107,0.15)  /* Subtle glow */
--success: #22c55e
--warning: #eab308
--error: #ef4444
--info: #3b82f6
--text: #e5e5e5         /* Primary text */
--text-muted: #737373   /* Secondary text */
--text-dim: #525252     /* Tertiary text */
```

---

## Implementation Order

1. **DashboardLayout** — Grid structure, panel system
2. **Top Bar** — Redesign with new style
3. **Right Panel** — Activity + Pipeline + Extensions
4. **Chat improvements** — Spacing, typography, timestamps
5. **Terminal** — Collapse/expand, better styling
6. **Input Bar** — Taller, better UX
7. **Responsive** — Collapse panels on smaller screens
8. **Animations** — Subtle transitions, loading states

---

## Tech Decisions

- **No new dependencies** — Tailwind + Lucide + existing libs are sufficient
- **CSS Grid** for dashboard layout (simpler than nested flexbox)
- **CSS transitions** for panel open/close (no animation library needed)
- **Zustand** for panel state (which panels open, activity log)

---

## Mockup ASCII — Desktop View

```
┌─────────────────────────────────────────────────────────────────────┐
│  ◉ SmartAgent  ● session:a1b2c3  CPU 1.2%  128MB   [🕐][🔧][📁][⬛]│
├───────────────────────────────────────┬─────────────────────────────┤
│ ┌─────────────────────────────────┐   │ ▾ Activity                  │
│ │ 👤 Audit API này tìm RCE...    │   │  13:45 🔍 web_search: swi.. │
│ └─────────────────────────────────┘   │  13:46 🧠 think: planning   │
│                                       │  13:46 🔧 create_tool: sca..│
│ ┌─────────────────────────────────┐   │  13:47 ⚡ scanner: found 12 │
│ │ 🤖 Đã phân tích API surface... │   │  13:48 🔧 create_tool: tes..│
│ │   ├─ POST /api/ai/{slug}       │   │                             │
│ │   ├─ POST /api/files/upload     │   │ ▾ Pipeline [3/5]            │
│ │   └─ GET /api/users/me          │   │  ✅ Recon         12s       │
│ └─────────────────────────────────┘   │  ✅ Surface Map   8s        │
│                                       │  ⏳ RCE Testing   ...       │
│ ┌─────────────────────────────────┐   │  ○ Exploitation             │
│ │ 🤖 Testing endpoint /api/ai... │   │  ○ Reporting                │
│ │   [streaming...]█               │   │                             │
│ └─────────────────────────────────┘   │ ▾ Extensions                │
│                                       │  🔧 scanner (Intel)         │
├───────────────────────────────────────│  🔧 payload_tester (Action) │
│ ▾ Terminal [exec_a1b2]               │  📘 api-rce-methodology     │
│ $ curl -X POST https://graphql...    │                             │
│ HTTP/1.1 200 OK                      │                             │
│ {"data": {"...                       │                             │
├───────────────────────────────────────┴─────────────────────────────┤
│ [📎] Nhập lệnh hoặc câu hỏi...                        [Cancel][➤] │
└─────────────────────────────────────────────────────────────────────┘
```
