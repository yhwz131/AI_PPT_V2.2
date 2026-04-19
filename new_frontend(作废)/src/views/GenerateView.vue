<template>
  <div class="generate-view">
    <div v-if="!generationStore.isGenerating && !generationStore.isCompleted && !generationStore.isFailed" class="config-section">
      <el-card class="summary-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="card-title">生成配置确认</span>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="文件名称">
            {{ workflowStore.fileName || '未设置' }}
          </el-descriptions-item>
          <el-descriptions-item label="数字人">
            {{ workflowStore.selectedHuman?.name || '未选择' }}
          </el-descriptions-item>
          <el-descriptions-item label="模板位置">
            {{ workflowStore.template }}
          </el-descriptions-item>
          <el-descriptions-item label="欢迎语">
            {{ workflowStore.welcomeText || '无' }}
          </el-descriptions-item>
          <el-descriptions-item label="BGM模式">
            <el-tag size="small" :type="bgmTagType">{{ bgmModeLabel }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="情感模式">
            {{ emoMethodLabel }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="file-name-input">
          <label class="input-label">输出文件名</label>
          <el-input
            v-model="outputFileName"
            placeholder="请输入输出文件名"
            clearable
          />
        </div>

        <div class="action-buttons">
          <el-button @click="goBack" size="large">
            上一步
          </el-button>
          <el-button
            type="primary"
            size="large"
            @click="handleStartGeneration"
            :disabled="!canStartGeneration"
          >
            开始生成
          </el-button>
        </div>
      </el-card>
    </div>

    <div v-if="generationStore.isGenerating" class="progress-section">
      <el-card class="progress-card" shadow="hover">
        <div class="progress-display">
          <div class="progress-circle-wrapper">
            <el-progress
              type="circle"
              :percentage="generationStore.progress"
              :width="180"
              :stroke-width="10"
              :color="progressColor"
            >
              <template #default>
                <div class="progress-inner">
                  <span class="progress-percent">{{ generationStore.progress }}%</span>
                  <span class="progress-label">总体进度</span>
                </div>
              </template>
            </el-progress>
          </div>

          <div class="progress-info">
            <div class="stage-message">
              <el-icon class="stage-icon" :size="20"><Loading /></el-icon>
              <span>{{ stageLabel }}</span>
            </div>
            <div v-if="generationStore.totalVideos > 0" class="video-counter">
              <el-tag type="info" effect="plain">
                视频 {{ generationStore.currentVideo }} / {{ generationStore.totalVideos }}
              </el-tag>
            </div>
            <div v-if="generationStore.currentStageProgress > 0" class="stage-progress">
              <el-progress
                :percentage="generationStore.currentStageProgress"
                :stroke-width="6"
                :color="progressColor"
                :show-text="true"
              />
            </div>
          </div>
        </div>

        <div class="cancel-action">
          <el-button
            type="danger"
            size="large"
            @click="handleCancel"
          >
            取消生成
          </el-button>
        </div>
      </el-card>

      <div v-if="generationStore.videoResults.length > 0" class="results-during-generation">
        <h3 class="section-title">视频生成进度</h3>
        <div class="video-results-grid">
          <el-card
            v-for="video in generationStore.videoResults"
            :key="video.video_index"
            class="video-result-card"
            :class="{ 'is-completed': video.status === 'completed', 'is-failed': video.status === 'failed' }"
            shadow="hover"
          >
            <div class="result-header">
              <span class="video-index">视频 #{{ video.video_index }}</span>
              <el-tag
                :type="video.status === 'completed' ? 'success' : 'danger'"
                size="small"
              >
                {{ video.status === 'completed' ? '已完成' : '失败' }}
              </el-tag>
            </div>
            <div v-if="video.content" class="result-content">{{ video.content }}</div>
            <div v-if="video.status === 'completed'" class="result-check">
              <el-icon color="var(--accent-success)" :size="24"><CircleCheckFilled /></el-icon>
            </div>
            <div v-if="video.status === 'failed' && video.error" class="result-error">
              {{ video.error }}
            </div>
          </el-card>
        </div>
      </div>
    </div>

    <div v-if="generationStore.isCompleted" class="completion-section">
      <el-result
        icon="success"
        title="视频生成完成！"
        :sub-title="`成功: ${generationStore.completedCount} 个 / 失败: ${generationStore.failedCount} 个`"
      />

      <el-card v-if="videoSource" class="player-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="card-title">视频预览</span>
          </div>
        </template>
        <VideoPlayer :src="videoSource" />
      </el-card>

      <div class="completion-actions">
        <el-button
          v-if="generationStore.finalResult?.video_path"
          type="primary"
          size="large"
          @click="handleDownload"
        >
          <el-icon><Download /></el-icon>
          下载视频
        </el-button>
        <el-button size="large" @click="handleReset">
          重新生成
        </el-button>
        <el-button size="large" @click="goToLibrary">
          前往视频库
        </el-button>
      </div>
    </div>

    <div v-if="generationStore.isFailed" class="error-section">
      <el-result
        icon="error"
        title="生成失败"
        :sub-title="generationStore.errorMessage || '生成过程中发生错误'"
      />
      <el-alert
        v-if="generationStore.errorMessage"
        :title="generationStore.errorMessage"
        type="error"
        show-icon
        :closable="false"
        class="error-alert"
      />
      <div class="error-actions">
        <el-button type="primary" size="large" @click="handleRetry">
          重试
        </el-button>
        <el-button size="large" @click="handleReset">
          重新配置
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkflowStore } from '@/stores/workflow'
import { useGenerationStore } from '@/stores/generation'
import { consumeSSEStream } from '@/utils/sse'
import VideoPlayer from '@/components/VideoPlayer.vue'
import { Loading, CircleCheckFilled, Download } from '@element-plus/icons-vue'

const router = useRouter()
const workflowStore = useWorkflowStore()
const generationStore = useGenerationStore()

const outputFileName = ref(workflowStore.outputFileName || workflowStore.fileName)

const stageLabelMap: Record<string, string> = {
  parse_script: '解析讲稿',
  prepare_files: '准备文件',
  audio_generation: '生成音频',
  process_audio: '处理音频',
  video_generation_start: '开始生成视频',
  convert_pdf: '转换背景图片',
  video_generation: '生成数字人视频',
  video_generation_complete: '视频生成完成',
  video_merge: '合并视频',
  video_merge_complete: '视频合并完成',
  video_conversion: '视频切片转换',
  video_conversion_completed: '视频切片完成',
}

const stageLabel = computed(() => {
  if (generationStore.stageMessage) return generationStore.stageMessage
  if (generationStore.stage) return stageLabelMap[generationStore.stage] || generationStore.stage
  return '准备中...'
})

const bgmModeLabel = computed(() => {
  const map: Record<string, string> = { default: '默认', custom: '自定义', none: '无' }
  return map[workflowStore.bgmMode] || workflowStore.bgmMode
})

const bgmTagType = computed(() => {
  const map: Record<string, string> = { default: '', custom: 'warning', none: 'info' }
  return map[workflowStore.bgmMode] || ''
})

const emoMethodLabel = computed(() => {
  const map: Record<number, string> = { 0: '默认', 2: '向量控制', 3: '文本控制' }
  return map[workflowStore.emoControlMethod] || '默认'
})

const canStartGeneration = computed(() => {
  return !!workflowStore.scriptContent && !!workflowStore.selectedHuman && !!workflowStore.pdfPath
})

const progressColor = computed(() => {
  if (generationStore.progress >= 100) return 'var(--accent-success)'
  if (generationStore.progress >= 50) return 'var(--accent-blue)'
  return 'var(--accent-primary)'
})

const videoSource = computed(() => {
  if (!generationStore.finalResult) return ''
  return generationStore.finalResult.hls_info?.m3u8_url || generationStore.finalResult.video_path || ''
})

function goBack() {
  router.push('/template')
}

function goToLibrary() {
  router.push('/library')
}

async function handleStartGeneration() {
  workflowStore.outputFileName = outputFileName.value
  generationStore.startGeneration()

  const callbacks = {
    onConnected: (data: { task_id: string }) => generationStore.onConnected(data),
    onProgress: (data: any) => generationStore.onProgress(data),
    onVideoResult: (data: any) => generationStore.onVideoResult(data),
    onSuccess: (data: any) => generationStore.onSuccess(data),
    onError: (data: { message: string }) => generationStore.onError(data),
    onEnd: () => {},
  }

  try {
    await consumeSSEStream(
      workflowStore.buildGenerationRequest(),
      callbacks,
      generationStore.abortController?.signal
    )
  } catch (err: any) {
    if (err.name !== 'AbortError') {
      generationStore.onError({ message: err.message || '连接失败，请重试' })
    }
  }
}

function handleCancel() {
  generationStore.cancelGeneration()
}

function handleReset() {
  generationStore.reset()
}

function handleRetry() {
  generationStore.reset()
  handleStartGeneration()
}

function handleDownload() {
  if (!generationStore.finalResult?.video_path) return
  const link = document.createElement('a')
  link.href = generationStore.finalResult.video_path
  link.download = outputFileName.value || 'video'
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
</script>

<style scoped lang="scss">
.generate-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}

.config-section {
  .summary-card {
    background-color: var(--bg-secondary);
    border-color: var(--border-color);
  }

  .file-name-input {
    margin-top: 24px;

    .input-label {
      display: block;
      margin-bottom: 8px;
      font-size: 14px;
      color: var(--text-secondary);
    }
  }

  .action-buttons {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.progress-section {
  .progress-card {
    background-color: var(--bg-secondary);
    border-color: var(--border-color);
  }

  .progress-display {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 32px;
    padding: 24px 0;
  }

  .progress-circle-wrapper {
    position: relative;
  }

  .progress-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .progress-percent {
    font-size: 32px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .progress-label {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .progress-info {
    width: 100%;
    max-width: 500px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }

  .stage-message {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    color: var(--text-primary);
    font-weight: 500;

    .stage-icon {
      animation: spin 1.5s linear infinite;
      color: var(--accent-primary);
    }
  }

  .video-counter {
    display: flex;
    justify-content: center;
  }

  .stage-progress {
    width: 100%;
  }

  .cancel-action {
    display: flex;
    justify-content: center;
    margin-top: 16px;
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.results-during-generation {
  margin-top: 24px;

  .section-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 16px;
  }
}

.video-results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.video-result-card {
  background-color: var(--bg-secondary);
  border-color: var(--border-color);
  transition: border-color 0.3s ease;

  &.is-completed {
    border-color: var(--accent-success);
  }

  &.is-failed {
    border-color: var(--accent-error);
  }

  .result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .video-index {
    font-weight: 600;
    color: var(--text-primary);
  }

  .result-content {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .result-check {
    display: flex;
    justify-content: flex-end;
    margin-top: 8px;
  }

  .result-error {
    margin-top: 8px;
    font-size: 13px;
    color: var(--accent-error);
  }
}

.completion-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;

  .player-card {
    width: 100%;
    background-color: var(--bg-secondary);
    border-color: var(--border-color);
  }

  .completion-actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    justify-content: center;
  }
}

.error-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;

  .error-alert {
    width: 100%;
    max-width: 600px;
  }

  .error-actions {
    display: flex;
    gap: 12px;
  }
}
</style>
