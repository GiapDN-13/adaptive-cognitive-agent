import { useState, useRef, useEffect, type KeyboardEvent, type ClipboardEvent } from 'react'
import { Send, Paperclip, Square, X } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'

interface Props {
  onSend: (content: string, images?: { format: string; data: string; previewUrl: string }[]) => void
  onCancel: () => void
  onFileSelect: (files: File[]) => void
}

// Đọc File ảnh → base64 (bỏ tiền tố data:) + format cho Bedrock image block.
async function fileToImagePayload(f: File): Promise<{ format: string; data: string }> {
  const buf = await f.arrayBuffer()
  let bin = ''
  const bytes = new Uint8Array(buf)
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i])
  const data = btoa(bin)
  const format = (f.type.split('/')[1] || 'png').toLowerCase().replace('jpg', 'jpeg')
  return { format, data }
}

interface Attachment {
  id: string
  file: File
  previewUrl: string
}

export function InputBar({ onSend, onCancel, onFileSelect }: Props) {
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const fileRef = useRef<HTMLInputElement>(null)
  const { isAgentWorking } = useChatStore()

  // revoke object URLs on unmount to avoid leaks
  useEffect(() => {
    return () => { attachments.forEach(a => URL.revokeObjectURL(a.previewUrl)) }
  }, [attachments])

  const addImages = (files: File[]) => {
    const imgs = files.filter(f => f.type.startsWith('image/'))
    if (!imgs.length) return
    setAttachments(prev => [
      ...prev,
      ...imgs.map(f => ({ id: crypto.randomUUID(), file: f, previewUrl: URL.createObjectURL(f) })),
    ])
  }

  const removeAttachment = (id: string) => {
    setAttachments(prev => {
      const gone = prev.find(a => a.id === id)
      if (gone) URL.revokeObjectURL(gone.previewUrl)
      return prev.filter(a => a.id !== id)
    })
  }

  const handleSubmit = async () => {
    const trimmed = input.trim()
    // Cho phép gửi nếu có text HOẶC có ảnh đính kèm
    if (!trimmed && attachments.length === 0) return
    // Gửi ảnh + text TRONG CÙNG 1 message để LLM xem được ảnh (không upload rời).
    let imgPayloads: { format: string; data: string; previewUrl: string }[] | undefined
    if (attachments.length) {
      const encoded = await Promise.all(attachments.map(async a => ({
        ...(await fileToImagePayload(a.file)),
        previewUrl: a.previewUrl,  // giữ để render trong chat (App tự revoke sau)
      })))
      imgPayloads = encoded
      setAttachments([])  // KHÔNG revoke ở đây — previewUrl còn dùng để hiển thị
    }
    onSend(trimmed, imgPayloads)
    setInput('')
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  // Paste ảnh từ clipboard (Ctrl+V) — bắt mọi image item.
  const handlePaste = (e: ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return
    const imgFiles: File[] = []
    for (const it of items) {
      if (it.kind === 'file' && it.type.startsWith('image/')) {
        const f = it.getAsFile()
        if (f) imgFiles.push(f)
      }
    }
    if (imgFiles.length) {
      e.preventDefault()  // chặn dán đường dẫn rác vào ô text
      addImages(imgFiles)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    // ảnh → preview; file khác → gửi thẳng như cũ
    const imgs = files.filter(f => f.type.startsWith('image/'))
    const others = files.filter(f => !f.type.startsWith('image/'))
    if (imgs.length) addImages(imgs)
    if (others.length) onFileSelect(others)
    e.target.value = ''
  }

  return (
    <div className="border-t border-white/10">
      {/* Hàng preview ảnh đính kèm */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 px-4 pt-3">
          {attachments.map(a => (
            <div key={a.id} className="relative group">
              <img
                src={a.previewUrl}
                alt="attachment"
                className="w-16 h-16 object-cover rounded-lg border border-white/15"
              />
              <button
                onClick={() => removeAttachment(a.id)}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-black/80 border border-white/20 flex items-center justify-center text-gray-300 hover:text-white hover:bg-red-500/70 transition opacity-0 group-hover:opacity-100"
                title="Bỏ ảnh"
              >
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 p-4">
        <button
          onClick={() => fileRef.current?.click()}
          className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition"
          title="Đính kèm file / ảnh"
        >
          <Paperclip size={20} />
        </button>
        <input ref={fileRef} type="file" className="hidden" onChange={handleFileChange} multiple accept="*/*" />

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="Nhập lệnh, câu hỏi… (dán ảnh bằng Ctrl+V)"
          className="flex-1 bg-surface border border-white/10 rounded-lg px-4 py-3 text-white resize-none outline-none focus:border-primary transition max-h-32"
          rows={1}
          disabled={isAgentWorking}
        />

        {isAgentWorking ? (
          <button
            onClick={onCancel}
            className="p-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 transition"
            title="Dừng"
          >
            <Square size={20} />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!input.trim() && attachments.length === 0}
            className="p-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary disabled:opacity-30 transition"
            title="Gửi"
          >
            <Send size={20} />
          </button>
        )}
      </div>
    </div>
  )
}
