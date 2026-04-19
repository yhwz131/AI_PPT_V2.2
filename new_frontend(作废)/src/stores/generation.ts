import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SSEProgressEvent, SSEVideoResultEvent, SSESuccessEvent } from '@/types'

export const useGenerationStore = defineStore('generation', () => {
  const isGenerating = ref(false)
  const taskId = ref('')
  const stage = ref('')
  const stageMessage = ref('')
  const progress = ref(0)
  const currentStageProgress = ref(0)
  const currentVideo = ref(0)
  const totalVideos = ref(0)
  const videoResults = ref<SSEVideoResultEvent[]>([])
  const finalResult = ref<SSESuccessEvent | null>(null)
  const errorMessage = ref('')
  const isCompleted = ref(false)
  const isFailed = ref(false)
  const abortController = ref<AbortController | null>(null)

  const completedCount = computed(() =>
    videoResults.value.filter(v => v.status === 'completed').length
  )

  const failedCount = computed(() =>
    videoResults.value.filter(v => v.status === 'failed').length
  )

  function startGeneration() {
    isGenerating.value = true
    isCompleted.value = false
    isFailed.value = false
    taskId.value = ''
    stage.value = ''
    stageMessage.value = '准备开始生成...'
    progress.value = 0
    currentStageProgress.value = 0
    currentVideo.value = 0
    totalVideos.value = 0
    videoResults.value = []
    finalResult.value = null
    errorMessage.value = ''
    abortController.value = new AbortController()
  }

  function onConnected(data: { task_id: string }) {
    taskId.value = data.task_id
    stageMessage.value = '已连接，开始处理...'
  }

  function onProgress(data: SSEProgressEvent) {
    stage.value = data.stage
    stageMessage.value = data.message
    progress.value = data.progress
    currentStageProgress.value = data.current_stage_progress || 0
    if (data.current !== undefined) currentVideo.value = data.current
    if (data.total !== undefined) totalVideos.value = data.total
  }

  function onVideoResult(data: SSEVideoResultEvent) {
    videoResults.value.push(data)
  }

  function onSuccess(data: SSESuccessEvent) {
    finalResult.value = data
    isCompleted.value = true
    isGenerating.value = false
    progress.value = 100
    stageMessage.value = '视频生成完成！'
  }

  function onError(data: { message: string }) {
    errorMessage.value = data.message
    isFailed.value = true
    isGenerating.value = false
  }

  function cancelGeneration() {
    abortController.value?.abort()
    isGenerating.value = false
    stageMessage.value = '已取消生成'
  }

  function reset() {
    isGenerating.value = false
    taskId.value = ''
    stage.value = ''
    stageMessage.value = ''
    progress.value = 0
    currentStageProgress.value = 0
    currentVideo.value = 0
    totalVideos.value = 0
    videoResults.value = []
    finalResult.value = null
    errorMessage.value = ''
    isCompleted.value = false
    isFailed.value = false
    abortController.value = null
  }

  return {
    isGenerating, taskId, stage, stageMessage, progress,
    currentStageProgress, currentVideo, totalVideos,
    videoResults, finalResult, errorMessage,
    isCompleted, isFailed, abortController,
    completedCount, failedCount,
    startGeneration, onConnected, onProgress, onVideoResult,
    onSuccess, onError, cancelGeneration, reset,
  }
})
