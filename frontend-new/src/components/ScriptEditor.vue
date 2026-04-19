<template>
  <div class="script-editor">
    <div class="script-editor__header">
      <span class="script-editor__title">解说稿</span>
      <span class="script-editor__hint">可直接编辑文本内容</span>
    </div>
    <div
      ref="editorRef"
      class="script-editor__body"
      contenteditable="true"
      v-html="content"
      @input="onInput"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const props = defineProps<{
  content: string
}>()

const emit = defineEmits<{
  (e: 'update', html: string): void
}>()

const editorRef = ref<HTMLElement | null>(null)

function onInput() {
  if (editorRef.value) {
    emit('update', editorRef.value.innerHTML)
  }
}
</script>

<style scoped>
.script-editor {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}

.script-editor__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #f8f9ff;
  border-bottom: 1px solid var(--border);
}

.script-editor__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.script-editor__hint {
  font-size: 12px;
  color: var(--text-hint);
}

.script-editor__body {
  padding: 16px;
  min-height: 200px;
  max-height: 400px;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.8;
  color: var(--text);
  outline: none;
}

.script-editor__body:focus {
  box-shadow: inset 0 0 0 2px rgba(103, 119, 239, 0.2);
}

.script-editor__body :deep(h3),
.script-editor__body :deep(h4) {
  margin: 12px 0 6px;
  font-size: 15px;
  color: var(--primary);
}

.script-editor__body :deep(p) {
  margin-bottom: 8px;
}
</style>
