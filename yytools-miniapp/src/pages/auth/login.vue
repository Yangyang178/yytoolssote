<template>
  <view class="login-page">
    <view class="login-header">
      <text class="logo-icon">🛠️</text>
      <text class="app-name">YYTools</text>
      <text class="app-desc">智能文件管理系统</text>
    </view>

    <view class="login-tabs">
      <view
        :class="['tab-item', activeTab === 'wx' && 'tab-active']"
        @click="activeTab = 'wx'"
      >
        <text>微信登录</text>
      </view>
      <view
        :class="['tab-item', activeTab === 'account' && 'tab-active']"
        @click="activeTab = 'account'"
      >
        <text>账号登录</text>
      </view>
    </view>

    <view v-if="activeTab === 'wx'" class="wx-login">
      <view class="wx-login-info">
        <text class="wx-tip">使用微信账号快速登录</text>
        <text class="wx-desc">首次登录将自动创建账号</text>
      </view>
      <button class="wx-btn" open-type="getPhoneNumber" @getphonenumber="onGetPhoneNumber">
        <text class="wx-btn-icon">📱</text>
        <text>微信一键登录</text>
      </button>
      <button class="wx-btn-outline" @click="onWxLogin">
        <text>其他方式微信登录</text>
      </button>
    </view>

    <view v-else class="account-login">
      <view class="form-group">
        <text class="form-label">邮箱</text>
        <input
          v-model="email"
          class="form-input"
          type="text"
          placeholder="请输入邮箱"
          autocomplete="off"
        />
      </view>
      <view class="form-group">
        <text class="form-label">密码</text>
        <input
          v-model="password"
          class="form-input"
          type="password"
          placeholder="请输入密码"
          autocomplete="off"
        />
      </view>
      <button class="login-btn" :loading="submitting" @click="onAccountLogin">
        登录
      </button>
      <view class="login-footer">
        <text class="footer-link" @click="goRegister">还没有账号？去注册</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useUserStore } from '../../stores/user'

const userStore = useUserStore()
const activeTab = ref<'wx' | 'account'>('wx')
const email = ref('')
const password = ref('')
const submitting = ref(false)

async function onWxLogin() {
  submitting.value = true
  try {
    const success = await userStore.handleWxLogin()
    if (success) {
      uni.reLaunch({ url: '/pages/index/index' })
    } else {
      uni.showToast({ title: '登录失败，请重试', icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: '登录失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

async function onGetPhoneNumber(e: any) {
  if (e.detail.errMsg !== 'getPhoneNumber:ok') {
    return
  }
  submitting.value = true
  try {
    const success = await userStore.handleWxLogin()
    if (success) {
      uni.reLaunch({ url: '/pages/index/index' })
    }
  } catch (e) {
    uni.showToast({ title: '登录失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

async function onAccountLogin() {
  if (!email.value.trim()) {
    uni.showToast({ title: '请输入邮箱', icon: 'none' })
    return
  }
  if (!password.value) {
    uni.showToast({ title: '请输入密码', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const success = await userStore.handleAccountLogin(email.value.trim(), password.value)
    if (success) {
      uni.reLaunch({ url: '/pages/index/index' })
    } else {
      uni.showToast({ title: '邮箱或密码错误', icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: '登录失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function goRegister() {
  uni.navigateTo({ url: '/pages/auth/login?mode=register' })
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 0 40rpx;
  display: flex;
  flex-direction: column;
}

.login-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 160rpx;
  margin-bottom: 60rpx;
}

.logo-icon {
  font-size: 100rpx;
  margin-bottom: 20rpx;
}

.app-name {
  font-size: 48rpx;
  font-weight: 700;
  color: #fff;
  margin-bottom: 12rpx;
}

.app-desc {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.8);
}

.login-tabs {
  display: flex;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 16rpx;
  padding: 6rpx;
  margin-bottom: 40rpx;
}

.tab-item {
  flex: 1;
  text-align: center;
  padding: 20rpx 0;
  border-radius: 12rpx;
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.7);
  transition: all 0.3s;
}

.tab-active {
  background: #fff;
  color: #667eea;
  font-weight: 600;
}

.wx-login {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.wx-login-info {
  text-align: center;
  margin-bottom: 60rpx;
}

.wx-tip {
  display: block;
  font-size: 32rpx;
  color: #fff;
  margin-bottom: 12rpx;
}

.wx-desc {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.6);
}

.wx-btn {
  width: 100%;
  background: #07c160;
  color: #fff;
  border: none;
  border-radius: 16rpx;
  padding: 28rpx 0;
  font-size: 32rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24rpx;
}

.wx-btn::after {
  border: none;
}

.wx-btn-icon {
  margin-right: 12rpx;
  font-size: 36rpx;
}

.wx-btn-outline {
  width: 100%;
  background: transparent;
  color: rgba(255, 255, 255, 0.8);
  border: 2rpx solid rgba(255, 255, 255, 0.3);
  border-radius: 16rpx;
  padding: 24rpx 0;
  font-size: 28rpx;
}

.wx-btn-outline::after {
  border: none;
}

.account-login {
  background: #fff;
  border-radius: 24rpx;
  padding: 40rpx;
}

.form-group {
  margin-bottom: 30rpx;
}

.form-label {
  display: block;
  font-size: 28rpx;
  color: #333;
  margin-bottom: 12rpx;
  font-weight: 500;
}

.form-input {
  width: 100%;
  height: 88rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
  box-sizing: border-box;
}

.login-btn {
  width: 100%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border: none;
  border-radius: 16rpx;
  padding: 28rpx 0;
  font-size: 32rpx;
  margin-top: 20rpx;
}

.login-btn::after {
  border: none;
}

.login-footer {
  text-align: center;
  margin-top: 30rpx;
}

.footer-link {
  font-size: 26rpx;
  color: #667eea;
}
</style>
