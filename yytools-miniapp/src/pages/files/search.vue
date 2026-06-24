<template>
  <view class="search-page">
    <view class="search-box">
      <input
        v-model="keyword"
        class="search-input"
        placeholder="搜索文件名..."
        focus
        confirm-type="search"
        @confirm="onSearch"
      />
      <text class="search-btn" @click="onSearch">搜索</text>
    </view>

    <view v-if="searched" class="results">
      <text class="result-count">找到 {{ files.length }} 个结果</text>
      <FileCard
        v-for="file in files"
        :key="file.id"
        :file="file"
        @click="goDetail(file.id)"
      />
      <EmptyState v-if="files.length === 0 && !loading" icon="🔍" text="没有找到相关文件" />
    </view>

    <view v-else class="search-tips">
      <text class="tip-icon">💡</text>
      <text class="tip-text">输入关键词搜索文件</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { searchFiles } from '../../api/files'
import FileCard from '../../components/FileCard.vue'
import EmptyState from '../../components/EmptyState.vue'

const keyword = ref('')
const files = ref<any[]>([])
const loading = ref(false)
const searched = ref(false)

async function onSearch() {
  if (!keyword.value.trim()) return
  loading.value = true
  searched.value = true
  try {
    const res: any = await searchFiles(keyword.value.trim())
    if (res.success) {
      files.value = res.data.files || res.data || []
    }
  } catch (e) {
    console.error('搜索失败:', e)
  } finally {
    loading.value = false
  }
}

function goDetail(id: string) {
  uni.navigateTo({ url: `/pages/files/detail?id=${id}` })
}
</script>

<style scoped>
.search-page {
  padding: 20rpx;
}

.search-box {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 16rpx;
  padding: 12rpx 20rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}

.search-input {
  flex: 1;
  height: 72rpx;
  font-size: 28rpx;
}

.search-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  font-size: 28rpx;
  padding: 16rpx 32rpx;
  border-radius: 12rpx;
  margin-left: 16rpx;
}

.result-count {
  display: block;
  font-size: 26rpx;
  color: #999;
  margin-bottom: 16rpx;
}

.search-tips {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 160rpx 0;
}

.tip-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}

.tip-text {
  font-size: 28rpx;
  color: #999;
}
</style>
