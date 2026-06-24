<template>
  <view class="generate-page">
    <scroll-view scroll-y class="chat-scroll" :scroll-top="scrollTop">
      <view v-if="messages.length === 0" class="welcome">
        <text class="welcome-icon">🤖</text>
        <text class="welcome-text">输入你的问题，AI 将为你解答</text>
      </view>
      <view v-for="(msg, i) in messages" :key="i" :class="['msg-wrap', msg.role === 'user' ? 'msg-user' : 'msg-ai']">
        <view :class="['msg-bubble', msg.role === 'user' ? 'bubble-user' : 'bubble-ai']">
          <text class="msg-text">{{ msg.content }}</text>
        </view>
      </view>
      <view v-if="generating" class="msg-wrap msg-ai">
        <view class="msg-bubble bubble-ai">
          <text class="msg-text typing">思考中...</text>
        </view>
      </view>
    </scroll-view>

    <view class="input-bar">
      <input
        v-model="inputText"
        class="chat-input"
        placeholder="输入消息..."
        confirm-type="send"
        @confirm="onSend"
      />
      <button class="send-btn" :disabled="!inputText.trim() || generating" @click="onSend">
        发送
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { aiChat } from '../../api/ai'

const messages = ref<{ role: string; content: string }[]>([])
const inputText = ref('')
const generating = ref(false)
const scrollTop = ref(0)

onLoad((options) => {
  if (options?.prompt) {
    inputText.value = decodeURIComponent(options.prompt)
  }
})

async function onSend() {
  const text = inputText.value.trim()
  if (!text || generating.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  await scrollToBottom()

  generating.value = true
  try {
    const res: any = await aiChat(text)
    if (res.success) {
      const reply = res.data.response || res.data.content || res.data || '无法获取回复'
      messages.value.push({ role: 'assistant', content: reply })
    } else {
      messages.value.push({ role: 'assistant', content: '抱歉，出了点问题，请稍后重试' })
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '网络错误，请稍后重试' })
  } finally {
    generating.value = false
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  scrollTop.value = 99999
}
</script>

<style scoped>
.generate-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.chat-scroll {
  flex: 1;
  padding: 20rpx;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}

.welcome-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}

.welcome-text {
  font-size: 28rpx;
  color: #999;
}

.msg-wrap {
  display: flex;
  margin-bottom: 24rpx;
}

.msg-user {
  justify-content: flex-end;
}

.msg-ai {
  justify-content: flex-start;
}

.msg-bubble {
  max-width: 75%;
  padding: 20rpx 28rpx;
  border-radius: 20rpx;
  word-break: break-all;
}

.bubble-user {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-bottom-right-radius: 4rpx;
}

.bubble-ai {
  background: #fff;
  border-bottom-left-radius: 4rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}

.msg-text {
  font-size: 28rpx;
  line-height: 1.6;
}

.bubble-user .msg-text {
  color: #fff;
}

.bubble-ai .msg-text {
  color: #333;
}

.typing {
  color: #999;
}

.input-bar {
  display: flex;
  align-items: center;
  padding: 16rpx 20rpx;
  background: #fff;
  border-top: 1rpx solid #eee;
  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
}

.chat-input {
  flex: 1;
  height: 72rpx;
  background: #f5f5f5;
  border-radius: 36rpx;
  padding: 0 28rpx;
  font-size: 28rpx;
  margin-right: 16rpx;
}

.send-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border: none;
  border-radius: 36rpx;
  padding: 0 36rpx;
  height: 72rpx;
  line-height: 72rpx;
  font-size: 28rpx;
}

.send-btn::after {
  border: none;
}

.send-btn[disabled] {
  opacity: 0.5;
}
</style>
