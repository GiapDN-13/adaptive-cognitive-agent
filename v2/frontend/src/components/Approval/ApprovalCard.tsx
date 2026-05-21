import { Shield, Check, X } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'

interface Props {
  onApprove: (requestId: string) => void
  onReject: (requestId: string) => void
}

export function ApprovalCard({ onApprove, onReject }: Props) {
  const { pendingApproval } = useChatStore()
  if (!pendingApproval) return null

  const riskColors = {
    low: 'border-green-500/30 bg-green-500/5',
    medium: 'border-yellow-500/30 bg-yellow-500/5',
    high: 'border-red-500/30 bg-red-500/5',
  }

  return (
    <div className={`mx-4 my-2 rounded-xl border p-4 ${riskColors[pendingApproval.riskLevel]}`}>
      <div className="flex items-center gap-2 mb-3">
        <Shield size={18} className="text-yellow-400" />
        <span className="font-medium text-sm">Yêu cầu phê duyệt</span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${
          pendingApproval.riskLevel === 'high' ? 'bg-red-500/20 text-red-400' :
          pendingApproval.riskLevel === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
          'bg-green-500/20 text-green-400'
        }`}>
          {pendingApproval.riskLevel}
        </span>
      </div>

      <pre className="bg-black/30 rounded-lg px-3 py-2 text-sm font-mono text-gray-300 overflow-x-auto mb-3">
        $ {pendingApproval.command}
      </pre>

      {pendingApproval.estimatedTime && (
        <p className="text-xs text-gray-500 mb-3">
          Thời gian ước tính: {pendingApproval.estimatedTime}
        </p>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => onApprove(pendingApproval.requestId)}
          className="flex items-center gap-1 px-4 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary font-medium text-sm transition"
        >
          <Check size={16} /> Approve
        </button>
        <button
          onClick={() => onReject(pendingApproval.requestId)}
          className="flex items-center gap-1 px-4 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 font-medium text-sm transition"
        >
          <X size={16} /> Reject
        </button>
      </div>
    </div>
  )
}
