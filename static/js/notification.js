let notifPollTimer = null;
let notifPollInterval = 30000;
let lastUnreadCount = 0;

function initNotificationSystem() {
    if (!document.getElementById('notifBadge')) return;
    pollUnreadCount();
    startPolling();
    document.addEventListener('click', handleOutsideClick);
}

function startPolling() {
    if (notifPollTimer) clearInterval(notifPollTimer);
    notifPollTimer = setInterval(pollUnreadCount, notifPollInterval);
}

function stopPolling() {
    if (notifPollTimer) {
        clearInterval(notifPollTimer);
        notifPollTimer = null;
    }
}

async function pollUnreadCount() {
    try {
        const res = await fetch('/api/notifications/unread');
        const data = await res.json();
        if (data.success) {
            updateBadge(data.data.count);
            if (data.data.count > lastUnreadCount && data.data.recent.length > 0) {
                const newest = data.data.recent[0];
                showToast(newest);
            }
            lastUnreadCount = data.data.count;
        }
    } catch (e) {}
}

function updateBadge(count) {
    const badge = document.getElementById('notifBadge');
    if (!badge) return;
    badge.textContent = count > 99 ? '99+' : count;
    badge.style.display = count > 0 ? 'flex' : 'none';
}

function toggleNotificationPanel() {
    const dropdown = document.getElementById('notifDropdown');
    const isShowing = dropdown.classList.contains('show');
    closeAllDropdowns();
    if (!isShowing) {
        dropdown.classList.add('show');
        loadDropdownList();
    }
}

function closeAllDropdowns() {
    document.querySelectorAll('.notification-dropdown.show').forEach(el => el.classList.remove('show'));
}

function handleOutsideClick(e) {
    const container = document.getElementById('navNotification');
    if (container && !container.contains(e.target)) {
        closeAllDropdowns();
    }
}

async function loadDropdownList() {
    const listEl = document.getElementById('notifList');
    if (!listEl) return;
    listEl.innerHTML = '<div class="notif-loading"><i class="bi bi-arrow-repeat spin"></i> 加载中...</div>';
    try {
        const res = await fetch('/api/notifications?limit=8');
        const data = await res.json();
        if (data.success && data.data.notifications.length > 0) {
            listEl.innerHTML = data.data.notifications.map(n => renderDropdownItem(n)).join('');
        } else {
            listEl.innerHTML = '<div class="notif-empty"><i class="bi bi-bell-slash"></i><p>暂无通知</p></div>';
        }
    } catch (e) {
        listEl.innerHTML = '<div class="notif-empty"><i class="bi bi-exclamation-triangle"></i><p>加载失败</p></div>';
    }
}

function renderDropdownItem(n) {
    const iconData = n.icon_data || {};
    const iconBg = iconData.bg || '#e5e7eb';
    const iconColor = iconData.color || '#374151';
    const iconChar = iconData.icon || '📢';
    const unreadClass = n.is_read ? '' : 'unread';
    return `
    <div class="notif-list-item ${unreadClass}" onclick="handleNotifClick('${n.id}', '${n.action_url || ''}')">
        <div class="notif-list-item-icon" style="background:${iconBg};color:${iconColor}">${iconChar}</div>
        <div class="notif-list-item-body">
            <div class="notif-list-item-title">${escapeHtml(n.title)}</div>
            <div class="notif-list-item-desc">${escapeHtml(n.content || '')}</div>
            <div class="notif-list-item-time">${n.time_ago || ''}</div>
        </div>
    </div>`;
}

async function handleNotifClick(notifId, actionUrl) {
    await markAsRead(notifId);
    if (actionUrl) window.location.href = actionUrl;
}

async function markAsRead(notifId) {
    try {
        await fetch(`/api/notifications/${notifId}/read`, { method: 'PUT' });
        const card = document.querySelector(`.notif-card[data-id="${notifId}"]`);
        if (card) card.classList.remove('unread');
        const item = document.querySelector(`.notif-list-item[onclick*="${notifId}"]`);
        if (item) item.classList.remove('unread');
    } catch (e) {}
}

async function markAllRead() {
    try {
        const currentType = new URLSearchParams(window.location.search).get('type') || '';
        let url = '/api/notifications/read-all';
        if (currentType) url += '?type=' + encodeURIComponent(currentType);
        const res = await fetch(url, { method: 'PUT' });
        const data = await res.json();
        if (data.success) {
            document.querySelectorAll('.notif-card.unread').forEach(el => el.classList.remove('unread'));
            document.querySelectorAll('.notif-list-item.unread').forEach(el => el.classList.remove('unread'));
            updateBadge(0);
            showToast({ title: `已标记 ${data.data.updated} 条为已读`, category: 'success' });
        }
    } catch (e) {}
}

async function deleteNotification(notifId) {
    if (!confirm('确定删除此通知？')) return;
    try {
        const res = await fetch(`/api/notifications/${notifId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            const card = document.querySelector(`.notif-card[data-id="${notifId}"]`);
            if (card) card.style.opacity = '0';
            setTimeout(() => card?.remove(), 300);
        }
    } catch (e) {}
}

async function clearAllNotifications() {
    if (!confirm('确定清空所有通知？此操作不可撤销。')) return;
    try {
        const currentType = new URLSearchParams(window.location.search).get('type') || '';
        let url = '/api/notifications/clear';
        if (currentType) url += '?type=' + encodeURIComponent(currentType);
        const res = await fetch(url, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            document.getElementById('notificationList').innerHTML =
                '<div class="text-center py-5 text-muted"><i class="bi bi-check-circle" style="font-size:3rem;color:#10b981;"></i><p class="mt-3">已清除 ' + data.data.deleted + ' 条通知</p></div>';
            updateBadge(0);
        }
    } catch (e) {}
}

function showAdminPanel() {
    const modal = new bootstrap.Modal(document.getElementById('adminModal'));
    modal.show();
}

async function adminClearAll() {
    if (!confirm('⚠️ 确定清空所有用户的所有通知？这是管理员操作，影响所有用户！')) return;
    try {
        const res = await fetch('/api/notifications/clear?type=admin_all', { method: 'DELETE' });
        const data = await res.json();
        alert(`已清除 ${data.data.deleted} 条通知`);
        bootstrap.Modal.getInstance(document.getElementById('adminModal'))?.hide();
        location.reload();
    } catch (e) {}
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(notif) {
    if (typeof showToastGlobal === 'function') {
        const title = typeof notif === 'string' ? notif : (notif.title || '');
        const cat = notif.category || 'info';
        showToastGlobal(title, cat);
    } else {
        console.log('[Notification]', notif);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotificationSystem);
} else {
    initNotificationSystem();
}
