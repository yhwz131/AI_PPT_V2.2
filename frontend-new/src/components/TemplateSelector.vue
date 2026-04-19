<template>
  <div class="template-selector">
    <h4 class="template-selector__title">数字人位置模板</h4>
    <div class="template-selector__grid">
      <div
        v-for="t in templates"
        :key="t.value"
        class="template-selector__item"
        :class="{ 'template-selector__item--active': modelValue === t.value }"
        @click="$emit('update:modelValue', t.value)"
      >
        <div class="template-selector__preview" :style="{ alignItems: t.vAlign, justifyContent: t.hAlign }">
          <div v-if="t.value !== 'none'" class="template-selector__avatar" />
        </div>
        <span class="template-selector__label">{{ t.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: string
}>()

defineEmits<{
  (e: 'update:modelValue', val: string): void
}>()

const templates = [
  { value: 'bottom-left',  label: '左下', vAlign: 'flex-end',   hAlign: 'flex-start' },
  { value: 'top-left',     label: '左上', vAlign: 'flex-start', hAlign: 'flex-start' },
  { value: 'bottom-right', label: '右下', vAlign: 'flex-end',   hAlign: 'flex-end' },
  { value: 'top-right',    label: '右上', vAlign: 'flex-start', hAlign: 'flex-end' },
  { value: 'center',       label: '居中', vAlign: 'center',     hAlign: 'center' },
  { value: 'none',         label: '无',   vAlign: 'center',     hAlign: 'center' },
]
</script>

<style scoped>
.template-selector__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.template-selector__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.template-selector__item {
  border: 2px solid var(--border);
  border-radius: 10px;
  padding: 8px;
  cursor: pointer;
  text-align: center;
  transition: border-color 0.2s;
}

.template-selector__item--active {
  border-color: var(--primary);
}

.template-selector__preview {
  width: 100%;
  aspect-ratio: 16/9;
  background: #f0f2f5;
  border-radius: 6px;
  display: flex;
  padding: 6px;
  margin-bottom: 6px;
}

.template-selector__avatar {
  width: 24px;
  height: 28px;
  border-radius: 4px;
  background: var(--primary-light);
}

.template-selector__label {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
