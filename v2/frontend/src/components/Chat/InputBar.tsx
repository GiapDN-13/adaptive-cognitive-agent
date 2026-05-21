import { useState, useRef, type KeyboardEvent } from 'react'
import { Send, Paperclip, Square } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'

interface Props {
  onSend: (content: string) => void
  onCancel: () => void
  onFileSelect: (files: File[]) => void
}

export function InputBar({ onSend, onCancel, onFileSelect }: Props) {
  const [input, setInput] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const { isAgentWorking } = useChatStore()

  const handleSubmit = () => {
    const trimmed = input.trim()
    if (!trimmed) return
    onSend(trimmed)
    setInput('')
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length) onFileSelect(files)
    e.target.value = ''
  }

  return (
    <div className="flex items-center gap-2 p-4 border-t border-white/10">
      <button
        onClick={() => fileRef.current?.click()}
        className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition"
        title="Upload file"
      >
        <Paperclip size={20} />
      </button>
      <input ref={fileRef} type="file" className="hidden" onChange={handleFileChange} multiple />

      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Nhập lệnh hoặc câu hỏi..."
        className="flex-1 bg-surface border border-white/10 rounded-lg px-4 py-3 text-white resize-none outline-none focus:border-primary transition max-h-32"
        rows={1}
        disabled={isAgentWorking}
      />

      {isAgentWorking ? (
        <button
          onClick={onCancel}
          className="p-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 transition"
          title="Cancel"
        >
          <Square size={20} />
        </button>
      ) : (
        <button
          onClick={handleSubmit}
          disabled={!input.trim()}
          className="p-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary disabled:opacity-30 transition"
          title="Send"
        >
          <Send size={20} />
        </button>
      )}
    </div>
  )
}
