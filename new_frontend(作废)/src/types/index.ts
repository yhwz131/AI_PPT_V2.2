export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

export interface UploadResponse {
  file_id: string
  file_path: string
  file_name: string
  file_size: number
}

export interface ConversionStartResponse {
  task_id: string
  file_id: string
  convert_type: string
  status: string
}

export interface ConversionTaskStatus {
  task_id: string
  status: 'processing' | 'completed' | 'failed'
  progress: number
  message: string
  type?: 'pdf' | 'images'
  pdf_url?: string
  download_url?: string
  image_urls?: string[]
  image_count?: number
  error?: string
}

export interface PreviewResponse {
  task_id: string
  file_id: string
  convert_type: string
  status: string
}

export interface ScriptResponse {
  script: string
  pdf_path: string
}

export interface BgmUploadResponse {
  bgm_path: string
  file_name: string
}

export interface DigitalHuman {
  name: string
  brief: string
  image: string
  audio: string
  video: string
}

export interface DigitalHumanListResponse {
  data: DigitalHuman[]
}

export interface GenerationStreamRequest {
  scriptContent: string
  human: DigitalHuman
  pdf_path: string
  file_name: string
  template: string
  welcome_text?: string
  bgm_mode?: 'default' | 'custom' | 'none'
  bgm_path?: string
  emo_control_method?: number
  emo_vec?: string
  emo_text?: string
}

export interface SSEConnectedEvent {
  task_id: string
}

export interface SSEProgressEvent {
  stage: string
  message: string
  progress: number
  current?: number
  total?: number
  current_stage_progress?: number
}

export interface SSEErrorEvent {
  message: string
}

export interface SSEVideoResultEvent {
  video_index: number
  status: 'completed' | 'failed'
  save_path?: string
  relative_path?: string
  content?: string
  error?: string
  error_details?: any
  created_at?: string
}

export interface SSESuccessEvent {
  success: boolean
  task_id: string
  total_videos: number
  completed: number
  failed: number
  video_results: SSEVideoResultEvent[]
  relative_paths?: string[]
  completed_at: string
  video_path: string
  hls_info: {
    m3u8_url?: string
    output_dir?: string
    segment_duration?: number
    status: string
    error?: string
  }
  time_estimation?: {
    total_segments: number
    total_time_seconds: number
    actual_progress: number
  }
}

export interface TaskStatus {
  status: string
  progress: number
  current_stage?: string
  message?: string
  results?: any
  error?: string
  created_at?: number
  updated_at?: number
  completed_at?: number
}

export interface TaskListItem {
  task_id: string
  status: string
  progress: number
  message?: string
  updated_at?: number
}

export interface BasicInformationItem {
  file_name: string
  content_text: string[]
  img_lis: string[]
  pdf_path: string
  video_path: string
  m3u8_url: string
  output_dir: string
}

export interface BasicInformationResponse {
  data: BasicInformationItem[]
}

export interface TemplateOption {
  label: string
  value: string
}

export type ScriptStyle = 'brief' | 'normal' | 'professional'

export type BgmMode = 'default' | 'custom' | 'none'

export type EmoControlMethod = 0 | 2 | 3
