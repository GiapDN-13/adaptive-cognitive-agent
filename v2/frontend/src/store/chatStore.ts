import { create } from 'zustand'
import type { Message, ApprovalRequest, PlanProposal, AgentQuestion, TerminalEntry } from '@/types/messages'

interface ChatState {
  sessionId: string | null
  containerStatus: 'idle' | 'creating' | 'running' | 'stopped'
  messages: Message[]
  streamingContent: string
  terminalEntries: Map<string, string[]>
  pendingApproval: ApprovalRequest | null
  pendingPlan: PlanProposal | null
  pendingQuestion: AgentQuestion | null
  isAgentWorking: boolean

  setSessionId: (id: string | null) => void
  setContainerStatus: (status: ChatState['containerStatus']) => void
  addMessage: (msg: Message) => void
  appendStreamChunk: (chunk: string) => void
  finalizeStream: () => void
  appendTerminal: (execId: string, content: string) => void
  clearTerminal: (execId: string) => void
  setPendingApproval: (req: ApprovalRequest | null) => void
  setPendingPlan: (plan: PlanProposal | null) => void
  setPendingQuestion: (q: AgentQuestion | null) => void
  setAgentWorking: (working: boolean) => void
  reset: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: null,
  containerStatus: 'idle',
  messages: [],
  streamingContent: '',
  terminalEntries: new Map(),
  pendingApproval: null,
  pendingPlan: null,
  pendingQuestion: null,
  isAgentWorking: false,

  setSessionId: (id) => set({ sessionId: id }),
  setContainerStatus: (status) => set({ containerStatus: status }),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  appendStreamChunk: (chunk) => set((s) => ({
    streamingContent: s.streamingContent + chunk,
  })),

  finalizeStream: () => {
    const { streamingContent } = get()
    if (streamingContent) {
      const msg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: streamingContent,
        timestamp: Date.now(),
      }
      set((s) => ({
        messages: [...s.messages, msg],
        streamingContent: '',
      }))
    }
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
  setPendingQuestion: (q) => set({ pendingQuestion: q }),
  setAgentWorking: (working) => set({ isAgentWorking: working }),

  reset: () => set({
    sessionId: null,
    containerStatus: 'idle',
    messages: [],
    streamingContent: '',
    terminalEntries: new Map(),
    pendingApproval: null,
    pendingPlan: null,
    pendingQuestion: null,
    isAgentWorking: false,
  }),
}))
