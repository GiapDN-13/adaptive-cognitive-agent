import { useCallback } from 'react'
import { createSession, deleteSession, getSessionStats } from '@/api/http'
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

  // Nối lại session đã lưu (localStorage) nếu container CÒN SỐNG. Lịch sử chat do
  // WebSocket tự replay khi connect (xem routes_ws history_replay) nên không nạp
  // thủ công ở đây để tránh trùng. Container chết → tạo mới. Đây là chốt chặn việc
  // reload/điều hướng tab tự đẻ container rỗng và làm agent mất context.
  const resumeOrStart = useCallback(async (savedId: string) => {
    setContainerStatus('creating')
    try {
      const stats = await getSessionStats(savedId)
      if (stats.running) {
        setSessionId(savedId)
        setContainerStatus('running')
        return
      }
    } catch { /* không kiểm được trạng thái → coi như chết, tạo mới */ }
    // session cũ đã chết: dọn id cũ rồi tạo mới
    reset()
    await startSession()
  }, [setSessionId, setContainerStatus, reset, startSession])

  const endSession = useCallback(async () => {
    if (sessionId) {
      await deleteSession(sessionId)
    }
    reset()
  }, [sessionId, reset])

  return { startSession, resumeOrStart, endSession, isActive: !!sessionId }
}
