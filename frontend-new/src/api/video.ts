import { staticUrl } from './client'

export interface VideoItem {
  file_name: string
  content_text: string[]
  img_lis: string[]
  pdf_path: string
  video_path: string
  m3u8_url: string
  output_dir?: string
}

export interface VideoCatalog {
  data: VideoItem[]
}

export async function fetchVideoList(): Promise<VideoItem[]> {
  try {
    const url = `${staticUrl('/static/data/basic_information.json')}?t=${Date.now()}`
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) return []
    const catalog: VideoCatalog = await res.json()
    return catalog.data || []
  } catch {
    return []
  }
}
