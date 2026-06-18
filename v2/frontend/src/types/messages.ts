export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  metadata?: Record<string, unknown>
  // Transparency blocks rendered inline in chat
  kind?: 'normal' | 'reasoning' | 'retrieval' | 'critique' | 'replay'
  retrieval?: RetrievalData
}

export interface RetrievalResult {
  title: string
  url: string
  snippet: string
}

export interface RetrievalData {
  query: string
  results: RetrievalResult[]
  count: number
  error?: string
}

export interface TerminalEntry {
  execId: string
  content: string
  stream: 'stdout' | 'stderr'
  done: boolean
}

export interface ApprovalRequest {
  requestId: string
  action: string
  command: string
  estimatedTime?: string
  riskLevel: 'low' | 'medium' | 'high'
}

export interface PlanProposal {
  planId: string
  title: string
  steps: PlanStep[]
}

export interface PlanStep {
  id: string
  description: string
  command?: string
  status?: 'pending' | 'running' | 'done' | 'failed'
}

export interface AgentQuestion {
  question: string
  options?: string[]
}

export interface FileReady {
  path: string
  downloadUrl: string
  sizeBytes: number
}

// WebSocket message types (server → client)
export type ServerMessage =
  | { type: 'agent_chunk'; content: string; done: boolean }
  | { type: 'agent_message'; content: string; metadata?: Record<string, unknown> }
  | { type: 'terminal_output'; exec_id: string; content: string; stream: string; done: boolean }
  | { type: 'approval_request'; request_id: string; action: string; command: string; estimated_time?: string; risk_level: string }
  | { type: 'plan_proposal'; plan_id: string; title: string; steps: PlanStep[] }
  | { type: 'step_progress'; plan_id: string; step_id: string; status: string }
  | { type: 'agent_question'; question: string; options?: string[] }
  | { type: 'file_ready'; path: string; download_url: string; size_bytes: number }
  | { type: 'session_status'; container_status: string; session_id?: string }
  | { type: 'agent_retrieval'; query: string; results: RetrievalResult[]; count: number; error?: string }
  | { type: 'agent_critique'; finding: string; severity?: string; resolved?: boolean }
  | { type: 'error'; message: string; recoverable: boolean }
