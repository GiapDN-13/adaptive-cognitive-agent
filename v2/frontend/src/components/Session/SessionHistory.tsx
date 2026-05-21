import { useState, useEffect } from 'react'
import { History, MessageSquare, Trash2, X } from 'lucide-react'
import { getSessionHistory, getHistoryMessages, type SessionHistoryItem } from '@/api/http'
import { useChatStore } from '@/store/chatStore'

interface Props {
  open: boolean
  onClose: () => void
}

export function SessionHistory({ open, onClose }: Props) {
  const [sessions, setSessions] = useState<SessionHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const { addMessage } = useChatStore()

  useEffect(() => {
    if (!open) return
    setLoading(true)
    getSessionHistory().then((s) => {
      setSessions(s)
      setLoading(false)
    })
  }, [open])

  const handleLoad = async (session: SessionHistoryItem) => {
    const messages = await getHistoryMessages(session.id)
    for (const msg of messages) {
      if (typeof msg.content === 'string') {
        addMessage({
          id: crypto.randomUUID(),
          role: msg.role === 'user' ? 'user' : 'assistant',
          content: msg.content,
          timestamp: Date.now(),
        })
      }
    }
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="w-80 bg-surface border-r border-white/10 h-full flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            <History size={16} className="text-primary" />
            <span className="font-medium text-sm">Session History</span>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-white/10 rounded">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading && (
            <p className="text-gray-500 text-sm p-4">Loading...</p>
          )}

          {!loading && sessions.length === 0 && (
            <p className="text-gray-500 text-sm p-4">No past sessions.</p>
          )}

          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => handleLoad(s)}
              className="w-full text-left px-4 py-3 hover:bg-white/5 border-b border-white/5 transition"
            >
              <div className="flex items-center gap-2">
                <MessageSquare size={14} className="text-gray-400 shrink-0" />
                <span className="text-sm text-gray-200 truncate">{s.title}</span>
              </div>
              <span className="text-xs text-gray-500 mt-1 block">
                {new Date(s.updated_at).toLocaleDateString()} {new Date(s.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 bg-black/50" onClick={onClose} />
    </div>
  )
}
