const BASE_URL = '/api'

export async function createSession(): Promise<{ id: string; container_id: string }> {
  const res = await fetch(`${BASE_URL}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!res.ok) throw new Error(`Failed to create session: ${res.statusText}`)
  return res.json()
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE_URL}/sessions/${sessionId}`, { method: 'DELETE' })
}

export async function uploadFile(sessionId: string, file: File): Promise<{ path: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}/files`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`)
  return res.json()
}

export function getFileDownloadUrl(sessionId: string, path: string): string {
  return `${BASE_URL}/sessions/${sessionId}/files${path}`
}

export async function getSessionStats(sessionId: string): Promise<{
  status: string
  running: boolean
  cpu_percent: number
  memory_mb: number
}> {
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}/stats`)
  if (!res.ok) return { status: 'unknown', running: false, cpu_percent: 0, memory_mb: 0 }
  return res.json()
}
