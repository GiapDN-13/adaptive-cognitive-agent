import { useCallback } from 'react'
import { createSession, deleteSession } from '@/api/http'
import { useChatStore } from '@/store/chatStore'

export function useSession() {
  const { sessionId, setSessionId, setContainerStatus, reset } = useChatStore()

  const startSession = useCallback(async () => {
    setContainerStatus('creating')
    try {
      const session = await createSession()
      setSessionId(session.id)
      setContainerStatus('running')
    } catch (e) {
      setContainerStatus('idle')
      throw e
    }
  }, [setSessionId, setContainerStatus])

  const endSession = useCallback(async () => {
    if (sessionId) {
      await deleteSession(sessionId)
    }
    reset()
  }, [sessionId, reset])

  return { startSession, endSession, isActive: !!sessionId }
}
