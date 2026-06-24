import http from './request'

export function getFolderList() {
  return http.get('/folders')
}

export function getFolderDetail(folderId: string) {
  return http.get(`/folders/${folderId}`)
}

export function createFolder(data: { name: string; description?: string }) {
  return http.post('/folders', data)
}

export function updateFolder(folderId: string, data: { name?: string; description?: string }) {
  return http.put(`/folders/${folderId}`, data)
}

export function deleteFolder(folderId: string) {
  return http.delete(`/folders/${folderId}`)
}

export function addFileToFolder(folderId: string, fileId: string) {
  return http.post(`/folders/${folderId}/files`, { file_id: fileId })
}

export function removeFileFromFolder(folderId: string, fileId: string) {
  return http.delete(`/folders/${folderId}/files/${fileId}`)
}
