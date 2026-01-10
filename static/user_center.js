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

// 页面加载完成后执行
window.addEventListener('DOMContentLoaded', () => {
    // 初始化页面状态
    
    // 如果没有搜索内容，隐藏搜索结果信息
    if (searchResultsInfo && !fileSearch.value.trim()) {
        searchResultsInfo.textContent = '';
    }
});