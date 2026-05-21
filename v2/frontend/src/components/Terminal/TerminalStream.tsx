import { useRef, useEffect, useState } from 'react'
import { useChatStore } from '@/store/chatStore'
import { Terminal, X, ChevronDown, ChevronUp } from 'lucide-react'

export function TerminalStream() {
  const { terminalEntries, clearTerminal } = useChatStore()
  const scrollRefs = useRef<Map<string, HTMLPreElement>>(new Map())
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  useEffect(() => {
    scrollRefs.current.forEach((el, id) => {
      if (el && !collapsed.has(id)) el.scrollTop = el.scrollHeight
    })
  })

  if (terminalEntries.size === 0) return null

  const entries = Array.from(terminalEntries.entries())
  const visible = entries.slice(-3)

  const toggleCollapse = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const clearAll = () => {
    entries.forEach(([id]) => clearTerminal(id))
  }

  return (
    <div className="border-t border-white/10 bg-black/20">
      {entries.length > 3 && (
        <div className="px-3 py-1 text-[10px] text-gray-500 border-b border-white/5">
          {entries.length - 3} older terminals hidden
        </div>
      )}

      {visible.map(([execId, lines]) => {
        const isCollapsed = collapsed.has(execId)
        const lineCount = lines.join('').split('\n').length
        const hasError = lines.some((l) => l.toLowerCase().includes('error') || l.toLowerCase().includes('traceback'))

        return (
          <div key={execId} className="border-b border-white/5 last:border-b-0">
            <div
              className={`flex items-center gap-2 px-3 py-1 cursor-pointer hover:bg-white/5 ${hasError ? 'bg-red-500/5' : 'bg-surface/30'}`}
              onClick={() => toggleCollapse(execId)}
            >
              <Terminal size={11} className={hasError ? 'text-red-400' : 'text-primary'} />
              <span className="text-[10px] text-gray-500 font-mono flex-1">
                {execId} <span className="text-gray-600">({lineCount} lines)</span>
              </span>
              {isCollapsed ? <ChevronDown size={10} className="text-gray-500" /> : <ChevronUp size={10} className="text-gray-500" />}
              <button
                onClick={(e) => { e.stopPropagation(); clearTerminal(execId) }}
                className="p-0.5 hover:bg-white/10 rounded opacity-40 hover:opacity-100"
              >
                <X size={10} />
              </button>
            </div>
            {!isCollapsed && (
              <pre
                ref={(el) => { if (el) scrollRefs.current.set(execId, el) }}
                className="px-3 py-2 text-[11px] font-mono text-gray-300 overflow-x-auto max-h-36 overflow-y-auto leading-tight"
              >
                {lines.join('')}
              </pre>
            )}
          </div>
        )
      })}

      {entries.length > 1 && (
        <div className="px-3 py-1 border-t border-white/5 flex justify-end">
          <button onClick={clearAll} className="text-[10px] text-gray-500 hover:text-gray-300">
            Clear all
          </button>
        </div>
      )}
    </div>
  )
}
