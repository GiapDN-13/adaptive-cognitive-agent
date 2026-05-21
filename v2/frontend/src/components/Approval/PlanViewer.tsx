import { Check, X, ListChecks } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'

interface Props {
  onApprove: (planId: string) => void
  onReject: (planId: string) => void
}

export function PlanViewer({ onApprove, onReject }: Props) {
  const { pendingPlan } = useChatStore()
  if (!pendingPlan) return null

  return (
    <div className="mx-4 my-2 rounded-xl border border-primary/30 bg-primary/5 p-4">
      <div className="flex items-center gap-2 mb-3">
        <ListChecks size={18} className="text-primary" />
        <span className="font-medium">{pendingPlan.title}</span>
      </div>

      <ol className="space-y-2 mb-4">
        {pendingPlan.steps.map((step, i) => (
          <li key={step.id} className="flex gap-3 text-sm">
            <span className="text-primary font-mono w-6 shrink-0">{i + 1}.</span>
            <div>
              <p className="text-gray-300">{step.description}</p>
              {step.command && (
                <code className="text-xs text-gray-500 font-mono mt-0.5 block">
                  $ {step.command}
                </code>
              )}
            </div>
          </li>
        ))}
      </ol>

      <div className="flex gap-2">
        <button
          onClick={() => onApprove(pendingPlan.planId)}
          className="flex items-center gap-1 px-4 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary font-medium text-sm transition"
        >
          <Check size={16} /> Approve Plan
        </button>
        <button
          onClick={() => onReject(pendingPlan.planId)}
          className="flex items-center gap-1 px-4 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 font-medium text-sm transition"
        >
          <X size={16} /> Reject
        </button>
      </div>
    </div>
  )
}
