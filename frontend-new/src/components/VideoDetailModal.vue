<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <div class="modal__header">
          <h3>{{ video?.file_name }}</h3>
          <button class="modal__close" @click="$emit('close')">✕</button>
        </div>

        <div class="modal__body">
          <div class="modal__player">
            <video ref="videoRef" controls class="modal__video" />
          </div>

          <div v-if="video?.img_lis?.length" class="modal__slides">
            <h4>幻灯片</h4>
            <div class="modal__slide-grid">
              <img
                v-for="(img, i) in video.img_lis"
                :key="i"
                :src="staticUrl(img)"
                :alt="`Slide ${i + 1}`"
                class="modal__slide-img"
              />
            </div>
          </div>

          <div v-if="video?.content_text?.length" class="modal__text">
            <h4>解说文本</h4>
            <div v-for="(txt, i) in video.content_text" :key="i" class="modal__text-item">
              <span class="modal__text-idx">{{ i + 1 }}</span>
              <p>{{ txt }}</p>
            </div>
          </div>
        </div>

        <div class="modal__footer">
          <button
            v-if="video?.video_path"
            class="modal__btn"
            @click="doDownload"
          >下载视频</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import Hls from 'hls.js'
import { staticUrl } from '../api/client'
import type { VideoItem } from '../api/video'

const props = defineProps<{
  visible: boolean
  video: VideoItem | null
}>()

defineEmits<{
  (e: 'close'): void
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
let hls: Hls | null = null

function doDownload() {
  if (!props.video?.video_path) return
  const a = document.createElement('a')
  a.href = staticUrl(props.video.video_path)
  a.download = props.video.video_path.split('/').pop() || 'video.mp4'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

watch(() => [props.visible, props.video], () => {
  destroyHls()
  if (props.visible && props.video?.m3u8_url && videoRef.value) {
    initHls(props.video.m3u8_url)
  }
}, { flush: 'post' })

function initHls(url: string) {
  const el = videoRef.value
  if (!el) return
  const src = staticUrl(url)

  if (Hls.isSupported()) {
    hls = new Hls()
    hls.loadSource(src)
    hls.attachMedia(el)
  } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
    el.src = src
  }
}

function destroyHls() {
  if (hls) {
    hls.destroy()
    hls = null
  }
  if (videoRef.value) {
    videoRef.value.pause()
    videoRef.value.removeAttribute('src')
    videoRef.value.load()
  }
}

onUnmounted(destroyHls)
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal {
  background: #fff;
  border-radius: 16px;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.modal__header h3 {
  font-size: 16px;
  font-weight: 600;
}

.modal__close {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #f0f0f0;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal__body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.modal__player {
  margin-bottom: 20px;
}

.modal__video {
  width: 100%;
  max-height: 400px;
  border-radius: 8px;
  background: #000;
}

.modal__slides h4,
.modal__text h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}

.modal__slide-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  margin-bottom: 20px;
}

.modal__slide-img {
  width: 100%;
  border-radius: 6px;
  border: 1px solid var(--border);
}

.modal__text-item {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.modal__text-idx {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.modal__text-item p {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.modal__footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  text-align: right;
}

.modal__btn {
  display: inline-block;
  padding: 8px 24px;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
}
</style>
