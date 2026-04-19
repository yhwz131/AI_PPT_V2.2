<template>
  <div class="video-list-page">
    <header class="video-list-page__header">
      <router-link to="/" class="video-list-page__back">← 返回首页</router-link>
      <h1 class="video-list-page__title">视频库</h1>
      <button class="video-list-page__refresh" :disabled="loading" @click="load">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M1 4v6h6M23 20v-6h-6"/>
          <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/>
        </svg>
        刷新
      </button>
    </header>

    <div v-if="loading" class="video-list-page__loading">
      <div class="video-list-page__spinner" />
      <span>加载视频列表...</span>
    </div>

    <div v-else-if="error" class="video-list-page__error">
      <p>{{ error }}</p>
      <button class="video-list-page__btn" @click="load">重试</button>
    </div>

    <div v-else-if="videos.length === 0" class="video-list-page__empty">
      <p>暂无视频，请先生成一个</p>
      <router-link to="/upload" class="video-list-page__btn video-list-page__btn--primary">去生成</router-link>
    </div>

    <div v-else class="video-list-page__grid">
      <VideoCard
        v-for="(v, i) in videos"
        :key="i"
        :name="v.file_name"
        :poster="v.img_lis?.[0] ? staticUrl(v.img_lis[0]) : ''"
        @click="openDetail(v)"
      />
    </div>

    <VideoDetailModal
      :visible="showDetail"
      :video="currentVideo"
      @close="showDetail = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onActivated } from 'vue'
import VideoCard from '../components/VideoCard.vue'
import VideoDetailModal from '../components/VideoDetailModal.vue'
import { fetchVideoList, type VideoItem } from '../api/video'
import { staticUrl } from '../api/client'

const videos = ref<VideoItem[]>([])
const loading = ref(false)
const error = ref('')
const showDetail = ref(false)
const currentVideo = ref<VideoItem | null>(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    videos.value = await fetchVideoList()
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function openDetail(v: VideoItem) {
  currentVideo.value = v
  showDetail.value = true
}

onMounted(load)
onActivated(load)
</script>

<style scoped>
.video-list-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
  min-height: 100vh;
}

.video-list-page__header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.video-list-page__back {
  font-size: 14px;
  color: var(--primary);
}

.video-list-page__title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  flex: 1;
}

.video-list-page__refresh {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  background: #f0f2f5;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.video-list-page__refresh:hover { background: #e4e7ed; }
.video-list-page__refresh:disabled { opacity: 0.5; }

.video-list-page__loading,
.video-list-page__error,
.video-list-page__empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary);
}

.video-list-page__spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #e0e4f0;
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.video-list-page__btn {
  display: inline-block;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  background: #f0f2f5;
  color: var(--text-secondary);
  margin-top: 12px;
  transition: all 0.2s;
}

.video-list-page__btn:hover { background: #e4e7ed; }

.video-list-page__btn--primary {
  background: var(--primary);
  color: #fff;
}

.video-list-page__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
}
</style>
