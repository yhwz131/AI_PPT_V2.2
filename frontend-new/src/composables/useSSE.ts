import { ref } from 'vue'
import { sseUrl } from '../api/client'

export interface SSEEvent {
  type: string
  data: any
  raw: string
}

export type SSEStatus = 'idle' | 'connecting' | 'connected' | 'error' | 'done'

/**
 * 基于 fetch + ReadableStream 的 SSE 实现，
 * 替代原生 EventSource 以避免自动重连被 Cursor 远程代理拦截。
 */
export function useSSE() {
  const events = ref<SSEEvent[]>([])
  const status = ref<SSEStatus>('idle')
  const latestEvent = ref<SSEEvent | null>(null)
  let abortCtrl: AbortController | null = null

  function pushEvent(type: string, raw: string) {
    if (type === 'end') {
      status.value = 'done'
      abortCtrl?.abort()
      return
    }
    let data: any
    try { data = JSON.parse(raw) } catch { data = raw }
    const evt: SSEEvent = { type, data, raw }
    events.value.push(evt)
    latestEvent.value = evt
    if (type === 'connected') status.value = 'connected'
    if (type === 'error') status.value = 'error'
  }

  async function connect(taskId: string) {
    disconnect()
    events.value = []
    status.value = 'connecting'

    abortCtrl = new AbortController()
    const url = sseUrl(`/my_digital_human/tasks/${taskId}/stream`)

    try {
      const res = await fetch(url, {
        signal: abortCtrl.signal,
        headers: { Accept: 'text/event-stream' },
      })
      if (!res.ok || !res.body) {
        status.value = 'error'
        return
      }
      status.value = 'connected'

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })

        const blocks = buf.split('\n\n')
        buf = blocks.pop() || ''

        for (const block of blocks) {
          if (!block.trim()) continue
          let evtType = ''
          let evtData = ''
          let isComment = true
          for (const line of block.split('\n')) {
            if (line.startsWith('event:')) {
              evtType = line.slice(6).trim()
              isComment = false
            } else if (line.startsWith('data:')) {
              evtData += (evtData ? '\n' : '') + line.slice(5).trim()
              isComment = false
            } else if (!line.startsWith(':')) {
              isComment = false
            }
          }
          if (isComment || (!evtType && !evtData)) continue
          pushEvent(evtType || 'message', evtData)
        }
        if ((status.value as SSEStatus) === 'done') break
      }

      if ((status.value as SSEStatus) !== 'done' && (status.value as SSEStatus) !== 'error') {
        status.value = 'done'
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return
      if ((status.value as SSEStatus) !== 'done') status.value = 'error'
    }
  }

  function disconnect() {
    abortCtrl?.abort()
    abortCtrl = null
    if (status.value !== 'done') status.value = 'idle'
  }

  return { events, status, latestEvent, connect, disconnect }
}
