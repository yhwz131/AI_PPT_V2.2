<template>
  <Teleport to="body">
    <div v-if="visible" class="cdh-overlay" @click.self="close">
      <div class="cdh-dialog">
        <div class="cdh-dialog__header">
          <h3>添加自定义数字人</h3>
          <button class="cdh-dialog__close" @click="close">✕</button>
        </div>

        <div class="cdh-dialog__body">
          <!-- 名称 -->
          <div class="cdh-field" :class="{ 'cdh-field--error': submitted && !form.name }">
            <label class="cdh-field__label">名称 <span class="cdh-field__req">*</span></label>
            <input v-model="form.name" class="cdh-field__input" placeholder="数字人名称" />
            <span v-if="submitted && !form.name" class="cdh-field__hint">请输入数字人名称</span>
          </div>

          <!-- 简介 -->
          <div class="cdh-field" :class="{ 'cdh-field--error': submitted && !form.brief }">
            <label class="cdh-field__label">简介 <span class="cdh-field__req">*</span></label>
            <input v-model="form.brief" class="cdh-field__input" placeholder="简短描述" />
            <span v-if="submitted && !form.brief" class="cdh-field__hint">请输入数字人简介</span>
          </div>

          <!-- 头像图片 -->
          <div class="cdh-field" :class="{ 'cdh-field--error': submitted && !form.avatar }">
            <label class="cdh-field__label">头像图片 <span class="cdh-field__req">*</span></label>
            <div class="cdh-field__media-row">
              <label class="cdh-field__file-btn">
                选择文件
                <input type="file" accept="image/*" hidden @change="onFileAvatar" />
              </label>
              <button class="cdh-field__rec-btn" @click="openCamera('avatar')">拍照</button>
              <span class="cdh-field__file-name">{{ avatarFileName }}</span>
            </div>
            <img v-if="avatarPreview" :src="avatarPreview" class="cdh-field__img-preview" />
            <span v-if="submitted && !form.avatar" class="cdh-field__hint">请上传或拍摄头像图片</span>
          </div>

          <!-- 音频 -->
          <div class="cdh-field" :class="{ 'cdh-field--error': submitted && !form.audio }">
            <label class="cdh-field__label">音频 <span class="cdh-field__req">*</span></label>
            <div class="cdh-field__media-row">
              <label class="cdh-field__file-btn">
                选择文件
                <input type="file" accept="audio/*" hidden @change="onFileAudio" />
              </label>
              <button
                class="cdh-field__rec-btn"
                :class="{ 'cdh-field__rec-btn--active': micRecording }"
                @click="toggleMicRecording"
              >
                {{ micRecording ? '停止录音' : '录音' }}
              </button>
              <span class="cdh-field__file-name">{{ audioFileName }}</span>
            </div>
            <div v-if="micRecording" class="cdh-field__rec-status">
              <span class="cdh-field__rec-dot"></span>
              录音中 {{ micDurationText }}
            </div>
            <audio v-if="audioPreviewUrl" :src="audioPreviewUrl" controls class="cdh-field__audio-preview" />
            <span v-if="submitted && !form.audio" class="cdh-field__hint">请上传或录制音频</span>
          </div>

          <!-- 视频 -->
          <div class="cdh-field" :class="{ 'cdh-field--error': submitted && !form.video }">
            <label class="cdh-field__label">视频 <span class="cdh-field__req">*</span></label>
            <div class="cdh-field__media-row">
              <label class="cdh-field__file-btn">
                选择文件
                <input type="file" accept="video/*" hidden @change="onFileVideo" />
              </label>
              <button class="cdh-field__rec-btn" @click="openCamera('video')">录制视频</button>
              <span class="cdh-field__file-name">{{ videoFileName }}</span>
            </div>
            <video v-if="videoPreviewUrl" :src="videoPreviewUrl" controls class="cdh-field__video-preview" />
            <span v-if="submitted && !form.video" class="cdh-field__hint">请上传或录制视频</span>
          </div>
        </div>

        <div class="cdh-dialog__footer">
          <button class="cdh-dialog__btn cdh-dialog__btn--cancel" @click="close">取消</button>
          <button class="cdh-dialog__btn cdh-dialog__btn--primary" :disabled="uploading" @click="doSubmit">
            {{ uploading ? '上传中...' : '上传' }}
          </button>
        </div>

        <!-- 摄像头弹窗 -->
        <div v-if="cameraMode" class="cdh-camera-overlay" @click.self="closeCamera">
          <div class="cdh-camera">
            <div class="cdh-camera__header">
              <h4>{{ cameraMode === 'avatar' ? '拍摄头像' : '录制视频' }}</h4>
              <button class="cdh-dialog__close" @click="closeCamera">✕</button>
            </div>
            <div class="cdh-camera__body">
              <video ref="cameraVideoEl" autoplay playsinline muted class="cdh-camera__preview"></video>
              <canvas ref="canvasEl" hidden></canvas>
            </div>
            <div class="cdh-camera__actions">
              <template v-if="cameraMode === 'avatar'">
                <button class="cdh-dialog__btn cdh-dialog__btn--primary" @click="capturePhoto">拍照</button>
              </template>
              <template v-else>
                <button
                  v-if="!camRecording"
                  class="cdh-dialog__btn cdh-dialog__btn--primary"
                  @click="startCamRecording"
                >开始录制</button>
                <button
                  v-else
                  class="cdh-dialog__btn cdh-dialog__btn--danger"
                  @click="stopCamRecording"
                >
                  停止录制 {{ camDurationText }}
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', payload: { name: string; brief: string; avatar: File; audio: File; video: File }): void
}>()

const form = ref({ name: '', brief: '', avatar: null as File | null, audio: null as File | null, video: null as File | null })
const submitted = ref(false)
const uploading = ref(false)

const avatarPreview = ref('')
const audioPreviewUrl = ref('')
const videoPreviewUrl = ref('')

const avatarFileName = computed(() => form.value.avatar?.name || '未选择文件')
const audioFileName = computed(() => form.value.audio?.name || '未选择文件')
const videoFileName = computed(() => form.value.video?.name || '未选择文件')

function onFileAvatar(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  form.value.avatar = f
  avatarPreview.value = URL.createObjectURL(f)
}
function onFileAudio(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  form.value.audio = f
  revokeUrl(audioPreviewUrl)
  audioPreviewUrl.value = URL.createObjectURL(f)
}
function onFileVideo(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  form.value.video = f
  revokeUrl(videoPreviewUrl)
  videoPreviewUrl.value = URL.createObjectURL(f)
}
function revokeUrl(r: { value: string }) {
  if (r.value) { URL.revokeObjectURL(r.value); r.value = '' }
}

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
}

async function webmBlobToWav(blob: Blob): Promise<Blob> {
  const ctx = new AudioContext()
  const buf = await ctx.decodeAudioData(await blob.arrayBuffer())
  const ch = buf.numberOfChannels
  const sr = buf.sampleRate
  const len = buf.length * ch * 2
  const ab = new ArrayBuffer(44 + len)
  const v = new DataView(ab)
  writeString(v, 0, 'RIFF')
  v.setUint32(4, 36 + len, true)
  writeString(v, 8, 'WAVE')
  writeString(v, 12, 'fmt ')
  v.setUint32(16, 16, true)
  v.setUint16(20, 1, true)
  v.setUint16(22, ch, true)
  v.setUint32(24, sr, true)
  v.setUint32(28, sr * ch * 2, true)
  v.setUint16(32, ch * 2, true)
  v.setUint16(34, 16, true)
  writeString(v, 36, 'data')
  v.setUint32(40, len, true)
  let off = 44
  for (let i = 0; i < buf.length; i++) {
    for (let c = 0; c < ch; c++) {
      const s = Math.max(-1, Math.min(1, buf.getChannelData(c)[i]))
      v.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true)
      off += 2
    }
  }
  ctx.close()
  return new Blob([ab], { type: 'audio/wav' })
}

function pickVideoMime(): string {
  for (const mime of ['video/mp4', 'video/webm']) {
    if (MediaRecorder.isTypeSupported(mime)) return mime
  }
  return 'video/webm'
}

// ======= Mic Recording =======
const micRecording = ref(false)
let micRecorder: MediaRecorder | null = null
let micChunks: Blob[] = []
let micStream: MediaStream | null = null
const micSeconds = ref(0)
let micTimer: ReturnType<typeof setInterval> | null = null
const micDurationText = computed(() => {
  const m = String(Math.floor(micSeconds.value / 60)).padStart(2, '0')
  const s = String(micSeconds.value % 60).padStart(2, '0')
  return `${m}:${s}`
})

async function toggleMicRecording() {
  if (micRecording.value) {
    micRecorder?.stop()
    return
  }
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    micRecorder = new MediaRecorder(micStream)
    micChunks = []
    micRecorder.ondataavailable = (e) => { if (e.data.size) micChunks.push(e.data) }
    micRecorder.onstop = async () => {
      micRecording.value = false
      clearInterval(micTimer!)
      micStream?.getTracks().forEach(t => t.stop())
      const rawBlob = new Blob(micChunks, { type: 'audio/webm' })
      try {
        const wavBlob = await webmBlobToWav(rawBlob)
        const file = new File([wavBlob], `录音_${Date.now()}.wav`, { type: 'audio/wav' })
        form.value.audio = file
        revokeUrl(audioPreviewUrl)
        audioPreviewUrl.value = URL.createObjectURL(wavBlob)
      } catch {
        const file = new File([rawBlob], `录音_${Date.now()}.ogg`, { type: 'audio/ogg' })
        form.value.audio = file
        revokeUrl(audioPreviewUrl)
        audioPreviewUrl.value = URL.createObjectURL(rawBlob)
      }
    }
    micRecorder.start()
    micRecording.value = true
    micSeconds.value = 0
    micTimer = setInterval(() => micSeconds.value++, 1000)
  } catch (err: any) {
    alert('无法访问麦克风: ' + (err?.message || '请确认使用 HTTPS 并允许浏览器权限'))
  }
}

// ======= Camera =======
const cameraMode = ref<'avatar' | 'video' | null>(null)
const cameraVideoEl = ref<HTMLVideoElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
let cameraStream: MediaStream | null = null

const camRecording = ref(false)
let camRecorder: MediaRecorder | null = null
let camChunks: Blob[] = []
const camSeconds = ref(0)
let camTimer: ReturnType<typeof setInterval> | null = null
const camDurationText = computed(() => {
  const m = String(Math.floor(camSeconds.value / 60)).padStart(2, '0')
  const s = String(camSeconds.value % 60).padStart(2, '0')
  return `${m}:${s}`
})

async function openCamera(mode: 'avatar' | 'video') {
  cameraMode.value = mode
  try {
    const constraints: MediaStreamConstraints = mode === 'avatar'
      ? { video: { facingMode: 'user', width: 640, height: 640 } }
      : { video: { facingMode: 'user', width: 1280, height: 720 }, audio: true }
    cameraStream = await navigator.mediaDevices.getUserMedia(constraints)
    await new Promise(r => setTimeout(r, 50))
    if (cameraVideoEl.value) {
      cameraVideoEl.value.srcObject = cameraStream
    }
  } catch (err: any) {
    alert('无法访问摄像头: ' + (err?.message || '请确认使用 HTTPS 并允许浏览器权限'))
    cameraMode.value = null
  }
}

function closeCamera() {
  camRecording.value = false
  clearInterval(camTimer!)
  camRecorder?.stop()
  cameraStream?.getTracks().forEach(t => t.stop())
  cameraMode.value = null
}

function capturePhoto() {
  const video = cameraVideoEl.value!
  const canvas = canvasEl.value!
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d')!.drawImage(video, 0, 0)
  canvas.toBlob(blob => {
    if (!blob) return
    const file = new File([blob], `头像_${Date.now()}.png`, { type: 'image/png' })
    form.value.avatar = file
    avatarPreview.value = URL.createObjectURL(blob)
    closeCamera()
  }, 'image/png')
}

function startCamRecording() {
  if (!cameraStream) return
  camChunks = []
  const mime = pickVideoMime()
  const ext = mime.includes('mp4') ? 'mp4' : 'webm'
  camRecorder = new MediaRecorder(cameraStream, { mimeType: mime })
  camRecorder.ondataavailable = (e) => { if (e.data.size) camChunks.push(e.data) }
  camRecorder.onstop = () => {
    camRecording.value = false
    clearInterval(camTimer!)
    const blob = new Blob(camChunks, { type: mime })
    const file = new File([blob], `录制_${Date.now()}.${ext}`, { type: mime })
    form.value.video = file
    revokeUrl(videoPreviewUrl)
    videoPreviewUrl.value = URL.createObjectURL(blob)
    closeCamera()
  }
  camRecorder.start()
  camRecording.value = true
  camSeconds.value = 0
  camTimer = setInterval(() => camSeconds.value++, 1000)
}

function stopCamRecording() {
  camRecorder?.stop()
}

// ======= Submit =======
function doSubmit() {
  submitted.value = true
  const { name, brief, avatar, audio, video } = form.value
  if (!name || !brief || !avatar || !audio || !video) return
  uploading.value = true
  emit('submit', { name, brief, avatar, audio, video })
}

function close() {
  closeCamera()
  if (micRecording.value) { micRecorder?.stop() }
  emit('close')
}

function resetAfterUpload() {
  uploading.value = false
  submitted.value = false
  form.value = { name: '', brief: '', avatar: null, audio: null, video: null }
  revokeUrl(audioPreviewUrl as any)
  revokeUrl(videoPreviewUrl as any)
  avatarPreview.value = ''
}

defineExpose({ resetAfterUpload, setUploading: (v: boolean) => uploading.value = v })

onBeforeUnmount(() => {
  cameraStream?.getTracks().forEach(t => t.stop())
  micStream?.getTracks().forEach(t => t.stop())
})
</script>

<style scoped>
.cdh-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.cdh-dialog {
  background: #fff;
  border-radius: 16px;
  width: 500px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.cdh-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.cdh-dialog__header h3 { font-size: 16px; font-weight: 600; }

.cdh-dialog__close {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #f0f0f0;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cdh-dialog__body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.cdh-dialog__footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.cdh-dialog__btn {
  padding: 8px 22px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.cdh-dialog__btn--cancel { background: #f0f2f5; color: var(--text-secondary); }
.cdh-dialog__btn--cancel:hover { background: #e4e7ed; }
.cdh-dialog__btn--primary { background: var(--primary); color: #fff; }
.cdh-dialog__btn--primary:hover { background: var(--primary-dark); }
.cdh-dialog__btn--primary:disabled { opacity: 0.5; cursor: not-allowed; }
.cdh-dialog__btn--danger { background: var(--danger, #f44); color: #fff; }

/* Fields */
.cdh-field { margin-bottom: 16px; }
.cdh-field--error .cdh-field__input { border-color: var(--danger, #f44); }

.cdh-field__label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.cdh-field__req { color: var(--danger, #f44); }

.cdh-field__input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.cdh-field__input:focus { border-color: var(--primary); outline: none; }

.cdh-field__hint {
  display: block;
  font-size: 12px;
  color: var(--danger, #f44);
  margin-top: 4px;
}

.cdh-field__media-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cdh-field__file-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  background: #f0f2f5;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.cdh-field__file-btn:hover { background: #e4e7ed; }

.cdh-field__rec-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  background: var(--primary);
  color: #fff;
  white-space: nowrap;
  transition: all 0.2s;
}

.cdh-field__rec-btn:hover { opacity: 0.9; }
.cdh-field__rec-btn--active { background: var(--danger, #f44); animation: pulse 1.2s infinite; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.cdh-field__file-name {
  font-size: 12px;
  color: var(--text-hint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.cdh-field__rec-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--danger, #f44);
  margin-top: 6px;
}

.cdh-field__rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--danger, #f44);
  animation: pulse 1s infinite;
}

.cdh-field__img-preview {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
  margin-top: 8px;
  border: 2px solid var(--border);
}

.cdh-field__audio-preview {
  width: 100%;
  height: 36px;
  margin-top: 8px;
}

.cdh-field__video-preview {
  width: 100%;
  max-height: 160px;
  border-radius: 8px;
  background: #000;
  margin-top: 8px;
}

/* Camera overlay */
.cdh-camera-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  border-radius: 16px;
}

.cdh-camera {
  background: #fff;
  border-radius: 12px;
  width: 420px;
  overflow: hidden;
}

.cdh-camera__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.cdh-camera__header h4 { font-size: 15px; font-weight: 600; }

.cdh-camera__body { background: #000; }

.cdh-camera__preview {
  width: 100%;
  max-height: 320px;
  display: block;
  object-fit: cover;
}

.cdh-camera__actions {
  padding: 12px 16px;
  display: flex;
  justify-content: center;
  gap: 10px;
}
</style>
