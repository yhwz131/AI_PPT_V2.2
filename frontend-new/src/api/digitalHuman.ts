import { apiGet, apiPost, apiUpload, apiDelete, staticUrl, type ApiResponse } from './client'

export interface DigitalHuman {
  name: string
  brief: string
  image: string
  audio: string
  video: string
}

export interface DigitalHumanCatalog {
  data: DigitalHuman[]
}

export interface GenerationRequest {
  scriptContent: string
  template: string
  human: {
    name: string
    avatar: string
    audio: string
    video: string
  }
  file_name: string
  pdf_path: string
  welcome_text?: string
  bgm_mode?: string
  bgm_path?: string
  style?: string
  emo_control_method?: string
  emo_vec?: string
  emo_text?: string
}

export async function fetchDigitalHumans(type: 'built-in' | 'custom'): Promise<DigitalHuman[]> {
  const file = type === 'built-in'
    ? '/static/Digital_human/Built-in_digital_human.json'
    : '/static/Digital_human/Customized_digital_human.json'
  try {
    const res = await fetch(staticUrl(file))
    if (!res.ok) return []
    const catalog: DigitalHumanCatalog = await res.json()
    return catalog.data || []
  } catch {
    return []
  }
}

export function createTask(req: GenerationRequest): Promise<ApiResponse<{ task_id: string }>> {
  return apiPost('/my_digital_human/tasks', req)
}

/** 用于刷新后校验任务是否仍在服务端（内存中） */
export function getTaskStatus(taskId: string): Promise<ApiResponse<Record<string, unknown>>> {
  return apiGet(`/my_digital_human/task_status/${encodeURIComponent(taskId)}`)
}

export interface TaskCheck {
  exists: 'ok' | 'gone' | 'error'
  status?: string
  results?: Record<string, unknown>
  created_at?: number
}

/** 查询任务是否仍存在，同时返回 status、results 和 created_at */
export async function checkTaskExists(taskId: string): Promise<TaskCheck> {
  const base = import.meta.env.VITE_API_BASE || ''
  try {
    const res = await fetch(`${base}/my_digital_human/task_status/${encodeURIComponent(taskId)}`)
    if (res.status === 404) return { exists: 'gone' }
    if (res.ok) {
      const json = await res.json()
      const data = json.data || {}
      return { exists: 'ok', status: data.status, results: data.results, created_at: data.created_at }
    }
    return { exists: 'error' }
  } catch {
    return { exists: 'error' }
  }
}

export function uploadCustomDigitalHuman(
  name: string, brief: string, avatar: File, audio: File, video: File
): Promise<ApiResponse<any>> {
  const fd = new FormData()
  fd.append('name', name)
  fd.append('brief', brief)
  fd.append('avatar', avatar)
  fd.append('audio', audio)
  fd.append('video', video)
  return apiUpload('/my_digital_human/digital-human/upload', fd)
}

export function deleteDigitalHuman(name: string): Promise<ApiResponse<any>> {
  return apiDelete(`/my_digital_human/digital-human/${encodeURIComponent(name)}`)
}
