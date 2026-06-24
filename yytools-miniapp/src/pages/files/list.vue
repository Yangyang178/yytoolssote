<template>
  <view class="file-list-page">
    <view class="search-bar" @click="goSearch">
      <text class="search-icon">🔍</text>
      <text class="search-placeholder">搜索文件...</text>
    </view>

    <view class="filter-tabs">
      <view
        v-for="tab in tabs"
        :key="tab.key"
        :class="['filter-tab', activeTab === tab.key && 'filter-tab-active']"
        @click="activeTab = tab.key"
      >
        <text>{{ tab.label }}</text>
      </view>
    </view>

    <scroll-view
      scroll-y
      class="file-scroll"
      @scrolltolower="loadMore"
    >
      <view v-if="filteredFiles.length === 0 && !loading" class="empty-wrap">
        <EmptyState icon="📂" text="暂无文件" actionText="上传文件" @action="goUpload" />
      </view>
      <view v-else>
        <FileCard
          v-for="file in filteredFiles"
          :key="file.id"
          :file="file"
          :showActions="true"
          @click="goDetail(file)"
        >
          <template #actions>
            <view class="card-actions">
              <text class="action-btn" @click.stop="onLike(file)">❤️ {{ file.like_count || 0 }}</text>
              <text class="action-btn" @click.stop="onFavorite(file)">{{ file.is_favorited ? '⭐' : '☆' }}</text>
            </view>
          </template>
        </FileCard>
      </view>
      <LoadingMore :loading="loading" :hasMore="hasMore" />
    </scroll-view>

    <view class="fab" @click="goUpload">
      <text class="fab-icon">+</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh } from '@dcloudio/uni-app'
import { useFilesStore } from '../../stores/files'
import { likeFile, unlikeFile, favoriteFile, unfavoriteFile } from '../../api/files'
import FileCard from '../../components/FileCard.vue'
import EmptyState from '../../components/EmptyState.vue'
import LoadingMore from '../../components/LoadingMore.vue'

const filesStore = useFilesStore()

const tabs = [
  { key: 'all', label: '全部' },
  { key: 'recent', label: '最近' },
  { key: 'favorite', label: '收藏' },
]
const activeTab = ref('all')
const loading = ref(false)
const hasMore = ref(true)

const filteredFiles = computed(() => {
  if (activeTab.value === 'favorite') {
    return filesStore.favorites
  }
  return filesStore.files
})

onShow(async () => {
  await refreshData()
})

onPullDownRefresh(async () => {
  await refreshData()
  uni.stopPullDownRefresh()
})

async function refreshData() {
  loading.value = true
  try {
    await Promise.all([
      filesStore.fetchFiles(true),
      filesStore.fetchFavorites(),
    ])
    hasMore.value = filesStore.hasMore
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (activeTab.value !== 'favorite') {
    await filesStore.fetchFiles()
    hasMore.value = filesStore.hasMore
  }
}

async function onLike(file: any) {
  try {
    if (file.is_liked) {
      await unlikeFile(file.id)
    } else {
      await likeFile(file.id)
    }
    file.is_liked = !file.is_liked
    file.like_count = (file.like_count || 0) + (file.is_liked ? 1 : -1)
  } catch (e) {
    console.error('操作失败:', e)
  }
}

async function onFavorite(file: any) {
  try {
    if (file.is_favorited) {
      await unfavoriteFile(file.id)
    } else {
      await favoriteFile(file.id)
    }
    file.is_favorited = !file.is_favorited
  } catch (e) {
    console.error('操作失败:', e)
  }
}

function goSearch() {
  uni.navigateTo({ url: '/pages/files/search' })
}

function goUpload() {
  uni.navigateTo({ url: '/pages/files/upload' })
}

function goDetail(file: any) {
  uni.navigateTo({ url: `/pages/files/detail?id=${file.id}` })
}
</script>

<style scoped>
.file-list-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.search-bar {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 16rpx;
  padding: 20rpx 24rpx;
  margin: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}

.search-icon {
  font-size: 28rpx;
  margin-right: 12rpx;
}

.search-placeholder {
  font-size: 28rpx;
  color: #999;
}

.filter-tabs {
  display: flex;
  padding: 0 20rpx;
  margin-bottom: 10rpx;
}

.filter-tab {
  padding: 12rpx 30rpx;
  border-radius: 30rpx;
  font-size: 26rpx;
  color: #666;
  margin-right: 16rpx;
  background: #fff;
}

.filter-tab-active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.file-scroll {
  flex: 1;
  padding: 0 20rpx;
}

.card-actions {
  display: flex;
  gap: 16rpx;
}

.action-btn {
  font-size: 24rpx;
  color: #999;
  padding: 8rpx 12rpx;
}

.empty-wrap {
  padding-top: 100rpx;
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
</style>
