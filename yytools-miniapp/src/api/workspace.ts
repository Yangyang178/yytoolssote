import http from './request'

export function getWorkspaceList() {
  return http.get('/workspaces')
}

export function getWorkspaceDetail(workspaceId: string) {
  return http.get(`/workspaces/${workspaceId}`)
}

export function createWorkspace(data: { name: string; description?: string }) {
  return http.post('/workspaces', data)
}

export function updateWorkspace(workspaceId: string, data: { name?: string; description?: string }) {
  return http.put(`/workspaces/${workspaceId}`, data)
}

export function deleteWorkspace(workspaceId: string) {
  return http.delete(`/workspaces/${workspaceId}`)
}

export function getWorkspaceMembers(workspaceId: string) {
  return http.get(`/workspaces/${workspaceId}/members`)
}

export function inviteMember(workspaceId: string, data: { email: string; role?: string }) {
  return http.post(`/workspaces/${workspaceId}/members`, data)
}

export function removeMember(workspaceId: string, userId: string) {
  return http.delete(`/workspaces/${workspaceId}/members/${userId}`)
}

export function addFileToWorkspace(workspaceId: string, fileId: string) {
  return http.post(`/workspaces/${workspaceId}/files`, { file_id: fileId })
}

export function removeFileFromWorkspace(workspaceId: string, fileId: string) {
  return http.delete(`/workspaces/${workspaceId}/files/${fileId}`)
}
