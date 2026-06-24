<template>
  <view class="detail-page">
    <view v-if="!file" class="loading-wrap">
      <text>加载中...</text>
    </view>
    <view v-else>
      <view class="file-header card">
        <text class="file-icon">{{ fileIcon }}</text>
        <view class="file-main">
          <text class="file-name">{{ file.filename }}</text>
          <text class="file-type">{{ fileType }}</text>
        </view>
      </view>

      <view class="file-meta card">
        <view class="meta-row">
          <text class="meta-label">大小</text>
          <text class="meta-value">{{ sizeStr }}</text>
        </view>
        <view class="meta-row">
          <text class="meta-label">上传时间</text>
          <text class="meta-value">{{ createdAt }}</text>
        </view>
        <view class="meta-row">
          <text class="meta-label">浏览次数</text>
          <text class="meta-value">{{ file.view_count || 0 }}</text>
        </view>
        <view v-if="file.project_name" class="meta-row">
          <text class="meta-label">项目名称</text>
          <text class="meta-value">{{ file.project_name }}</text>
        </view>
      </view>

      <view v-if="file.tags && file.tags.length" class="card">
        <text class="section-title">标签</text>
        <view class="tags-wrap">
          <text v-for="tag in file.tags" :key="tag.id" class="tag-item">{{ tag.name }}</text>
        </view>
      </view>

      <view v-if="file.categories && file.categories.length" class="card">
        <text class="section-title">分类</text>
        <view class="tags-wrap">
          <text v-for="cat in file.categories" :key="cat.id" class="tag-item cat-item">{{ cat.name }}</text>
        </view>
      </view>

      <view class="action-bar">
        <button class="action-btn primary" @click="onPreview">预览</button>
        <button class="action-btn" @click="onDownload">下载</button>
        <button :class="['action-btn', file.is_liked && 'liked']" @click="onLike">
          {{ file.is_liked ? '❤️' : '🤍' }} {{ file.like_count || 0 }}
        </button>
        <button :class="['action-btn', file.is_favorited && 'faved']" @click="onFavorite">
          {{ file.is_favorited ? '⭐' : '☆' }}
        </button>
      </view>

      <view class="danger-zone">
        <button class="delete-btn" @click="onDelete">删除文件</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getFileDetail, likeFile, unlikeFile, favoriteFile, unfavoriteFile, deleteFile } from '../../api/files'
import { formatFileSize, formatDate, getFileIcon, getFileType } from '../../utils/format'
import { previewFile } from '../../utils/preview'
import { config } from '../../api/config'

const file = ref<any>(null)
const fileId = ref('')

onLoad((options) => {
  if (options?.id) {
    fileId.value = options.id
    loadFile()
  }
})

async function loadFile() {
  try {
    const res: any = await getFileDetail(fileId.value)
    if (res.success) {
      file.value = res.data
    }
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

const fileIcon = computed(() => getFileIcon(file.value?.filename || ''))
const fileType = computed(() => getFileType(file.value?.filename || ''))
const sizeStr = computed(() => formatFileSize(file.value?.size || 0))
const createdAt = computed(() => formatDate(file.value?.created_at || ''))

function onPreview() {
  if (!file.value) return
  const url = `${config.baseUrl}/miniapp/api/files/preview/${file.value.stored_name}`
  previewFile(url, file.value.filename)
}

function onDownload() {
  if (!file.value) return
  const url = `${config.baseUrl}/miniapp/api/files/download/${file.value.stored_name}`
  uni.downloadFile({
    url,
    header: { Authorization: `Bearer ${uni.getStorageSync(config.tokenKey)}` },
    success: (res) => {
      if (res.statusCode === 200) {
        uni.openDocument({ filePath: res.tempFilePath, showMenu: true })
      }
    },
    fail: () => {
      uni.showToast({ title: '下载失败', icon: 'none' })
    },
  })
}

async function onLike() {
  if (!file.value) return
  try {
    if (file.value.is_liked) {
      await unlikeFile(file.value.id)
    } else {
      await likeFile(file.value.id)
    }
    file.value.is_liked = !file.value.is_liked
    file.value.like_count = (file.value.like_count || 0) + (file.value.is_liked ? 1 : -1)
  } catch (e) {
    console.error('操作失败:', e)
  }
}

async function onFavorite() {
  if (!file.value) return
  try {
    if (file.value.is_favorited) {
      await unfavoriteFile(file.value.id)
    } else {
      await favoriteFile(file.value.id)
    }
    file.value.is_favorited = !file.value.is_favorited
  } catch (e) {
    console.error('操作失败:', e)
  }
}

function onDelete() {
  uni.showModal({
    title: '确认删除',
    content: '删除后不可恢复，确定要删除吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          await deleteFile(fileId.value)
          uni.showToast({ title: '删除成功', icon: 'success' })
          setTimeout(() => uni.navigateBack(), 1500)
        } catch (e) {
          uni.showToast({ title: '删除失败', icon: 'none' })
        }
      }
    },
  })
}
</script>

<style scoped>
.detail-page {
  padding: 20rpx;
  padding-bottom: 200rpx;
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

.file-header {
  display: flex;
  align-items: center;
}

.file-icon {
  font-size: 64rpx;
  margin-right: 24rpx;
}

.file-main {
  flex: 1;
  min-width: 0;
}

.file-name {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 8rpx;
  word-break: break-all;
}

.file-type {
  font-size: 24rpx;
  color: #999;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  padding: 12rpx 0;
  border-bottom: 1rpx solid #f5f5f5;
}

.meta-row:last-child {
  border-bottom: none;
}

.meta-label {
  font-size: 26rpx;
  color: #999;
}

.meta-value {
  font-size: 26rpx;
  color: #333;
}

.section-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 16rpx;
}

.tags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.tag-item {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
  font-size: 24rpx;
  padding: 8rpx 20rpx;
  border-radius: 20rpx;
}

.cat-item {
  background: rgba(240, 173, 78, 0.1);
  color: #f0ad4e;
}

.action-bar {
  display: flex;
  gap: 16rpx;
  padding: 20rpx 0;
}

.action-btn {
  flex: 1;
  background: #f5f5f5;
  color: #666;
  border: none;
  border-radius: 12rpx;
  padding: 20rpx 0;
  font-size: 26rpx;
  text-align: center;
}

.action-btn::after {
  border: none;
}

.action-btn.primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.action-btn.liked {
  color: #dd524d;
}

.action-btn.faved {
  color: #f0ad4e;
}

.danger-zone {
  margin-top: 30rpx;
}

.delete-btn {
  background: #fff;
  color: #dd524d;
  border: 2rpx solid #dd524d;
  border-radius: 12rpx;
  padding: 20rpx 0;
  font-size: 28rpx;
}

.delete-btn::after {
  border: none;
}
</style>
