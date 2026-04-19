import request from './request'
import type { ApiResponse, ConversionStartResponse, ConversionTaskStatus } from '@/types'

export function startConversion(fileId: string, convertType: string = 'pdf', imageFormat: string = 'png') {
  const formData = new FormData()
  formData.append('file_id', fileId)
  formData.append('convert_type', convertType)
  formData.append('image_format', imageFormat)
  return request.post<ApiResponse<ConversionStartResponse>>('/conversion/start', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function getConversionStatus(taskId: string) {
  return request.get<ApiResponse<ConversionTaskStatus>>(`/conversion/tasks/${taskId}`)
}
