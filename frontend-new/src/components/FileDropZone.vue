<template>
  <div
    class="dropzone"
    :class="{ 'dropzone--over': isOver, 'dropzone--disabled': disabled }"
    @dragover.prevent="isOver = true"
    @dragleave.prevent="isOver = false"
    @drop.prevent="onDrop"
    @click="openPicker"
  >
    <input
      ref="fileInput"
      type="file"
      :accept="accept"
      style="display: none"
      @change="onFileSelect"
    />
    <template v-if="!file">
      <div class="dropzone__icon">
        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="#999" stroke-width="1.5">
          <path d="M12 16V4m0 0L8 8m4-4l4 4"/>
          <path d="M20 16v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2"/>
        </svg>
      </div>
      <p class="dropzone__text">拖拽PPT文件到此处，或点击选择</p>
      <p class="dropzone__hint">支持 .ppt / .pptx，最大50MB</p>
    </template>
    <template v-else>
      <div class="dropzone__file">
        <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="var(--success)" stroke-width="1.5">
          <path d="M9 12l2 2 4-4"/>
          <circle cx="12" cy="12" r="10"/>
        </svg>
        <span class="dropzone__filename">{{ file.name }}</span>
        <button class="dropzone__remove" @click.stop="removeFile" :disabled="disabled">✕</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  accept?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'file', file: File): void
  (e: 'remove'): void
}>()

const file = ref<File | null>(null)
const isOver = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

function openPicker() {
  if (props.disabled) return
  fileInput.value?.click()
}

function onDrop(e: DragEvent) {
  isOver.value = false
  if (props.disabled) return
  const f = e.dataTransfer?.files[0]
  if (f) selectFile(f)
}

function onFileSelect(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) selectFile(f)
}

function selectFile(f: File) {
  if (f.size > 50 * 1024 * 1024) {
    alert('文件大小不能超过50MB')
    return
  }
  file.value = f
  emit('file', f)
}

function removeFile() {
  file.value = null
  if (fileInput.value) fileInput.value.value = ''
  emit('remove')
}
</script>

<style scoped>
.dropzone {
  border: 2px dashed #d0d0d0;
  border-radius: 12px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #fafbff;
}

.dropzone--over {
  border-color: var(--primary);
  background: rgba(103, 119, 239, 0.05);
}

.dropzone--disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.dropzone__icon {
  margin-bottom: 12px;
}

.dropzone__text {
  font-size: 15px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.dropzone__hint {
  font-size: 13px;
  color: var(--text-hint);
}

.dropzone__file {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
}

.dropzone__filename {
  font-size: 15px;
  color: var(--text);
  font-weight: 500;
}

.dropzone__remove {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #f0f0f0;
  font-size: 12px;
  color: #999;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}
.dropzone__remove:hover { background: #e0e0e0; }
</style>
