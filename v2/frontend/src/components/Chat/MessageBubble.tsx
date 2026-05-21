import ReactMarkdown from 'react-markdown'
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
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
        isUser ? 'bg-primary/20 text-primary' :
        isSystem ? 'bg-red-500/20 text-red-400' :
        'bg-white/10 text-white'
      }`}>
        {isUser ? <User size={16} /> : isSystem ? <AlertCircle size={16} /> : <Bot size={16} />}
      </div>

      <div className={`max-w-[80%] rounded-xl px-4 py-3 ${
        isUser ? 'bg-primary/10 border border-primary/20' :
        isSystem ? 'bg-red-500/10 border border-red-500/20' :
        'bg-surface border border-white/5'
      }`}>
        <div className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
        {message.metadata?.iterations != null && (
          <div className="mt-2 text-xs text-gray-500">
            {String(message.metadata.iterations)} iterations
          </div>
        )}
      </div>
    </div>
  )
}
