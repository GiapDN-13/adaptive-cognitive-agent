import { useState, useEffect } from 'react'
import { useChatStore } from '@/store/chatStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useSession } from '@/hooks/useSession'
import { ChatContainer } from '@/components/Chat/ChatContainer'
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
  const { startSession, endSession } = useSession()
  const [historyOpen, setHistoryOpen] = useState(false)
  const [rightPanelOpen, setRightPanelOpen] = useState(true)

  useEffect(() => {
    if (!sessionId && containerStatus === 'idle') {
      startSession()
    }
  }, [sessionId, containerStatus, startSession])

  const handleSend = (content: string) => {
    const msg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    addMessage(msg)
    sendMessage(content)
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
              <div className="mx-4 my-2 rounded-xl border border-blue-500/30 bg-blue-500/5 p-4">
                <p className="text-sm mb-3">{pendingQuestion.question}</p>
                {pendingQuestion.options ? (
                  <div className="flex flex-wrap gap-2">
                    {pendingQuestion.options.map((opt) => (
                      <button
                        key={opt}
                        onClick={() => {
                          sendUserResponse(opt)
                          setPendingQuestion(null)
                        }}
                        className="px-3 py-1.5 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-sm transition"
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                ) : (
                  <input
                    type="text"
                    className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500/50"
                    placeholder="Nhập câu trả lời..."
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        sendUserResponse((e.target as HTMLInputElement).value)
                        setPendingQuestion(null)
                      }
                    }}
                  />
                )}
              </div>
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
