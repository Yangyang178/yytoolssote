// 初始化全局变量
let isLoggedIn = false;

// 初始化登录状态
function initLoginStatus() {
  const appData = document.getElementById('app-data');
  if (appData) {
    try {
      isLoggedIn = JSON.parse(appData.dataset.isLoggedIn);
    } catch (error) {
      console.error('解析登录状态失败:', error);
      isLoggedIn = false;
    }
  }
}

// 处理文件操作事件
function initFileActions() {
  const fileActions = document.querySelectorAll('.file-action');
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
        if (action.textContent.trim() === '删除') {
          if (!confirm('确定要删除这个文件吗？此操作不可恢复。')) {
            e.preventDefault();
          }
        }
      });
    }
  });
}

// 初始化文件互动状态
async function initFileInteractions() {
  const fileCards = document.querySelectorAll('.file-card');
  
  for (const card of fileCards) {
    const likeBtn = card.querySelector('.like-btn');
    const favoriteBtn = card.querySelector('.favorite-btn');
    
    if (!likeBtn || !favoriteBtn) {
      continue;
    }
    
    const fileId = likeBtn.dataset?.fileId;
    
    if (!fileId) {
      continue;
    }
    
    try {
      const response = await fetch(`/api/files/${fileId}/interactions`);
      const data = await response.json();
      
      if (data.success) {
        // 更新点赞数和状态
        const likeCount = likeBtn.querySelector('.count');
        if (likeCount) {
          likeCount.textContent = data.like_count;
        }
        if (data.is_liked) {
          likeBtn.classList.add('active');
        }
        
        // 更新收藏数和状态
        const favoriteCount = favoriteBtn.querySelector('.count');
        if (favoriteCount) {
          favoriteCount.textContent = data.favorite_count;
        }
        if (data.is_favorited) {
          favoriteBtn.classList.add('active');
        }
      }
    } catch (error) {
      console.error(`初始化文件 ${fileId} 互动状态失败：`, error);
    }
  }
}

// 处理点赞按钮点击事件
async function handleLike(fileId, btn) {
  if (!isLoggedIn) {
    alert('请先登录，才能执行此操作');
    return;
  }
  
  if (!fileId || !btn) {
    console.error('点赞失败：缺少必要参数');
    return;
  }
  
  try {
    const response = await fetch(`/api/files/${fileId}/like`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (data.success) {
      // 更新按钮状态
      if (data.liked) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
      
      // 更新点赞数
      const countElement = btn.querySelector('.count');
      if (countElement) {
        countElement.textContent = data.count;
      }
    }
  } catch (error) {
    console.error(`点赞失败：`, error);
    alert('点赞失败，请稍后重试');
  }
}

// 处理收藏按钮点击事件
async function handleFavorite(fileId, btn) {
  if (!isLoggedIn) {
    alert('请先登录，才能执行此操作');
    return;
  }
  
  if (!fileId || !btn) {
    console.error('收藏失败：缺少必要参数');
    return;
  }
  
  try {
    const response = await fetch(`/api/files/${fileId}/favorite`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (data.success) {
      // 更新按钮状态
      if (data.favorited) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
      
      // 更新收藏数
      const countElement = btn.querySelector('.count');
      if (countElement) {
        countElement.textContent = data.count;
      }
    }
  } catch (error) {
    console.error(`收藏失败：`, error);
    alert('收藏失败，请稍后重试');
  }
}

// 绑定事件监听
function bindInteractionEvents() {
  // 处理点赞按钮点击事件
  const likeBtns = document.querySelectorAll('.like-btn');
  likeBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const fileId = btn.dataset?.fileId;
      if (fileId) {
        handleLike(fileId, btn);
      }
    });
  });
  
  // 处理收藏按钮点击事件
  const favoriteBtns = document.querySelectorAll('.favorite-btn');
  favoriteBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const fileId = btn.dataset?.fileId;
      if (fileId) {
        handleFavorite(fileId, btn);
      }
    });
  });
}

// 搜索文件功能
function searchFiles() {
  const searchInput = document.getElementById('file-search');
  if (!searchInput) {
    return;
  }
  
  const searchTerm = searchInput.value.toLowerCase().trim();
  const fileCards = document.querySelectorAll('.file-card');
  const clearBtn = document.getElementById('clear-search');
  
  // 显示/隐藏清除按钮
  if (clearBtn) {
    if (searchTerm === '') {
      clearBtn.classList.add('hidden');
    } else {
      clearBtn.classList.remove('hidden');
    }
  }
  
  fileCards.forEach(card => {
    const searchData = card.dataset?.search?.toLowerCase();
    if (searchTerm === '' || (searchData && searchData.includes(searchTerm))) {
      card.style.display = 'block';
    } else {
      card.style.display = 'none';
    }
  });
}

// 清除搜索内容
function clearSearch() {
  const searchInput = document.getElementById('file-search');
  if (!searchInput) {
    return;
  }
  
  const clearBtn = document.getElementById('clear-search');
  const fileCards = document.querySelectorAll('.file-card');
  
  // 清除输入内容
  searchInput.value = '';
  
  // 隐藏清除按钮
  if (clearBtn) {
    clearBtn.classList.add('hidden');
  }
  
  // 显示所有文件卡片
  fileCards.forEach(card => {
    card.style.display = 'block';
  });
}

// 回车键触发搜索
window.addEventListener('DOMContentLoaded', () => {
  // 初始化登录状态
  initLoginStatus();
  
  // 处理文件操作事件
  initFileActions();
  
  // 初始化文件互动状态
  initFileInteractions();
  
  // 绑定事件监听
  bindInteractionEvents();
  
  const searchInput = document.getElementById('file-search');
  const clearBtn = document.getElementById('clear-search');
  
  // 添加搜索框回车键事件监听
  if (searchInput) {
    searchInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        searchFiles();
      }
    });
    
    // 监听输入变化，显示/隐藏清除按钮
    searchInput.addEventListener('input', function() {
      if (this.value === '') {
        if (clearBtn) {
          clearBtn.classList.add('hidden');
        }
        // 显示所有文件卡片
        const fileCards = document.querySelectorAll('.file-card');
        fileCards.forEach(card => {
          card.style.display = 'block';
        });
      } else {
        if (clearBtn) {
          clearBtn.classList.remove('hidden');
        }
      }
    });
  }
});