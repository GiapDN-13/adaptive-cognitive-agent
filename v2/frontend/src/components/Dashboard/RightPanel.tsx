import { useState, useEffect, useRef } from 'react'
import { Activity, Layers, Wrench, Puzzle, ChevronDown, ChevronRight, Search, Brain, Zap, FileText, Shield, Eye, Settings, Trash2, RefreshCw, CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'

// ---------------------------------------------------------------------------
// Activity Timeline
// ---------------------------------------------------------------------------

interface ActivityEntry {
  id: string
  timestamp: number
  tool: string
  detail: string
  type: 'info' | 'success' | 'warning' | 'error'
}

const TOOL_CONFIG: Record<string, { icon: typeof Brain; color: string }> = {
  thinking: { icon: Brain, color: 'text-purple-400' },
  shell_exec: { icon: Zap, color: 'text-yellow-400' },
  web_search: { icon: Search, color: 'text-blue-400' },
  write_file: { icon: FileText, color: 'text-green-400' },
  read_file: { icon: Eye, color: 'text-gray-400' },
  create_tool: { icon: Wrench, color: 'text-primary' },
  create_skill: { icon: Puzzle, color: 'text-orange-400' },
  create_hook: { icon: Shield, color: 'text-red-400' },
  pipeline: { icon: Layers, color: 'text-cyan-400' },
  ask_user: { icon: Brain, color: 'text-blue-300' },
  propose_plan: { icon: Layers, color: 'text-indigo-400' },
  execute_pipeline: { icon: Layers, color: 'text-cyan-400' },
  spawn_subagent: { icon: Brain, color: 'text-violet-400' },
}

function ActivityTimeline() {
  const { agentStatus, isAgentWorking, agentElapsed } = useChatStore()
  const [entries, setEntries] = useState<ActivityEntry[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const lastStatusRef = useRef<string | null>(null)

  useEffect(() => {
    // Ignore heartbeat-style "Thinking... (Xs)" strings — they are keepalives, not
    // activity. (Heartbeats now use agentElapsed and never reach agentStatus, but
    // guard here too in case any path still sets such a status.)
    if (!agentStatus || agentStatus === lastStatusRef.current) return
    if (/^Thinking\.\.\.\s*\(\d+s\)$/.test(agentStatus)) return
    lastStatusRef.current = agentStatus

    const toolMatch = agentStatus.match(/^Using (\w+)/)
    const tool = toolMatch ? toolMatch[1] : agentStatus.includes('Thinking') ? 'thinking' : 'unknown'
    const detail = toolMatch ? agentStatus.replace(`Using ${toolMatch[1]}`, '').replace(/^:\s*/, '') : agentStatus

    const entry: ActivityEntry = {
      id: crypto.randomUUID(),
      timestamp: Date.now(),
      tool,
      detail: detail.slice(0, 80),
      type: tool === 'create_tool' || tool === 'create_skill' ? 'success' : 'info',
    }
    setEntries(prev => [...prev.slice(-50), entry])
  }, [agentStatus])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [entries])

  const formatTime = (ts: number) => {
    const d = new Date(ts)
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        {entries.length === 0 && !isAgentWorking && (
          <p className="text-xs text-gray-600 text-center py-4">Activity sẽ hiển thị khi agent làm việc</p>
        )}
        {entries.map(entry => {
          const config = TOOL_CONFIG[entry.tool] || { icon: Zap, color: 'text-gray-500' }
          const Icon = config.icon
          return (
            <div key={entry.id} className="flex items-start gap-2 py-0.5 group">
              <span className="text-[10px] text-gray-600 font-mono shrink-0 mt-0.5">{formatTime(entry.timestamp)}</span>
              <Icon size={11} className={`${config.color} shrink-0 mt-0.5`} />
              <span className="text-[11px] text-gray-400 truncate">{entry.detail || entry.tool}</span>
            </div>
          )
        })}
        {isAgentWorking && (
          <div className="flex items-center gap-2 py-0.5">
            <Loader2 size={11} className="text-primary animate-spin" />
            <span className="text-[11px] text-primary/70">
              Working{agentElapsed && agentElapsed >= 8 ? ` (${agentElapsed}s)` : '...'}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pipeline Progress
// ---------------------------------------------------------------------------

function PipelineProgress() {
  const { agentStatus } = useChatStore()

  const pipelineMatch = agentStatus?.match(/\[(\d+)\/(\d+)\]\s*(.+)/)
  if (!pipelineMatch) return null

  const current = parseInt(pipelineMatch[1])
  const total = parseInt(pipelineMatch[2])
  const stageName = pipelineMatch[3]

  return (
    <div className="px-3 py-3 border-t border-white/[0.04]">
      <div className="flex items-center gap-2 mb-2">
        <Layers size={12} className="text-cyan-400" />
        <span className="text-[11px] font-medium text-gray-300">Pipeline</span>
        <span className="text-[10px] text-gray-500 ml-auto">{current}/{total}</span>
      </div>

      {/* Progress bar */}
      <div className="flex gap-1 mb-2">
        {Array.from({ length: total }, (_, i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded-full transition-all duration-300 ${
              i < current ? 'bg-primary' :
              i === current - 1 ? 'bg-primary animate-pulse' :
              'bg-white/[0.06]'
            }`}
          />
        ))}
      </div>

      <span className="text-[11px] text-gray-400">{stageName}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Extensions Compact
// ---------------------------------------------------------------------------

interface ToolInfo {
  name: string
  builtin: boolean
  category: string
}

function ExtensionsCompact() {
  const { sessionId } = useChatStore()
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [loading, setLoading] = useState(false)

  const fetchTools = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/extensions/tools')
      const data = await res.json()
      setTools(data.tools || [])
    } catch { /* silent */ }
    setLoading(false)
  }

  useEffect(() => {
    if (sessionId) fetchTools()
  }, [sessionId])

  // Auto-refresh every 10s to catch new tools
  useEffect(() => {
    if (!sessionId) return
    const interval = setInterval(fetchTools, 10000)
    return () => clearInterval(interval)
  }, [sessionId])

  const runtimeTools = tools.filter(t => !t.builtin)
  const builtinCount = tools.filter(t => t.builtin).length

  const handleDelete = async (name: string) => {
    await fetch(`/api/extensions/tools/${name}`, { method: 'DELETE' })
    fetchTools()
  }

  const CATEGORY_COLORS: Record<string, string> = {
    action: 'text-blue-400',
    intelligence: 'text-green-400',
    meta: 'text-purple-400',
  }

  return (
    <div className="px-3 py-3 border-t border-white/[0.04]">
      <div className="flex items-center gap-2 mb-2">
        <Wrench size={12} className="text-primary" />
        <span className="text-[11px] font-medium text-gray-300">Extensions</span>
        <span className="text-[10px] text-gray-500 ml-auto">{tools.length} tools</span>
        <button onClick={fetchTools} className="p-0.5 hover:bg-white/[0.06] rounded">
          <RefreshCw size={10} className={loading ? 'animate-spin text-gray-500' : 'text-gray-600'} />
        </button>
      </div>

      {runtimeTools.length > 0 && (
        <div className="space-y-1 mb-2">
          <span className="text-[10px] uppercase tracking-wider text-primary/60 font-medium">Runtime ({runtimeTools.length})</span>
          {runtimeTools.map(tool => (
            <div key={tool.name} className="flex items-center gap-2 py-0.5 group">
              <Wrench size={10} className={CATEGORY_COLORS[tool.category] || 'text-gray-400'} />
              <span className="text-[11px] text-gray-300 font-mono flex-1 truncate">{tool.name}</span>
              <button
                onClick={() => handleDelete(tool.name)}
                className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-500/20 rounded"
              >
                <Trash2 size={9} className="text-red-400" />
              </button>
            </div>
          ))}
        </div>
      )}

      <span className="text-[10px] text-gray-600">{builtinCount} built-in tools loaded</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Right Panel Container
// ---------------------------------------------------------------------------

export function RightPanel() {
  const [sections, setSections] = useState({ activity: true, extensions: true })

  const toggleSection = (key: keyof typeof sections) => {
    setSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div className="w-[320px] border-l border-white/[0.06] bg-surface/40 flex flex-col overflow-hidden">
      {/* Activity Section */}
      <div className="flex flex-col min-h-0 flex-1">
        <button
          onClick={() => toggleSection('activity')}
          className="flex items-center gap-2 px-3 py-2 hover:bg-white/[0.03] transition shrink-0"
        >
          {sections.activity ? <ChevronDown size={11} className="text-gray-500" /> : <ChevronRight size={11} className="text-gray-500" />}
          <Activity size={12} className="text-primary" />
          <span className="text-[11px] font-medium text-gray-300">Activity</span>
        </button>
        {sections.activity && <ActivityTimeline />}
      </div>

      {/* Pipeline (auto-shows when active) */}
      <PipelineProgress />

      {/* Extensions Section */}
      <div className="shrink-0">
        <button
          onClick={() => toggleSection('extensions')}
          className="flex items-center gap-2 px-3 py-2 hover:bg-white/[0.03] transition w-full"
        >
          {sections.extensions ? <ChevronDown size={11} className="text-gray-500" /> : <ChevronRight size={11} className="text-gray-500" />}
          <Wrench size={12} className="text-primary" />
          <span className="text-[11px] font-medium text-gray-300">Extensions</span>
        </button>
        {sections.extensions && <ExtensionsCompact />}
      </div>
    </div>
  )
}
