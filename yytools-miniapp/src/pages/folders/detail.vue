<template>
  <view class="folder-detail-page">
    <view v-if="!folder" class="loading-wrap">
      <text>加载中...</text>
    </view>
    <view v-else>
      <view class="folder-header card">
        <text class="folder-icon">📂</text>
        <view class="folder-info">
          <text class="folder-name">{{ folder.name }}</text>
          <text v-if="folder.description" class="folder-desc">{{ folder.description }}</text>
        </view>
      </view>

      <view class="section-title">
        <text>文件列表 ({{ files.length }})</text>
      </view>

      <view v-if="files.length === 0" class="empty-wrap">
        <EmptyState icon="📄" text="文件夹内暂无文件" />
      </view>
      <view v-else>
        <FileCard
          v-for="file in files"
          :key="file.id"
          :file="file"
          @click="goFileDetail(file.id)"
        />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getFolderDetail } from '../../api/folders'
import FileCard from '../../components/FileCard.vue'
import EmptyState from '../../components/EmptyState.vue'

const folder = ref<any>(null)
const files = ref<any[]>([])
const folderId = ref('')

onLoad((options) => {
  if (options?.id) {
    folderId.value = options.id
    loadFolder()
  }
})

async function loadFolder() {
  try {
    const res: any = await getFolderDetail(folderId.value)
    if (res.success) {
      folder.value = res.data.folder || res.data
      files.value = res.data.files || []
    }
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function goFileDetail(id: string) {
  uni.navigateTo({ url: `/pages/files/detail?id=${id}` })
}
</script>

<style scoped>
.folder-detail-page {
  padding: 20rpx;
}

.loading-wrap {
  display: flex;
  justify-content: center;
  padding: 100rpx 0;
  color: #999;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.folder-header {
  display: flex;
  align-items: center;
}

.folder-icon {
  font-size: 56rpx;
  margin-right: 20rpx;
}

.folder-info {
  flex: 1;
}

.folder-name {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 8rpx;
}

.folder-desc {
  font-size: 26rpx;
  color: #999;
}

.section-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 16rpx;
}

.empty-wrap {
  padding-top: 60rpx;
}
</style>
