<template>
  <view class="home-page">
    <view class="home-header">
      <view class="greeting">
        <text class="greeting-text">{{ greeting }}，{{ username }}</text>
        <text class="greeting-sub">今天想做什么？</text>
      </view>
    </view>

    <view class="quick-actions">
      <view class="action-item" @click="goUpload">
        <view class="action-icon-wrap" style="background: rgba(102, 126, 234, 0.1);">
          <text class="action-icon">📤</text>
        </view>
        <text class="action-label">上传文件</text>
      </view>
      <view class="action-item" @click="goSearch">
        <view class="action-icon-wrap" style="background: rgba(76, 217, 100, 0.1);">
          <text class="action-icon">🔍</text>
        </view>
        <text class="action-label">搜索文件</text>
      </view>
      <view class="action-item" @click="goFolders">
        <view class="action-icon-wrap" style="background: rgba(240, 173, 78, 0.1);">
          <text class="action-icon">📁</text>
        </view>
        <text class="action-label">项目文件夹</text>
      </view>
      <view class="action-item" @click="goAi">
        <view class="action-icon-wrap" style="background: rgba(118, 75, 162, 0.1);">
          <text class="action-icon">🤖</text>
        </view>
        <text class="action-label">AI 工具</text>
      </view>
    </view>

    <view class="section">
      <view class="section-header">
        <text class="section-title">最近文件</text>
        <text class="section-more" @click="goFiles">查看全部</text>
      </view>
      <view v-if="recentFiles.length === 0" class="empty-hint">
        <text class="empty-text">暂无文件，快去上传吧</text>
      </view>
      <view v-else>
        <FileCard
          v-for="file in recentFiles"
          :key="file.id"
          :file="file"
          @click="goDetail(file.id)"
        />
      </view>
    </view>

    <view class="section">
      <view class="section-header">
        <text class="section-title">我的空间</text>
        <text class="section-more" @click="goWorkspaces">查看全部</text>
      </view>
      <view v-if="workspaces.length === 0" class="empty-hint">
        <text class="empty-text">暂无协作空间</text>
      </view>
      <view v-else class="workspace-list">
        <view
          v-for="ws in workspaces"
          :key="ws.id"
          class="workspace-card"
          @click="goWorkspaceDetail(ws.id)"
        >
          <text class="ws-name">{{ ws.name }}</text>
          <text class="ws-meta">{{ ws.member_count || 0 }} 成员 · {{ ws.file_count || 0 }} 文件</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '../../stores/user'
import { getFileList } from '../../api/files'
import { getWorkspaceList } from '../../api/workspace'
import FileCard from '../../components/FileCard.vue'

const userStore = useUserStore()
const recentFiles = ref<any[]>([])
const workspaces = ref<any[]>([])

const username = computed(() => userStore.username || '用户')

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

onShow(async () => {
  await loadData()
})

async function loadData() {
  try {
    const [filesRes, wsRes]: any[] = await Promise.all([
      getFileList({ page: 1, per_page: 5 }),
      getWorkspaceList(),
    ])
    if (filesRes.success) {
      recentFiles.value = filesRes.data.files || filesRes.data || []
    }
    if (wsRes.success) {
      const owned = wsRes.data.owned || []
      const joined = wsRes.data.joined || []
      workspaces.value = [...owned, ...joined].slice(0, 3)
    }
  } catch (e) {
    console.error('加载首页数据失败:', e)
  }
}

function goUpload() {
  uni.navigateTo({ url: '/pages/files/upload' })
}
function goSearch() {
  uni.navigateTo({ url: '/pages/files/search' })
}
function goFolders() {
  uni.navigateTo({ url: '/pages/folders/list' })
}
function goAi() {
  uni.navigateTo({ url: '/pages/ai/index' })
}
function goFiles() {
  uni.switchTab({ url: '/pages/files/list' })
}
function goWorkspaces() {
  uni.switchTab({ url: '/pages/workspace/list' })
}
function goDetail(id: string) {
  uni.navigateTo({ url: `/pages/files/detail?id=${id}` })
}
function goWorkspaceDetail(id: string) {
  uni.navigateTo({ url: `/pages/workspace/detail?id=${id}` })
}
</script>

<style scoped>
.home-page {
  padding: 20rpx;
}

.home-header {
  margin-bottom: 30rpx;
}

.greeting-text {
  display: block;
  font-size: 40rpx;
  font-weight: 700;
  color: #333;
  margin-bottom: 8rpx;
}

.greeting-sub {
  font-size: 28rpx;
  color: #999;
}

.quick-actions {
  display: flex;
  justify-content: space-between;
  background: #fff;
  border-radius: 20rpx;
  padding: 30rpx 20rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.action-icon-wrap {
  width: 88rpx;
  height: 88rpx;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12rpx;
}

.action-icon {
  font-size: 40rpx;
}

.action-label {
  font-size: 24rpx;
  color: #666;
}

.section {
  margin-bottom: 30rpx;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #333;
}

.section-more {
  font-size: 26rpx;
  color: #667eea;
}

.empty-hint {
  background: #fff;
  border-radius: 16rpx;
  padding: 40rpx;
  text-align: center;
}

.empty-text {
  font-size: 28rpx;
  color: #999;
}

.workspace-list {
  display: flex;
  flex-direction: column;
}

.workspace-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.ws-name {
  display: block;
  font-size: 30rpx;
  font-weight: 500;
  color: #333;
  margin-bottom: 8rpx;
}

.ws-meta {
  font-size: 24rpx;
  color: #999;
}
</style>
