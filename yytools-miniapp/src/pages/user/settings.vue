<template>
  <view class="settings-page">
    <view class="card">
      <text class="section-title">基本信息</text>
      <view class="form-group">
        <text class="form-label">用户名</text>
        <input v-model="form.username" class="form-input" placeholder="输入用户名" />
      </view>
      <button class="save-btn" @click="onSaveProfile">保存</button>
    </view>

    <view class="card">
      <text class="section-title">修改密码</text>
      <view class="form-group">
        <text class="form-label">当前密码</text>
        <input v-model="pwdForm.oldPassword" class="form-input" type="password" placeholder="输入当前密码" />
      </view>
      <view class="form-group">
        <text class="form-label">新密码</text>
        <input v-model="pwdForm.newPassword" class="form-input" type="password" placeholder="输入新密码" />
      </view>
      <view class="form-group">
        <text class="form-label">确认新密码</text>
        <input v-model="pwdForm.confirmPassword" class="form-input" type="password" placeholder="再次输入新密码" />
      </view>
      <button class="save-btn" @click="onChangePassword">修改密码</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { useUserStore } from '../../stores/user'
import { changePassword } from '../../api/auth'

const userStore = useUserStore()

const form = reactive({
  username: userStore.username,
})

const pwdForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

async function onSaveProfile() {
  if (!form.username.trim()) {
    uni.showToast({ title: '用户名不能为空', icon: 'none' })
    return
  }
  try {
    await userStore.updateProfile({ username: form.username.trim() })
    uni.showToast({ title: '保存成功', icon: 'success' })
  } catch (e) {
    console.error('保存失败:', e)
  }
}

async function onChangePassword() {
  if (!pwdForm.oldPassword || !pwdForm.newPassword) {
    uni.showToast({ title: '请填写完整', icon: 'none' })
    return
  }
  if (pwdForm.newPassword !== pwdForm.confirmPassword) {
    uni.showToast({ title: '两次密码不一致', icon: 'none' })
    return
  }
  if (pwdForm.newPassword.length < 6) {
    uni.showToast({ title: '密码至少6位', icon: 'none' })
    return
  }
  try {
    await changePassword(pwdForm.oldPassword, pwdForm.newPassword)
    uni.showToast({ title: '密码修改成功', icon: 'success' })
    pwdForm.oldPassword = ''
    pwdForm.newPassword = ''
    pwdForm.confirmPassword = ''
  } catch (e) {
    console.error('修改密码失败:', e)
  }
}
</script>

<style scoped>
.settings-page {
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

.save-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border: none;
  border-radius: 12rpx;
  padding: 20rpx 0;
  font-size: 28rpx;
}

.save-btn::after {
  border: none;
}
</style>
