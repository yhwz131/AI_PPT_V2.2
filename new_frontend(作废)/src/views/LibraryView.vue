<template>
  <div class="library-view">
    <div class="library-header">
      <h2 class="library-title">作品库</h2>
      <el-button
        :icon="Refresh"
        circle
        :loading="loading"
        @click="loadWorks"
      />
    </div>

    <el-alert
      v-if="errorMsg"
      :title="errorMsg"
      type="error"
      show-icon
      closable
      @close="errorMsg = ''"
      class="library-alert"
    />

    <div v-if="loading" class="works-grid">
      <el-card
        v-for="i in 8"
        :key="i"
        class="work-card skeleton-card"
        shadow="hover"
      >
        <el-skeleton animated>
          <template #template>
            <el-skeleton-item variant="image" class="skeleton-thumb" />
            <div class="skeleton-body">
              <el-skeleton-item variant="h3" class="skeleton-title" />
              <el-skeleton-item variant="text" class="skeleton-text" />
            </div>
          </template>
        </el-skeleton>
      </el-card>
    </div>

    <el-empty
      v-else-if="works.length === 0"
      description="暂无作品"
      :image-size="160"
    />

    <div v-else class="works-grid">
      <el-card
        v-for="work in works"
        :key="work.file_name"
        class="work-card"
        shadow="hover"
        @click="openPlayer(work)"
      >
        <div class="card-thumbnail">
          <el-image
            :src="getThumbnail(work)"
            fit="cover"
            class="thumbnail-image"
          >
            <template #error>
              <div class="thumbnail-placeholder">
                <el-icon :size="48"><PictureFilled /></el-icon>
              </div>
            </template>
          </el-image>
          <div class="play-overlay">
            <el-icon :size="48" class="play-icon"><VideoPlay /></el-icon>
          </div>
        </div>
        <div class="card-body">
          <h3 class="card-title" :title="work.file_name">{{ work.file_name }}</h3>
          <span class="card-pages">{{ work.content_text?.length ?? 0 }} 页</span>
        </div>
      </el-card>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="currentWork?.file_name ?? ''"
      width="70%"
      destroy-on-close
      class="video-dialog"
      align-center
    >
      <VideoPlayer
        v-if="dialogVisible && currentWork"
        :src="getVideoSrc(currentWork)"
        :poster="getThumbnail(currentWork)"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Refresh, VideoPlay, PictureFilled } from '@element-plus/icons-vue'
import { getBasicInformation } from '@/api'
import VideoPlayer from '@/components/VideoPlayer.vue'
import type { BasicInformationItem } from '@/types'

const works = ref<BasicInformationItem[]>([])
const loading = ref(false)
const errorMsg = ref('')
const dialogVisible = ref(false)
const currentWork = ref<BasicInformationItem | null>(null)

function getThumbnail(work: BasicInformationItem): string {
  if (work.img_lis?.length > 0) {
    return work.img_lis[0]
  }
  return ''
}

function getVideoSrc(work: BasicInformationItem): string {
  if (work.m3u8_url) {
    return work.m3u8_url
  }
  return work.video_path ?? ''
}

function openPlayer(work: BasicInformationItem) {
  currentWork.value = work
  dialogVisible.value = true
}

async function loadWorks() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await getBasicInformation()
    works.value = res.data?.data ?? []
  } catch (e: any) {
    errorMsg.value = e?.message ?? '加载作品列表失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadWorks()
})
</script>

<style scoped lang="scss">
.library-view {
  max-width: 1400px;
  margin: 0 auto;
}

.library-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.library-title {
  font-size: 1.6rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.library-alert {
  margin-bottom: 20px;
}

.works-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.work-card {
  cursor: pointer;
  border-radius: 12px;
  background-color: var(--bg-card);
  border-color: var(--bg-border);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  overflow: hidden;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  }

  :deep(.el-card__body) {
    padding: 0;
  }
}

.skeleton-card {
  cursor: default;

  &:hover {
    transform: none;
    box-shadow: none;
  }

  :deep(.el-card__body) {
    padding: 16px;
  }
}

.skeleton-thumb {
  width: 100%;
  height: 180px;
}

.skeleton-body {
  padding: 12px 0 0;
}

.skeleton-title {
  width: 60%;
  height: 20px;
  margin-bottom: 10px;
}

.skeleton-text {
  width: 40%;
  height: 16px;
}

.card-thumbnail {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background-color: var(--bg-border);
}

.thumbnail-image {
  width: 100%;
  height: 100%;

  :deep(img) {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.thumbnail-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background-color: var(--bg-border);
  color: var(--text-secondary);
}

.play-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.35);
  opacity: 0;
  transition: opacity 0.25s ease;

  .work-card:hover & {
    opacity: 1;
  }
}

.play-icon {
  color: #fff;
  filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.5));
}

.card-body {
  padding: 14px 16px;
}

.card-title {
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-pages {
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.video-dialog {
  :deep(.el-dialog) {
    background-color: var(--bg-card);
    border: 1px solid var(--bg-border);
    border-radius: 12px;
  }

  :deep(.el-dialog__header) {
    padding: 16px 20px;
    border-bottom: 1px solid var(--bg-border);
  }

  :deep(.el-dialog__title) {
    color: var(--text-primary);
    font-weight: 600;
  }

  :deep(.el-dialog__headerbtn .el-dialog__close) {
    color: var(--text-secondary);
  }

  :deep(.el-dialog__body) {
    padding: 20px;
  }
}
</style>
