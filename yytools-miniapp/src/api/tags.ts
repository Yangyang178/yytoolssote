import http from './request'

export function getTags() {
  return http.get('/tags')
}

export function createTag(name: string) {
  return http.post('/tags', { name })
}

export function deleteTag(tagId: string) {
  return http.delete(`/tags/${tagId}`)
}

export function addTagToFile(fileId: string, tagId: string) {
  return http.post(`/files/${fileId}/tags`, { tag_id: tagId })
}

export function removeTagFromFile(fileId: string, tagId: string) {
  return http.delete(`/files/${fileId}/tags/${tagId}`)
}

export function getFilesByTag(tagId: string) {
  return http.get(`/tags/${tagId}/files`)
}
