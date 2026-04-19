import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/upload',
  },
  {
    path: '/upload',
    name: 'Upload',
    component: () => import('@/views/UploadView.vue'),
  },
  {
    path: '/script',
    name: 'Script',
    component: () => import('@/views/ScriptView.vue'),
  },
  {
    path: '/template',
    name: 'Template',
    component: () => import('@/views/TemplateView.vue'),
  },
  {
    path: '/generate',
    name: 'Generate',
    component: () => import('@/views/GenerateView.vue'),
  },
  {
    path: '/library',
    name: 'Library',
    component: () => import('@/views/LibraryView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
