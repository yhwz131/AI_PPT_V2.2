<template>
  <div class="gen-progress">
    <div class="gen-progress__header">
      <span class="gen-progress__stage" :class="{ 'gen-progress__stage--error': hasError }">{{ currentStage }}</span>
      <span class="gen-progress__timer">{{ timer }}</span>
    </div>

    <div class="gen-progress__bar-wrap">
      <div class="gen-progress__bar" :class="{ 'gen-progress__bar--error': hasError }" :style="{ width: progressPct + '%' }" />
    </div>
    <p class="gen-progress__pct">{{ progressPct }}%</p>

    <div ref="logRef" class="gen-progress__log">
      <template v-for="(evt, i) in events" :key="i">
        <div v-if="formatEvent(evt)" class="gen-progress__entry" :class="'gen-progress__entry--' + evt.type">
          <span class="gen-progress__dot" />
          <span>{{ formatEvent(evt) }}</span>
        </div>
      </template>
    </div>

    <div v-if="videoResults.length > 0" class="gen-progress__videos">
      <h4>已完成片段 ({{ videoResults.length }})</h4>
      <div v-for="(v, i) in videoResults" :key="i" class="gen-progress__video-item">
        {{ v.video_name || `片段 ${i + 1}` }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, ref, nextTick } from 'vue'
import type { SSEEvent } from '../composables/useSSE'

const props = defineProps<{
  events: SSEEvent[]
  timer: string
}>()

const logRef = ref<HTMLElement | null>(null)

const stageNameMap: Record<string, string> = {
  parse_script: '解析讲稿',
  prepare_files: '准备文件',
  audio_generation: '生成音频',
  video_generation: '生成视频',
  video_merge: '合并视频',
  video_merge_complete: '合并完成',
  bgm_mixing: '添加背景音乐',
  bgm_mixing_complete: 'BGM完成',
  video_conversion: '视频切片转换',
  video_conversion_completed: '切片完成',
}

const hasError = computed(() => props.events.some(e => e.type === 'error'))
const isFinished = computed(() => !hasError.value && props.events.some(e => e.type === 'success'))

const progressPct = computed(() => {
  if (isFinished.value) return 100
  if (hasError.value) {
    const progressEvts = props.events.filter(e => e.type === 'progress')
    if (progressEvts.length === 0) return 0
    return Math.round(progressEvts[progressEvts.length - 1].data?.progress ?? 0)
  }
  const progressEvts = props.events.filter(e => e.type === 'progress')
  if (progressEvts.length === 0) return 0
  const last = progressEvts[progressEvts.length - 1]
  return Math.round(last.data?.progress ?? last.data?.percent ?? 0)
})

const currentStage = computed(() => {
  if (hasError.value) return '生成失败'
  if (isFinished.value) return '全部完成'
  const progressEvts = props.events.filter(e => e.type === 'progress')
  if (progressEvts.length === 0) return '准备中...'
  const last = progressEvts[progressEvts.length - 1]
  const stage = last.data?.stage || ''
  return stageNameMap[stage] || last.data?.message || stage || '处理中...'
})

const videoResults = computed(() => {
  return props.events.filter(e => e.type === 'video_result').map(e => e.data)
})

function formatEvent(evt: SSEEvent): string {
  if (evt.type === 'progress') {
    return `[${Math.round(evt.data?.progress ?? 0)}%] ${evt.data?.message || evt.data?.stage || ''}`
  }
  if (evt.type === 'video_result') {
    return `✓ 片段完成: ${evt.data?.video_name || ''}`
  }
  if (evt.type === 'error') {
    return `✕ 错误: ${evt.data?.message || evt.raw}`
  }
  if (evt.type === 'success') {
    return `✓ 全部完成!`
  }
  if (evt.type === 'connected') {
    return '已连接'
  }
  return evt.raw
}

watch(() => props.events.length, async () => {
  await nextTick()
  if (logRef.value) {
    logRef.value.scrollTop = logRef.value.scrollHeight
  }
})
</script>

<style scoped>
.gen-progress {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}

.gen-progress__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.gen-progress__stage {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.gen-progress__stage--error {
  color: var(--danger);
}

.gen-progress__timer {
  font-size: 14px;
  color: var(--primary);
  font-family: 'Courier New', monospace;
  font-weight: 600;
}

.gen-progress__bar-wrap {
  width: 100%;
  height: 8px;
  background: #e0e4f0;
  border-radius: 4px;
  overflow: hidden;
}

.gen-progress__bar {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--primary-light));
  border-radius: 4px;
  transition: width 0.3s ease;
}

.gen-progress__bar--error {
  background: linear-gradient(90deg, #e74c3c, #ff6b6b);
}

.gen-progress__pct {
  font-size: 13px;
  color: var(--text-hint);
  text-align: right;
  margin-top: 4px;
  margin-bottom: 16px;
}

.gen-progress__log {
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  background: #f8f9ff;
}

.gen-progress__entry {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
  line-height: 1.5;
}

.gen-progress__entry--error { color: var(--danger); }
.gen-progress__entry--success { color: var(--success); }
.gen-progress__entry--video_result { color: var(--success); }

.gen-progress__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-hint);
  margin-top: 6px;
  flex-shrink: 0;
}

.gen-progress__entry--error .gen-progress__dot { background: var(--danger); }
.gen-progress__entry--success .gen-progress__dot { background: var(--success); }
.gen-progress__entry--video_result .gen-progress__dot { background: var(--success); }

.gen-progress__videos {
  margin-top: 16px;
}

.gen-progress__videos h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.gen-progress__video-item {
  font-size: 13px;
  color: var(--success);
  padding: 4px 0;
}
</style>
