import type { ServerMessage } from '@/types/messages'

type MessageHandler = (msg: ServerMessage) => void

export class WebSocketManager {
  private ws: WebSocket | null = null
  private sessionId: string
  private handler: MessageHandler
  private reconnectAttempts = 0
  private maxReconnects = 5
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private intentionalClose = false
  private pendingMessages: Record<string, unknown>[] = []

  onSessionLost: (() => void) | null = null
  onConnectionError: ((reason: string) => void) | null = null
  onReconnecting: ((attempt: number, maxAttempts: number) => void) | null = null
  onReconnectFailed: (() => void) | null = null

  constructor(sessionId: string, handler: MessageHandler) {
    this.sessionId = sessionId
    this.handler = handler
  }

  connect() {
    // Guard against double-connect (React StrictMode dev mounts twice, and
    // reconnect timers can overlap). If a socket is already opening/open, keep it.
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      return
    }
    this.intentionalClose = false
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/${this.sessionId}`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.intentionalClose = false
      for (const msg of this.pendingMessages) {
        this.ws!.send(JSON.stringify(msg))
      }
      this.pendingMessages = []
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'ping') return
        this.handler(msg as ServerMessage)
      } catch (e) {
        console.error('Failed to parse WS message:', e)
      }
    }

    this.ws.onclose = (event) => {
      const { code } = event

      if (code === 4004) {
        this.cleanup()
        this.onSessionLost?.()
        return
      }

      if (code === 1000) {
        this.cleanup()
        return
      }

      // Abnormal closure — attempt reconnect
      if (!this.intentionalClose && this.reconnectAttempts < this.maxReconnects) {
        this.reconnectAttempts++
        this.onReconnecting?.(this.reconnectAttempts, this.maxReconnects)
        const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 15000)
        this.reconnectTimer = setTimeout(() => this.connect(), delay)
      } else if (!this.intentionalClose) {
        this.onReconnectFailed?.()
      }
    }

    this.ws.onerror = () => {
      this.onConnectionError?.('WebSocket error')
    }
  }

  private cleanup() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.reconnectAttempts = 0
    this.pendingMessages = []
  }

  send(data: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    } else if (this.ws?.readyState === WebSocket.CONNECTING) {
      this.pendingMessages.push(data)
    } else {
      this.onConnectionError?.('Cannot send: not connected')
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
    this.intentionalClose = true
    this.cleanup()
    const ws = this.ws
    this.ws = null
    if (!ws) return
    if (ws.readyState === WebSocket.CONNECTING) {
      // Closing a still-CONNECTING socket logs "closed before established" noise and
      // triggers onclose/reconnect. Neutralize handlers and close once it opens.
      ws.onopen = () => ws.close(1000)
      ws.onclose = null
      ws.onerror = null
      ws.onmessage = null
    } else {
      ws.close(1000)
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
