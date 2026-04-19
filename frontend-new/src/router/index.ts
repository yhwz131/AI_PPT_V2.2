import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: () => import('../pages/IndexPage.vue') },
    { path: '/upload', component: () => import('../pages/UploadPage.vue') },
    { path: '/videos', component: () => import('../pages/VideoListPage.vue') },
  ],
})

export default router
