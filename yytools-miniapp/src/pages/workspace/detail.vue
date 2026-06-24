<template>
  <view class="workspace-detail-page">
    <view v-if="!workspace" class="loading-wrap">
      <text>加载中...</text>
    </view>
    <view v-else>
      <view class="ws-header card">
        <text class="ws-name">{{ workspace.name }}</text>
        <text v-if="workspace.description" class="ws-desc">{{ workspace.description }}</text>
        <view class="ws-stats">
          <view class="stat-item">
            <text class="stat-num">{{ workspace.member_count || 0 }}</text>
            <text class="stat-label">成员</text>
          </view>
          <view class="stat-item">
            <text class="stat-num">{{ workspace.file_count || 0 }}</text>
            <text class="stat-label">文件</text>
          </view>
        </view>
      </view>

      <view class="action-row">
        <button class="action-btn" @click="goMembers">👥 成员管理</button>
        <button class="action-btn" @click="onInvite">📧 邀请成员</button>
      </view>

      <view class="section-title">
        <text>空间文件</text>
      </view>

      <view v-if="files.length === 0" class="empty-wrap">
        <EmptyState icon="📄" text="暂无文件" />
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
import { getWorkspaceDetail, inviteMember } from '../../api/workspace'
import FileCard from '../../components/FileCard.vue'
import EmptyState from '../../components/EmptyState.vue'

const workspace = ref<any>(null)
const files = ref<any[]>([])
const workspaceId = ref('')

onLoad((options) => {
  if (options?.id) {
    workspaceId.value = options.id
    loadData()
  }
})

async function loadData() {
  try {
    const res: any = await getWorkspaceDetail(workspaceId.value)
    if (res.success) {
      workspace.value = res.data.workspace || res.data
      files.value = res.data.files || []
    }
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function goMembers() {
  uni.navigateTo({ url: `/pages/workspace/members?id=${workspaceId.value}` })
}

function onInvite() {
  uni.showModal({
    title: '邀请成员',
    editable: true,
    placeholderText: '输入邮箱地址',
    success: async (res) => {
      if (res.confirm && res.content) {
        try {
          const inviteRes: any = await inviteMember(workspaceId.value, {
            email: res.content.trim(),
          })
          if (inviteRes.success) {
            uni.showToast({ title: '邀请成功', icon: 'success' })
            await loadData()
          }
        } catch (e) {
          console.error('邀请失败:', e)
        }
      }
    },
  })
}

function goFileDetail(id: string) {
  uni.navigateTo({ url: `/pages/files/detail?id=${id}` })
}
</script>

<style scoped>
.workspace-detail-page {
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

.ws-name {
  display: block;
  font-size: 36rpx;
  font-weight: 700;
  color: #333;
  margin-bottom: 12rpx;
}

.ws-desc {
  display: block;
  font-size: 26rpx;
  color: #666;
  margin-bottom: 20rpx;
}

.ws-stats {
  display: flex;
  gap: 40rpx;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-num {
  font-size: 36rpx;
  font-weight: 700;
  color: #667eea;
}

.stat-label {
  font-size: 24rpx;
  color: #999;
}

.action-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.action-btn {
  flex: 1;
  background: #fff;
  border: 2rpx solid #eee;
  border-radius: 12rpx;
  padding: 20rpx 0;
  font-size: 26rpx;
  color: #333;
}

.action-btn::after {
  border: none;
}

.section-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 16rpx;
}

.empty-wrap {
  padding-top: 40rpx;
}
</style>
