// 处理文件操作事件
window.addEventListener('DOMContentLoaded', () => {
  // 处理 .file-action-btn 元素
  const fileActions = document.querySelectorAll('.file-action-btn');
  
  fileActions.forEach(action => {
    if (action.tagName === 'A') {
      // 处理链接点击
      action.addEventListener('click', (e) => {
        if (!isLoggedIn) {
          alert('请先登录，才能执行此操作');
          e.preventDefault();
          return;
        }
      });
    } else if (action.tagName === 'BUTTON') {
      // 处理按钮点击
      action.addEventListener('click', (e) => {
        if (!isLoggedIn) {
          alert('请先登录，才能执行此操作');
          e.preventDefault();
          return;
        }
        
        // 如果是删除按钮，显示确认对话框
        if (action.classList.contains('action-delete')) {
          if (!confirm('确定要删除这个文件吗？此操作不可恢复。')) {
            e.preventDefault();
            return;
          }
        }
        // 如果是替换按钮，调用 openReplaceModal 函数
        else if (action.classList.contains('action-replace')) {
          e.preventDefault();
          const fileId = action.dataset.fileId;
          const fileName = action.dataset.fileName;
          openReplaceModal(fileId, fileName);
        }
      });
    }
  });

  // 专门处理取消收藏按钮
  const unfavoriteBtns = document.querySelectorAll('.btn-unfavorite');
  unfavoriteBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      
      if (!isLoggedIn) {
        alert('请先登录，才能执行此操作');
        return;
      }
      
      if (!confirm('确定要取消收藏这个文件吗？')) {
        return;
      }
      
      const fileId = btn.dataset.fileId;
      handleUnfavorite(fileId, btn);
    });
  });
});

// 状态消息管理
function showStatusMessage(message, type = 'info', duration = 3000) {
  // 创建状态消息元素
  let statusMessage = document.getElementById('statusMessage');
  if (!statusMessage) {
    statusMessage = document.createElement('div');
    statusMessage.id = 'statusMessage';
    document.body.appendChild(statusMessage);
  }
  
  // 设置消息内容和样式
  statusMessage.textContent = message;
  statusMessage.className = `status-message ${type}`;
  
  // 显示消息
  statusMessage.classList.add('show');
  
  // 自动隐藏消息
  setTimeout(() => {
    statusMessage.classList.remove('show');
  }, duration);
}

// 处理取消收藏操作
async function handleUnfavorite(fileId, btn) {
  if (!fileId || !btn) {
    console.error('取消收藏失败：缺少必要参数');
    showStatusMessage('取消收藏失败：缺少必要参数', 'error');
    return;
  }
  
  // 添加加载状态
  btn.classList.add('loading');
  
  try {
    const response = await fetch(`/api/files/${fileId}/favorite`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (data.success) {
      // 取消收藏成功，刷新页面或更新UI
      showStatusMessage('取消收藏成功', 'success');
      window.location.reload();
    } else {
      showStatusMessage(`取消收藏失败: ${data.message || '未知错误'}`, 'error');
    }
  } catch (error) {
    console.error(`取消收藏失败：`, error);
    showStatusMessage(`取消收藏失败: ${error.message}`, 'error');
  } finally {
    // 移除加载状态
    btn.classList.remove('loading');
  }
}

// 搜索功能
function setupFileSearch() {
  const searchInput = document.getElementById('file-search');
  const searchBtn = document.querySelector('.search-btn');
  const searchClearBtn = document.getElementById('search-clear-btn');
  const searchResultsInfo = document.getElementById('search-results-info');
  const fileCards = document.querySelectorAll('.user-file-card');
  
  if (!searchInput || !fileCards.length) return;
  
  // 搜索函数
  function performSearch() {
    const searchTerm = searchInput.value.toLowerCase().trim();
    let visibleCount = 0;
    
    fileCards.forEach(card => {
      const searchData = card.getAttribute('data-search')?.toLowerCase() || '';
      
      // 改进的搜索算法：支持模糊匹配
      const matches = searchTerm === '' || searchData.includes(searchTerm);
      
      if (matches) {
        card.style.display = 'block';
        visibleCount++;
      } else {
        card.style.display = 'none';
      }
    });
    
    // 更新搜索结果信息
    updateSearchResultsInfo(visibleCount, fileCards.length);
    
    // 更新清空按钮状态
    updateClearButtonState();
  }
  
  // 更新搜索结果信息
  function updateSearchResultsInfo(visibleCount, totalCount) {
    if (!searchResultsInfo) return;
    
    const searchTerm = searchInput.value.toLowerCase().trim();
    
    if (searchTerm === '') {
      searchResultsInfo.textContent = '';
    } else {
      searchResultsInfo.textContent = `找到 ${visibleCount} 个匹配结果（共 ${totalCount} 个文件）`;
    }
  }
  
  // 更新清空按钮状态
  function updateClearButtonState() {
    if (!searchClearBtn) return;
    
    if (searchInput.value.trim() !== '') {
      searchClearBtn.classList.add('visible');
    } else {
      searchClearBtn.classList.remove('visible');
    }
  }
  
  // 清空搜索
  function clearSearch() {
    searchInput.value = '';
    updateClearButtonState();
    performSearch();
    searchInput.focus();
  }
  
  // 监听输入事件，实时搜索
  searchInput.addEventListener('input', performSearch);
  
  // 监听搜索按钮点击
  if (searchBtn) {
    searchBtn.addEventListener('click', performSearch);
  }
  
  // 监听清空按钮点击
  if (searchClearBtn) {
    searchClearBtn.addEventListener('click', clearSearch);
  }
  
  // 监听键盘事件
  searchInput.addEventListener('keydown', (e) => {
    // Enter键执行搜索
    if (e.key === 'Enter') {
      performSearch();
    }
    // Escape键清空搜索
    if (e.key === 'Escape') {
      clearSearch();
    }
  });
  
  // 初始更新
  updateClearButtonState();
}

// 模态框功能
function toggleEditModal() {
  const modal = document.getElementById('edit-modal');
  if (modal.classList.contains('show')) {
    modal.classList.remove('show');
    modal.style.display = 'none';
  } else {
    modal.style.display = 'flex';
    modal.classList.add('show');
  }
}

// 为编辑资料按钮添加事件监听器
window.addEventListener('DOMContentLoaded', () => {
  // 设置文件搜索功能
  setupFileSearch();
  // 编辑资料按钮
  const editProfileBtn = document.getElementById('edit-profile-btn');
  if (editProfileBtn) {
    editProfileBtn.addEventListener('click', toggleEditModal);
  }

  // 关闭模态框按钮
  const closeModalBtn = document.getElementById('close-modal-btn');
  if (closeModalBtn) {
    closeModalBtn.addEventListener('click', toggleEditModal);
  }

  // 取消编辑按钮
  const cancelEditBtn = document.getElementById('cancel-edit-btn');
  if (cancelEditBtn) {
    cancelEditBtn.addEventListener('click', toggleEditModal);
  }

  // 退出登录按钮
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (confirm('确定要退出登录吗？')) {
        window.location.href = '/logout';
      }
    });
  }

  // 访问记录折叠按钮
  const toggleLogsBtn = document.getElementById('toggle-logs-btn');
  if (toggleLogsBtn) {
    toggleLogsBtn.addEventListener('click', toggleLogs);
  }

  // 点击模态框外部关闭模态框
  window.addEventListener('click', (event) => {
    const modal = document.getElementById('edit-modal');
    if (event.target === modal) {
      toggleEditModal();
    }
  });

  // 头像上传功能
  const avatarInput = document.getElementById('avatar');
  const avatarFileSize = document.getElementById('avatar-file-size');
  const avatarPreviewImg = document.getElementById('avatar-preview-img');
  const avatarPreviewPlaceholder = document.getElementById('avatar-preview-placeholder');

  if (avatarInput) {
    avatarInput.addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (file) {
        // 显示文件大小
        const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
        avatarFileSize.textContent = `已选择文件: ${file.name} (${fileSizeMB} MB)`;
        
        // 预览头像
        const reader = new FileReader();
        reader.onload = function(e) {
          if (avatarPreviewImg) {
            avatarPreviewImg.src = e.target.result;
            avatarPreviewImg.style.display = 'block';
          } else {
            // 如果没有预览元素，创建一个
            const newPreviewImg = document.createElement('img');
            newPreviewImg.id = 'avatar-preview-img';
            newPreviewImg.src = e.target.result;
            newPreviewImg.alt = '预览头像';
            newPreviewImg.style.display = 'block';
            newPreviewImg.style.width = '100%';
            newPreviewImg.style.height = '100%';
            newPreviewImg.style.objectFit = 'cover';
            newPreviewImg.style.borderRadius = '50%';
            
            // 移除占位符
            if (avatarPreviewPlaceholder) {
              avatarPreviewPlaceholder.remove();
            }
            
            // 添加预览图片
            const avatarPreview = document.querySelector('.avatar-preview');
            avatarPreview.appendChild(newPreviewImg);
          }
          
          // 隐藏占位符
          if (avatarPreviewPlaceholder) {
            avatarPreviewPlaceholder.style.display = 'none';
          }
        };
        reader.readAsDataURL(file);
      } else {
        // 清除文件大小显示
        avatarFileSize.textContent = '';
      }
    });
  }
});

// 折叠/展开访问记录
function toggleLogs() {
  const logsContainer = document.getElementById('logs-container');
  const toggleIcon = document.getElementById('toggle-icon');
  
  if (logsContainer.style.display === 'none' || logsContainer.style.display === '') {
    // 展开记录
    logsContainer.style.display = 'block';
    toggleIcon.textContent = '▼';
  } else {
    // 折叠记录
    logsContainer.style.display = 'none';
    toggleIcon.textContent = '▶';
  }
}

// 替换文件模态框控制
function openReplaceModal(fileId, fileName) {
  const modal = document.getElementById('replaceModal');
  const fileIdInput = document.getElementById('replaceFileId');
  if (modal && fileIdInput) {
    modal.classList.remove('hidden');
    modal.classList.add('show');
    fileIdInput.value = fileId;
  }
}

function closeReplaceModal() {
  const modal = document.getElementById('replaceModal');
  if (modal) {
    modal.classList.remove('show');
    modal.classList.add('hidden');
  }
}

// 点击模态框外部关闭模态框
window.addEventListener('click', (event) => {
  const modal = document.getElementById('replaceModal');
  if (modal && event.target === modal) {
    closeReplaceModal();
  }
});

// 为替换按钮添加事件监听器
window.addEventListener('DOMContentLoaded', () => {
  // 替换文件模态框关闭按钮
  const closeReplaceBtn = document.querySelector('#replaceModal .modal-close');
  if (closeReplaceBtn) {
    closeReplaceBtn.addEventListener('click', closeReplaceModal);
  }
  
  // 替换文件模态框取消按钮
  const cancelReplaceBtn = document.querySelector('#replaceFileForm .btn-cancel');
  if (cancelReplaceBtn) {
    cancelReplaceBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeReplaceModal();
    });
  }
});
