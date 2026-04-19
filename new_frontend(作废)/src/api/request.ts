import axios from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '@/types'

const request = axios.create({
  baseURL: '',
  timeout: 300000,
})

let loadingCount = 0

function startLoading() {
  loadingCount++
}

function stopLoading() {
  loadingCount--
}

request.interceptors.request.use(
  (config) => {
    startLoading()
    return config
  },
  (error) => {
    stopLoading()
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    stopLoading()
    const res = response.data as ApiResponse
    if (res.code !== undefined && res.code !== 0 && res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return response.data
  },
  (error) => {
    stopLoading()
    const message = error.response?.data?.message || error.message || '网络错误'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default request
