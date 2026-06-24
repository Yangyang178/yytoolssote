<template>
  <view class="folder-list-page">
    <view v-if="folders.length === 0 && !loading" class="empty-wrap">
      <EmptyState icon="📁" text="暂无项目文件夹" actionText="创建文件夹" @action="showCreateModal = true" />
    </view>
    <view v-else>
      <view v-for="folder in folders" :key="folder.id" class="folder-card" @click="goDetail(folder.id)">
        <text class="folder-icon">📂</text>
        <view class="folder-info">
          <text class="folder-name">{{ folder.name }}</text>
          <text class="folder-meta">{{ folder.file_count || 0 }} 个文件</text>
        </view>
        <text class="folder-arrow">›</text>
      </view>
    </view>

    <view class="fab" @click="showCreateModal = true">
      <text class="fab-icon">+</text>
    </view>

    <view v-if="showCreateModal" class="modal-mask" @click="showCreateModal = false">
      <view class="modal-content" @click.stop>
        <text class="modal-title">创建文件夹</text>
        <input v-model="newFolderName" class="form-input" placeholder="文件夹名称" focus />
        <input v-model="newFolderDesc" class="form-input" placeholder="描述（可选）" />
        <view class="modal-actions">
          <button class="modal-btn cancel" @click="showCreateModal = false">取消</button>
          <button class="modal-btn confirm" @click="onCreateFolder">创建</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getFolderList, createFolder } from '../../api/folders'
import EmptyState from '../../components/EmptyState.vue'

const folders = ref<any[]>([])
const loading = ref(false)
const showCreateModal = ref(false)
const newFolderName = ref('')
const newFolderDesc = ref('')

onShow(async () => {
  await loadFolders()
})

async function loadFolders() {
  loading.value = true
  try {
    const res: any = await getFolderList()
    if (res.success) {
      folders.value = res.data.folders || res.data || []
    }
  } catch (e) {
    console.error('加载文件夹失败:', e)
  } finally {
    loading.value = false
  }
}

async function onCreateFolder() {
  if (!newFolderName.value.trim()) {
    uni.showToast({ title: '请输入文件夹名称', icon: 'none' })
    return
  }
  try {
    const res: any = await createFolder({
      name: newFolderName.value.trim(),
      description: newFolderDesc.value.trim(),
    })
    if (res.success) {
      uni.showToast({ title: '创建成功', icon: 'success' })
      showCreateModal.value = false
      newFolderName.value = ''
      newFolderDesc.value = ''
      await loadFolders()
    }
  } catch (e) {
    console.error('创建失败:', e)
  }
}

function goDetail(id: string) {
  uni.navigateTo({ url: `/pages/folders/detail?id=${id}` })
}
</script>

<style scoped>
.folder-list-page {
  padding: 20rpx;
  min-height: 100vh;
}

.empty-wrap {
  padding-top: 100rpx;
}

.folder-card {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.folder-icon {
  font-size: 48rpx;
  margin-right: 20rpx;
}

.folder-info {
  flex: 1;
  min-width: 0;
}

.folder-name {
  display: block;
  font-size: 30rpx;
  font-weight: 500;
  color: #333;
  margin-bottom: 8rpx;
}

.folder-meta {
  font-size: 24rpx;
  color: #999;
}

.folder-arrow {
  font-size: 36rpx;
  color: #ccc;
}

.fab {
  position: fixed;
  right: 40rpx;
  bottom: 180rpx;
  width: 100rpx;
  height: 100rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(102, 126, 234, 0.4);
}

.fab-icon {
  font-size: 48rpx;
  color: #fff;
  font-weight: 300;
}

.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

.modal-content {
  width: 600rpx;
  background: #fff;
  border-radius: 24rpx;
  padding: 40rpx;
}

.modal-title {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 30rpx;
  text-align: center;
}

.form-input {
  width: 100%;
  height: 80rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
  margin-bottom: 20rpx;
  box-sizing: border-box;
}

.modal-actions {
  display: flex;
  gap: 20rpx;
  margin-top: 10rpx;
}

.modal-btn {
  flex: 1;
  border-radius: 12rpx;
  padding: 20rpx 0;
  font-size: 28rpx;
  text-align: center;
}

.modal-btn::after {
  border: none;
}

.modal-btn.cancel {
  background: #f0f0f0;
  color: #666;
}

.modal-btn.confirm {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}
</style>
