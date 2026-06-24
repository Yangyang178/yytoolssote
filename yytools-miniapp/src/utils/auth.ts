import { config } from '../api/config'

export function getToken(): string {
  return uni.getStorageSync(config.tokenKey) || ''
}

export function setToken(token: string) {
  uni.setStorageSync(config.tokenKey, token)
}

export function removeToken() {
  uni.removeStorageSync(config.tokenKey)
}

export function isLoggedIn(): boolean {
  return !!getToken()
}

export function getUserInfo(): any {
  const raw = uni.getStorageSync(config.userInfoKey)
  if (!raw) return null
  try {
    return typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return null
  }
}

export function setUserInfo(info: any) {
  uni.setStorageSync(config.userInfoKey, JSON.stringify(info))
}

export function removeUserInfo() {
  uni.removeStorageSync(config.userInfoKey)
}

export function clearAuth() {
  removeToken()
  removeUserInfo()
}
