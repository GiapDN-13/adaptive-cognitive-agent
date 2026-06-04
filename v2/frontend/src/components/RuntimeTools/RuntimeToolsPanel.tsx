import { useState, useEffect } from 'react'
import { Wrench, Puzzle, Shield, Trash2, RefreshCw, Zap, Eye, Settings } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'

interface ToolInfo {
  name: string
  builtin: boolean
  category: string
  dependencies: string[]
}

interface SkillInfo {
  id: string
  name: string
  description: string
  runtime: boolean
}

const CATEGORY_CONFIG: Record<string, { icon: typeof Wrench; color: string; label: string }> = {
  action: { icon: Zap, color: 'text-blue-400', label: 'Action' },
  intelligence: { icon: Eye, color: 'text-green-400', label: 'Intel' },
  meta: { icon: Settings, color: 'text-purple-400', label: 'Meta' },
}

export function RuntimeToolsPanel() {
  const { sessionId, containerStatus } = useChatStore()
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<'tools' | 'skills'>('tools')

  const fetchData = async () => {
    setLoading(true)
    try {
      const [toolsRes, skillsRes] = await Promise.all([
        fetch('/api/extensions/tools').then(r => r.json()),
        fetch('/api/extensions/skills').then(r => r.json()),
      ])
      setTools(toolsRes.tools || [])
      setSkills(skillsRes.skills || [])
    } catch {
      // silent fail
    }
    setLoading(false)
  }

  useEffect(() => {
    if (sessionId && containerStatus === 'running') {
      fetchData()
    }
  }, [sessionId, containerStatus])

  const handleDeleteTool = async (name: string) => {
    if (!confirm(`Xóa tool "${name}"?`)) return
    await fetch(`/api/extensions/tools/${name}`, { method: 'DELETE' })
    fetchData()
  }

  const handleDeleteSkill = async (id: string) => {
    if (!confirm(`Xóa skill "${id}"?`)) return
    await fetch(`/api/extensions/skills/${id}`, { method: 'DELETE' })
    fetchData()
  }

  const runtimeTools = tools.filter(t => !t.builtin)
  const builtinTools = tools.filter(t => t.builtin)
  const runtimeSkills = skills.filter(s => s.runtime)

  return (
    <div className="border-t border-white/10 max-h-72 overflow-y-auto bg-surface/30">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5 sticky top-0 bg-surface/80 backdrop-blur z-10">
        <Wrench size={14} className="text-primary" />
        <span className="text-xs font-medium text-gray-300">Extensions</span>

        <div className="flex items-center gap-1 ml-2">
          <button
            onClick={() => setTab('tools')}
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition ${
              tab === 'tools' ? 'bg-primary/20 text-primary' : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            Tools ({tools.length})
          </button>
          <button
            onClick={() => setTab('skills')}
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition ${
              tab === 'skills' ? 'bg-primary/20 text-primary' : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            Skills ({runtimeSkills.length})
          </button>
        </div>

        <button onClick={fetchData} className="ml-auto p-1 hover:bg-white/10 rounded">
          <RefreshCw size={12} className={loading ? 'animate-spin text-gray-400' : 'text-gray-500'} />
        </button>
      </div>

      {/* Tools Tab */}
      {tab === 'tools' && (
        <div>
          {/* Runtime tools section */}
          {runtimeTools.length > 0 && (
            <div>
              <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider text-primary/70 font-medium bg-primary/5">
                Runtime-Created ({runtimeTools.length})
              </div>
              <div className="divide-y divide-white/5">
                {runtimeTools.map(tool => (
                  <ToolRow key={tool.name} tool={tool} onDelete={handleDeleteTool} />
                ))}
              </div>
            </div>
          )}

          {/* Builtin tools section */}
          <div>
            <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider text-gray-500 font-medium">
              Built-in ({builtinTools.length})
            </div>
            <div className="divide-y divide-white/5">
              {builtinTools.map(tool => (
                <ToolRow key={tool.name} tool={tool} />
              ))}
            </div>
          </div>

          {tools.length === 0 && !loading && (
            <p className="text-gray-500 text-xs p-3 text-center">No tools loaded</p>
          )}
        </div>
      )}

      {/* Skills Tab */}
      {tab === 'skills' && (
        <div>
          {runtimeSkills.length === 0 && !loading && (
            <p className="text-gray-500 text-xs p-3 text-center">
              No runtime skills yet. Agent sẽ tự tạo khi cần.
            </p>
          )}
          <div className="divide-y divide-white/5">
            {runtimeSkills.map(skill => (
              <div key={skill.id} className="flex items-center gap-2 px-3 py-1.5 hover:bg-white/5 group">
                <Puzzle size={14} className="text-orange-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-xs text-gray-300 block truncate">{skill.name}</span>
                  <span className="text-[10px] text-gray-500 block truncate">{skill.description}</span>
                </div>
                <button
                  onClick={() => handleDeleteSkill(skill.id)}
                  className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-500/20 rounded transition"
                >
                  <Trash2 size={12} className="text-red-400" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ToolRow({ tool, onDelete }: { tool: ToolInfo; onDelete?: (name: string) => void }) {
  const config = CATEGORY_CONFIG[tool.category] || CATEGORY_CONFIG.action
  const Icon = config.icon

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-white/5 group">
      <Icon size={14} className={`${config.color} shrink-0`} />
      <span className="text-xs text-gray-300 flex-1 truncate font-mono">{tool.name}</span>
      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
        tool.builtin ? 'bg-white/5 text-gray-500' : 'bg-primary/10 text-primary'
      }`}>
        {config.label}
      </span>
      {!tool.builtin && onDelete && (
        <button
          onClick={() => onDelete(tool.name)}
          className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-500/20 rounded transition"
        >
          <Trash2 size={12} className="text-red-400" />
        </button>
      )}
    </div>
  )
}
