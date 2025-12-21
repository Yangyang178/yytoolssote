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

// 处理取消收藏操作
async function handleUnfavorite(fileId, btn) {
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
      window.location.reload();
    } else {
      alert('取消收藏失败，请稍后重试');
    }
  } catch (error) {
    console.error(`取消收藏失败：`, error);
    alert('取消收藏失败，请稍后重试');
  }
}

// 模态框功能
function toggleEditModal() {
  const modal = document.getElementById('edit-modal');
  if (modal.style.display === 'flex') {
    modal.style.display = 'none';
  } else {
    modal.style.display = 'flex';
    modal.classList.add('show');
  }
}

// 为编辑资料按钮添加事件监听器
window.addEventListener('DOMContentLoaded', () => {
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
