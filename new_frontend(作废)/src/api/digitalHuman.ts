import request from './request'
import type { TaskStatus } from '@/types'

export function getTaskStatus(taskId: string) {
  return request.get<TaskStatus>(`/my_digital_human/task_status/${taskId}`)
}

export function getTasks(params?: { status?: string; limit?: number }) {
  return request.get('/my_digital_human/tasks', { params })
}

export function uploadDigitalHuman(data: {
  name: string
  brief: string
  avatar: File
  audio: File
  video: File
}) {
  const formData = new FormData()
  formData.append('name', data.name)
  formData.append('brief', data.brief)
  formData.append('avatar', data.avatar)
  formData.append('audio', data.audio)
  formData.append('video', data.video)
  return request.post('/my_digital_human/digital-human/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000
  })
}

export function deleteDigitalHuman(name: string) {
  return request.delete(`/my_digital_human/digital-human/${encodeURIComponent(name)}`)
}

export function generateNonStream(data: any) {
  return request.post('/my_digital_human/digital_character_generation', data, {
    timeout: 1800000
  })
}
