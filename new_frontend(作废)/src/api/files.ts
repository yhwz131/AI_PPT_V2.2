import request from './request'
import type { ApiResponse, UploadResponse, PreviewResponse, ScriptResponse, BgmUploadResponse } from '@/types'

export function uploadFile(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<ApiResponse<UploadResponse>>('/files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function previewFile(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<ApiResponse<PreviewResponse>>('/files/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function uploadBgm(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<ApiResponse<BgmUploadResponse>>('/files/upload_bgm', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function generateScript(file: File | null, pdfPath: string, style: string = 'normal') {
  const formData = new FormData()
  if (file) {
    formData.append('file', file)
  } else {
    const emptyFile = new File([''], 'placeholder.pptx', { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' })
    formData.append('file', emptyFile)
  }
  formData.append('pdf_path', pdfPath)
  formData.append('style', style)
  return request.post<ApiResponse<ScriptResponse>>('/files/voice_over_script_generation', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000
  })
}
