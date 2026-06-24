<template>
  <view class="empty-state">
    <text class="empty-icon">{{ icon }}</text>
    <text class="empty-text">{{ text }}</text>
    <button v-if="actionText" class="action-btn" @click="$emit('action')">{{ actionText }}</button>
  </view>
</template>

<script setup lang="ts">
defineProps<{
  icon?: string
  text?: string
  actionText?: string
}>()

defineEmits(['action'])
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120rpx 40rpx;
}

.empty-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}

.empty-text {
  font-size: 28rpx;
  color: #999;
  margin-bottom: 30rpx;
}

.action-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border: none;
  border-radius: 12rpx;
  padding: 16rpx 48rpx;
  font-size: 28rpx;
}

.action-btn::after {
  border: none;
}
</style>
