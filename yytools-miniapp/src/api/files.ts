import http from './request'

export function getFileList(params?: { page?: number; per_page?: number; folder_id?: string }) {
  return http.get('/files', { params })
}

export function getFileDetail(fileId: string) {
  return http.get(`/files/${fileId}`)
}

export function uploadFile(data: FormData) {
  return http.post('/files/upload', data, {
    header: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteFile(fileId: string) {
  return http.delete(`/files/${fileId}`)
}

export function searchFiles(keyword: string) {
  return http.get('/files/search', { params: { keyword } })
}

export function likeFile(fileId: string) {
  return http.post(`/files/${fileId}/like`)
}

export function unlikeFile(fileId: string) {
  return http.delete(`/files/${fileId}/like`)
}

export function favoriteFile(fileId: string) {
  return http.post(`/files/${fileId}/favorite`)
}

export function unfavoriteFile(fileId: string) {
  return http.delete(`/files/${fileId}/favorite`)
}

export function getFavoriteFiles() {
  return http.get('/files/favorites')
}

export function getFileDownloadUrl(storedName: string) {
  return `${http.config.baseURL}/files/download/${storedName}`
}

export function getFilePreviewUrl(storedName: string) {
  return `${http.config.baseURL}/files/preview/${storedName}`
}
