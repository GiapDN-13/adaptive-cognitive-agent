import { useState, useEffect } from 'react'
import { Folder, FileText, ChevronRight, ArrowLeft, RefreshCw, Download } from 'lucide-react'
import { getFileTree, getFileDownloadUrl, type FileEntry } from '@/api/http'
import { useChatStore } from '@/store/chatStore'

export function FileBrowser() {
  const { sessionId, containerStatus } = useChatStore()
  const [currentPath, setCurrentPath] = useState('/workspace')
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)

  const fetchTree = async (path: string) => {
    if (!sessionId) return
    setLoading(true)
    const result = await getFileTree(sessionId, path)
    setEntries(result)
    setCurrentPath(path)
    setLoading(false)
  }

  useEffect(() => {
    if (sessionId && containerStatus === 'running') {
      fetchTree('/workspace')
    }
  }, [sessionId, containerStatus])

  if (!sessionId || containerStatus !== 'running') return null

  const handleClick = (entry: FileEntry) => {
    if (entry.type === 'directory') {
      fetchTree(entry.path)
    }
  }

  const handleBack = () => {
    const parent = currentPath.split('/').slice(0, -1).join('/') || '/'
    fetchTree(parent)
  }

  const formatSize = (size: number | null) => {
    if (size === null) return ''
    if (size < 1024) return `${size}B`
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`
    return `${(size / (1024 * 1024)).toFixed(1)}MB`
  }

  return (
    <div className="border-t border-white/10 max-h-64 overflow-y-auto bg-surface/30">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5 sticky top-0 bg-surface/80 backdrop-blur">
        <button
          onClick={handleBack}
          disabled={currentPath === '/'}
          className="p-1 hover:bg-white/10 rounded disabled:opacity-30"
        >
          <ArrowLeft size={14} />
        </button>
        <span className="text-xs font-mono text-gray-400 flex-1 truncate">{currentPath}</span>
        <button onClick={() => fetchTree(currentPath)} className="p-1 hover:bg-white/10 rounded">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {entries.length === 0 && !loading && (
        <p className="text-gray-500 text-xs p-3">Empty directory</p>
      )}

      <div className="divide-y divide-white/5">
        {entries.map((entry) => (
          <div
            key={entry.path}
            className="flex items-center gap-2 px-3 py-1.5 hover:bg-white/5 cursor-pointer group"
            onClick={() => handleClick(entry)}
          >
            {entry.type === 'directory' ? (
              <Folder size={14} className="text-yellow-400 shrink-0" />
            ) : (
              <FileText size={14} className="text-gray-400 shrink-0" />
            )}
            <span className="text-xs text-gray-300 flex-1 truncate">{entry.name}</span>
            {entry.type === 'file' && (
              <>
                <span className="text-[10px] text-gray-500">{formatSize(entry.size)}</span>
                <a
                  href={getFileDownloadUrl(sessionId, entry.path)}
                  onClick={(e) => e.stopPropagation()}
                  className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-white/10 rounded"
                >
                  <Download size={12} className="text-gray-400" />
                </a>
              </>
            )}
            {entry.type === 'directory' && (
              <ChevronRight size={12} className="text-gray-500" />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
