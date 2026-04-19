import { ref, onUnmounted } from 'vue'

export function useTimer() {
  const elapsed = ref(0)
  const display = ref('00:00')
  let timer: ReturnType<typeof setInterval> | null = null
  let startTime = 0

  function tick() {
    elapsed.value = Math.floor((Date.now() - startTime) / 1000)
    const m = String(Math.floor(elapsed.value / 60)).padStart(2, '0')
    const s = String(elapsed.value % 60).padStart(2, '0')
    display.value = `${m}:${s}`
  }

  function start() {
    stop()
    startTime = Date.now()
    elapsed.value = 0
    display.value = '00:00'
    timer = setInterval(tick, 1000)
  }

  /** 刷新页后恢复计时（与 saveTaskToStorage 的 startTime 一致） */
  function startFrom(savedStartMs: number) {
    stop()
    startTime = savedStartMs
    tick()
    timer = setInterval(tick, 1000)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function reset() {
    stop()
    elapsed.value = 0
    display.value = '00:00'
  }

  onUnmounted(stop)

  return { elapsed, display, start, startFrom, stop, reset }
}
