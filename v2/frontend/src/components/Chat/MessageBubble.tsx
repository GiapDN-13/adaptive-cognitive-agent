import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { User, Bot, AlertCircle } from 'lucide-react'
import type { Message } from '@/types/messages'

interface Props {
  message: Message
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-1 ${
        isUser ? 'bg-primary/20 text-primary' :
        isSystem ? 'bg-red-500/20 text-red-400' :
        'bg-white/10 text-white'
      }`}>
        {isUser ? <User size={14} /> : isSystem ? <AlertCircle size={14} /> : <Bot size={14} />}
      </div>

      <div className={`max-w-[85%] rounded-xl px-4 py-3 ${
        isUser ? 'bg-primary/10 border border-primary/20' :
        isSystem ? 'bg-red-500/10 border border-red-500/20' :
        'bg-surface border border-white/5'
      }`}>
        <div className="prose prose-invert prose-sm max-w-none
          prose-p:my-1.5 prose-li:my-0.5
          prose-table:text-xs prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1
          prose-table:border-collapse prose-th:border prose-th:border-white/10 prose-td:border prose-td:border-white/10
          prose-th:bg-white/5 prose-th:text-left
          prose-code:text-primary prose-code:bg-white/5 prose-code:px-1 prose-code:rounded prose-code:text-xs
          prose-pre:bg-black/40 prose-pre:border prose-pre:border-white/10 prose-pre:rounded-lg prose-pre:text-xs
          prose-headings:mt-3 prose-headings:mb-1
        ">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
        {message.metadata?.iterations != null && (
          <div className="mt-2 text-[10px] text-gray-500">
            {String(message.metadata.iterations)} iterations
          </div>
        )}
      </div>
    </div>
  )
}
