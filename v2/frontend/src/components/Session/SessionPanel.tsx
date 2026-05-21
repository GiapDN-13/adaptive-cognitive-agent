import { Play, Square, Loader2 } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'

interface Props {
  onStart: () => void
  onEnd: () => void
}

export function SessionPanel({ onStart, onEnd }: Props) {
  const { containerStatus, sessionId } = useChatStore()

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-white/10 bg-surface/50">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${
          containerStatus === 'running' ? 'bg-green-400' :
          containerStatus === 'creating' ? 'bg-yellow-400 animate-pulse' :
          'bg-gray-500'
        }`} />
        <span className="text-xs text-gray-400 font-mono">
          {containerStatus === 'running' ? `session:${sessionId?.slice(0, 8)}` :
           containerStatus === 'creating' ? 'Starting...' :
           'No session'}
        </span>
      </div>

      <div className="ml-auto">
        {containerStatus === 'idle' && (
          <button
            onClick={onStart}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary text-xs font-medium transition"
          >
            <Play size={12} /> New Session
          </button>
        )}
        {containerStatus === 'creating' && (
          <Loader2 size={16} className="text-yellow-400 animate-spin" />
        )}
        {containerStatus === 'running' && (
          <button
            onClick={onEnd}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 text-xs font-medium transition"
          >
            <Square size={12} /> End
          </button>
        )}
      </div>
    </div>
  )
}
