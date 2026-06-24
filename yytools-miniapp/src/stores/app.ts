import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const loading = ref(false)
  const toastMsg = ref('')
  const toastType = ref<'success' | 'error' | 'info'>('info')

  function showLoading() {
    loading.value = true
  }

  function hideLoading() {
    loading.value = false
  }

  function showToast(msg: string, type: 'success' | 'error' | 'info' = 'info') {
    toastMsg.value = msg
    toastType.value = type
    uni.showToast({
      title: msg,
      icon: type === 'error' ? 'none' : type === 'success' ? 'success' : 'none',
      duration: 2000,
    })
  }

  return {
    loading,
    toastMsg,
    toastType,
    showLoading,
    hideLoading,
    showToast,
  }
})
