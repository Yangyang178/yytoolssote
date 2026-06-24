import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { wxLogin, accountLogin, getProfile, updateProfile as updateProfileApi } from '../api/auth'
import { setToken, setUserInfo, getToken, getUserInfo, clearAuth } from '../utils/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref(getToken())
  const userInfo = ref(getUserInfo())

  const isLoggedIn = computed(() => !!token.value)
  const username = computed(() => userInfo.value?.username || '')
  const email = computed(() => userInfo.value?.email || '')
  const avatar = computed(() => userInfo.value?.avatar || '')
  const role = computed(() => userInfo.value?.role || 'user')

  async function handleWxLogin() {
    try {
      const loginRes = await new Promise<UniApp.LoginRes>((resolve, reject) => {
        uni.login({
          provider: 'weixin',
          success: resolve,
          fail: reject,
        })
      })

      const res: any = await wxLogin(loginRes.code)
      if (res.success) {
        token.value = res.data.token
        userInfo.value = res.data.user
        setToken(res.data.token)
        setUserInfo(res.data.user)
        return true
      }
      return false
    } catch (e) {
      console.error('微信登录失败:', e)
      return false
    }
  }

  async function handleAccountLogin(emailVal: string, password: string) {
    const res: any = await accountLogin(emailVal, password)
    if (res.success) {
      token.value = res.data.token
      userInfo.value = res.data.user
      setToken(res.data.token)
      setUserInfo(res.data.user)
      return true
    }
    return false
  }

  async function fetchProfile() {
    try {
      const res: any = await getProfile()
      if (res.success) {
        userInfo.value = res.data
        setUserInfo(res.data)
      }
    } catch (e) {
      console.error('获取用户信息失败:', e)
    }
  }

  async function updateProfile(data: { username?: string; avatar?: string }) {
    const res: any = await updateProfileApi(data)
    if (res.success) {
      if (data.username) userInfo.value = { ...userInfo.value, username: data.username }
      if (data.avatar) userInfo.value = { ...userInfo.value, avatar: data.avatar }
      setUserInfo(userInfo.value)
    }
    return res
  }

  function handleLogout() {
    token.value = ''
    userInfo.value = null
    clearAuth()
    uni.reLaunch({ url: '/pages/auth/login' })
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    username,
    email,
    avatar,
    role,
    handleWxLogin,
    handleAccountLogin,
    fetchProfile,
    updateProfile,
    handleLogout,
  }
})
