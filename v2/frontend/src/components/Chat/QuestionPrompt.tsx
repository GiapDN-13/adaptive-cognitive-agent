import { useState, useRef, useEffect } from 'react'
import { HelpCircle, CornerDownLeft, Pencil } from 'lucide-react'

interface Props {
  question: string
  options?: string[]
  onAnswer: (answer: string) => void
}

export function QuestionPrompt({ question, options, onAnswer }: Props) {
  const [custom, setCustom] = useState('')
  const [editing, setEditing] = useState(!options || options.length === 0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  // Keyboard: number keys 1-9 pick an option quickly (Claude CLI style)
  useEffect(() => {
    if (editing || !options) return
    const onKey = (e: KeyboardEvent) => {
      const n = parseInt(e.key)
      if (n >= 1 && n <= options.length) {
        onAnswer(options[n - 1])
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [options, editing, onAnswer])

  const submitCustom = () => {
    const v = custom.trim()
    if (v) onAnswer(v)
  }

  return (
    <div className="mx-4 my-2 rounded-xl border border-blue-500/30 bg-blue-500/5 p-4">
      <div className="flex items-start gap-2 mb-3">
        <HelpCircle size={16} className="text-blue-400 shrink-0 mt-0.5" />
        <p className="text-sm text-gray-200 whitespace-pre-wrap">{question}</p>
      </div>

      {options && options.length > 0 && !editing && (
        <div className="space-y-1.5">
          {options.map((opt, i) => (
            <button
              key={opt}
              onClick={() => onAnswer(opt)}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-black/20 hover:bg-blue-500/15 border border-white/5 hover:border-blue-500/40 text-left transition group"
            >
              <span className="w-5 h-5 rounded flex items-center justify-center text-[11px] font-mono bg-white/5 text-gray-400 group-hover:bg-blue-500/20 group-hover:text-blue-300 shrink-0">
                {i + 1}
              </span>
              <span className="text-sm text-gray-200 flex-1">{opt}</span>
              {i === 0 && (
                <span className="text-[10px] text-blue-400/70 shrink-0">khuyến nghị</span>
              )}
            </button>
          ))}

          <button
            onClick={() => setEditing(true)}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-white/5 text-left transition text-gray-500 hover:text-gray-300"
          >
            <span className="w-5 h-5 rounded flex items-center justify-center shrink-0">
              <Pencil size={12} />
            </span>
            <span className="text-sm">Trả lời khác (tự nhập)…</span>
          </button>

          <p className="text-[10px] text-gray-600 mt-1.5 pl-1">
            Bấm số <span className="font-mono text-gray-500">1–{options.length}</span> để chọn nhanh
          </p>
        </div>
      )}

      {editing && (
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            className="flex-1 bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500/50"
            placeholder="Nhập câu trả lời…"
            onKeyDown={(e) => {
              if (e.key === 'Enter') submitCustom()
              if (e.key === 'Escape' && options && options.length > 0) setEditing(false)
            }}
          />
          <button
            onClick={submitCustom}
            disabled={!custom.trim()}
            className="px-3 py-2 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 disabled:opacity-40 text-blue-400 transition"
          >
            <CornerDownLeft size={14} />
          </button>
          {options && options.length > 0 && (
            <button
              onClick={() => setEditing(false)}
              className="text-xs text-gray-500 hover:text-gray-300 px-2"
            >
              Quay lại
            </button>
          )}
        </div>
      )}
    </div>
  )
}
