import Request from 'luch-request'
import { config } from './config'

const http = new Request()

http.setConfig((defaults) => {
  defaults.baseURL = config.baseUrl + config.apiPrefix
  defaults.timeout = 30000
  defaults.header = {
    'Content-Type': 'application/json',
  }
  return defaults
})

http.interceptors.request.use(
  (config) => {
    const token = uni.getStorageSync('yytools_token')
    if (token) {
      config.header = {
        ...config.header,
        Authorization: `Bearer ${token}`,
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

http.interceptors.response.use(
  (response) => {
    const data = response.data as any
    if (data.success === false) {
      uni.showToast({ title: data.message || '请求失败', icon: 'none' })
      if (data.code === 401) {
        uni.removeStorageSync('yytools_token')
        uni.removeStorageSync('yytools_user_info')
        uni.reLaunch({ url: '/pages/auth/login' })
      }
      return Promise.reject(data)
    }
    return data
  },
  (error) => {
    if (error.statusCode === 401) {
      uni.removeStorageSync('yytools_token')
      uni.removeStorageSync('yytools_user_info')
      uni.reLaunch({ url: '/pages/auth/login' })
    } else {
      uni.showToast({ title: '网络错误，请稍后重试', icon: 'none' })
    }
    return Promise.reject(error)
  }
)

export default http
