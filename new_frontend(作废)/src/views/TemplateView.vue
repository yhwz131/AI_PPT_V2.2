<template>
  <div class="template-view">
    <div class="template-header">
      <h2>模板配置</h2>
      <p class="subtitle">选择数字人、模板位置和生成参数</p>
    </div>

    <div class="config-layout">
      <div class="config-main">
        <div class="config-section">
          <div class="section-label">数字人选择</div>
          <div class="human-tabs">
            <div class="human-tab" :class="{ active: humanTab === 'builtin' }" @click="humanTab = 'builtin'">内置数字人</div>
            <div class="human-tab" :class="{ active: humanTab === 'custom' }" @click="humanTab = 'custom'">自定义数字人</div>
          </div>
          <div v-loading="humansLoading" class="human-grid">
            <div
              v-for="human in (humanTab === 'builtin' ? builtInHumans : customizedHumans)"
              :key="human.name"
              class="human-card"
              :class="{ selected: selectedHuman?.name === human.name }"
              @click="handleSelectHuman(human)"
            >
              <div class="human-avatar-wrap">
                <img :src="getHumanImageUrl(human)" :alt="human.name" class="human-avatar-img" />
                <div v-if="selectedHuman?.name === human.name" class="avatar-check">
                  <el-icon :size="14"><Check /></el-icon>
                </div>
              </div>
              <div class="human-name">{{ human.name }}</div>
              <div class="human-brief">{{ human.brief }}</div>
              <el-button
                v-if="humanTab === 'custom'"
                class="human-del-btn"
                type="danger"
                text
                size="small"
                @click.stop="handleDeleteHuman(human)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <div v-if="humanTab === 'custom'" class="human-card add-card" @click="uploadDialogVisible = true">
              <el-icon :size="32" color="var(--text-secondary)"><Plus /></el-icon>
              <div class="human-name">上传数字人</div>
            </div>
          </div>
        </div>

        <div class="config-section">
          <div class="section-label">模板位置</div>
          <div class="position-layout">
            <div class="position-grid">
              <div
                v-for="opt in templateOptions"
                :key="opt.value"
                class="position-option"
                :class="{ selected: templatePosition === opt.value }"
                @click="templatePosition = opt.value"
              >
                {{ opt.label }}
              </div>
            </div>
            <div class="position-preview">
              <div class="preview-screen">
                <div class="preview-indicator" :class="positionClass" />
                <span v-if="templatePosition === '无数字人'" class="preview-none-text">无</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="config-sidebar">
        <div class="sidebar-section">
          <div class="sidebar-label">欢迎语</div>
          <el-input v-model="welcomeText" placeholder="请输入欢迎语" maxlength="100" show-word-limit />
        </div>

        <div class="sidebar-section">
          <div class="sidebar-label">背景音乐</div>
          <el-radio-group v-model="bgmMode" size="small">
            <el-radio-button value="default">默认</el-radio-button>
            <el-radio-button value="custom">自定义</el-radio-button>
            <el-radio-button value="none">无</el-radio-button>
          </el-radio-group>
          <div v-if="bgmMode === 'custom'" class="bgm-upload-area">
            <el-upload :auto-upload="false" :show-file-list="false" accept="audio/*" :on-change="handleBgmFileChange">
              <el-button size="small" :loading="bgmUploading"><el-icon><Upload /></el-icon> 选择音频</el-button>
            </el-upload>
            <span v-if="bgmFileName" class="bgm-name">{{ bgmFileName }}</span>
          </div>
        </div>

        <div class="sidebar-section">
          <div class="sidebar-label">TTS 情感</div>
          <el-radio-group v-model="emoControlMethod" size="small">
            <el-radio-button :value="0">自然</el-radio-button>
            <el-radio-button :value="2">向量</el-radio-button>
            <el-radio-button :value="3">文本</el-radio-button>
          </el-radio-group>
          <div v-if="emoControlMethod === 2" class="emo-panel">
            <el-alert v-if="emoVecSum > 1.5" title="向量总和不能超过1.5" type="error" show-icon :closable="false" class="emo-alert" />
            <div class="emo-sliders">
              <div v-for="(_, i) in emoVectorValues" :key="i" class="emo-row">
                <span class="emo-dim">D{{ i + 1 }}</span>
                <el-slider v-model="emoVectorValues[i]" :min="0" :max="1.2" :step="0.01" />
                <span class="emo-val">{{ emoVectorValues[i].toFixed(2) }}</span>
              </div>
            </div>
          </div>
          <div v-if="emoControlMethod === 3" class="emo-panel">
            <el-input v-model="emoText" type="textarea" placeholder="请输入情感描述" :rows="3" maxlength="200" show-word-limit />
          </div>
        </div>
      </div>
    </div>

    <div class="nav-section">
      <el-button size="large" @click="goBack"><el-icon><ArrowLeft /></el-icon> 上一步</el-button>
      <el-button type="primary" size="large" @click="goNext">下一步 <el-icon><ArrowRight /></el-icon></el-button>
    </div>

    <el-dialog v-model="uploadDialogVisible" title="上传自定义数字人" width="480px" :close-on-click-modal="false">
      <el-form :model="uploadForm" label-position="top">
        <el-form-item label="名称"><el-input v-model="uploadForm.name" placeholder="请输入数字人名称" /></el-form-item>
        <el-form-item label="简介"><el-input v-model="uploadForm.brief" placeholder="请输入数字人简介" /></el-form-item>
        <el-form-item label="头像">
          <el-upload :auto-upload="false" :show-file-list="false" accept="image/*" :on-change="(f: any) => uploadForm.avatarFile = f.raw">
            <el-button size="small"><el-icon><Upload /></el-icon> 选择头像</el-button>
            <span v-if="uploadForm.avatarFile" class="upload-fn">{{ uploadForm.avatarFile.name }}</span>
          </el-upload>
        </el-form-item>
        <el-form-item label="音频文件">
          <el-upload :auto-upload="false" :show-file-list="false" accept="audio/*" :on-change="(f: any) => uploadForm.audioFile = f.raw">
            <el-button size="small"><el-icon><Upload /></el-icon> 选择音频</el-button>
            <span v-if="uploadForm.audioFile" class="upload-fn">{{ uploadForm.audioFile.name }}</span>
          </el-upload>
        </el-form-item>
        <el-form-item label="视频文件">
          <el-upload :auto-upload="false" :show-file-list="false" accept="video/*" :on-change="(f: any) => uploadForm.videoFile = f.raw">
            <el-button size="small"><el-icon><Upload /></el-icon> 选择视频</el-button>
            <span v-if="uploadForm.videoFile" class="upload-fn">{{ uploadForm.videoFile.name }}</span>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadingHuman" @click="handleUploadHuman">确认上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Upload, ArrowLeft, ArrowRight, Check } from '@element-plus/icons-vue'
import { getBuiltInHumans, getCustomizedHumans, uploadBgm, uploadDigitalHuman, deleteDigitalHuman } from '@/api'
import type { DigitalHuman, BgmMode } from '@/types'
import { useWorkflowStore } from '@/stores/workflow'

const router = useRouter()
const workflowStore = useWorkflowStore()

const humanTab = ref<'builtin' | 'custom'>('builtin')
const builtInHumans = ref<DigitalHuman[]>([])
const customizedHumans = ref<DigitalHuman[]>([])
const humansLoading = ref(false)
const selectedHuman = ref<DigitalHuman | null>(workflowStore.selectedHuman)
const templatePosition = ref(workflowStore.template)
const welcomeText = ref(workflowStore.welcomeText)
const bgmMode = ref<BgmMode>(workflowStore.bgmMode)
const bgmPath = ref(workflowStore.bgmPath)
const bgmFileName = ref('')
const bgmUploading = ref(false)
const emoControlMethod = ref(workflowStore.emoControlMethod)
const emoVectorValues = reactive<number[]>(
  workflowStore.emoVec ? workflowStore.emoVec.split(',').map(Number) : [0, 0, 0, 0, 0, 0, 0, 0]
)
const emoText = ref(workflowStore.emoText)
const uploadDialogVisible = ref(false)
const uploadingHuman = ref(false)
const uploadForm = reactive({
  name: '', brief: '',
  avatarFile: null as File | null, audioFile: null as File | null, videoFile: null as File | null,
})

const templateOptions = [
  { label: '左上', value: '浮层-左上' },
  { label: '左下', value: '浮层-左下' },
  { label: '右上', value: '浮层-右上' },
  { label: '右下', value: '浮层-右下' },
  { label: '中央', value: '浮层-中央' },
  { label: '无数字人', value: '无数字人' },
]

const positionClass = computed(() => {
  const map: Record<string, string> = {
    '浮层-左下': 'pos-bottom-left', '浮层-左上': 'pos-top-left',
    '浮层-右下': 'pos-bottom-right', '浮层-右上': 'pos-top-right',
    '浮层-中央': 'pos-center', '无数字人': 'pos-none',
  }
  return map[templatePosition.value] || 'pos-bottom-left'
})

const emoVecSum = computed(() => emoVectorValues.reduce((a, b) => a + b, 0))

function getHumanImageUrl(human: DigitalHuman): string {
  if (human.image.startsWith('/') || human.image.startsWith('http')) return human.image
  return `/static/Digital_human/${human.image}`
}

async function loadHumans() {
  humansLoading.value = true
  try {
    const [builtInRes, customizedRes] = await Promise.all([getBuiltInHumans(), getCustomizedHumans()])
    builtInHumans.value = builtInRes.data.data || []
    customizedHumans.value = customizedRes.data.data || []
  } catch { ElMessage.error('加载数字人列表失败') }
  finally { humansLoading.value = false }
}

function handleSelectHuman(human: DigitalHuman) { selectedHuman.value = human }

async function handleDeleteHuman(human: DigitalHuman) {
  try {
    await ElMessageBox.confirm(`确定删除数字人「${human.name}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteDigitalHuman(human.name)
    ElMessage.success('删除成功')
    if (selectedHuman.value?.name === human.name) selectedHuman.value = null
    await loadHumans()
  } catch {}
}

async function handleUploadHuman() {
  if (!uploadForm.name.trim()) { ElMessage.warning('请输入数字人名称'); return }
  if (!uploadForm.avatarFile || !uploadForm.audioFile || !uploadForm.videoFile) { ElMessage.warning('请上传所有必需文件'); return }
  uploadingHuman.value = true
  try {
    await uploadDigitalHuman({ name: uploadForm.name.trim(), brief: uploadForm.brief.trim(), avatar: uploadForm.avatarFile, audio: uploadForm.audioFile, video: uploadForm.videoFile })
    ElMessage.success('上传成功')
    uploadDialogVisible.value = false
    uploadForm.name = ''; uploadForm.brief = ''; uploadForm.avatarFile = null; uploadForm.audioFile = null; uploadForm.videoFile = null
    await loadHumans()
  } catch {} finally { uploadingHuman.value = false }
}

async function handleBgmFileChange(file: any) {
  const rawFile = file.raw as File
  bgmUploading.value = true
  try {
    const res = await uploadBgm(rawFile) as any
    bgmPath.value = res.data.bgm_path
    bgmFileName.value = res.data.file_name || rawFile.name
    ElMessage.success('BGM上传成功')
  } catch {} finally { bgmUploading.value = false }
}

function goBack() { workflowStore.setStep(1); router.push('/script') }

function goNext() {
  if (templatePosition.value !== '无数字人' && !selectedHuman.value) { ElMessage.warning('请选择一个数字人'); return }
  if (emoControlMethod.value === 2 && emoVecSum.value > 1.5) { ElMessage.warning('情感向量总和不能超过1.5'); return }
  if (bgmMode.value === 'custom' && !bgmPath.value) { ElMessage.warning('请上传自定义BGM文件'); return }
  const emoVecStr = emoControlMethod.value === 2 ? emoVectorValues.map(v => v.toFixed(2)).join(',') : ''
  workflowStore.setTemplateData({
    human: templatePosition.value === '无数字人' ? null : selectedHuman.value,
    template: templatePosition.value, welcomeText: welcomeText.value,
    bgmMode: bgmMode.value, bgmPath: bgmPath.value,
    emoControlMethod: emoControlMethod.value, emoVec: emoVecStr,
    emoText: emoControlMethod.value === 3 ? emoText.value : '',
  })
  workflowStore.setStep(3)
  router.push('/generate')
}

onMounted(() => { loadHumans() })
</script>

<style scoped lang="scss">
.template-view {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.template-header {
  h2 { font-size: 1.5rem; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
  .subtitle { color: var(--text-secondary); font-size: 0.9rem; }
}

.config-layout {
  display: flex;
  gap: 24px;
}

.config-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.config-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.config-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
}

.section-label {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 14px;
}

.human-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.human-tab {
  padding: 8px 20px;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  &:hover { color: var(--text-primary); }
  &.active { color: var(--accent-primary); border-bottom-color: var(--accent-primary); }
}

.human-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  min-height: 100px;
}

.human-card {
  background: var(--bg-primary);
  border: 2px solid var(--border-color);
  border-radius: 10px;
  padding: 14px 8px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  position: relative;
  &:hover { border-color: var(--accent-primary); transform: translateY(-2px); }
  &.selected { border-color: var(--accent-primary); box-shadow: 0 0 0 1px var(--accent-primary), 0 4px 12px rgba(59,130,246,0.25); }
  &.add-card { border-style: dashed; justify-content: center; min-height: 120px; &:hover { border-style: solid; } }
}

.human-avatar-wrap {
  width: 64px; height: 64px; border-radius: 50%; overflow: hidden; position: relative; background: var(--border-color);
}

.human-avatar-img { width: 100%; height: 100%; object-fit: cover; }

.avatar-check {
  position: absolute; inset: 0; background: rgba(59,130,246,0.6);
  display: flex; align-items: center; justify-content: center; color: #fff;
}

.human-name { font-size: 0.8rem; font-weight: 600; color: var(--text-primary); text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.human-brief { font-size: 0.7rem; color: var(--text-secondary); text-align: center; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.human-del-btn { position: absolute; top: 4px; right: 4px; }

.position-layout { display: flex; gap: 24px; align-items: center; }

.position-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; flex-shrink: 0; }

.position-option {
  padding: 8px 16px; border: 1px solid var(--border-color); border-radius: 8px;
  text-align: center; cursor: pointer; font-size: 0.85rem; color: var(--text-secondary);
  transition: all 0.2s;
  &:hover { border-color: var(--accent-primary); color: var(--text-primary); }
  &.selected { background: var(--accent-primary); border-color: var(--accent-primary); color: #fff; }
}

.position-preview { flex: 1; display: flex; justify-content: center; align-items: center; }

.preview-screen {
  width: 160px; height: 110px; background: var(--bg-primary); border: 2px solid var(--border-color);
  border-radius: 6px; position: relative; overflow: hidden;
}

.preview-indicator {
  width: 30px; height: 30px; border-radius: 50%; background: var(--accent-primary); opacity: 0.7;
  position: absolute; transition: all 0.3s;
  &.pos-bottom-left { bottom: 6px; left: 6px; }
  &.pos-top-left { top: 6px; left: 6px; }
  &.pos-bottom-right { bottom: 6px; right: 6px; }
  &.pos-top-right { top: 6px; right: 6px; }
  &.pos-center { top: 50%; left: 50%; transform: translate(-50%, -50%); }
  &.pos-none { display: none; }
}

.preview-none-text { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); font-size: 0.9rem; }

.sidebar-section {
  background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 10px; padding: 16px;
  display: flex; flex-direction: column; gap: 10px;
}

.sidebar-label { font-size: 0.85rem; font-weight: 600; color: var(--text-primary); }

.bgm-upload-area { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.bgm-name { font-size: 0.8rem; color: var(--text-secondary); }

.emo-panel { margin-top: 8px; }
.emo-alert { margin-bottom: 8px; }
.emo-sliders { display: flex; flex-direction: column; gap: 4px; }
.emo-row { display: flex; align-items: center; gap: 6px; }
.emo-dim { font-size: 0.7rem; color: var(--text-secondary); width: 24px; flex-shrink: 0; }
.emo-val { font-size: 0.7rem; color: var(--text-secondary); width: 32px; text-align: right; flex-shrink: 0; }

.upload-fn { font-size: 0.8rem; color: var(--text-secondary); margin-left: 8px; }

.nav-section { display: flex; justify-content: space-between; padding-top: 16px; border-top: 1px solid var(--border-color); }
</style>
