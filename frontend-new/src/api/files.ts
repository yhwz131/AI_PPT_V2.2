import { apiUpload, type ApiResponse } from './client'

export interface FileInfo {
  file_id: string
  filename: string
  file_path: string
  file_size: number
}

export interface PreviewResult {
  task_id: string
  file_id: string
  convert_type: string
  status: string
}

export interface ScriptResult {
  script: string
  pdf_path: string
}

export interface BgmResult {
  bgm_path: string
  bgm_url: string
  file_name: string
}

export function uploadPPT(file: File): Promise<ApiResponse<PreviewResult>> {
  const fd = new FormData()
  fd.append('file', file)
  return apiUpload('/files/preview', fd)
}

export function generateScript(file: File, pdfPath: string, style: string = 'normal'): Promise<ApiResponse<ScriptResult>> {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('pdf_path', pdfPath)
  fd.append('style', style)
  return apiUpload('/files/voice_over_script_generation', fd)
}

export function uploadBgm(file: File): Promise<ApiResponse<BgmResult>> {
  const fd = new FormData()
  fd.append('file', file)
  return apiUpload('/files/upload_bgm', fd)
}
