import { Check, X, ListChecks, Loader2, CircleDot, Circle, XCircle } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import type { PlanStep } from '@/types/messages'

interface Props {
  onApprove: (planId: string) => void
  onReject: (planId: string) => void
}

function StepIcon({ status }: { status: PlanStep['status'] }) {
  switch (status) {
    case 'running':
      return <Loader2 size={14} className="text-yellow-400 animate-spin" />
    case 'done':
      return <Check size={14} className="text-green-400" />
    case 'failed':
      return <XCircle size={14} className="text-red-400" />
    default:
      return <Circle size={14} className="text-gray-500" />
  }
}

function PlanSteps({ steps, showStatus }: { steps: PlanStep[]; showStatus: boolean }) {
  return (
    <ol className="space-y-2 mb-4">
      {steps.map((step, i) => (
        <li key={step.id} className="flex gap-3 text-sm items-start">
          {showStatus ? (
            <span className="mt-0.5 shrink-0"><StepIcon status={step.status} /></span>
          ) : (
            <span className="text-primary font-mono w-6 shrink-0">{i + 1}.</span>
          )}
          <div className="flex-1">
            <p className={`${
              step.status === 'done' ? 'text-gray-400 line-through' :
              step.status === 'running' ? 'text-white font-medium' :
              step.status === 'failed' ? 'text-red-300' :
              'text-gray-300'
            }`}>
              {step.description}
            </p>
            {step.command && (
              <code className="text-xs text-gray-500 font-mono mt-0.5 block">
                $ {step.command}
              </code>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

export function PlanViewer({ onApprove, onReject }: Props) {
  const { pendingPlan, activePlan } = useChatStore()

  if (activePlan) {
    const done = activePlan.steps.filter((s) => s.status === 'done').length
    const failed = activePlan.steps.filter((s) => s.status === 'failed').length
    const total = activePlan.steps.length
    const isComplete = done + failed === total

    return (
      <div className="mx-4 my-2 rounded-xl border border-primary/30 bg-primary/5 p-4">
        <div className="flex items-center gap-2 mb-3">
          <ListChecks size={18} className="text-primary" />
          <span className="font-medium">{activePlan.title}</span>
          <span className="ml-auto text-xs text-gray-400">
            {done}/{total} {isComplete ? (failed > 0 ? '(with errors)' : 'complete') : 'running...'}
          </span>
        </div>
        <PlanSteps steps={activePlan.steps} showStatus={true} />
      </div>
    )
  }

  if (!pendingPlan) return null

  return (
    <div className="mx-4 my-2 rounded-xl border border-primary/30 bg-primary/5 p-4">
      <div className="flex items-center gap-2 mb-3">
        <ListChecks size={18} className="text-primary" />
        <span className="font-medium">{pendingPlan.title}</span>
      </div>

      <PlanSteps steps={pendingPlan.steps} showStatus={false} />

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
