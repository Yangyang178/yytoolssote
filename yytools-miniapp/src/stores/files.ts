import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getFileList, searchFiles, deleteFile, getFavoriteFiles } from '../api/files'

export const useFilesStore = defineStore('files', () => {
  const files = ref<any[]>([])
  const favorites = ref<any[]>([])
  const loading = ref(false)
  const page = ref(1)
  const hasMore = ref(true)
  const keyword = ref('')

  async function fetchFiles(reset = false) {
    if (loading.value) return
    if (reset) {
      page.value = 1
      hasMore.value = true
      files.value = []
    }
    if (!hasMore.value) return

    loading.value = true
    try {
      const res: any = await getFileList({ page: page.value, per_page: 20 })
      if (res.success) {
        const list = res.data.files || res.data || []
        if (reset) {
          files.value = list
        } else {
          files.value = [...files.value, ...list]
        }
        hasMore.value = list.length >= 20
        page.value++
      }
    } catch (e) {
      console.error('获取文件列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function search(keywordVal: string) {
    keyword.value = keywordVal
    if (!keywordVal.trim()) {
      return fetchFiles(true)
    }
    loading.value = true
    try {
      const res: any = await searchFiles(keywordVal)
      if (res.success) {
        files.value = res.data.files || res.data || []
      }
    } catch (e) {
      console.error('搜索失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function removeFile(fileId: string) {
    const res: any = await deleteFile(fileId)
    if (res.success) {
      files.value = files.value.filter((f) => f.id !== fileId)
      uni.showToast({ title: '删除成功', icon: 'success' })
    }
    return res
  }

  async function fetchFavorites() {
    try {
      const res: any = await getFavoriteFiles()
      if (res.success) {
        favorites.value = res.data.files || res.data || []
      }
    } catch (e) {
      console.error('获取收藏列表失败:', e)
    }
  }

  return {
    files,
    favorites,
    loading,
    page,
    hasMore,
    keyword,
    fetchFiles,
    search,
    removeFile,
    fetchFavorites,
  }
})
