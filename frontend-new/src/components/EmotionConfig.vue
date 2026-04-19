<template>
  <div class="emo-config">
    <h4 class="emo-config__title">TTS情感控制</h4>
    <div class="emo-config__options">
      <label v-for="opt in methods" :key="opt.value" class="emo-config__radio">
        <input
          type="radio"
          :value="opt.value"
          :checked="method === opt.value"
          @change="$emit('update:method', opt.value)"
        />
        <span>{{ opt.label }}</span>
      </label>
    </div>

    <div v-if="method === 'vector'" class="emo-config__vector">
      <p class="emo-config__hint">8维情感向量 (每个值 ≤ 1.2, 总和 ≤ 1.5)</p>
      <div class="emo-config__inputs">
        <div v-for="(label, i) in vectorLabels" :key="i" class="emo-config__field">
          <label>{{ label }}</label>
          <input
            type="number"
            step="0.1"
            min="0"
            max="1.2"
            :value="vecValues[i]"
            @input="onVecInput(i, ($event.target as HTMLInputElement).value)"
          />
        </div>
      </div>
      <p v-if="vectorError" class="emo-config__error">{{ vectorError }}</p>
    </div>

    <div v-if="method === 'text'" class="emo-config__text">
      <textarea
        :value="emoText"
        @input="$emit('update:emoText', ($event.target as HTMLTextAreaElement).value)"
        placeholder="输入情感文本描述..."
        rows="2"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  method: string
  emoVec: string
  emoText: string
}>()

const emit = defineEmits<{
  (e: 'update:method', val: string): void
  (e: 'update:emoVec', val: string): void
  (e: 'update:emoText', val: string): void
}>()

const methods = [
  { value: 'natural', label: '自然' },
  { value: 'vector', label: '向量(8维)' },
  { value: 'text', label: '文本' },
]

const vectorLabels = ['开心', '悲伤', '愤怒', '惊讶', '恐惧', '厌恶', '轻蔑', '中性']

const vecValues = computed(() => {
  if (!props.emoVec) return [0, 0, 0, 0, 0, 0, 0, 1]
  return props.emoVec.split(',').map(Number)
})

const vectorError = computed(() => {
  const vals = vecValues.value
  if (vals.some(v => v > 1.2)) return '每个值不能超过1.2'
  if (vals.reduce((a, b) => a + b, 0) > 1.5) return '总和不能超过1.5'
  return ''
})

function onVecInput(idx: number, val: string) {
  const arr = [...vecValues.value]
  arr[idx] = parseFloat(val) || 0
  emit('update:emoVec', arr.join(','))
}

const hasError = computed(() => !!vectorError.value)
defineExpose({ hasError })
</script>

<style scoped>
.emo-config__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.emo-config__options {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.emo-config__radio {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
}

.emo-config__hint {
  font-size: 12px;
  color: var(--text-hint);
  margin-bottom: 8px;
}

.emo-config__inputs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.emo-config__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.emo-config__field label {
  font-size: 12px;
  color: var(--text-secondary);
}

.emo-config__field input {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}

.emo-config__error {
  font-size: 12px;
  color: var(--danger);
  margin-top: 6px;
}

.emo-config__text textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  resize: vertical;
}
</style>
