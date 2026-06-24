import http from './request'

export function aiChat(message: string, model: string = 'deepseek-chat') {
  return http.post('/ai/chat', { message, model })
}

export function getAiHistory() {
  return http.get('/ai/history')
}

export function deleteAiHistory(contentId: string) {
  return http.delete(`/ai/history/${contentId}`)
}
