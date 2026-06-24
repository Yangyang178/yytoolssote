import http from './request'

export function getUserStats() {
  return http.get('/user/stats')
}

export function getAccessLogs(params?: { page?: number; per_page?: number }) {
  return http.get('/user/access-logs', { params })
}

export function getOperationLogs(params?: { page?: number; per_page?: number }) {
  return http.get('/user/operation-logs', { params })
}

export function getStorageUsage() {
  return http.get('/user/storage')
}

export function submitFeedback(data: { title: string; content: string; category: string }) {
  return http.post('/user/feedback', data)
}
