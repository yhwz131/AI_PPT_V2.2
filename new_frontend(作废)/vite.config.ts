import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/files': {
        target: 'http://127.0.0.1:9088',
        changeOrigin: true,
      },
      '/conversion': {
        target: 'http://127.0.0.1:9088',
        changeOrigin: true,
      },
      '/my_digital_human': {
        target: 'http://127.0.0.1:9088',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:9088',
        changeOrigin: true,
      },
      '/video': {
        target: 'http://127.0.0.1:9088',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://127.0.0.1:9088',
        changeOrigin: true,
      },
    },
  },
})
