import { useState } from 'react'
import { Search, ChevronRight, ChevronDown, ExternalLink, AlertCircle } from 'lucide-react'
import type { RetrievalData } from '@/types/messages'

interface Props {
  data: RetrievalData
}

export function RetrievalBlock({ data }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-1 bg-blue-500/15 text-blue-400">
        <Search size={14} />
      </div>
      <div className="max-w-[85%] flex-1 rounded-xl border border-blue-500/20 bg-blue-500/5 overflow-hidden">
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center gap-2 px-3 py-2 hover:bg-blue-500/10 transition text-left"
        >
          {open ? <ChevronDown size={13} className="text-blue-400 shrink-0" /> : <ChevronRight size={13} className="text-blue-400 shrink-0" />}
          <span className="text-[10px] uppercase tracking-wider text-blue-400/70 font-medium shrink-0">Search</span>
          <span className="text-xs text-gray-300 font-mono truncate">"{data.query}"</span>
          <span className="text-[10px] text-gray-500 ml-auto shrink-0">
            {data.error ? 'lỗi' : `${data.count} kết quả`}
          </span>
        </button>

        {open && (
          <div className="px-3 pb-2.5 space-y-2">
            {data.error && (
              <div className="flex items-center gap-2 text-xs text-red-400">
                <AlertCircle size={12} /> {data.error}
              </div>
            )}
            {data.results.map((r, i) => (
              <div key={i} className="border-l-2 border-blue-500/20 pl-2.5 py-0.5">
                <div className="flex items-start gap-1.5">
                  <span className="text-[10px] text-gray-600 mt-0.5 shrink-0">{i + 1}.</span>
                  <div className="min-w-0">
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-300 hover:text-blue-200 hover:underline inline-flex items-center gap-1"
                    >
                      <span className="truncate">{r.title}</span>
                      <ExternalLink size={9} className="shrink-0 opacity-60" />
                    </a>
                    <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{r.snippet}</p>
                  </div>
                </div>
              </div>
            ))}
            {data.results.length === 0 && !data.error && (
              <p className="text-[11px] text-gray-500">Không có kết quả.</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
