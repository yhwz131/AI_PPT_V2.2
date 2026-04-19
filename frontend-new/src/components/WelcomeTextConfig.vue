<template>
  <div class="welcome-config">
    <h4 class="welcome-config__title">背景欢迎字幕</h4>
    <div class="welcome-config__field">
      <label class="welcome-config__label">欢迎语</label>
      <input
        class="welcome-config__input"
        type="text"
        :value="welcomeText"
        placeholder="例：欢迎来到AI PPT数字人讲解平台"
        @input="$emit('update:welcomeText', ($event.target as HTMLInputElement).value)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  welcomeText: string
}>()

defineEmits<{
  (e: 'update:welcomeText', val: string): void
}>()
</script>

<style scoped>
.welcome-config__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.welcome-config__field {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.welcome-config__label {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
  min-width: 56px;
}

.welcome-config__input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text);
  outline: none;
  transition: border-color 0.2s;
}

.welcome-config__input:focus {
  border-color: var(--primary);
}

.welcome-config__input::placeholder {
  color: var(--text-hint);
}
</style>
