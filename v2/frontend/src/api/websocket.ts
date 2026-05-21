import type { ServerMessage } from '@/types/messages'

type MessageHandler = (msg: ServerMessage) => void

export class WebSocketManager {
  private ws: WebSocket | null = null
  private sessionId: string
  private handler: MessageHandler
  private reconnectAttempts = 0
  private maxReconnects = 5
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  onSessionLost: (() => void) | null = null

  constructor(sessionId: string, handler: MessageHandler) {
    this.sessionId = sessionId
    this.handler = handler
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/${this.sessionId}`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as ServerMessage
        this.handler(msg)
      } catch (e) {
        console.error('Failed to parse WS message:', e)
      }
    }

    this.ws.onclose = (event) => {
      if (event.code === 4004) {
        if (this.onSessionLost) this.onSessionLost()
        return
      }
      if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnects) {
        this.reconnectAttempts++
        const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000)
        this.reconnectTimer = setTimeout(() => this.connect(), delay)
      }
    }

    this.ws.onerror = () => {}
  }

  send(data: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  sendMessage(content: string) {
    this.send({ type: 'user_message', content })
  }

  sendApproval(requestId: string, approved: boolean, modifiedCommand?: string) {
    this.send({ type: 'approval_response', request_id: requestId, approved, modified_command: modifiedCommand })
  }

  sendUserResponse(content: string) {
    this.send({ type: 'user_response', content })
  }

  sendCancel() {
    this.send({ type: 'cancel' })
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.ws?.close(1000)
    this.ws = null
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
