import { useEffect, useRef } from 'react'
import { useChatStore } from '@/store/chatStore'
import { MessageBubble } from './MessageBubble'
import { RetrievalBlock } from './RetrievalBlock'
import { ReasoningBlock } from './ReasoningBlock'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, WifiOff, RefreshCw, AlertTriangle } from 'lucide-react'

function ConnectionBanner() {
  const { connectionStatus, connectionDetail } = useChatStore()

  if (connectionStatus === 'connected') return null

  const config = {
    reconnecting: { bg: 'bg-yellow-900/80', icon: RefreshCw, text: 'Reconnecting...', iconClass: 'animate-spin' },
    disconnected: { bg: 'bg-red-900/80', icon: WifiOff, text: 'Disconnected', iconClass: '' },
    error: { bg: 'bg-red-900/80', icon: AlertTriangle, text: 'Connection error', iconClass: '' },
  }[connectionStatus]

  if (!config) return null
  const Icon = config.icon

  return (
    <div className={`sticky top-0 z-10 ${config.bg} border-b border-white/10 px-4 py-2 flex items-center gap-2 text-sm text-white/90`}>
      <Icon size={14} className={config.iconClass} />
      <span>{config.text}</span>
      {connectionDetail && <span className="text-xs text-white/60 ml-1">({connectionDetail})</span>}
    </div>
  )
}

export function ChatContainer() {
  const { messages, streamingContent, thinkingContent, isAgentWorking, agentStatus } = useChatStore()
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  // Chỉ auto-scroll khi user ĐANG Ở ĐÁY — nếu họ cuộn lên đọc lại thì KHÔNG
  // giật xuống mỗi chunk stream (đây là nguyên nhân chính gây "khó chịu" khi xem).
  const stickToBottom = useRef(true)

  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  useEffect(() => {
    if (stickToBottom.current) {
      // 'auto' khi đang stream (mượt liên tục, không animation chồng nhau);
      bottomRef.current?.scrollIntoView({ behavior: streamingContent ? 'auto' : 'smooth' })
    }
  }, [messages, streamingContent, thinkingContent])

  return (
    <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto px-4 py-4 space-y-3 scroll-smooth">
      <ConnectionBanner />
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-gray-500">
          <Bot size={40} className="mb-3 text-primary/40" />
          <p className="text-base font-medium text-gray-400">SmartAgent V2</p>
          <p className="text-xs mt-1 text-gray-600">Docker sandbox — any domain, real execution</p>
        </div>
      )}

      {messages.map((msg) => {
        if (msg.kind === 'retrieval' && msg.retrieval) {
          return <RetrievalBlock key={msg.id} data={msg.retrieval} />
        }
        if (msg.kind === 'reasoning') {
          return <ReasoningBlock key={msg.id} content={msg.content} />
        }
        return <MessageBubble key={msg.id} message={msg} />
      })}

      {/* Thinking bubble */}
      {thinkingContent && (
        <div className="flex gap-3 msg-in">
          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-1 bg-purple-500/10">
            <Bot size={14} className="text-purple-400" />
          </div>
          <div className="max-w-[85%] rounded-xl px-4 py-3 bg-purple-900/10 border border-purple-500/20">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase tracking-wider text-purple-400/70 font-medium">Thinking</span>
              <span className="flex gap-0.5">
                <span className="w-1 h-1 rounded-full bg-purple-400/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1 h-1 rounded-full bg-purple-400/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1 h-1 rounded-full bg-purple-400/60 animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
            </div>
            <p className="text-sm text-gray-400 italic leading-relaxed whitespace-pre-wrap">{thinkingContent}</p>
          </div>
        </div>
      )}

      {streamingContent && (
        <div className="flex gap-3">
          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-1 bg-white/10 text-white">
            <Bot size={14} />
          </div>
          <div className="max-w-[85%] rounded-xl px-4 py-3 bg-surface border border-white/5">
            <div className="prose prose-invert prose-sm max-w-none prose-p:my-1.5 prose-code:text-primary prose-code:bg-white/5 prose-code:px-1 prose-code:rounded prose-code:text-xs">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingContent}</ReactMarkdown>
              <span className="inline-block w-1.5 h-4 bg-primary rounded-sm stream-caret ml-0.5 -mb-0.5" />
            </div>
          </div>
        </div>
      )}

      {isAgentWorking && !streamingContent && (
        <div className="flex gap-3">
          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-1 bg-white/10">
            <Bot size={14} className="text-primary animate-pulse" />
          </div>
          <div className="px-4 py-3 text-gray-500 text-sm flex items-center gap-2">
            <span className="flex gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '300ms' }} />
            </span>
            {agentStatus && (
              <span className="ml-2 text-xs text-gray-600 font-mono truncate max-w-[300px]">
                {agentStatus}
              </span>
            )}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
