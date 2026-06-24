<template>
  <view class="logs-page">
    <view class="tabs">
      <view :class="['tab', activeTab === 'access' && 'tab-active']" @click="activeTab = 'access'">
        <text>访问记录</text>
      </view>
      <view :class="['tab', activeTab === 'operation' && 'tab-active']" @click="activeTab = 'operation'">
        <text>操作日志</text>
      </view>
    </view>

    <view v-if="currentLogs.length === 0" class="empty-wrap">
      <EmptyState icon="📋" text="暂无记录" />
    </view>
    <view v-else>
      <view v-for="log in currentLogs" :key="log.id" class="log-card">
        <view class="log-main">
          <text class="log-action">{{ formatAction(log.action) }}</text>
          <text v-if="log.message" class="log-msg">{{ log.message }}</text>
        </view>
        <text class="log-time">{{ formatRelativeTime(log.created_at || log.access_time) }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getAccessLogs, getOperationLogs } from '../../api/user'
import { formatRelativeTime } from '../../utils/format'
import EmptyState from '../../components/EmptyState.vue'

const activeTab = ref<'access' | 'operation'>('access')
const accessLogs = ref<any[]>([])
const operationLogs = ref<any[]>([])

const currentLogs = computed(() => {
  return activeTab.value === 'access' ? accessLogs.value : operationLogs.value
})

onShow(async () => {
  await loadLogs()
})

async function loadLogs() {
  try {
    const [accessRes, opRes]: any[] = await Promise.all([
      getAccessLogs({ page: 1, per_page: 50 }),
      getOperationLogs({ page: 1, per_page: 50 }),
    ])
    if (accessRes.success) {
      accessLogs.value = accessRes.data.logs || accessRes.data || []
    }
    if (opRes.success) {
      operationLogs.value = opRes.data.logs || opRes.data || []
    }
  } catch (e) {
    console.error('加载日志失败:', e)
  }
}

function formatAction(action: string): string {
  const map: Record<string, string> = {
    view: '浏览',
    download: '下载',
    open: '打开',
    upload: '上传',
    delete: '删除',
    login: '登录',
    logout: '退出',
    register: '注册',
    update_profile: '更新资料',
    change_password: '修改密码',
    ai_chat: 'AI对话',
  }
  return map[action] || action || '操作'
}
</script>

<style scoped>
.logs-page {
  padding: 20rpx;
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

.log-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 12rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}

.log-main {
  flex: 1;
  min-width: 0;
}

.log-action {
  display: block;
  font-size: 28rpx;
  color: #333;
  font-weight: 500;
  margin-bottom: 4rpx;
}

.log-msg {
  display: block;
  font-size: 24rpx;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-time {
  font-size: 24rpx;
  color: #ccc;
  margin-left: 16rpx;
  flex-shrink: 0;
}
</style>
