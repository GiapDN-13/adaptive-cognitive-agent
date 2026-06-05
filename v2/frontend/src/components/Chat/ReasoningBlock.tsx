import { useState } from 'react'
import { Brain, ChevronRight, ChevronDown } from 'lucide-react'

interface Props {
  content: string
}

export function ReasoningBlock({ content }: Props) {
  const [open, setOpen] = useState(false)

  // First line as preview
  const preview = content.trim().split('\n').filter(Boolean)[0]?.slice(0, 70) || 'reasoning'

  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-1 bg-purple-500/15 text-purple-400">
        <Brain size={14} />
      </div>
      <div className="max-w-[85%] flex-1 rounded-xl border border-purple-500/20 bg-purple-900/10 overflow-hidden">
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center gap-2 px-3 py-2 hover:bg-purple-500/10 transition text-left"
        >
          {open ? <ChevronDown size={13} className="text-purple-400 shrink-0" /> : <ChevronRight size={13} className="text-purple-400 shrink-0" />}
          <span className="text-[10px] uppercase tracking-wider text-purple-400/70 font-medium shrink-0">Reasoning</span>
          {!open && <span className="text-xs text-gray-400 italic truncate">{preview}…</span>}
        </button>
        {open && (
          <div className="px-3 pb-2.5">
            <p className="text-[12px] text-gray-400 italic leading-relaxed whitespace-pre-wrap">{content}</p>
          </div>
        )}
      </div>
    </div>
  )
}
