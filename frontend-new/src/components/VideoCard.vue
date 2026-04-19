<template>
  <div class="video-card" @click="$emit('click')">
    <div class="video-card__poster">
      <img v-if="poster" :src="poster" :alt="name" />
      <div class="video-card__play">
        <svg viewBox="0 0 24 24" width="36" height="36" fill="rgba(255,255,255,0.9)">
          <polygon points="8,5 19,12 8,19"/>
        </svg>
      </div>
    </div>
    <div class="video-card__info">
      <span class="video-card__name">{{ name }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  name: string
  poster: string
}>()

defineEmits<{
  (e: 'click'): void
}>()
</script>

<style scoped>
.video-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  background: #fff;
}

.video-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.video-card__poster {
  position: relative;
  width: 100%;
  aspect-ratio: 16/9;
  background: #e0e4f0;
  overflow: hidden;
}

.video-card__poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-card__play {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.video-card:hover .video-card__play {
  opacity: 1;
}

.video-card__info {
  padding: 10px 12px;
}

.video-card__name {
  font-size: 14px;
  color: var(--text);
  font-weight: 500;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
