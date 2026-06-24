<template>
  <view class="file-card" @click="$emit('click', file)">
    <view class="file-icon">{{ icon }}</view>
    <view class="file-info">
      <text class="file-name ellipsis">{{ file.filename || '未命名文件' }}</text>
      <text class="file-meta">{{ fileType }} · {{ sizeStr }}</text>
    </view>
    <view v-if="showActions" class="file-actions" @click.stop>
      <slot name="actions"></slot>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatFileSize, getFileIcon, getFileType } from '../utils/format'

const props = defineProps<{
  file: any
  showActions?: boolean
}>()

defineEmits(['click'])

const icon = computed(() => getFileIcon(props.file.filename || ''))
const fileType = computed(() => getFileType(props.file.filename || ''))
const sizeStr = computed(() => formatFileSize(props.file.size || 0))
</script>

<style scoped>
.file-card {
  display: flex;
  align-items: center;
  padding: 24rpx;
  background: #fff;
  border-radius: 16rpx;
  margin-bottom: 16rpx;
}

.file-icon {
  font-size: 48rpx;
  margin-right: 20rpx;
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 28rpx;
  color: #333;
  display: block;
  margin-bottom: 8rpx;
}

.file-meta {
  font-size: 24rpx;
  color: #999;
}

.file-actions {
  flex-shrink: 0;
  margin-left: 16rpx;
}
</style>
