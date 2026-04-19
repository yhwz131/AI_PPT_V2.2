<template>
  <div class="style-selector">
    <span class="style-selector__label">解说风格：</span>
    <div class="style-selector__options">
      <button
        v-for="opt in options"
        :key="opt.value"
        class="style-selector__btn"
        :class="{ 'style-selector__btn--active': modelValue === opt.value }"
        @click="$emit('update:modelValue', opt.value)"
      >
        {{ opt.label }}
      </button>
    </div>
    <p class="style-selector__desc">{{ currentDesc }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: string
}>()

defineEmits<{
  (e: 'update:modelValue', val: string): void
}>()

const options = [
  { value: 'brief',        label: '简洁', desc: '精炼概括，每页仅保留核心要点，适合快节奏展示' },
  { value: 'normal',       label: '正常', desc: '详略得当，兼顾内容完整与表达流畅，适合大多数场景' },
  { value: 'professional', label: '专业', desc: '深度解读，补充分析与专业术语说明，适合学术或商务汇报' },
]

const currentDesc = computed(() =>
  options.find(o => o.value === props.modelValue)?.desc || ''
)
</script>

<style scoped>
.style-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.style-selector__label {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.style-selector__options {
  display: flex;
  gap: 8px;
}

.style-selector__btn {
  padding: 6px 18px;
  border-radius: 20px;
  font-size: 13px;
  background: #f0f2f5;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.style-selector__btn--active {
  background: var(--primary);
  color: #fff;
}

.style-selector__btn:hover:not(.style-selector__btn--active) {
  background: #e4e7ed;
}

.style-selector__desc {
  width: 100%;
  font-size: 12px;
  color: var(--text-hint);
  margin-top: -4px;
  padding-left: 2px;
  line-height: 1.5;
}
</style>
