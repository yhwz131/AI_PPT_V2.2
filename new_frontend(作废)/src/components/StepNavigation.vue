<template>
  <div class="step-navigation">
    <div class="steps-container">
      <div
        v-for="(step, index) in steps"
        :key="index"
        class="step-item"
        :class="{
          'is-active': currentStep === index,
          'is-completed': currentStep > index,
          'is-clickable': canClickStep(index)
        }"
        @click="handleStepClick(index)"
      >
        <div class="step-circle">
          <el-icon v-if="currentStep > index" :size="18"><Check /></el-icon>
          <span v-else>{{ index + 1 }}</span>
        </div>
        <div class="step-label">{{ step.label }}</div>
        <div v-if="index < steps.length - 1" class="step-line" :class="{ 'is-completed': currentStep > index }" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkflowStore } from '@/stores/workflow'
import { Check } from '@element-plus/icons-vue'

const router = useRouter()
const workflowStore = useWorkflowStore()

const steps = [
  { label: '上传PPT', path: '/upload' },
  { label: '讲稿编辑', path: '/script' },
  { label: '模板配置', path: '/template' },
  { label: '生成视频', path: '/generate' },
]

const currentStep = computed(() => workflowStore.currentStep)

function canClickStep(index: number): boolean {
  return workflowStore.canGoToStep(index)
}

function handleStepClick(index: number) {
  if (canClickStep(index)) {
    workflowStore.setStep(index)
    router.push(steps[index].path)
  }
}
</script>

<style scoped lang="scss">
.step-navigation {
  background-color: var(--bg-secondary);
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
}

.steps-container {
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: 700px;
  margin: 0 auto;
}

.step-item {
  display: flex;
  align-items: center;
  position: relative;

  &.is-clickable {
    cursor: pointer;
    &:hover .step-circle {
      transform: scale(1.1);
    }
  }

  &:not(.is-clickable) {
    cursor: not-allowed;
    opacity: 0.5;
  }
}

.step-circle {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  background-color: var(--bg-primary);
  color: var(--text-secondary);
  border: 2px solid var(--border-color);
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.step-item.is-active .step-circle {
  background-color: var(--accent-primary);
  border-color: var(--accent-primary);
  color: white;
}

.step-item.is-completed .step-circle {
  background-color: var(--accent-success);
  border-color: var(--accent-success);
  color: white;
}

.step-label {
  margin-left: 8px;
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.step-item.is-active .step-label {
  color: var(--accent-primary);
  font-weight: 600;
}

.step-item.is-completed .step-label {
  color: var(--accent-success);
}

.step-line {
  width: 60px;
  height: 2px;
  background-color: var(--border-color);
  margin: 0 12px;
  transition: background-color 0.3s ease;

  &.is-completed {
    background-color: var(--accent-success);
  }
}
</style>
