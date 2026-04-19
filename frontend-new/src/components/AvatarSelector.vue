<template>
  <div class="avatar-selector">
    <h4 class="avatar-selector__title">选择数字人</h4>

    <div class="avatar-selector__tabs">
      <button
        class="avatar-selector__tab"
        :class="{ 'avatar-selector__tab--active': tab === 'built-in' }"
        @click="tab = 'built-in'"
      >内置</button>
      <button
        class="avatar-selector__tab"
        :class="{ 'avatar-selector__tab--active': tab === 'custom' }"
        @click="tab = 'custom'"
      >自定义</button>
    </div>

    <div v-if="loading" class="avatar-selector__loading">加载中...</div>

    <div v-else class="avatar-selector__grid">
      <div
        v-for="dh in currentList"
        :key="dh.name"
        class="avatar-selector__card"
        :class="{ 'avatar-selector__card--active': selected?.name === dh.name }"
        @click="selectAvatar(dh)"
      >
        <img :src="staticUrl(dh.image)" :alt="dh.name" class="avatar-selector__img" />
        <span class="avatar-selector__name">{{ dh.name }}</span>
        <button
          class="avatar-selector__info"
          @click.stop="detailTarget = dh"
          title="详情"
        >i</button>
        <button
          v-if="tab === 'custom'"
          class="avatar-selector__del"
          @click.stop="$emit('delete', dh.name)"
          title="删除"
        >✕</button>
      </div>

      <div v-if="tab === 'custom'" class="avatar-selector__card avatar-selector__add" @click="$emit('addCustom')">
        <span class="avatar-selector__add-icon">+</span>
        <span class="avatar-selector__name">添加</span>
      </div>
    </div>

    <!-- 数字人详情弹窗 -->
    <Teleport to="body">
      <div v-if="detailTarget" class="avatar-detail-overlay" @click.self="detailTarget = null">
        <div class="avatar-detail">
          <button class="avatar-detail__close" @click="detailTarget = null">✕</button>
          <img :src="staticUrl(detailTarget.image)" :alt="detailTarget.name" class="avatar-detail__img" />
          <h3 class="avatar-detail__name">{{ detailTarget.name }}</h3>
          <p class="avatar-detail__brief">{{ detailTarget.brief || '暂无介绍' }}</p>
          <div class="avatar-detail__media">
            <div v-if="detailTarget.audio" class="avatar-detail__item">
              <span class="avatar-detail__label">音色试听</span>
              <audio :src="staticUrl(detailTarget.audio)" controls preload="none" />
            </div>
            <div v-if="detailTarget.video" class="avatar-detail__item">
              <span class="avatar-detail__label">形象预览</span>
              <video :src="staticUrl(detailTarget.video)" controls preload="none" class="avatar-detail__video" />
            </div>
          </div>
          <button class="avatar-detail__select" @click="selectAvatar(detailTarget!); detailTarget = null">
            选择此数字人
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchDigitalHumans, type DigitalHuman } from '../api/digitalHuman'
import { staticUrl } from '../api/client'

const props = defineProps<{
  selected: DigitalHuman | null
}>()

const emit = defineEmits<{
  (e: 'select', dh: DigitalHuman): void
  (e: 'delete', name: string): void
  (e: 'addCustom'): void
}>()

const tab = ref<'built-in' | 'custom'>('built-in')
const builtIn = ref<DigitalHuman[]>([])
const custom = ref<DigitalHuman[]>([])
const loading = ref(false)
const detailTarget = ref<DigitalHuman | null>(null)

const currentList = computed(() => tab.value === 'built-in' ? builtIn.value : custom.value)

async function load() {
  loading.value = true
  try {
    const [b, c] = await Promise.all([
      fetchDigitalHumans('built-in'),
      fetchDigitalHumans('custom'),
    ])
    builtIn.value = b
    custom.value = c
  } finally {
    loading.value = false
  }
}

function selectAvatar(dh: DigitalHuman) {
  emit('select', dh)
}

onMounted(load)

defineExpose({ reload: load })
</script>

<style scoped>
.avatar-selector__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.avatar-selector__tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.avatar-selector__tab {
  padding: 6px 20px;
  border-radius: 20px;
  font-size: 13px;
  background: #f0f2f5;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.avatar-selector__tab--active {
  background: var(--primary);
  color: #fff;
}

.avatar-selector__loading {
  text-align: center;
  padding: 24px;
  color: var(--text-hint);
}

.avatar-selector__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 12px;
}

.avatar-selector__card {
  border: 2px solid var(--border);
  border-radius: 10px;
  padding: 8px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s;
  position: relative;
}

.avatar-selector__card--active {
  border-color: var(--primary);
}

.avatar-selector__img {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
  margin-bottom: 6px;
}

.avatar-selector__name {
  font-size: 12px;
  color: var(--text-secondary);
  display: block;
}

.avatar-selector__info {
  position: absolute;
  bottom: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  font-style: italic;
  font-family: Georgia, serif;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.avatar-selector__card:hover .avatar-selector__info {
  opacity: 1;
}

.avatar-selector__del {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--danger);
  color: #fff;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-selector__add {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-style: dashed;
}

.avatar-selector__add-icon {
  font-size: 28px;
  color: var(--text-hint);
  margin-bottom: 4px;
}

/* ===== 详情弹窗 ===== */
.avatar-detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.avatar-detail {
  background: #fff;
  border-radius: 16px;
  width: 400px;
  max-height: 85vh;
  overflow-y: auto;
  padding: 28px 24px 20px;
  position: relative;
  text-align: center;
}

.avatar-detail__close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #f0f0f0;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-detail__img {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  object-fit: cover;
  margin-bottom: 12px;
  border: 3px solid var(--primary-light);
}

.avatar-detail__name {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 8px;
}

.avatar-detail__brief {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
  margin-bottom: 20px;
  text-align: left;
  padding: 0 4px;
}

.avatar-detail__media {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 20px;
}

.avatar-detail__item {
  text-align: left;
}

.avatar-detail__label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-hint);
  margin-bottom: 6px;
}

.avatar-detail__item audio {
  width: 100%;
  height: 36px;
}

.avatar-detail__video {
  width: 100%;
  max-height: 200px;
  border-radius: 8px;
  background: #000;
}

.avatar-detail__select {
  width: 100%;
  padding: 10px;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.avatar-detail__select:hover {
  background: var(--primary-dark);
}
</style>
