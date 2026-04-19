import type { SSEConnectedEvent, SSEProgressEvent, SSEErrorEvent, SSEVideoResultEvent, SSESuccessEvent } from '@/types'

export type SSEEventType = 'connected' | 'progress' | 'error' | 'video_result' | 'success' | 'end'

export interface SSECallbacks {
  onConnected?: (data: SSEConnectedEvent) => void
  onProgress?: (data: SSEProgressEvent) => void
  onError?: (data: SSEErrorEvent) => void
  onVideoResult?: (data: SSEVideoResultEvent) => void
  onSuccess?: (data: SSESuccessEvent) => void
  onEnd?: () => void
}

export async function consumeSSEStream(
  requestBody: any,
  callbacks: SSECallbacks,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch('/my_digital_human/digital_character_generation_stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify(requestBody),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No readable stream')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const dataStr = line.slice(6).trim()
        if (!dataStr || dataStr === '{}') {
          if (currentEvent === 'end') {
            callbacks.onEnd?.()
          }
          continue
        }

        try {
          const data = JSON.parse(dataStr)
          switch (currentEvent) {
            case 'connected':
              callbacks.onConnected?.(data)
              break
            case 'progress':
              callbacks.onProgress?.(data)
              break
            case 'error':
              callbacks.onError?.(data)
              break
            case 'video_result':
              callbacks.onVideoResult?.(data)
              break
            case 'success':
              callbacks.onSuccess?.(data)
              break
          }
        } catch (e) {
          console.warn('Failed to parse SSE data:', dataStr, e)
        }
        currentEvent = ''
      }
    }
  }
}
