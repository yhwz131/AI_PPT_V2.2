<template>
  <div class="video-player">
    <video
      ref="videoRef"
      controls
      class="video-element"
      :poster="poster"
    />
    <div v-if="error" class="video-error">
      <el-icon :size="48"><WarningFilled /></el-icon>
      <p>视频加载失败</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import Hls from 'hls.js'
import { WarningFilled } from '@element-plus/icons-vue'

const props = defineProps<{
  src: string
  poster?: string
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const error = ref(false)
let hls: Hls | null = null

function initPlayer() {
  if (!videoRef.value || !props.src) return

  destroyPlayer()
  error.value = false

  if (props.src.endsWith('.m3u8') || props.src.includes('.m3u8')) {
    if (Hls.isSupported()) {
      hls = new Hls({
        enableWorker: true,
        lowLatencyMode: true,
      })
      hls.loadSource(props.src)
      hls.attachMedia(videoRef.value)
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          error.value = true
          hls?.destroy()
          hls = null
        }
      })
    } else if (videoRef.value.canPlayType('application/vnd.apple.mpegurl')) {
      videoRef.value.src = props.src
    }
  } else {
    videoRef.value.src = props.src
  }
}

function destroyPlayer() {
  if (hls) {
    hls.destroy()
    hls = null
  }
}

watch(() => props.src, () => {
  initPlayer()
})

onMounted(() => {
  initPlayer()
})

onUnmounted(() => {
  destroyPlayer()
})
</script>

<style scoped lang="scss">
.video-player {
  position: relative;
  width: 100%;
  background-color: #000;
  border-radius: 8px;
  overflow: hidden;
}

.video-element {
  width: 100%;
  max-height: 500px;
  display: block;
}

.video-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--accent-error);
  background-color: rgba(0, 0, 0, 0.8);
}
</style>
