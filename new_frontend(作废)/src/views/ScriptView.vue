<template>
  <div class="script-view">
    <div class="script-header">
      <h2>讲稿编辑</h2>
      <p class="subtitle">选择风格生成解说词，生成后可逐页编辑内容</p>
    </div>

    <div class="style-generate-bar">
      <div class="style-group">
        <span class="bar-label">讲稿风格</span>
        <el-radio-group v-model="selectedStyle" size="default" :disabled="generating">
          <el-radio-button v-for="item in styleOptions" :key="item.value" :value="item.value">
            {{ item.label }}
          </el-radio-button>
        </el-radio-group>
      </div>
      <el-button
        type="primary"
        size="large"
        :loading="generating"
        :disabled="!canGenerate"
        @click="handleGenerate"
      >
        <el-icon v-if="!generating"><MagicStick /></el-icon>
        {{ generating ? '正在生成讲稿...' : 'AI 生成讲稿' }}
      </el-button>
    </div>

    <el-alert
      v-if="generateError"
      :title="generateError"
      type="error"
      show-icon
      closable
      @close="generateError = ''"
    />

    <div v-if="pages.length > 0" class="editor-layout">
      <div class="thumbnail-panel">
        <div class="panel-title">幻灯片</div>
        <div class="thumbnail-list">
          <div
            v-for="(img, index) in workflowStore.imageUrls"
            :key="index"
            class="thumbnail-item"
            :class="{ active: activePageIndex === index }"
            @click="scrollToPage(index)"
          >
            <el-image :src="img" fit="contain" class="thumb-img">
              <template #error>
                <div class="thumb-placeholder">{{ index + 1 }}</div>
              </template>
            </el-image>
            <span class="thumb-num">{{ index + 1 }}</span>
          </div>
        </div>
      </div>

      <div class="editor-panel">
        <div class="editor-toolbar">
          <span class="page-count-label">共 {{ pages.length }} 页讲稿</span>
          <el-button type="primary" text size="small" @click="addPage">
            <el-icon><Plus /></el-icon>
            添加页面
          </el-button>
        </div>

        <div ref="pagesListRef" class="pages-scroll">
          <div
            v-for="(page, index) in pages"
            :id="`page-${index}`"
            :key="index"
            class="page-editor-card"
            :class="{ active: activePageIndex === index }"
          >
            <div class="page-editor-header">
              <div class="page-badge">{{ index + 1 }}</div>
              <span class="page-label">第{{ index + 1 }}页</span>
              <el-button
                v-if="pages.length > 1"
                type="danger"
                text
                size="small"
                class="delete-btn"
                @click="removePage(index)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <div class="page-editor-body">
              <el-input
                v-model="page.title"
                placeholder="页面标题"
                size="large"
                class="title-input"
                @input="rebuildScript"
              />
              <el-input
                v-model="page.content"
                type="textarea"
                :rows="3"
                placeholder="解说内容"
                resize="none"
                @input="rebuildScript"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!generating" class="empty-state">
      <el-icon :size="64" color="var(--border-color)"><Document /></el-icon>
      <p class="empty-title">尚未生成讲稿</p>
      <p class="empty-desc">选择讲稿风格后，点击「AI 生成讲稿」按钮</p>
    </div>

    <div class="nav-section">
      <el-button size="large" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        上一步
      </el-button>
      <el-button
        type="primary"
        size="large"
        :disabled="!canProceed"
        @click="goNext"
      >
        下一步
        <el-icon><ArrowRight /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkflowStore } from '@/stores/workflow'
import { generateScript } from '@/api'
import { Plus, Delete, ArrowLeft, ArrowRight, MagicStick, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { ScriptStyle } from '@/types'

interface PageData {
  title: string
  content: string
}

const router = useRouter()
const workflowStore = useWorkflowStore()

const selectedStyle = ref<ScriptStyle>('normal')
const generating = ref(false)
const generateError = ref('')
const pages = ref<PageData[]>([])
const activePageIndex = ref(0)

const styleOptions = [
  { value: 'brief' as ScriptStyle, label: '简略' },
  { value: 'normal' as ScriptStyle, label: '普通' },
  { value: 'professional' as ScriptStyle, label: '专业' },
]

const canGenerate = computed(() => !!workflowStore.pdfPath && !generating.value)
const canProceed = computed(() => pages.value.length > 0 && pages.value.some(p => p.title || p.content))

function parseScript(html: string): PageData[] {
  const result: PageData[] = []
  const divRegex = /<div>([\s\S]*?)<\/div>/g
  let match: RegExpExecArray | null
  while ((match = divRegex.exec(html)) !== null) {
    const block = match[1]
    const titleMatch = block.match(/<h3>标题:\s*([\s\S]*?)<\/h3>/)
    const contentMatch = block.match(/<p>内容:\s*([\s\S]*?)<\/p>/)
    result.push({
      title: titleMatch ? titleMatch[1].trim() : '',
      content: contentMatch ? contentMatch[1].trim() : '',
    })
  }
  return result
}

function rebuildScript() {
  const parts = pages.value.map((page, index) =>
    `<div><h4>第${index + 1}页</h4>\n<h3>标题: ${page.title}</h3>\n<p>内容: ${page.content}</p></div>`
  )
  workflowStore.setScriptData(parts.join('\n\n'), selectedStyle.value)
}

function addPage() {
  pages.value.push({ title: '', content: '' })
  rebuildScript()
  activePageIndex.value = pages.value.length - 1
}

function removePage(index: number) {
  pages.value.splice(index, 1)
  if (activePageIndex.value >= pages.value.length) {
    activePageIndex.value = Math.max(0, pages.value.length - 1)
  }
  rebuildScript()
}

function scrollToPage(index: number) {
  activePageIndex.value = index
  const el = document.getElementById(`page-${index}`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

async function handleGenerate() {
  if (!workflowStore.pdfPath) {
    ElMessage.warning('缺少文件信息，请返回上传页面重新上传')
    return
  }
  generating.value = true
  generateError.value = ''
  try {
    const res = await generateScript(
      workflowStore.originalFile,
      workflowStore.pdfPath,
      selectedStyle.value
    ) as any
    if (res.code === 200 || res.code === 0) {
      const script = res.data.script
      pages.value = parseScript(script)
      workflowStore.setScriptData(script, selectedStyle.value)
      ElMessage.success('讲稿生成成功')
    } else {
      generateError.value = res.message || '讲稿生成失败'
    }
  } catch (err: any) {
    generateError.value = err?.response?.data?.detail || err?.message || '网络错误，请重试'
  } finally {
    generating.value = false
  }
}

function goBack() {
  workflowStore.setStep(0)
  router.push('/upload')
}

function goNext() {
  rebuildScript()
  workflowStore.setStep(2)
  router.push('/template')
}

onMounted(() => {
  if (workflowStore.scriptContent) {
    pages.value = parseScript(workflowStore.scriptContent)
    selectedStyle.value = workflowStore.scriptStyle
  }
  if (workflowStore.currentStep < 1) {
    workflowStore.setStep(1)
  }
})
</script>

<style scoped lang="scss">
.script-view {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.script-header {
  h2 {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
  }
  .subtitle {
    color: var(--text-secondary);
    font-size: 0.9rem;
  }
}

.style-generate-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px 24px;
  gap: 16px;
  flex-wrap: wrap;
}

.style-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bar-label {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
}

.editor-layout {
  display: flex;
  gap: 20px;
  min-height: 500px;
}

.thumbnail-panel {
  width: 140px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.panel-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 0 4px;
}

.thumbnail-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  max-height: 520px;
  padding-right: 4px;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 2px; }
}

.thumbnail-item {
  cursor: pointer;
  border: 2px solid transparent;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s ease;
  position: relative;

  &:hover { border-color: var(--accent-primary); }
  &.active {
    border-color: var(--accent-primary);
    box-shadow: 0 0 8px rgba(59, 130, 246, 0.3);
  }
}

.thumb-img {
  width: 100%;
  height: 80px;
  display: block;
  background: var(--bg-primary);
}

.thumb-placeholder {
  width: 100%;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 1.2rem;
  font-weight: 600;
}

.thumb-num {
  position: absolute;
  bottom: 4px;
  right: 6px;
  font-size: 0.7rem;
  color: var(--text-secondary);
  background: rgba(15, 23, 42, 0.8);
  padding: 1px 5px;
  border-radius: 4px;
}

.editor-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-count-label {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.pages-scroll {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 520px;
  overflow-y: auto;
  padding-right: 4px;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-track { background: var(--bg-primary); border-radius: 3px; }
  &::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 3px; }
}

.page-editor-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 16px;
  transition: all 0.2s ease;

  &.active {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 1px var(--accent-primary);
  }
}

.page-editor-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.page-badge {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  flex-shrink: 0;
}

.page-label {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 0.9rem;
}

.delete-btn {
  margin-left: auto;
}

.page-editor-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.title-input {
  :deep(.el-input__wrapper) {
    font-size: 1rem;
    font-weight: 600;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 12px;
  background: var(--bg-secondary);
  border: 1px dashed var(--border-color);
  border-radius: 12px;
}

.empty-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-desc {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.nav-section {
  display: flex;
  justify-content: space-between;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}
</style>
