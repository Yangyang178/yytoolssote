<template>
  <view v-if="loading" class="loading-more">
    <view class="loading-spinner"></view>
    <text class="loading-text">加载中...</text>
  </view>
  <view v-else-if="!hasMore" class="loading-more">
    <text class="loading-text">没有更多了</text>
  </view>
</template>

<script setup lang="ts">
defineProps<{
  loading?: boolean
  hasMore?: boolean
}>()
</script>

<style scoped>
.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30rpx 0;
}

.loading-spinner {
  width: 32rpx;
  height: 32rpx;
  border: 4rpx solid #e0e0e0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 16rpx;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 24rpx;
  color: #999;
}
</style>
