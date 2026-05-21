import { useChatStore } from '@/store/chatStore'
import { Terminal, Download } from 'lucide-react'

export function TerminalStream() {
  const { terminalEntries } = useChatStore()

  if (terminalEntries.size === 0) return null

  return (
    <div className="border-t border-white/10">
      {Array.from(terminalEntries.entries()).map(([execId, lines]) => (
        <div key={execId} className="border-b border-white/5">
          <div className="flex items-center gap-2 px-4 py-2 bg-surface/50">
            <Terminal size={14} className="text-primary" />
            <span className="text-xs text-gray-400 font-mono">exec:{execId}</span>
          </div>
          <pre className="px-4 py-3 text-sm font-mono text-gray-300 overflow-x-auto max-h-64 overflow-y-auto bg-black/30">
            {lines.join('')}
          </pre>
        </div>
      ))}
    </div>
  )
}
