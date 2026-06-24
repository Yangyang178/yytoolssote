<template>
  <view class="ai-page">
    <view class="ai-header card">
      <text class="ai-icon">🤖</text>
      <text class="ai-title">AI 智能助手</text>
      <text class="ai-desc">基于 DeepSeek 的智能对话</text>
    </view>

    <view class="ai-features">
      <view class="feature-item" @click="goGenerate('chat')">
        <text class="feature-icon">💬</text>
        <text class="feature-name">AI 对话</text>
      </view>
      <view class="feature-item" @click="goGenerate('code')">
        <text class="feature-icon">💻</text>
        <text class="feature-name">代码生成</text>
      </view>
      <view class="feature-item" @click="goGenerate('write')">
        <text class="feature-icon">✍️</text>
        <text class="feature-name">文案写作</text>
      </view>
      <view class="feature-item" @click="goGenerate('translate')">
        <text class="feature-icon">🌐</text>
        <text class="feature-name">翻译助手</text>
      </view>
    </view>

    <view class="section">
      <view class="section-header">
        <text class="section-title">历史记录</text>
        <text v-if="history.length > 0" class="clear-btn" @click="onClearHistory">清空</text>
      </view>
      <view v-if="history.length === 0" class="empty-wrap">
        <EmptyState icon="💭" text="暂无对话记录" />
      </view>
      <view v-else>
        <view v-for="item in history" :key="item.id" class="history-card" @click="goGenerate('chat', item.prompt)">
          <text class="history-prompt">{{ item.prompt }}</text>
          <text class="history-time">{{ formatRelativeTime(item.created_at) }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getAiHistory, deleteAiHistory } from '../../api/ai'
import { formatRelativeTime } from '../../utils/format'
import EmptyState from '../../components/EmptyState.vue'

const history = ref<any[]>([])

onShow(async () => {
  await loadHistory()
})

async function loadHistory() {
  try {
    const res: any = await getAiHistory()
    if (res.success) {
      history.value = res.data || []
    }
  } catch (e) {
    console.error('加载历史失败:', e)
  }
}

function goGenerate(mode: string, prompt?: string) {
  let url = `/pages/ai/generate?mode=${mode}`
  if (prompt) url += `&prompt=${encodeURIComponent(prompt)}`
  uni.navigateTo({ url })
}

async function onClearHistory() {
  uni.showModal({
    title: '确认清空',
    content: '确定要清空所有对话记录吗？',
    success: async (res) => {
      if (res.confirm) {
        for (const item of history.value) {
          try {
            await deleteAiHistory(item.id)
          } catch (e) {
            // continue
          }
        }
        history.value = []
        uni.showToast({ title: '已清空', icon: 'success' })
      }
    },
  })
}
</script>

<style scoped>
.ai-page {
  padding: 20rpx;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.ai-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.ai-icon {
  font-size: 72rpx;
  margin-bottom: 16rpx;
}

.ai-title {
  font-size: 36rpx;
  font-weight: 700;
  color: #fff;
  margin-bottom: 8rpx;
}

.ai-desc {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.8);
}

.ai-features {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  margin-bottom: 30rpx;
}

.feature-item {
  width: calc(50% - 8rpx);
  background: #fff;
  border-radius: 16rpx;
  padding: 30rpx;
  display: flex;
  align-items: center;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.feature-icon {
  font-size: 40rpx;
  margin-right: 16rpx;
}

.feature-name {
  font-size: 28rpx;
  color: #333;
  font-weight: 500;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.section-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
}

.clear-btn {
  font-size: 26rpx;
  color: #dd524d;
}

.empty-wrap {
  padding-top: 40rpx;
}

.history-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 12rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}

.history-prompt {
  display: block;
  font-size: 28rpx;
  color: #333;
  margin-bottom: 8rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-time {
  font-size: 24rpx;
  color: #999;
}
</style>
