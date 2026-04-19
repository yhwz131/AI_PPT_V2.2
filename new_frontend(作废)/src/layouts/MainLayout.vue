<template>
  <div class="main-layout">
    <header class="app-header">
      <div class="header-left">
        <h1 class="app-title">
          <el-icon><VideoCamera /></el-icon>
          AI数字人PPT视频讲解
        </h1>
      </div>
      <div class="header-right">
        <el-button text @click="$router.push('/library')">
          <el-icon><FolderOpened /></el-icon>
          作品库
        </el-button>
      </div>
    </header>

    <StepNavigation v-if="showSteps" />

    <main class="app-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import StepNavigation from '@/components/StepNavigation.vue'
import { VideoCamera, FolderOpened } from '@element-plus/icons-vue'

const route = useRoute()
const showSteps = computed(() => !['/library'].includes(route.path))
</script>

<style scoped lang="scss">
.main-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--bg-primary);
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background-color: var(--bg-secondary);
  border-bottom: 2px solid var(--border-color);
}

.header-left {
  display: flex;
  align-items: center;
}

.app-title {
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--accent-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;

  :deep(.el-button) {
    color: var(--text-secondary);
    &:hover {
      color: var(--accent-primary);
    }
  }
}

.app-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}
</style>
