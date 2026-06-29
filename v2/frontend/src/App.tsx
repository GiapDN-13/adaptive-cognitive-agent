import { useState, useEffect, useRef } from 'react'
import { useChatStore } from '@/store/chatStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useSession } from '@/hooks/useSession'
import { ChatContainer } from '@/components/Chat/ChatContainer'
import { QuestionPrompt } from '@/components/Chat/QuestionPrompt'
import { InputBar } from '@/components/Chat/InputBar'
import { TerminalStream } from '@/components/Terminal/TerminalStream'
import { ApprovalCard } from '@/components/Approval/ApprovalCard'
import { PlanViewer } from '@/components/Approval/PlanViewer'
import { SessionHistory } from '@/components/Session/SessionHistory'
import { RightPanel } from '@/components/Dashboard/RightPanel'
import { TopBar } from '@/components/Dashboard/TopBar'
import { uploadFile } from '@/api/http'
import type { Message } from '@/types/messages'

export default function App() {
  const { sessionId, containerStatus, addMessage, pendingQuestion, setPendingQuestion } = useChatStore()
  const { sendMessage, sendApproval, sendUserResponse, sendCancel } = useWebSocket()
  const { startSession, resumeOrStart, endSession } = useSession()
  const [historyOpen, setHistoryOpen] = useState(false)
  const [rightPanelOpen, setRightPanelOpen] = useState(true)

  // Guard chống tạo session 2 lần: containerStatus='creating' được set bất đồng bộ
  // sau await, nên effect có thể chạy lại khi status vẫn 'idle' → tạo 2 Docker
  // container. Ref chặn ngay lập tức (đồng bộ), không chờ state cập nhật.
  // Khi mở/reload tab: nếu có sessionId lưu trong localStorage → NỐI LẠI container
  // cũ (resumeOrStart) thay vì đẻ container rỗng mới làm mất context.
  const startingRef = useRef(false)
  useEffect(() => {
    if (containerStatus === 'idle' && !startingRef.current) {
      startingRef.current = true
      const boot = sessionId ? resumeOrStart(sessionId) : startSession()
      Promise.resolve(boot).finally(() => { startingRef.current = false })
    }
  }, [sessionId, containerStatus, startSession, resumeOrStart])

  const handleSend = (content: string, images?: { format: string; data: string; previewUrl: string }[]) => {
    const msg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
      imageUrls: images?.map(i => i.previewUrl),  // render ảnh trong khung chat
    }
    addMessage(msg)
    // Gửi base64 + format cho backend (ghép image block cho LLM); bỏ previewUrl khỏi payload.
    sendMessage(content, images?.map(({ format, data }) => ({ format, data })))
  }

  const handleFileUpload = async (files: File[]) => {
    if (!sessionId) return
    for (const file of files) {
      try {
        const result = await uploadFile(sessionId, file)
        addMessage({
          id: crypto.randomUUID(),
          role: 'system',
          content: `File uploaded: ${result.path}`,
          timestamp: Date.now(),
        })
      } catch (e) {
        addMessage({
          id: crypto.randomUUID(),
          role: 'system',
          content: `Upload failed: ${(e as Error).message}`,
          timestamp: Date.now(),
        })
      }
    }
  }

  const handleApprove = (requestId: string) => {
    sendApproval(requestId, true)
    useChatStore.getState().setPendingApproval(null)
  }
  const handleReject = (requestId: string) => {
    sendApproval(requestId, false)
    useChatStore.getState().setPendingApproval(null)
  }
  const handlePlanApprove = (planId: string) => {
    sendApproval(planId, true)
    useChatStore.getState().setPendingPlan(null)
  }
  const handlePlanReject = (planId: string) => {
    sendApproval(planId, false)
    useChatStore.getState().setPendingPlan(null)
  }

  return (
    <div className="h-screen flex flex-col bg-bg text-white overflow-hidden">
      {/* Top Bar */}
      <TopBar
        onStart={startSession}
        onEnd={endSession}
        onHistoryOpen={() => setHistoryOpen(true)}
        onRightPanelToggle={() => setRightPanelOpen(!rightPanelOpen)}
        rightPanelOpen={rightPanelOpen}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Chat + Terminal + Input */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Chat Messages */}
          <div className="flex-1 overflow-hidden flex flex-col">
            <ChatContainer />

            <ApprovalCard onApprove={handleApprove} onReject={handleReject} />
            <PlanViewer onApprove={handlePlanApprove} onReject={handlePlanReject} />

            {pendingQuestion && (
              <QuestionPrompt
                question={pendingQuestion.question}
                options={pendingQuestion.options}
                onAnswer={(answer) => {
                  sendUserResponse(answer)
                  setPendingQuestion(null)
                }}
              />
            )}
          </div>

          {/* Terminal */}
          <TerminalStream />

          {/* Input */}
          {containerStatus === 'running' && (
            <InputBar
              onSend={handleSend}
              onCancel={sendCancel}
              onFileSelect={handleFileUpload}
            />
          )}
        </div>

        {/* Right Panel */}
        {rightPanelOpen && containerStatus === 'running' && (
          <RightPanel />
        )}
      </div>

      {/* Modals */}
      <SessionHistory open={historyOpen} onClose={() => setHistoryOpen(false)} />
    </div>
  )
}
