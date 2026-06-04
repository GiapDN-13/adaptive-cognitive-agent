import { useEffect, useRef, useCallback } from 'react'
import { WebSocketManager } from '@/api/websocket'
import { useChatStore } from '@/store/chatStore'
import type { ServerMessage } from '@/types/messages'

export function useWebSocket() {
  const wsRef = useRef<WebSocketManager | null>(null)
  const { sessionId, setContainerStatus, appendStreamChunk, finalizeStream, appendTerminal, setPendingApproval, setPendingPlan, setActivePlan, updateStepStatus, setPendingQuestion, addMessage, setAgentWorking } = useChatStore()

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'agent_thinking' as any: {
        const { setThinking, finalizeThinking } = useChatStore.getState()
        if ((msg as any).done) {
          finalizeThinking()
        } else {
          setThinking((msg as any).content || '')
        }
        break
      }

      case 'agent_chunk':
        if (msg.done) {
          finalizeStream()
          setAgentWorking(false)
        } else {
          appendStreamChunk(msg.content)
        }
        break

      case 'agent_message': {
        const state = useChatStore.getState()
        if (state.streamingContent) {
          finalizeStream()
        } else {
          const lastMsg = state.messages[state.messages.length - 1]
          const isDuplicate = lastMsg?.role === 'assistant' && lastMsg.content === msg.content
          if (!isDuplicate) {
            addMessage({
              id: crypto.randomUUID(),
              role: 'assistant',
              content: msg.content,
              timestamp: Date.now(),
              metadata: msg.metadata,
            })
          }
        }
        if (state.activePlan) {
          setActivePlan(null)
        }
        setAgentWorking(false)
        break
      }

      case 'terminal_output':
        if (!msg.done) {
          appendTerminal(msg.exec_id, msg.content)
        }
        break

      case 'file_ready' as any:
        break

      case 'approval_request':
        setPendingApproval({
          requestId: msg.request_id,
          action: msg.action,
          command: msg.command,
          estimatedTime: msg.estimated_time,
          riskLevel: msg.risk_level as 'low' | 'medium' | 'high',
        })
        break

      case 'plan_proposal':
        setPendingPlan({
          planId: msg.plan_id,
          title: msg.title,
          steps: msg.steps.map((s) => ({ ...s, status: 'pending' as const })),
        })
        break

      case 'step_progress':
        updateStepStatus(msg.plan_id, msg.step_id, msg.status as any)
        break

      case 'agent_question':
        setPendingQuestion({
          question: msg.question,
          options: msg.options,
        })
        break

      case 'session_status':
        setContainerStatus(msg.container_status === 'running' ? 'running' : 'stopped')
        setAgentWorking(false)
        useChatStore.getState().setConnectionStatus('connected')
        break

      case 'history_replay' as any:
        for (const m of (msg as any).messages || []) {
          addMessage({
            id: crypto.randomUUID(),
            role: m.role === 'user' ? 'user' : 'assistant',
            content: m.content,
            timestamp: Date.now(),
          })
        }
        break

      case 'agent_status' as any: {
        const { setAgentStatus } = useChatStore.getState()
        const detail = (msg as any).detail || (msg as any).tool || ''
        const tool = (msg as any).tool || ''
        if (tool === 'thinking') {
          setAgentStatus('Thinking...')
        } else if (tool) {
          setAgentStatus(`Using ${tool}${detail ? ': ' + detail.slice(0, 60) : ''}`)
        } else {
          setAgentStatus(detail || null)
        }
        break
      }

      case 'agent_heartbeat' as any: {
        const { setAgentStatus } = useChatStore.getState()
        const elapsed = (msg as any).elapsed_since_last_chunk || 0
        setAgentStatus(`Thinking... (${elapsed}s)`)
        break
      }

      case 'error' as any: {
        const errorMsg = (msg as any).message || 'Unknown error'
        const recoverable = (msg as any).recoverable
        const state = useChatStore.getState()
        if (state.streamingContent) {
          finalizeStream()
        }
        if (!recoverable) {
          state.setConnectionStatus('error', errorMsg)
        }
        addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `⚠️ ${errorMsg}`,
          timestamp: Date.now(),
        })
        setAgentWorking(false)
        break
      }

      default:
        break
    }
  }, [addMessage, appendStreamChunk, appendTerminal, finalizeStream, setActivePlan, setAgentWorking, setContainerStatus, setPendingApproval, setPendingPlan, setPendingQuestion, updateStepStatus])

  useEffect(() => {
    if (!sessionId) return

    const ws = new WebSocketManager(sessionId, handleMessage)

    ws.onReconnecting = (attempt, max) => {
      useChatStore.getState().setConnectionStatus('reconnecting', `Attempt ${attempt}/${max}`)
    }

    ws.onReconnectFailed = () => {
      useChatStore.getState().setConnectionStatus('disconnected', 'Reconnect failed')
    }

    ws.onSessionLost = () => {
      useChatStore.getState().setConnectionStatus('error', 'Session expired')
      useChatStore.getState().reset()
    }

    ws.onConnectionError = (reason) => {
      useChatStore.getState().setConnectionStatus('error', reason)
    }

    ws.connect()
    wsRef.current = ws

    return () => {
      ws.disconnect()
      wsRef.current = null
    }
  }, [sessionId, handleMessage])

  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current?.isConnected) {
      useChatStore.getState().setConnectionStatus('error', 'Not connected')
      return
    }
    wsRef.current.sendMessage(content)
    setAgentWorking(true)
  }, [setAgentWorking])

  const sendApproval = useCallback((requestId: string, approved: boolean, modifiedCommand?: string) => {
    wsRef.current?.sendApproval(requestId, approved, modifiedCommand)
  }, [])

  const sendUserResponse = useCallback((content: string) => {
    wsRef.current?.sendUserResponse(content)
  }, [])

  const sendCancel = useCallback(() => {
    wsRef.current?.sendCancel()
  }, [])

  return { sendMessage, sendApproval, sendUserResponse, sendCancel, isConnected: wsRef.current?.isConnected ?? false }
}
