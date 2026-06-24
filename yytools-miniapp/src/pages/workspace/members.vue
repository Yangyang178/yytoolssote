<template>
  <view class="members-page">
    <view v-if="members.length === 0" class="empty-wrap">
      <EmptyState icon="👥" text="暂无成员" />
    </view>
    <view v-else>
      <view v-for="member in members" :key="member.user_id" class="member-card">
        <view class="member-avatar">
          <text>{{ (member.username || '?')[0].toUpperCase() }}</text>
        </view>
        <view class="member-info">
          <text class="member-name">{{ member.username || '未知用户' }}</text>
          <text class="member-role">{{ roleLabel(member.role) }}</text>
        </view>
        <button
          v-if="canRemove && member.role !== 'owner'"
          class="remove-btn"
          @click="onRemove(member)"
        >
          移除
        </button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getWorkspaceMembers, removeMember } from '../../api/workspace'
import { useUserStore } from '../../stores/user'
import EmptyState from '../../components/EmptyState.vue'

const userStore = useUserStore()
const members = ref<any[]>([])
const workspaceId = ref('')
const userRole = ref('')

const canRemove = computed(() => userRole.value === 'owner')

onLoad((options) => {
  if (options?.id) {
    workspaceId.value = options.id
    loadMembers()
  }
})

async function loadMembers() {
  try {
    const res: any = await getWorkspaceMembers(workspaceId.value)
    if (res.success) {
      members.value = res.data.members || res.data || []
      const me = members.value.find((m: any) => m.user_id === userStore.userInfo?.id)
      if (me) userRole.value = me.role
    }
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function roleLabel(role: string) {
  const map: Record<string, string> = { owner: '创建者', admin: '管理员', editor: '编辑者', viewer: '查看者' }
  return map[role] || role
}

function onRemove(member: any) {
  uni.showModal({
    title: '确认移除',
    content: `确定要移除 ${member.username} 吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await removeMember(workspaceId.value, member.user_id)
          uni.showToast({ title: '已移除', icon: 'success' })
          await loadMembers()
        } catch (e) {
          uni.showToast({ title: '移除失败', icon: 'none' })
        }
      }
    },
  })
}
</script>

<style scoped>
.members-page {
  padding: 20rpx;
}

.empty-wrap {
  padding-top: 100rpx;
}

.member-card {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
}

.member-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20rpx;
  font-size: 32rpx;
  color: #fff;
  font-weight: 600;
}

.member-info {
  flex: 1;
}

.member-name {
  display: block;
  font-size: 28rpx;
  font-weight: 500;
  color: #333;
  margin-bottom: 4rpx;
}

.member-role {
  font-size: 24rpx;
  color: #999;
}

.remove-btn {
  background: transparent;
  color: #dd524d;
  border: 2rpx solid #dd524d;
  border-radius: 8rpx;
  padding: 8rpx 24rpx;
  font-size: 24rpx;
}

.remove-btn::after {
  border: none;
}
</style>
