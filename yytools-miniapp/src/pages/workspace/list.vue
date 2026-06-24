<template>
  <view class="workspace-list-page">
    <view class="tabs">
      <view :class="['tab', activeTab === 'owned' && 'tab-active']" @click="activeTab = 'owned'">
        <text>我创建的</text>
      </view>
      <view :class="['tab', activeTab === 'joined' && 'tab-active']" @click="activeTab = 'joined'">
        <text>我加入的</text>
      </view>
    </view>

    <view v-if="currentList.length === 0 && !loading" class="empty-wrap">
      <EmptyState
        :icon="activeTab === 'owned' ? '🏗️' : '🤝'"
        :text="activeTab === 'owned' ? '还没有创建空间' : '还没有加入空间'"
        :actionText="activeTab === 'owned' ? '创建空间' : undefined"
        @action="showCreateModal = true"
      />
    </view>
    <view v-else>
      <view
        v-for="ws in currentList"
        :key="ws.id"
        class="workspace-card"
        @click="goDetail(ws.id)"
      >
        <view class="ws-header">
          <text class="ws-name">{{ ws.name }}</text>
          <text v-if="ws.member_role" class="ws-role">{{ ws.member_role }}</text>
        </view>
        <text v-if="ws.description" class="ws-desc">{{ ws.description }}</text>
        <view class="ws-meta">
          <text>{{ ws.member_count || 0 }} 成员</text>
          <text>{{ ws.file_count || 0 }} 文件</text>
        </view>
      </view>
    </view>

    <view class="fab" @click="showCreateModal = true">
      <text class="fab-icon">+</text>
    </view>

    <view v-if="showCreateModal" class="modal-mask" @click="showCreateModal = false">
      <view class="modal-content" @click.stop>
        <text class="modal-title">创建协作空间</text>
        <input v-model="newName" class="form-input" placeholder="空间名称" focus />
        <textarea v-model="newDesc" class="form-textarea" placeholder="描述（可选）" />
        <view class="modal-actions">
          <button class="modal-btn cancel" @click="showCreateModal = false">取消</button>
          <button class="modal-btn confirm" @click="onCreate">创建</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getWorkspaceList, createWorkspace } from '../../api/workspace'
import EmptyState from '../../components/EmptyState.vue'

const activeTab = ref<'owned' | 'joined'>('owned')
const ownedWorkspaces = ref<any[]>([])
const joinedWorkspaces = ref<any[]>([])
const loading = ref(false)
const showCreateModal = ref(false)
const newName = ref('')
const newDesc = ref('')

const currentList = computed(() => {
  return activeTab.value === 'owned' ? ownedWorkspaces.value : joinedWorkspaces.value
})

onShow(async () => {
  await loadData()
})

async function loadData() {
  loading.value = true
  try {
    const res: any = await getWorkspaceList()
    if (res.success) {
      ownedWorkspaces.value = res.data.owned || []
      joinedWorkspaces.value = res.data.joined || []
    }
  } catch (e) {
    console.error('加载空间列表失败:', e)
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  if (!newName.value.trim()) {
    uni.showToast({ title: '请输入空间名称', icon: 'none' })
    return
  }
  try {
    const res: any = await createWorkspace({
      name: newName.value.trim(),
      description: newDesc.value.trim(),
    })
    if (res.success) {
      uni.showToast({ title: '创建成功', icon: 'success' })
      showCreateModal.value = false
      newName.value = ''
      newDesc.value = ''
      await loadData()
    }
  } catch (e) {
    console.error('创建失败:', e)
  }
}

function goDetail(id: string) {
  uni.navigateTo({ url: `/pages/workspace/detail?id=${id}` })
}
</script>

<style scoped>
.workspace-list-page {
  padding: 20rpx;
  min-height: 100vh;
}

.tabs {
  display: flex;
  background: #fff;
  border-radius: 16rpx;
  padding: 6rpx;
  margin-bottom: 20rpx;
}

.tab {
  flex: 1;
  text-align: center;
  padding: 18rpx 0;
  border-radius: 12rpx;
  font-size: 28rpx;
  color: #666;
}

.tab-active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  font-weight: 600;
}

.empty-wrap {
  padding-top: 100rpx;
}

.workspace-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.ws-header {
  display: flex;
  align-items: center;
  margin-bottom: 8rpx;
}

.ws-name {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
  flex: 1;
}

.ws-role {
  font-size: 22rpx;
  color: #667eea;
  background: rgba(102, 126, 234, 0.1);
  padding: 4rpx 16rpx;
  border-radius: 10rpx;
}

.ws-desc {
  display: block;
  font-size: 26rpx;
  color: #666;
  margin-bottom: 12rpx;
}

.ws-meta {
  display: flex;
  gap: 24rpx;
  font-size: 24rpx;
  color: #999;
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

.form-textarea {
  width: 100%;
  height: 140rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 20rpx;
  font-size: 28rpx;
  margin-bottom: 20rpx;
  box-sizing: border-box;
}

.modal-actions {
  display: flex;
  gap: 20rpx;
}

.modal-btn {
  flex: 1;
  border-radius: 12rpx;
  padding: 20rpx 0;
  font-size: 28rpx;
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
