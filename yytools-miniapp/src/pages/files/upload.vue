<template>
  <view class="upload-page">
    <view class="card">
      <text class="section-title">选择文件</text>
      <view class="upload-area" @click="chooseFile">
        <text class="upload-icon">📤</text>
        <text class="upload-text">点击选择文件</text>
        <text class="upload-hint">支持所有类型文件</text>
      </view>
    </view>

    <view v-if="selectedFiles.length > 0" class="card">
      <text class="section-title">已选文件 ({{ selectedFiles.length }})</text>
      <view v-for="(f, i) in selectedFiles" :key="i" class="selected-file">
        <text class="sel-name">{{ f.name }}</text>
        <text class="sel-size">{{ f.sizeStr }}</text>
        <text class="sel-remove" @click="removeFile(i)">✕</text>
      </view>
    </view>

    <view class="card">
      <text class="section-title">文件信息</text>
      <view class="form-group">
        <text class="form-label">项目名称（可选）</text>
        <input v-model="projectName" class="form-input" placeholder="输入项目名称" />
      </view>
      <view class="form-group">
        <text class="form-label">项目描述（可选）</text>
        <textarea v-model="projectDesc" class="form-textarea" placeholder="输入项目描述" />
      </view>
    </view>

    <button class="submit-btn" :loading="uploading" :disabled="selectedFiles.length === 0" @click="onUpload">
      上传文件
    </button>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { config } from '../../api/config'
import { formatFileSize } from '../../utils/format'

interface SelectedFile {
  name: string
  path: string
  size: number
  sizeStr: string
}

const selectedFiles = ref<SelectedFile[]>([])
const projectName = ref('')
const projectDesc = ref('')
const uploading = ref(false)

function chooseFile() {
  uni.chooseMessageFile({
    count: 10,
    type: 'file',
    success: (res) => {
      const newFiles = res.tempFiles.map((f: any) => ({
        name: f.name,
        path: f.path,
        size: f.size,
        sizeStr: formatFileSize(f.size),
      }))
      selectedFiles.value = [...selectedFiles.value, ...newFiles]
    },
  })
}

function removeFile(index: number) {
  selectedFiles.value.splice(index, 1)
}

async function onUpload() {
  if (selectedFiles.value.length === 0) return
  uploading.value = true

  const token = uni.getStorageSync(config.tokenKey)
  let successCount = 0
  let failCount = 0

  for (const f of selectedFiles.value) {
    try {
      await new Promise<void>((resolve, reject) => {
        uni.uploadFile({
          url: `${config.baseUrl}${config.apiPrefix}/files/upload`,
          filePath: f.path,
          name: 'file',
          header: { Authorization: `Bearer ${token}` },
          formData: {
            project_name: projectName.value,
            project_desc: projectDesc.value,
          },
          success: (res) => {
            if (res.statusCode === 200) {
              const data = JSON.parse(res.data)
              if (data.success) {
                successCount++
              } else {
                failCount++
              }
            } else {
              failCount++
            }
            resolve()
          },
          fail: () => {
            failCount++
            resolve()
          },
        })
      })
    } catch (e) {
      failCount++
    }
  }

  uploading.value = false
  if (failCount === 0) {
    uni.showToast({ title: '全部上传成功', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 1500)
  } else {
    uni.showToast({ title: `${successCount}成功 ${failCount}失败`, icon: 'none' })
  }
}
</script>

<style scoped>
.upload-page {
  padding: 20rpx;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.section-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 20rpx;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 0;
  border: 2rpx dashed #ddd;
  border-radius: 16rpx;
  background: #fafafa;
}

.upload-icon {
  font-size: 64rpx;
  margin-bottom: 16rpx;
}

.upload-text {
  font-size: 28rpx;
  color: #667eea;
  margin-bottom: 8rpx;
}

.upload-hint {
  font-size: 24rpx;
  color: #999;
}

.selected-file {
  display: flex;
  align-items: center;
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f5f5f5;
}

.selected-file:last-child {
  border-bottom: none;
}

.sel-name {
  flex: 1;
  font-size: 26rpx;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sel-size {
  font-size: 24rpx;
  color: #999;
  margin: 0 16rpx;
}

.sel-remove {
  font-size: 28rpx;
  color: #dd524d;
  padding: 8rpx;
}

.form-group {
  margin-bottom: 24rpx;
}

.form-label {
  display: block;
  font-size: 26rpx;
  color: #666;
  margin-bottom: 12rpx;
}

.form-input {
  width: 100%;
  height: 80rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
  box-sizing: border-box;
}

.form-textarea {
  width: 100%;
  height: 160rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 20rpx;
  font-size: 28rpx;
  box-sizing: border-box;
}

.submit-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border: none;
  border-radius: 16rpx;
  padding: 28rpx 0;
  font-size: 32rpx;
  margin-top: 20rpx;
}

.submit-btn::after {
  border: none;
}

.submit-btn[disabled] {
  opacity: 0.5;
}
</style>
