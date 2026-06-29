import { useState, useEffect } from 'react'
import { Play, Square, Loader2, Cpu, HardDrive, History, PanelRightOpen, PanelRightClose, Zap, ExternalLink } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import { getSessionStats } from '@/api/http'

interface Props {
  onStart: () => void
  onEnd: () => void
  onHistoryOpen: () => void
  onRightPanelToggle: () => void
  rightPanelOpen: boolean
}

export function TopBar({ onStart, onEnd, onHistoryOpen, onRightPanelToggle, rightPanelOpen }: Props) {
  const { containerStatus, sessionId, isAgentWorking, agentStatus } = useChatStore()
  const [stats, setStats] = useState({ cpu_percent: 0, memory_mb: 0 })
  const [appUrl, setAppUrl] = useState<string | null>(null)
  // appPort: cổng host đã map (có ngay cả khi app CHƯA listening) — để hiện nút Preview
  // "thử mở" thay vì ẩn hoàn toàn khi app chết. listening: app thật sự đang trả lời.
  const [appPort, setAppPort] = useState<number | null>(null)
  const [appListening, setAppListening] = useState(false)

  useEffect(() => {
    if (!sessionId || containerStatus !== 'running') return
    let cancelled = false
    const tick = async () => {
      // Skip polling while the tab is hidden — avoids piling up requests in the
      // background and the request storm that made the UI feel laggy.
      if (document.hidden || cancelled) return
      try {
        const s = await getSessionStats(sessionId)
        if (cancelled) return
        setStats({ cpu_percent: s.cpu_percent, memory_mb: s.memory_mb })
        const res = await fetch(`/api/sessions/${sessionId}/app`)
        const data = await res.json()
        if (!cancelled) {
          setAppListening(!!data.listening)
          setAppUrl(data.listening ? data.url : null)
          setAppPort(data.app_port ?? null)
        }
      } catch {
        if (!cancelled) { setAppListening(false); setAppUrl(null) }
      }
    }
    const interval = setInterval(tick, 5000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [sessionId, containerStatus])

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-white/[0.06] bg-surface/80 backdrop-blur-sm">
      {/* Logo */}
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 rounded-md bg-primary/20 flex items-center justify-center">
          <Zap size={12} className="text-primary" />
        </div>
        <span className="text-sm font-semibold text-white/90 hidden sm:inline">SmartAgent</span>
      </div>

      {/* Divider */}
      <div className="w-px h-4 bg-white/[0.06]" />

      {/* Status */}
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${
          containerStatus === 'running'
            ? isAgentWorking ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'
            : containerStatus === 'creating' ? 'bg-yellow-400 animate-pulse'
            : 'bg-gray-500'
        }`} />
        <span className="text-xs text-gray-400 font-mono">
          {containerStatus === 'running' ? sessionId?.slice(0, 8) :
           containerStatus === 'creating' ? 'Starting...' :
           'No session'}
        </span>
      </div>

      {/* Agent Status (when working) */}
      {isAgentWorking && agentStatus && (
        <>
          <div className="w-px h-4 bg-white/[0.06]" />
          <span className="text-[11px] text-primary font-mono truncate max-w-[200px]">
            {agentStatus}
          </span>
        </>
      )}

      {/* Stats */}
      {containerStatus === 'running' && (
        <>
          <div className="w-px h-4 bg-white/[0.06] ml-auto" />
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Cpu size={11} /> {stats.cpu_percent.toFixed(1)}%
            </span>
            <span className="flex items-center gap-1">
              <HardDrive size={11} /> {stats.memory_mb.toFixed(0)}MB
            </span>
          </div>
        </>
      )}

      {/* Actions */}
      <div className={`flex items-center gap-1.5 ${containerStatus !== 'running' ? 'ml-auto' : ''}`}>
        {appListening && appUrl ? (
          // App đang chạy → nút xanh, mở ngay.
          <a
            href={appUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-500/15 hover:bg-green-500/25 text-green-400 text-xs font-medium transition animate-pulse"
            title={`Open app running at ${appUrl}`}
          >
            <ExternalLink size={12} /> Open App
          </a>
        ) : appPort ? (
          // Cổng đã map nhưng app CHƯA trả lời (chưa start / đang boot / đã chết) →
          // vẫn cho user nút "thử mở" thay vì ẩn hoàn toàn. Mở thẳng host port.
          <a
            href={`http://localhost:${appPort}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] text-gray-300 text-xs font-medium transition"
            title={`App chưa phản hồi trên cổng ${appPort} — có thể đang khởi động hoặc chưa chạy. Bấm để thử mở.`}
          >
            <ExternalLink size={12} /> App :{appPort} (thử mở)
          </a>
        ) : null}
        <button
          onClick={onHistoryOpen}
          className="p-1.5 hover:bg-white/[0.06] rounded-md transition text-gray-400 hover:text-gray-200"
          title="History"
        >
          <History size={14} />
        </button>

        {containerStatus === 'running' && (
          <button
            onClick={onRightPanelToggle}
            className={`p-1.5 rounded-md transition ${rightPanelOpen ? 'bg-primary/15 text-primary' : 'hover:bg-white/[0.06] text-gray-400 hover:text-gray-200'}`}
            title="Activity Panel"
          >
            {rightPanelOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
          </button>
        )}

        {containerStatus === 'idle' && (
          <button
            onClick={onStart}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary text-xs font-medium transition"
          >
            <Play size={11} /> New Session
          </button>
        )}
        {containerStatus === 'creating' && (
          <Loader2 size={16} className="text-yellow-400 animate-spin" />
        )}
        {containerStatus === 'running' && (
          <button
            onClick={onEnd}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-medium transition"
          >
            <Square size={10} /> End
          </button>
        )}
      </div>
    </div>
  )
}
