<template>
  <div class="home">
    <div class="home__content">
      <p class="home__en-title">AI PPT Digital Human Presentation Platform</p>
      <h1 class="home__title">AI PPT 数 字 人 讲 解 平 台</h1>

      <div class="home__cards">
        <router-link to="/upload" class="home__card">
          <div class="home__card-icon">
            <svg viewBox="0 0 24 24" width="44" height="44" fill="none" stroke="currentColor" stroke-width="1.5">
              <rect x="3" y="3" width="18" height="14" rx="2"/>
              <polygon points="10,6 16,10 10,14"/>
              <line x1="3" y1="20" x2="21" y2="20" stroke-linecap="round"/>
              <line x1="8" y1="17" x2="8" y2="20"/>
              <line x1="16" y1="17" x2="16" y2="20"/>
            </svg>
          </div>
          <span class="home__card-label">AI数字人视频生成</span>
        </router-link>

        <router-link to="/videos" class="home__card">
          <div class="home__card-icon">
            <svg viewBox="0 0 24 24" width="44" height="44" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="12" cy="12" r="10"/>
              <polygon points="10,8 16,12 10,16"/>
            </svg>
          </div>
          <span class="home__card-label">AI数字人视频查看</span>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.home {
  width: 100%;
  min-height: 100vh;
  background: linear-gradient(180deg, #4b79e4, #3560c0);
  background-image: url('/images/bg1.gif');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  background-attachment: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
}

.home__content {
  text-align: center;
  padding: 40px 20px;
}

.home__en-title {
  font-size: 16px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.8);
  letter-spacing: 3px;
  margin-bottom: 14px;
}

.home__title {
  font-size: 38px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 6px;
  margin-bottom: 50px;
}

.home__cards {
  display: flex;
  gap: 28px;
  justify-content: center;
  flex-wrap: wrap;
}

.home__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 200px;
  height: 160px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: transform 0.2s, background 0.2s;
  cursor: pointer;
}

.home__card:hover {
  transform: translateY(-4px);
  background: rgba(255, 255, 255, 0.25);
}

.home__card-icon {
  color: rgba(255, 255, 255, 0.85);
  margin-bottom: 14px;
}

.home__card-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
}
</style>
