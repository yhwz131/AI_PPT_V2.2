<template>
  <div class="step-nav">
    <div
      v-for="(label, i) in steps"
      :key="i"
      class="step-nav__item"
      :class="{
        'step-nav__item--active': i === current,
        'step-nav__item--done': i < current,
        'step-nav__item--clickable': i < current
      }"
      @click="i < current && $emit('go', i)"
    >
      <div class="step-nav__circle">
        <template v-if="i < current">✓</template>
        <template v-else>{{ i + 1 }}</template>
      </div>
      <span class="step-nav__label">{{ label }}</span>
      <div v-if="i < steps.length - 1" class="step-nav__line" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  steps: string[]
  current: number
}>()

defineEmits<{
  (e: 'go', step: number): void
}>()
</script>

<style scoped>
.step-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 0 24px;
}

.step-nav__item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: default;
}

.step-nav__item--clickable {
  cursor: pointer;
}

.step-nav__circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  background: #e0e4f0;
  color: #999;
  flex-shrink: 0;
  transition: all 0.3s;
}

.step-nav__item--active .step-nav__circle {
  background: var(--primary);
  color: #fff;
}

.step-nav__item--done .step-nav__circle {
  background: var(--success);
  color: #fff;
}

.step-nav__label {
  font-size: 14px;
  color: var(--text-hint);
  white-space: nowrap;
  transition: color 0.3s;
}

.step-nav__item--active .step-nav__label {
  color: var(--primary);
  font-weight: 600;
}

.step-nav__item--done .step-nav__label {
  color: var(--success);
}

.step-nav__line {
  width: 48px;
  height: 2px;
  background: #e0e4f0;
  margin: 0 8px;
}

.step-nav__item--done + .step-nav__item .step-nav__line,
.step-nav__item--done .step-nav__line {
  background: var(--success);
}
</style>
