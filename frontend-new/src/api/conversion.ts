import { apiGet, type ApiResponse } from './client'

export interface ConversionStatus {
  task_id: string
  status: string
  progress: number
  message: string
  type?: string
  pdf_url?: string
  download_url?: string
  image_urls?: string[]
  image_count?: number
  error?: string
}

export function getConversionStatus(taskId: string): Promise<ApiResponse<ConversionStatus>> {
  return apiGet(`/conversion/tasks/${taskId}`)
}

export function pollConversionTask(
  taskId: string,
  intervalMs = 2000,
  maxAttempts = 90
): Promise<ConversionStatus> {
  return new Promise((resolve, reject) => {
    let attempt = 0
    const timer = setInterval(async () => {
      attempt++
      if (attempt > maxAttempts) {
        clearInterval(timer)
        reject(new Error('转换超时，请稍后重试'))
        return
      }
      try {
        const res = await getConversionStatus(taskId)
        const data = res.data
        if (data.status === 'completed') {
          clearInterval(timer)
          resolve(data)
        } else if (data.status === 'failed') {
          clearInterval(timer)
          reject(new Error(data.error || data.message || '转换失败'))
        }
      } catch (e: any) {
        console.warn('轮询转换状态失败:', e)
      }
    }, intervalMs)
  })
}
