<template>
  <div class="upload-page">
    <Transition name="toast-fade">
      <div v-if="toastMsg" class="upload-page__toast">{{ toastMsg }}</div>
    </Transition>

    <header class="upload-page__header">
      <router-link to="/" class="upload-page__back">← 返回首页</router-link>
      <h1 class="upload-page__title">AI数字人视频生成</h1>
    </header>

    <StepNav :steps="['添加讲稿', '选择模板', '生成视频']" :current="step" @go="goToStep" />

    <!-- Step 0: 添加讲稿 -->
    <div v-if="step === 0" class="upload-page__section">
      <FileDropZone
        accept=".ppt,.pptx"
        :disabled="uploading"
        @file="onFileSelected"
        @remove="resetFile"
      />

      <div v-if="uploading" class="upload-page__status">
        <div class="upload-page__spinner" />
        <span>{{ uploadStatus }}</span>
      </div>

      <div v-if="pdfReady" class="upload-page__pdf-preview">
        <h4>PDF预览</h4>
        <div class="upload-page__pdf-frame">
          <iframe :src="pdfPreviewUrl" />
        </div>
      </div>

      <div v-if="pdfReady" class="upload-page__script-gen">
        <StyleSelector v-model="scriptStyle" />
        <button
          class="upload-page__btn upload-page__btn--primary"
          :disabled="generatingScript"
          @click="doGenerateScript"
        >
          {{ generatingScript ? '生成中...' : '生成解说稿' }}
        </button>
      </div>

      <ScriptEditor
        v-if="scriptContent"
        :content="scriptContent"
        @update="onScriptUpdate"
      />

      <div v-if="scriptContent" class="upload-page__actions">
        <button class="upload-page__btn upload-page__btn--primary" @click="step = 1">
          下一步 →
        </button>
      </div>
    </div>

    <!-- Step 1: 选择模板 -->
    <div v-if="step === 1" class="upload-page__section">
      <TemplateSelector v-model="template" />

      <AvatarSelector
        ref="avatarSelectorRef"
        :selected="selectedAvatar"
        @select="selectedAvatar = $event"
        @delete="onDeleteAvatar"
        @addCustom="showCustomUpload = true"
      />

      <WelcomeTextConfig
        :welcome-text="welcomeText"
        @update:welcome-text="welcomeText = $event"
      />

      <BgmConfig
        :mode="bgmMode"
        :bgm-path="bgmPath"
        @update:mode="bgmMode = $event"
        @update:bgm-path="bgmPath = $event"
      />

      <EmotionConfig
        ref="emotionConfigRef"
        :method="emoMethod"
        :emo-vec="emoVec"
        :emo-text="emoText"
        @update:method="emoMethod = $event"
        @update:emo-vec="emoVec = $event"
        @update:emo-text="emoText = $event"
      />

      <div class="upload-page__actions">
        <button class="upload-page__btn" @click="step = 0">← 上一步</button>
        <button
          class="upload-page__btn upload-page__btn--primary"
          :disabled="!selectedAvatar || emoHasError"
          @click="goToStep2"
        >
          下一步 →
        </button>
      </div>

      <!-- 自定义数字人上传弹窗 -->
      <Teleport to="body">
        <div v-if="showCustomUpload" class="modal-overlay" @click.self="showCustomUpload = false">
          <div class="modal modal--sm">
            <div class="modal__header">
              <h3>添加自定义数字人</h3>
              <button class="modal__close" @click="showCustomUpload = false">✕</button>
            </div>
            <div class="modal__body">
              <div class="form-field">
                <label>名称</label>
                <input v-model="customDH.name" placeholder="数字人名称" />
              </div>
              <div class="form-field">
                <label>简介</label>
                <input v-model="customDH.brief" placeholder="简短描述" />
              </div>
              <div class="form-field">
                <label>头像图片</label>
                <input type="file" accept="image/*" @change="customDH.avatar = ($event.target as HTMLInputElement).files?.[0] || null" />
              </div>
              <div class="form-field">
                <label>音频</label>
                <input type="file" accept="audio/*" @change="customDH.audio = ($event.target as HTMLInputElement).files?.[0] || null" />
              </div>
              <div class="form-field">
                <label>视频</label>
                <input type="file" accept="video/*" @change="customDH.video = ($event.target as HTMLInputElement).files?.[0] || null" />
              </div>
            </div>
            <div class="modal__footer">
              <button
                class="upload-page__btn upload-page__btn--primary"
                :disabled="customUploading"
                @click="doUploadCustom"
              >
                {{ customUploading ? '上传中...' : '上传' }}
              </button>
            </div>
          </div>
        </div>
      </Teleport>
    </div>

    <!-- Step 2: 生成视频 -->
    <div v-if="step === 2" class="upload-page__section">
      <div v-if="!generating && !generationDone && !generationError" class="upload-page__gen-start">
        <div class="config-preview">
          <h4 class="config-preview__title">配置预览</h4>
          <div class="config-preview__grid">
            <div class="config-preview__item">
              <span class="config-preview__label">PPT文件</span>
              <span class="config-preview__value">{{ fileName || '未选择' }}</span>
            </div>
            <div class="config-preview__item">
              <span class="config-preview__label">解说风格</span>
              <span class="config-preview__value">{{ styleLabel }}</span>
            </div>
            <div class="config-preview__item">
              <span class="config-preview__label">数字人</span>
              <span class="config-preview__value">
                <img v-if="selectedAvatar" :src="staticUrl(selectedAvatar.image)" class="config-preview__avatar" />
                {{ selectedAvatar?.name || '未选择' }}
              </span>
            </div>
            <div class="config-preview__item">
              <span class="config-preview__label">位置模板</span>
              <span class="config-preview__value">{{ templateLabel }}</span>
            </div>
            <div class="config-preview__item">
              <span class="config-preview__label">欢迎字幕</span>
              <span class="config-preview__value">{{ welcomeText || '默认' }}</span>
            </div>
            <div class="config-preview__item">
              <span class="config-preview__label">背景音乐</span>
              <span class="config-preview__value">{{ bgmLabel }}</span>
            </div>
            <div class="config-preview__item">
              <span class="config-preview__label">情感模式</span>
              <span class="config-preview__value">{{ emoLabel }}</span>
            </div>
            <div class="config-preview__item config-preview__item--full">
              <span class="config-preview__label">解说稿</span>
              <span class="config-preview__value config-preview__script">{{ scriptPreview }}</span>
            </div>
          </div>
        </div>
        <button class="upload-page__btn upload-page__btn--primary upload-page__btn--lg" @click="startGeneration">
          开始生成
        </button>
      </div>

      <GenerationProgress
        v-if="generating || generationDone || generationError"
        :events="sseState.events.value"
        :timer="timerState.display.value"
      />

      <div v-if="generationDone" class="upload-page__result">
        <h4>生成完成</h4>
        <video v-if="finalVideoUrl" ref="resultVideoRef" controls class="upload-page__result-video" />
        <div class="upload-page__actions">
          <button
            v-if="finalDownloadUrl"
            class="upload-page__btn upload-page__btn--primary"
            @click="doDownloadResult"
          >下载视频</button>
          <router-link to="/videos" class="upload-page__btn">去视频库</router-link>
          <button class="upload-page__btn" @click="resetAll">重新生成</button>
        </div>
      </div>

      <div v-if="generating" class="upload-page__actions">
        <button class="upload-page__btn upload-page__btn--danger" @click="cancelGeneration">取消</button>
      </div>

      <div v-if="generationError && !generating" class="upload-page__actions">
        <button class="upload-page__btn" @click="backFromError">← 返回修改</button>
        <button class="upload-page__btn upload-page__btn--primary" @click="retryGeneration">重新生成</button>
      </div>

      <div v-if="!generating && !generationDone && !generationError" class="upload-page__actions">
        <button class="upload-page__btn" @click="step = 1">← 上一步</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Hls from 'hls.js'
import StepNav from '../components/StepNav.vue'
import FileDropZone from '../components/FileDropZone.vue'
import ScriptEditor from '../components/ScriptEditor.vue'
import StyleSelector from '../components/StyleSelector.vue'
import TemplateSelector from '../components/TemplateSelector.vue'
import AvatarSelector from '../components/AvatarSelector.vue'
import BgmConfig from '../components/BgmConfig.vue'
import WelcomeTextConfig from '../components/WelcomeTextConfig.vue'
import EmotionConfig from '../components/EmotionConfig.vue'
import GenerationProgress from '../components/GenerationProgress.vue'
import { uploadPPT, generateScript } from '../api/files'
import { pollConversionTask } from '../api/conversion'
import { createTask, checkTaskExists, uploadCustomDigitalHuman, deleteDigitalHuman, type DigitalHuman, type GenerationRequest } from '../api/digitalHuman'
import { useSSE } from '../composables/useSSE'
import { useTimer } from '../composables/useTimer'
import { staticUrl } from '../api/client'

const router = useRouter()
const route = useRoute()
const step = ref(0)

// ===== Toast =====
const toastMsg = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(msg: string, duration = 1200) {
  toastMsg.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMsg.value = '' }, duration)
}

// ===== Step 0 state =====
const uploading = ref(false)
const uploadStatus = ref('')
const pdfReady = ref(false)
const pdfPreviewUrl = ref('')
const pdfPath = ref('')
const uploadedFile = ref<File | null>(null)
const scriptStyle = ref('normal')
const generatingScript = ref(false)
const scriptContent = ref('')
const fileName = ref('')

async function onFileSelected(file: File) {
  uploadedFile.value = file
  fileName.value = file.name
  uploading.value = true
  uploadStatus.value = '上传并转换中...'

  try {
    const res = await uploadPPT(file)
    const taskId = res.data.task_id
    uploadStatus.value = 'PPT转换中，请稍候...'

    const conv = await pollConversionTask(taskId)
    pdfPath.value = conv.pdf_url || conv.download_url || ''
    pdfPreviewUrl.value = staticUrl(pdfPath.value)
    pdfReady.value = true
    uploadStatus.value = ''
  } catch (err: any) {
    alert('上传/转换失败: ' + err.message)
    uploadStatus.value = ''
  } finally {
    uploading.value = false
  }
}

function resetFile() {
  uploadedFile.value = null
  pdfReady.value = false
  pdfPreviewUrl.value = ''
  pdfPath.value = ''
  scriptContent.value = ''
  fileName.value = ''
}

async function doGenerateScript() {
  if (!uploadedFile.value || !pdfPath.value) return
  generatingScript.value = true
  try {
    const res = await generateScript(uploadedFile.value, pdfPath.value, scriptStyle.value)
    scriptContent.value = res.data.script
    if (res.data.pdf_path) pdfPath.value = res.data.pdf_path
    showToast('解说稿生成完成')
    await nextTick()
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
  } catch (err: any) {
    alert('生成解说稿失败: ' + err.message)
  } finally {
    generatingScript.value = false
  }
}

function onScriptUpdate(html: string) {
  scriptContent.value = html
}

// ===== Step 1 state =====
const template = ref('bottom-left')
const selectedAvatar = ref<DigitalHuman | null>(null)
const welcomeText = ref('')
const bgmMode = ref('default')
const bgmPath = ref('')
const emoMethod = ref('natural')
const emoVec = ref('0,0,0,0,0,0,0,1')
const emoText = ref('')
const showCustomUpload = ref(false)
const customUploading = ref(false)
const customDH = ref<{ name: string; brief: string; avatar: File | null; audio: File | null; video: File | null }>({
  name: '', brief: '', avatar: null, audio: null, video: null
})
const avatarSelectorRef = ref<InstanceType<typeof AvatarSelector> | null>(null)
const emotionConfigRef = ref<InstanceType<typeof EmotionConfig> | null>(null)

const emoHasError = computed(() => {
  if (emoMethod.value !== 'vector') return false
  const vals = emoVec.value.split(',').map(Number)
  return vals.some(v => v > 1.2) || vals.reduce((a, b) => a + b, 0) > 1.5
})

function goToStep2() {
  if (emoHasError.value) {
    alert('请先修正TTS情感向量：总和不能超过1.5，单个值不能超过1.2')
    return
  }
  step.value = 2
}

async function doUploadCustom() {
  const { name, brief, avatar, audio, video } = customDH.value
  if (!name || !avatar || !audio || !video) {
    alert('请填写完整信息')
    return
  }
  customUploading.value = true
  try {
    await uploadCustomDigitalHuman(name, brief, avatar, audio, video)
    showCustomUpload.value = false
    customDH.value = { name: '', brief: '', avatar: null, audio: null, video: null }
    avatarSelectorRef.value?.reload()
  } catch (err: any) {
    alert('上传失败: ' + err.message)
  } finally {
    customUploading.value = false
  }
}

async function onDeleteAvatar(name: string) {
  if (!confirm(`确定删除数字人 "${name}"？`)) return
  try {
    await deleteDigitalHuman(name)
    if (selectedAvatar.value?.name === name) selectedAvatar.value = null
    avatarSelectorRef.value?.reload()
  } catch (err: any) {
    alert('删除失败: ' + err.message)
  }
}

// ===== Config preview computed =====
const styleLabel = computed(() => {
  const map: Record<string, string> = { brief: '简洁', normal: '正常', professional: '专业' }
  return map[scriptStyle.value] || scriptStyle.value
})

const templateLabel = computed(() => {
  const map: Record<string, string> = {
    'bottom-left': '左下', 'top-left': '左上', 'bottom-right': '右下',
    'top-right': '右上', center: '居中', none: '无'
  }
  return map[template.value] || template.value
})

const bgmLabel = computed(() => {
  const map: Record<string, string> = { default: '默认', custom: '自定义', none: '无' }
  return map[bgmMode.value] || bgmMode.value
})

const emoLabel = computed(() => {
  const map: Record<string, string> = { natural: '自然', vector: '向量(8维)', text: '文本' }
  return map[emoMethod.value] || emoMethod.value
})

const scriptPreview = computed(() => {
  const plain = scriptContent.value.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
  return plain.length > 120 ? plain.slice(0, 120) + '…' : plain
})

// ===== Step 2 state =====
const generating = ref(false)
const generationDone = ref(false)
const generationError = ref(false)
const finalVideoUrl = ref('')
const finalDownloadUrl = ref('')
const downloadFileName = ref('')
const resultVideoRef = ref<HTMLVideoElement | null>(null)
let resultHls: Hls | null = null

const TASK_STORAGE_KEY = 'ppttalk_active_task'

const sseState = useSSE()
const timerState = useTimer()

function saveTaskToStorage(taskId: string) {
  const payload = JSON.stringify({
    taskId,
    startTime: Date.now(),
    fileName: fileName.value,
    step: 2,
  })
  try {
    localStorage.setItem(TASK_STORAGE_KEY, payload)
    sessionStorage.setItem(TASK_STORAGE_KEY, payload)
  } catch {
    /* 隐私模式等 */
  }
}

function clearTaskStorage() {
  try {
    localStorage.removeItem(TASK_STORAGE_KEY)
    sessionStorage.removeItem(TASK_STORAGE_KEY)
  } catch {
    /* ignore */
  }
  if (route.query.task) {
    router.replace({ path: '/upload', query: {} })
  }
}

async function tryResumeTask() {
  const qTask = typeof route.query.task === 'string' ? route.query.task.trim() : ''
  let raw: string | null = null
  try {
    raw = sessionStorage.getItem(TASK_STORAGE_KEY) || localStorage.getItem(TASK_STORAGE_KEY)
  } catch {
    raw = null
  }

  let taskId = qTask
  let saved: { taskId?: string; startTime?: number; fileName?: string } | null = null
  if (raw) {
    try {
      saved = JSON.parse(raw)
    } catch {
      saved = null
    }
  }
  if (!taskId && saved?.taskId) taskId = saved.taskId
  if (!taskId) return

  if (saved?.startTime && Date.now() - saved.startTime > 24 * 3600 * 1000) {
    clearTaskStorage()
    return
  }

  const check = await checkTaskExists(taskId)
  if (check.exists === 'gone') {
    clearTaskStorage()
    showToast('任务已结束或已过期，请重新生成')
    return
  }

  step.value = 2
  fileName.value = saved?.fileName || ''

  // 恢复计时器的起始时间：优先用本地存储，回退到后端 created_at（秒→毫秒）
  const resumeStartMs = saved?.startTime || (check.created_at ? check.created_at * 1000 : 0)

  if (check.status === 'completed' || check.status === 'failed') {
    generating.value = false
    if (resumeStartMs) {
      timerState.startFrom(resumeStartMs)
      timerState.stop()
    }
    clearTaskStorage()
    const results = check.results as Record<string, any> | undefined
    if (results?.success) {
      generationDone.value = true
      const m3u8 = results.hls_info?.m3u8_url || results.video_url
      const mp4 = results.video_path
      if (m3u8) {
        finalVideoUrl.value = m3u8
        nextTick(() => initResultPlayer(m3u8))
      }
      if (mp4) {
        finalDownloadUrl.value = mp4 as string
        downloadFileName.value = (mp4 as string).split('/').pop() || 'video.mp4'
      }
    } else {
      generationError.value = true
    }
    sseState.connect(taskId)
    return
  }

  generating.value = true
  generationDone.value = false
  generationError.value = false
  if (resumeStartMs) {
    timerState.startFrom(resumeStartMs)
  } else {
    timerState.start()
  }
  sseState.connect(taskId)
  if (route.query.task !== taskId) {
    router.replace({ path: '/upload', query: { task: taskId } })
  }
}

async function startGeneration() {
  if (!selectedAvatar.value) return

  const req: GenerationRequest = {
    scriptContent: scriptContent.value,
    template: template.value,
    human: {
      name: selectedAvatar.value.name,
      avatar: selectedAvatar.value.image,
      audio: selectedAvatar.value.audio,
      video: selectedAvatar.value.video,
    },
    file_name: fileName.value,
    pdf_path: pdfPath.value,
    welcome_text: welcomeText.value || undefined,
    bgm_mode: bgmMode.value,
    bgm_path: bgmPath.value,
    style: scriptStyle.value,
    emo_control_method: emoMethod.value,
    emo_vec: emoMethod.value === 'vector' ? emoVec.value : undefined,
    emo_text: emoMethod.value === 'text' ? emoText.value : undefined,
  }

  try {
    const res = await createTask(req)
    const taskId = res.data.task_id
    generating.value = true
    timerState.start()
    saveTaskToStorage(taskId)
    router.replace({ path: '/upload', query: { task: taskId } })
    sseState.connect(taskId)
  } catch (err: any) {
    alert('创建任务失败: ' + err.message)
  }
}

watch(() => sseState.latestEvent.value, (evt) => {
  if (!evt) return
  if (evt.type === 'error') {
    generating.value = false
    generationError.value = true
    timerState.stop()
    clearTaskStorage()
  }
  if (evt.type === 'success') {
    if (generationError.value) return
    generating.value = false
    generationDone.value = true
    timerState.stop()
    clearTaskStorage()
    const m3u8 = evt.data?.hls_info?.m3u8_url || evt.data?.m3u8_url || evt.data?.video_url
    const mp4 = evt.data?.video_path
    if (m3u8) {
      finalVideoUrl.value = m3u8
      nextTick(() => initResultPlayer(m3u8))
    }
    if (mp4) {
      finalDownloadUrl.value = mp4
      downloadFileName.value = mp4.split('/').pop() || 'video.mp4'
    }
  }
})

watch(() => sseState.status.value, (s) => {
  if (s === 'done' && generating.value) {
    generating.value = false
    timerState.stop()
  }
  if (s === 'error' && generating.value) {
    generating.value = false
    generationError.value = true
    timerState.stop()
    showToast('连接任务流失败，任务可能已结束')
  }
})

function initResultPlayer(url: string) {
  const el = resultVideoRef.value
  if (!el) return
  const src = staticUrl(url)
  if (Hls.isSupported()) {
    resultHls = new Hls()
    resultHls.loadSource(src)
    resultHls.attachMedia(el)
  } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
    el.src = src
  }
}

function doDownloadResult() {
  if (!finalDownloadUrl.value) return
  const a = document.createElement('a')
  a.href = staticUrl(finalDownloadUrl.value)
  a.download = downloadFileName.value || 'video.mp4'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function cancelGeneration() {
  sseState.disconnect()
  generating.value = false
  timerState.stop()
  clearTaskStorage()
}

function backFromError() {
  generationError.value = false
  clearTaskStorage()
  sseState.disconnect()
  timerState.reset()
  step.value = 1
}

function retryGeneration() {
  generationError.value = false
  sseState.disconnect()
  timerState.reset()
  startGeneration()
}

function resetAll() {
  step.value = 0
  uploading.value = false
  pdfReady.value = false
  scriptContent.value = ''
  selectedAvatar.value = null
  generating.value = false
  generationDone.value = false
  generationError.value = false
  finalVideoUrl.value = ''
  finalDownloadUrl.value = ''
  clearTaskStorage()
  timerState.reset()
  sseState.disconnect()
  if (resultHls) { resultHls.destroy(); resultHls = null }
}

function goToStep(s: number) {
  if (s < step.value) step.value = s
}

onMounted(() => {
  void tryResumeTask()
})

onUnmounted(() => {
  sseState.disconnect()
  timerState.stop()
  if (resultHls) resultHls.destroy()
})
</script>

<style scoped>
/* ===== Toast ===== */
.upload-page__toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2000;
  background: var(--success);
  color: #fff;
  padding: 10px 28px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  pointer-events: none;
}

.toast-fade-enter-active { transition: opacity 0.2s, transform 0.2s; }
.toast-fade-leave-active { transition: opacity 0.4s, transform 0.4s; }
.toast-fade-enter-from { opacity: 0; transform: translateX(-50%) translateY(-12px); }
.toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(-8px); }

.upload-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  min-height: 100vh;
}

.upload-page__header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
}

.upload-page__back {
  font-size: 14px;
  color: var(--primary);
}

.upload-page__title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.upload-page__section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.upload-page__status {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #f0f4ff;
  border-radius: 10px;
  font-size: 14px;
  color: var(--primary);
}

.upload-page__spinner {
  width: 20px;
  height: 20px;
  border: 3px solid #e0e4f0;
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.upload-page__pdf-preview h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.upload-page__pdf-frame {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.upload-page__pdf-frame iframe {
  width: 100%;
  height: 400px;
  border: none;
}

.upload-page__script-gen {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.upload-page__actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.upload-page__btn {
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  background: #f0f2f5;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.upload-page__btn:hover { background: #e4e7ed; }
.upload-page__btn:disabled { opacity: 0.5; cursor: not-allowed; }

.upload-page__btn--primary {
  background: var(--primary);
  color: #fff;
}
.upload-page__btn--primary:hover { background: var(--primary-dark); }

.upload-page__btn--danger {
  background: var(--danger);
  color: #fff;
}

.upload-page__btn--lg {
  padding: 14px 40px;
  font-size: 16px;
}

.upload-page__gen-start {
  text-align: center;
  padding: 24px 0;
}

/* ===== 配置预览 ===== */
.config-preview {
  background: #f8f9fc;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
  text-align: left;
}

.config-preview__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.config-preview__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
}

.config-preview__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.config-preview__item--full {
  grid-column: 1 / -1;
}

.config-preview__label {
  font-size: 12px;
  color: var(--text-hint);
  font-weight: 500;
}

.config-preview__value {
  font-size: 14px;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 6px;
}

.config-preview__avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  object-fit: cover;
}

.config-preview__script {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  display: block;
  margin-top: 2px;
}

.upload-page__result {
  text-align: center;
}

.upload-page__result h4 {
  font-size: 16px;
  font-weight: 600;
  color: var(--success);
  margin-bottom: 16px;
}

.upload-page__result-video {
  width: 100%;
  max-height: 400px;
  border-radius: 10px;
  background: #000;
  margin-bottom: 16px;
}

/* Modal styles shared within this page */
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
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal--sm { width: 440px; }

.modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.modal__header h3 { font-size: 16px; font-weight: 600; }

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

.modal__footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  text-align: right;
}

.form-field {
  margin-bottom: 14px;
}

.form-field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.form-field input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
}
</style>
