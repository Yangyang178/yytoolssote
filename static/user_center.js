// 用户中心页面交互逻辑

// 编辑资料模态框交互
const editProfileBtn = document.getElementById('edit-profile-btn');
const editModal = document.getElementById('edit-modal');
const closeModalBtn = document.getElementById('close-modal-btn');
const cancelEditBtn = document.getElementById('cancel-edit-btn');
const removeAvatarBtn = document.getElementById('remove-avatar-btn');
const editProfileForm = document.getElementById('edit-profile-form');

// 打开编辑资料模态框
if (editProfileBtn) {
    editProfileBtn.addEventListener('click', () => {
        editModal.style.display = 'block';
    });
}

// 关闭编辑资料模态框
function closeEditModal() {
    editModal.style.display = 'none';
}

if (closeModalBtn) {
    closeModalBtn.addEventListener('click', closeEditModal);
}

if (cancelEditBtn) {
    cancelEditBtn.addEventListener('click', closeEditModal);
}

// 点击模态框外部关闭模态框
window.addEventListener('click', (e) => {
    if (e.target === editModal) {
        closeEditModal();
    }
});

// 移除头像功能
if (removeAvatarBtn) {
    removeAvatarBtn.addEventListener('click', () => {
        if (confirm('确定要移除头像吗？')) {
            // 创建隐藏输入字段表示移除头像
            let removeAvatarInput = document.getElementById('remove-avatar-input');
            if (!removeAvatarInput) {
                removeAvatarInput = document.createElement('input');
                removeAvatarInput.type = 'hidden';
                removeAvatarInput.id = 'remove-avatar-input';
                removeAvatarInput.name = 'remove_avatar';
                editProfileForm.appendChild(removeAvatarInput);
            }
            removeAvatarInput.value = '1';
            
            // 更新预览
            const currentAvatar = document.querySelector('.current-avatar');
            if (currentAvatar) {
                const avatarIcon = document.createElement('div');
                avatarIcon.className = 'avatar-icon-large';
                avatarIcon.textContent = document.getElementById('edit-username').value[0].toUpperCase();
                currentAvatar.innerHTML = '';
                currentAvatar.appendChild(avatarIcon);
            }
            
            // 隐藏移除头像按钮
            removeAvatarBtn.style.display = 'none';
        }
    });
}

// 文件搜索功能
const fileSearch = document.getElementById('file-search');
const searchClearBtn = document.getElementById('search-clear-btn');
const userFileCards = document.querySelectorAll('.user-file-card');
const searchResultsInfo = document.getElementById('search-results-info');

if (fileSearch) {
    fileSearch.addEventListener('input', () => {
        const searchTerm = fileSearch.value.trim().toLowerCase();
        let visibleCount = 0;
        
        userFileCards.forEach(card => {
            const searchText = card.getAttribute('data-search').toLowerCase();
            if (searchTerm === '' || searchText.includes(searchTerm)) {
                card.style.display = 'block';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });
        
        // 更新搜索结果信息
        if (searchTerm) {
            searchResultsInfo.textContent = `找到 ${visibleCount} 个匹配的文件`;
        } else {
            searchResultsInfo.textContent = '';
        }
    });
}

// 清除搜索
if (searchClearBtn) {
    searchClearBtn.addEventListener('click', () => {
        fileSearch.value = '';
        fileSearch.dispatchEvent(new Event('input'));
    });
}

// 替换文件模态框交互
const replaceModal = document.getElementById('replaceModal');
const replaceFileForm = document.getElementById('replaceFileForm');
const replaceFileId = document.getElementById('replaceFileId');
const replaceFile = document.getElementById('replaceFile');
const fileSize = document.querySelector('.file-size');

// 打开替换文件模态框
const replaceButtons = document.querySelectorAll('.action-replace');
replaceButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const fileId = btn.getAttribute('data-file-id');
        replaceFileId.value = fileId;
        replaceModal.classList.remove('hidden');
        replaceModal.style.display = 'block';
    });
});

// 关闭替换文件模态框
function closeReplaceModal() {
    replaceModal.classList.add('hidden');
    replaceModal.style.display = 'none';
    replaceFileForm.reset();
    if (fileSize) fileSize.textContent = '';
}

// 点击模态框外部关闭
window.addEventListener('click', (e) => {
    if (e.target === replaceModal) {
        closeReplaceModal();
    }
});

// 文件大小显示
if (replaceFile) {
    replaceFile.addEventListener('change', () => {
        if (replaceFile.files[0]) {
            const size = replaceFile.files[0].size;
            if (size < 1024) {
                fileSize.textContent = `${size} B`;
            } else if (size < 1024 * 1024) {
                fileSize.textContent = `${(size / 1024).toFixed(2)} KB`;
            } else {
                fileSize.textContent = `${(size / (1024 * 1024)).toFixed(2)} MB`;
            }
        } else {
            fileSize.textContent = '';
        }
    });
}

// 日志折叠功能
const toggleLogsBtn = document.getElementById('toggle-logs-btn');
const toggleIcon = document.getElementById('toggle-icon');
const logsContainer = document.getElementById('logs-container');

if (toggleLogsBtn) {
    toggleLogsBtn.addEventListener('click', () => {
        if (logsContainer.style.display === 'none' || logsContainer.style.display === '') {
            logsContainer.style.display = 'block';
            toggleIcon.textContent = '▼';
        } else {
            logsContainer.style.display = 'none';
            toggleIcon.textContent = '▶';
        }
    });
}

const toggleOperationLogsBtn = document.getElementById('toggle-operation-logs-btn');
const toggleOperationIcon = document.getElementById('toggle-operation-icon');
const operationLogsContainer = document.getElementById('operation-logs-container');

if (toggleOperationLogsBtn) {
    toggleOperationLogsBtn.addEventListener('click', () => {
        if (operationLogsContainer.style.display === 'none' || operationLogsContainer.style.display === '') {
            operationLogsContainer.style.display = 'block';
            toggleOperationIcon.textContent = '▼';
        } else {
            operationLogsContainer.style.display = 'none';
            toggleOperationIcon.textContent = '▶';
        }
    });
}

// 退出登录功能
const logoutBtn = document.getElementById('logout-btn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        if (confirm('确定要退出登录吗？')) {
            window.location.href = '/logout';
        }
    });
}

// 取消收藏功能
const unfavoriteButtons = document.querySelectorAll('.btn-unfavorite');
unfavoriteButtons.forEach(btn => {
    btn.addEventListener('click', async () => {
        const fileId = btn.getAttribute('data-file-id');
        if (confirm('确定要取消收藏该文件吗？')) {
            try {
                const response = await fetch(`/api/files/${fileId}/favorite`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                
                if (response.ok) {
                    const result = await response.json();
                    if (result.success) {
                        // 更新收藏数显示
                        const favoriteCountEl = btn.closest('.file-card').querySelector('.favorite-count .value');
                        if (favoriteCountEl) {
                            favoriteCountEl.textContent = result.data.count;
                        }
                        
                        // 移除当前文件卡片
                        btn.closest('.file-card').remove();
                        
                        // 显示成功消息
                        alert('取消收藏成功');
                        
                        // 如果没有收藏文件了，更新UI
                        const remainingCards = document.querySelectorAll('.file-card');
                        if (remainingCards.length === 0) {
                            const filesGrid = document.querySelector('.files-grid');
                            if (filesGrid) {
                                filesGrid.innerHTML = `
                                    <div class="empty-state">
                                        <div class="empty-icon">⭐</div>
                                        <h3 class="empty-title">暂无收藏文件</h3>
                                        <p class="empty-desc">您还没有收藏任何文件，去首页探索并收藏感兴趣的文件吧</p>
                                        <a href="/" class="btn btn-primary">
                                            <i class="icon-explore">🔍</i> 去首页探索
                                        </a>
                                    </div>
                                `;
                            }
                        }
                    } else {
                        alert('取消收藏失败：' + (result.message || '未知错误'));
                    }
                } else {
                    // 尝试解析错误响应
                    try {
                        const errorResult = await response.json();
                        alert('取消收藏失败：' + (errorResult.message || '请求失败'));
                    } catch {
                        alert('取消收藏失败，请重试');
                    }
                }
            } catch (error) {
                console.error('取消收藏请求错误:', error);
                alert('取消收藏失败，请检查网络连接');
            }
        }
    });
});

// 页面加载完成后执行
window.addEventListener('DOMContentLoaded', () => {
    // 初始化页面状态
    
    // 如果没有搜索内容，隐藏搜索结果信息
    if (searchResultsInfo && !fileSearch.value.trim()) {
        searchResultsInfo.textContent = '';
    }
});