import { useEffect, useRef, useCallback } from 'react'
import { WebSocketManager } from '@/api/websocket'
import { useChatStore } from '@/store/chatStore'
import type { ServerMessage } from '@/types/messages'

export function useWebSocket() {
  const wsRef = useRef<WebSocketManager | null>(null)
  const { sessionId, setContainerStatus, appendStreamChunk, finalizeStream, appendTerminal, setPendingApproval, setPendingPlan, setPendingQuestion, addMessage, setAgentWorking } = useChatStore()

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'agent_chunk':
        if (msg.done) {
          finalizeStream()
          setAgentWorking(false)
        } else {
          appendStreamChunk(msg.content)
        }
        break

      case 'agent_message':
        finalizeStream()
        addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: msg.content,
          timestamp: Date.now(),
          metadata: msg.metadata,
        })
        setAgentWorking(false)
        break

      case 'terminal_output':
        if (!msg.done) {
          appendTerminal(msg.exec_id, msg.content)
        }
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
          steps: msg.steps,
        })
        break

      case 'agent_question':
        setPendingQuestion({
          question: msg.question,
          options: msg.options,
        })
        break

      case 'session_status':
        setContainerStatus(msg.container_status === 'running' ? 'running' : 'stopped')
        break

      case 'error':
        addMessage({
          id: crypto.randomUUID(),
          role: 'system',
          content: `Error: ${msg.message}`,
          timestamp: Date.now(),
        })
        setAgentWorking(false)
        break
    }
  }, [finalizeStream, appendStreamChunk, appendTerminal, setPendingApproval, setPendingPlan, setPendingQuestion, addMessage, setAgentWorking, setContainerStatus])

  useEffect(() => {
    if (!sessionId) return

    const ws = new WebSocketManager(sessionId, handleMessage)
    ws.connect()
    wsRef.current = ws

    return () => {
      ws.disconnect()
      wsRef.current = null
    }
  }, [sessionId, handleMessage])

  const sendMessage = useCallback((content: string) => {
    wsRef.current?.sendMessage(content)
    setAgentWorking(true)
  }, [setAgentWorking])

  const sendApproval = useCallback((requestId: string, approved: boolean) => {
    wsRef.current?.sendApproval(requestId, approved)
    setPendingApproval(null)
  }, [setPendingApproval])

  const sendUserResponse = useCallback((content: string) => {
    wsRef.current?.sendUserResponse(content)
    setPendingQuestion(null)
  }, [setPendingQuestion])

  const sendCancel = useCallback(() => {
    wsRef.current?.sendCancel()
    setAgentWorking(false)
  }, [setAgentWorking])

  return { sendMessage, sendApproval, sendUserResponse, sendCancel }
}
