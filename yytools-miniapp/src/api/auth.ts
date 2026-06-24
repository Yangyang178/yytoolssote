import http from './request'

export function wxLogin(code: string) {
  return http.post('/auth/wx-login', { code })
}

export function accountLogin(email: string, password: string) {
  return http.post('/auth/login', { email, password })
}

export function register(data: { email: string; username: string; password: string; code: string }) {
  return http.post('/auth/register', data)
}

export function sendVerifyCode(email: string, purpose: string = 'login') {
  return http.post('/auth/send-code', { email, purpose })
}

export function getProfile() {
  return http.get('/auth/profile')
}

export function updateProfile(data: { username?: string; avatar?: string }) {
  return http.post('/auth/profile', data)
}

export function changePassword(oldPassword: string, newPassword: string) {
  return http.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword })
}

export function logout() {
  return http.post('/auth/logout')
}
