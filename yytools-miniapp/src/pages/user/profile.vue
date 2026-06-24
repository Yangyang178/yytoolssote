<template>
  <view class="profile-page">
    <view class="profile-header">
      <view class="avatar-wrap">
        <text class="avatar-text">{{ (username || '?')[0].toUpperCase() }}</text>
      </view>
      <text class="profile-name">{{ username }}</text>
      <text class="profile-email">{{ email }}</text>
    </view>

    <view class="stats-row">
      <view class="stat-item">
        <text class="stat-num">{{ stats.fileCount }}</text>
        <text class="stat-label">文件</text>
      </view>
      <view class="stat-item">
        <text class="stat-num">{{ stats.folderCount }}</text>
        <text class="stat-label">文件夹</text>
      </view>
      <view class="stat-item">
        <text class="stat-num">{{ stats.totalSize }}</text>
        <text class="stat-label">存储</text>
      </view>
    </view>

    <view class="menu-list">
      <view class="menu-item" @click="goSettings">
        <text class="menu-icon">⚙️</text>
        <text class="menu-text">账号设置</text>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-item" @click="goAccessLogs">
        <text class="menu-icon">📋</text>
        <text class="menu-text">访问记录</text>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-item" @click="goFeedback">
        <text class="menu-icon">💬</text>
        <text class="menu-text">意见反馈</text>
        <text class="menu-arrow">›</text>
      </view>
    </view>

    <button class="logout-btn" @click="onLogout">退出登录</button>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '../../stores/user'
import { getUserStats } from '../../api/user'
import { formatFileSize } from '../../utils/format'

const userStore = useUserStore()
const username = computed(() => userStore.username)
const email = computed(() => userStore.email)

const stats = reactive({
  fileCount: 0,
  folderCount: 0,
  totalSize: '0 B',
})

onShow(async () => {
  await loadStats()
  if (userStore.isLoggedIn) {
    await userStore.fetchProfile()
  }
})

async function loadStats() {
  try {
    const res: any = await getUserStats()
    if (res.success) {
      stats.fileCount = res.data.file_count || 0
      stats.folderCount = res.data.folder_count || 0
      stats.totalSize = formatFileSize(res.data.total_size || 0)
    }
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

function goSettings() {
  uni.navigateTo({ url: '/pages/user/settings' })
}

function goAccessLogs() {
  uni.navigateTo({ url: '/pages/user/access-logs' })
}

function goFeedback() {
  uni.showModal({
    title: '意见反馈',
    editable: true,
    placeholderText: '请输入你的反馈',
    success: async (res) => {
      if (res.confirm && res.content) {
        uni.showToast({ title: '感谢反馈！', icon: 'success' })
      }
    },
  })
}

function onLogout() {
  uni.showModal({
    title: '确认退出',
    content: '确定要退出登录吗？',
    success: (res) => {
      if (res.confirm) {
        userStore.handleLogout()
      }
    },
  })
}
</script>

<style scoped>
.profile-page {
  padding: 20rpx;
}

.profile-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 24rpx;
  margin-bottom: 20rpx;
}

.avatar-wrap {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16rpx;
}

.avatar-text {
  font-size: 48rpx;
  color: #fff;
  font-weight: 700;
}

.profile-name {
  font-size: 36rpx;
  font-weight: 700;
  color: #fff;
  margin-bottom: 8rpx;
}

.profile-email {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.8);
}

.stats-row {
  display: flex;
  background: #fff;
  border-radius: 16rpx;
  padding: 30rpx 0;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-num {
  font-size: 36rpx;
  font-weight: 700;
  color: #667eea;
  margin-bottom: 8rpx;
}

.stat-label {
  font-size: 24rpx;
  color: #999;
}

.menu-list {
  background: #fff;
  border-radius: 16rpx;
  overflow: hidden;
  margin-bottom: 30rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 28rpx 24rpx;
  border-bottom: 1rpx solid #f5f5f5;
}

.menu-item:last-child {
  border-bottom: none;
}

.menu-icon {
  font-size: 36rpx;
  margin-right: 16rpx;
}

.menu-text {
  flex: 1;
  font-size: 28rpx;
  color: #333;
}

.menu-arrow {
  font-size: 32rpx;
  color: #ccc;
}

.logout-btn {
  background: #fff;
  color: #dd524d;
  border: 2rpx solid #dd524d;
  border-radius: 16rpx;
  padding: 24rpx 0;
  font-size: 30rpx;
}

.logout-btn::after {
  border: none;
}
</style>
