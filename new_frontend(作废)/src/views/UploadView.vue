<template>
  <div class="upload-view">
    <el-card class="upload-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span class="card-title">上传PPT文件</span>
          <span class="card-subtitle" v-if="uploadState === 'idle'">支持 .ppt / .pptx 格式</span>
        </div>
      </template>

      <div v-if="uploadState === 'idle'" class="upload-area">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-exceed="handleExceed"
          :before-upload="beforeUpload"
          accept=".ppt,.pptx"
          drag
          class="ppt-upload"
        >
          <el-icon class="upload-icon" :size="48"><UploadFilled /></el-icon>
          <div class="upload-text">将PPT文件拖拽到此处，或<em>点击上传</em></div>
          <div class="upload-hint">仅支持 .ppt / .pptx 格式文件</div>
        </el-upload>
      </div>

      <div v-if="uploadState !== 'idle'" class="upload-progress">
        <div class="file-info">
          <el-icon :size="20"><Document /></el-icon>
          <span class="file-name">{{ selectedFileName }}</span>
          <span class="file-size" v-if="selectedFileSize">({{ formatFileSize(selectedFileSize) }})</span>
        </div>

        <div v-if="uploadState === 'uploading'" class="state-info">
          <el-icon class="is-loading" :size="16"><Loading /></el-icon>
          <span>正在上传文件...</span>
        </div>

        <div v-if="uploadState === 'converting'" class="state-info">
          <el-icon class="is-loading" :size="16"><Loading /></el-icon>
          <span>正在转换文件...</span>
          <el-progress
            :percentage="conversionProgress"
            :stroke-width="8"
            :color="progressColors"
            class="conversion-progress"
          />
        </div>

        <div v-if="uploadState === 'failed'" class="state-info error">
          <el-alert
            :title="errorMessage"
            type="error"
            show-icon
            :closable="false"
          />
          <el-button type="primary" @click="resetUpload" class="retry-btn">
            重新上传
          </el-button>
        </div>

        <div v-if="uploadState === 'completed'" class="state-info success">
          <el-icon :size="16" color="var(--accent-success)"><CircleCheckFilled /></el-icon>
          <span>转换完成</span>
          <el-button v-if="pdfUrl" text type="primary" @click="openPdf" class="preview-btn">
            <el-icon><View /></el-icon>
            预览文件
          </el-button>
          <el-button text type="primary" @click="resetUpload" class="re-upload-btn">
            重新上传
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card v-if="previewImages.length > 0" class="preview-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span class="card-title">幻灯片预览</span>
          <span class="card-subtitle">共 {{ previewImages.length }} 页</span>
        </div>
      </template>

      <div class="preview-grid">
        <div
          v-for="(img, index) in previewImages"
          :key="index"
          class="preview-item"
          @click="previewIndex = index"
        >
          <el-image
            :src="img"
            fit="contain"
            class="preview-image"
            :preview-src-list="previewImages"
            :initial-index="index"
          />
          <div class="preview-page-number">{{ index + 1 }}</div>
        </div>
      </div>

      <div v-if="pdfUrl" class="pdf-link">
        <el-button type="primary" text @click="openPdf">
          <el-icon><Document /></el-icon>
          查看PDF文件
        </el-button>
      </div>
    </el-card>

    <div class="navigation-footer">
      <el-button
        type="primary"
        size="large"
        :disabled="uploadState !== 'completed'"
        @click="goToScript"
        class="next-btn"
      >
        下一步：讲稿编辑
        <el-icon class="el-icon--right"><ArrowRight /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkflowStore } from '@/stores/workflow'
import { uploadFile, startConversion, getConversionStatus } from '@/api'
import { UploadFilled, Document, Loading, CircleCheckFilled, ArrowRight, View } from '@element-plus/icons-vue'
import type { UploadFile, UploadInstance, UploadRawFile } from 'element-plus'
import { ElMessage } from 'element-plus'

const router = useRouter()
const workflowStore = useWorkflowStore()

type UploadState = 'idle' | 'uploading' | 'converting' | 'completed' | 'failed'

const uploadState = ref<UploadState>('idle')
const selectedFileName = ref('')
const selectedFileSize = ref(0)
const conversionProgress = ref(0)
const errorMessage = ref('')
const pdfUrl = ref('')
const previewImages = ref<string[]>([])
const previewIndex = ref(0)
const uploadRef = ref<UploadInstance>()

const progressColors = [
  { color: '#3b82f6', percentage: 60 },
  { color: '#10b981', percentage: 100 },
]

let pollTimer: ReturnType<typeof setInterval> | null = null

const hasExistingData = computed(() => !!workflowStore.pdfPath && workflowStore.imageUrls.length > 0)

if (hasExistingData.value) {
  uploadState.value = 'completed'
  selectedFileName.value = workflowStore.fileName
  pdfUrl.value = workflowStore.pdfPath
  previewImages.value = [...workflowStore.imageUrls]
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function beforeUpload(rawFile: UploadRawFile): boolean {
  const validTypes = [
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  ]
  const validExtensions = ['.ppt', '.pptx']
  const fileName = rawFile.name.toLowerCase()
  const hasValidExt = validExtensions.some(ext => fileName.endsWith(ext))

  if (!validTypes.includes(rawFile.type) && !hasValidExt) {
    ElMessage.error('仅支持 .ppt / .pptx 格式文件')
    return false
  }
  return true
}

function handleFileChange(uploadFile: UploadFile) {
  if (!uploadFile.raw) return

  const raw = uploadFile.raw
  const fileName = raw.name.toLowerCase()
  if (!fileName.endsWith('.ppt') && !fileName.endsWith('.pptx')) {
    ElMessage.error('仅支持 .ppt / .pptx 格式文件')
    uploadRef.value?.clearFiles()
    return
  }

  selectedFileName.value = raw.name
  selectedFileSize.value = raw.size
  startUploadFlow(raw)
}

function handleExceed() {
  ElMessage.warning('只能上传一个文件，请先移除已选文件')
}

async function startUploadFlow(file: File) {
  try {
    uploadState.value = 'uploading'
    conversionProgress.value = 0
    errorMessage.value = ''

    const uploadRes = await uploadFile(file) as any
    if (uploadRes.code !== 200 && uploadRes.code !== 0) {
      throw new Error(uploadRes.message || '上传失败')
    }

    const uploadData = uploadRes.data
    const file_id = uploadData.file_id
    const file_path = uploadData.file_path || uploadData.filename
    const file_name = uploadData.filename || uploadData.file_name

    uploadState.value = 'converting'

    const convertRes = await startConversion(file_id) as any
    if (convertRes.code !== 200 && convertRes.code !== 0) {
      throw new Error(convertRes.message || '转换启动失败')
    }

    const { task_id } = convertRes.data

    await pollConversionStatus(task_id, file_id, file_path, file_name, file)
  } catch (err: any) {
    uploadState.value = 'failed'
    errorMessage.value = err?.response?.data?.message || err?.message || '操作失败，请重试'
  }
}

function pollConversionStatus(
  taskId: string,
  fileId: string,
  filePath: string,
  fileName: string,
  originalFile: File
): Promise<void> {
  return new Promise((resolve, reject) => {
    pollTimer = setInterval(async () => {
      try {
        const res = await getConversionStatus(taskId) as any
        const status = res.data

        conversionProgress.value = Math.min(status.progress, 100)

        if (status.status === 'completed') {
          stopPolling()

          pdfUrl.value = status.pdf_url || ''
          previewImages.value = status.image_urls || []

          const pdfPathForBackend = (status.pdf_url || '').replace(/^\//, '')

          workflowStore.setUploadData({
            fileId,
            filePath,
            fileName,
            pdfPath: pdfPathForBackend,
            imageUrls: status.image_urls || [],
            originalFile,
          })

          uploadState.value = 'completed'
          resolve()
        } else if (status.status === 'failed') {
          stopPolling()
          reject(new Error(status.message || status.error || '转换失败'))
        }
      } catch (err: any) {
        stopPolling()
        reject(err)
      }
    }, 2000)
  })
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function resetUpload() {
  stopPolling()
  uploadState.value = 'idle'
  selectedFileName.value = ''
  selectedFileSize.value = 0
  conversionProgress.value = 0
  errorMessage.value = ''
  pdfUrl.value = ''
  previewImages.value = []
  uploadRef.value?.clearFiles()
}

function openPdf() {
  if (pdfUrl.value) {
    window.open(pdfUrl.value, '_blank')
  }
}

function goToScript() {
  workflowStore.setStep(1)
  router.push('/script')
}

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped lang="scss">
.upload-view {
  max-width: 900px;
  margin: 0 auto;
}

.upload-card,
.preview-card {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  margin-bottom: 20px;

  :deep(.el-card__header) {
    border-bottom: 1px solid var(--border-color);
    padding: 16px 20px;
  }

  :deep(.el-card__body) {
    padding: 20px;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
}

.upload-area {
  :deep(.el-upload) {
    width: 100%;
  }

  :deep(.el-upload-dragger) {
    background-color: var(--bg-primary);
    border: 2px dashed var(--border-color);
    border-radius: 8px;
    padding: 48px 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    transition: border-color 0.3s ease;

    &:hover {
      border-color: var(--accent-primary);
    }
  }

  :deep(.el-upload-list) {
    display: none;
  }
}

.upload-icon {
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.upload-text {
  font-size: 14px;
  color: var(--text-secondary);

  em {
    color: var(--accent-primary);
    font-style: normal;
  }
}

.upload-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
  opacity: 0.7;
}

.upload-progress {
  .file-info {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background-color: var(--bg-primary);
    border-radius: 6px;
    margin-bottom: 16px;
  }

  .file-name {
    font-size: 14px;
    color: var(--text-primary);
    font-weight: 500;
  }

  .file-size {
    font-size: 12px;
    color: var(--text-secondary);
  }
}

.state-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-secondary);

  &.success {
    color: var(--accent-success);
  }

  &.error {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
}

.conversion-progress {
  margin-top: 12px;
  width: 100%;

  :deep(.el-progress-bar__outer) {
    background-color: var(--bg-primary);
  }
}

.retry-btn,
.re-upload-btn {
  margin-top: 4px;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
}

.preview-item {
  position: relative;
  cursor: pointer;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  transition: border-color 0.3s ease, transform 0.2s ease;

  &:hover {
    border-color: var(--accent-primary);
    transform: translateY(-2px);
  }
}

.preview-image {
  width: 100%;
  height: 120px;
  display: block;

  :deep(.el-image__inner) {
    object-fit: contain;
  }
}

.preview-page-number {
  text-align: center;
  padding: 6px 0;
  font-size: 12px;
  color: var(--text-secondary);
  border-top: 1px solid var(--border-color);
}

.pdf-link {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);

  :deep(.el-button) {
    font-size: 14px;
  }
}

.navigation-footer {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0;
}

.next-btn {
  min-width: 180px;
  font-size: 15px;
}
</style>
