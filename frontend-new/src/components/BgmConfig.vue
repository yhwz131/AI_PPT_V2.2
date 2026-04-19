<template>
  <div class="bgm-config">
    <h4 class="bgm-config__title">背景音乐</h4>
    <div class="bgm-config__options">
      <label v-for="opt in modes" :key="opt.value" class="bgm-config__radio">
        <input
          type="radio"
          :value="opt.value"
          :checked="mode === opt.value"
          @change="$emit('update:mode', opt.value)"
        />
        <span>{{ opt.label }}</span>
      </label>
    </div>

    <div v-if="mode === 'custom'" class="bgm-config__upload">
      <input type="file" accept=".mp3,.wav,.ogg,.m4a,.aac" @change="onFileSelect" />
      <span v-if="uploading" class="bgm-config__hint">上传中...</span>
      <span v-else-if="bgmUrl" class="bgm-config__hint bgm-config__hint--ok">已上传 ✓</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { uploadBgm } from '../api/files'

const props = defineProps<{
  mode: string
  bgmPath: string
}>()

const emit = defineEmits<{
  (e: 'update:mode', val: string): void
  (e: 'update:bgmPath', val: string): void
}>()

const modes = [
  { value: 'default', label: '默认' },
  { value: 'custom', label: '自定义' },
  { value: 'none', label: '无' },
]

const uploading = ref(false)
const bgmUrl = ref('')

async function onFileSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const res = await uploadBgm(file)
    bgmUrl.value = res.data.bgm_url || res.data.bgm_path
    emit('update:bgmPath', res.data.bgm_path)
  } catch (err: any) {
    alert('上传失败: ' + (err.message || '未知错误'))
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.bgm-config__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.bgm-config__options {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.bgm-config__radio {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
}

.bgm-config__upload {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bgm-config__hint {
  font-size: 13px;
  color: var(--text-hint);
}

.bgm-config__hint--ok {
  color: var(--success);
}
</style>
