import { create } from 'zustand'
import type { Message, ApprovalRequest, PlanProposal, PlanStep, AgentQuestion, TerminalEntry } from '@/types/messages'

interface ChatState {
  sessionId: string | null
  containerStatus: 'idle' | 'creating' | 'running' | 'stopped'
  messages: Message[]
  streamingContent: string
  thinkingContent: string
  thinkingHistory: string[]
  terminalEntries: Map<string, string[]>
  pendingApproval: ApprovalRequest | null
  pendingPlan: PlanProposal | null
  activePlan: PlanProposal | null
  pendingQuestion: AgentQuestion | null
  isAgentWorking: boolean
  agentStatus: string | null
  connectionStatus: 'connected' | 'reconnecting' | 'disconnected' | 'error'
  connectionDetail: string | null

  setSessionId: (id: string | null) => void
  setContainerStatus: (status: ChatState['containerStatus']) => void
  addMessage: (msg: Message) => void
  appendStreamChunk: (chunk: string) => void
  finalizeStream: () => void
  setThinking: (content: string) => void
  finalizeThinking: () => void
  appendTerminal: (execId: string, content: string) => void
  clearTerminal: (execId: string) => void
  setPendingApproval: (req: ApprovalRequest | null) => void
  setPendingPlan: (plan: PlanProposal | null) => void
  setActivePlan: (plan: PlanProposal | null) => void
  updateStepStatus: (planId: string, stepId: string, status: PlanStep['status']) => void
  setPendingQuestion: (q: AgentQuestion | null) => void
  setAgentWorking: (working: boolean) => void
  setAgentStatus: (status: string | null) => void
  setConnectionStatus: (status: ChatState['connectionStatus'], detail?: string | null) => void
  reset: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: null,
  containerStatus: 'idle',
  messages: [],
  streamingContent: '',
  thinkingContent: '',
  thinkingHistory: [],
  terminalEntries: new Map(),
  pendingApproval: null,
  pendingPlan: null,
  activePlan: null,
  pendingQuestion: null,
  isAgentWorking: false,
  agentStatus: null,
  connectionStatus: 'connected',
  connectionDetail: null,

  setSessionId: (id) => set({ sessionId: id }),
  setContainerStatus: (status) => set({ containerStatus: status }),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  appendStreamChunk: (chunk) => set((s) => ({
    streamingContent: s.streamingContent + chunk,
  })),

  finalizeStream: () => {
    const { streamingContent } = get()
    if (!streamingContent) return
    const msg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: streamingContent,
      timestamp: Date.now(),
    }
    set({ messages: [...get().messages, msg], streamingContent: '' })
  },

  setThinking: (content) => set({ thinkingContent: content }),

  finalizeThinking: () => {
    const { thinkingContent } = get()
    if (!thinkingContent) return
    set((s) => ({
      thinkingHistory: [...s.thinkingHistory, thinkingContent],
      thinkingContent: '',
    }))
  },

  appendTerminal: (execId, content) => set((s) => {
    const entries = new Map(s.terminalEntries)
    const existing = entries.get(execId) || []
    entries.set(execId, [...existing, content])
    return { terminalEntries: entries }
  }),

  clearTerminal: (execId) => set((s) => {
    const entries = new Map(s.terminalEntries)
    entries.delete(execId)
    return { terminalEntries: entries }
  }),

  setPendingApproval: (req) => set({ pendingApproval: req }),
  setPendingPlan: (plan) => set({ pendingPlan: plan }),
  setActivePlan: (plan) => set({ activePlan: plan }),
  updateStepStatus: (planId, stepId, status) => set((s) => {
    if (!s.activePlan || s.activePlan.planId !== planId) return s
    const steps = s.activePlan.steps.map((step) =>
      step.id === stepId ? { ...step, status } : step
    )
    return { activePlan: { ...s.activePlan, steps } }
  }),
  setPendingQuestion: (q) => set({ pendingQuestion: q }),
  setAgentWorking: (working) => set({ isAgentWorking: working, ...(working ? {} : { agentStatus: null }) }),
  setAgentStatus: (status) => set({ agentStatus: status }),
  setConnectionStatus: (status, detail = null) => set({ connectionStatus: status, connectionDetail: detail }),

  reset: () => set({
    sessionId: null,
    containerStatus: 'idle',
    messages: [],
    streamingContent: '',
    thinkingContent: '',
    thinkingHistory: [],
    terminalEntries: new Map(),
    pendingApproval: null,
    pendingPlan: null,
    activePlan: null,
    pendingQuestion: null,
    isAgentWorking: false,
    agentStatus: null,
    connectionStatus: 'connected',
    connectionDetail: null,
  }),
}))
