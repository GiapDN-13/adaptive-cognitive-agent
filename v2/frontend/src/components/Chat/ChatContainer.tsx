import { useEffect, useRef } from 'react'
import { useChatStore } from '@/store/chatStore'
import { MessageBubble } from './MessageBubble'
import { Bot } from 'lucide-react'

export function ChatContainer() {
  const { messages, streamingContent, isAgentWorking } = useChatStore()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-gray-500">
          <Bot size={48} className="mb-4 text-primary/50" />
          <p className="text-lg">SmartAgent V2</p>
          <p className="text-sm mt-1">Docker sandbox execution — bất kỳ domain nào</p>
        </div>
      )}

      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}

      {streamingContent && (
        <div className="flex gap-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-white/10 text-white">
            <Bot size={16} />
          </div>
          <div className="max-w-[80%] rounded-xl px-4 py-3 bg-surface border border-white/5">
            <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap">
              {streamingContent}
              <span className="animate-pulse">▊</span>
            </div>
          </div>
        </div>
      )}

      {isAgentWorking && !streamingContent && (
        <div className="flex gap-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-white/10">
            <Bot size={16} className="text-primary animate-pulse" />
          </div>
          <div className="px-4 py-3 text-gray-500 text-sm">
            Đang xử lý...
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
