import { useChatStore } from '@/store/chatStore'
import { Bot, Wrench, Search, FileText, Shield, Zap, Brain } from 'lucide-react'

const TOOL_ICONS: Record<string, { icon: typeof Bot; color: string }> = {
  thinking: { icon: Brain, color: 'text-purple-400' },
  shell_exec: { icon: Zap, color: 'text-yellow-400' },
  web_search: { icon: Search, color: 'text-blue-400' },
  write_file: { icon: FileText, color: 'text-green-400' },
  read_file: { icon: FileText, color: 'text-gray-400' },
  create_tool: { icon: Wrench, color: 'text-primary' },
  create_skill: { icon: Brain, color: 'text-orange-400' },
  create_hook: { icon: Shield, color: 'text-red-400' },
  pipeline: { icon: Zap, color: 'text-cyan-400' },
}

export function AgentStatusBar() {
  const { isAgentWorking, agentStatus } = useChatStore()

  if (!isAgentWorking || !agentStatus) return null

  // Parse tool name from status like "Using shell_exec: ls -la"
  const toolMatch = agentStatus.match(/^Using (\w+)/)
  const toolName = toolMatch ? toolMatch[1] : agentStatus.includes('Thinking') ? 'thinking' : ''
  const config = TOOL_ICONS[toolName] || { icon: Bot, color: 'text-gray-400' }
  const Icon = config.icon

  // Detect pipeline stage
  const pipelineMatch = agentStatus.match(/\[(\d+)\/(\d+)\]\s*(.+)/)

  return (
    <div className="flex items-center gap-2 px-4 py-1.5 border-t border-white/5 bg-surface/50">
      <Icon size={12} className={`${config.color} animate-pulse`} />

      {pipelineMatch ? (
        <div className="flex items-center gap-2 flex-1">
          <div className="flex gap-0.5">
            {Array.from({ length: parseInt(pipelineMatch[2]) }, (_, i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 rounded-full ${
                  i < parseInt(pipelineMatch[1]) ? 'bg-primary' :
                  i === parseInt(pipelineMatch[1]) - 1 ? 'bg-primary animate-pulse' :
                  'bg-white/10'
                }`}
              />
            ))}
          </div>
          <span className="text-[11px] text-gray-400 truncate">
            {pipelineMatch[3]}
          </span>
        </div>
      ) : (
        <span className="text-[11px] text-gray-400 font-mono truncate flex-1">
          {agentStatus}
        </span>
      )}
    </div>
  )
}
