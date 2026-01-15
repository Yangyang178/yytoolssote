// 初始化全局变量
let isLoggedIn = false;
let searchTimeout = null;

// 导航栏汉堡菜单交互
function initNavBar() {
  const navToggle = document.getElementById('navToggle');
  const navButtons = document.getElementById('navButtons');
  
  if (navToggle && navButtons) {
    navToggle.addEventListener('click', () => {
      navToggle.classList.toggle('active');
      navButtons.classList.toggle('active');
      
      // 阻止页面滚动当菜单打开时
      document.body.style.overflow = navButtons.classList.contains('active') ? 'hidden' : '';
    });
    
    // 点击菜单外部关闭菜单
    document.addEventListener('click', (e) => {
      if (!navToggle.contains(e.target) && !navButtons.contains(e.target)) {
        navToggle.classList.remove('active');
        navButtons.classList.remove('active');
        document.body.style.overflow = '';
      }
    });
    
    // 点击链接后关闭菜单
    const navLinks = navButtons.querySelectorAll('a');
    navLinks.forEach(link => {
      link.addEventListener('click', () => {
        navToggle.classList.remove('active');
        navButtons.classList.remove('active');
        document.body.style.overflow = '';
      });
    });
    
    // 监听窗口大小变化，在大屏幕上自动关闭菜单
    window.addEventListener('resize', () => {
      if (window.innerWidth > 768) {
        navToggle.classList.remove('active');
        navButtons.classList.remove('active');
        document.body.style.overflow = '';
      }
    });
  }
}

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

// 初始化文件互动状态 - 添加错误处理
async function initFileInteractions() {
  try {
    console.log('开始初始化文件互动状态');
    
    // 获取所有文件卡片
    const fileCards = document.querySelectorAll('.file-card');
    
    // 遍历每个文件卡片，初始化互动状态
    for (const card of fileCards) {
      const fileId = card.querySelector('.like-btn')?.dataset?.fileId;
      if (fileId) {
        try {
          // 调用API获取互动状态
          const response = await fetch(`/api/files/${fileId}/interaction-status`);
          const data = await response.json();
          
          if (data.success) {
            // 更新点赞状态
            const likeBtn = card.querySelector('.like-btn');
            const likeCount = likeBtn.querySelector('.count');
            const likeIcon = likeBtn.querySelector('.icon-like');
            likeCount.textContent = data.data.like_count;
            if (data.data.liked) {
              likeIcon.style.color = '#EF4444'; // 红色表示已点赞
            }
            
            // 更新收藏状态
            const favoriteBtn = card.querySelector('.favorite-btn');
            const favoriteCount = favoriteBtn.querySelector('.count');
            const favoriteIcon = favoriteBtn.querySelector('.icon-favorite');
            favoriteCount.textContent = data.data.favorite_count;
            if (data.data.favorited) {
              favoriteIcon.style.color = '#F59E0B'; // 黄色表示已收藏
            }
          }
        } catch (error) {
          console.error(`初始化文件 ${fileId} 互动状态失败:`, error);
        }
      }
    }
    
    console.log('文件互动状态初始化完成');
  } catch (error) {
    console.error('初始化文件互动状态时发生错误:', error);
    window.hideLoading();
    window.showToast('初始化文件互动状态失败: ' + error.message, 'error');
  }
}

// 处理点赞按钮点击事件
async function handleLike(fileId, btn) {
  if (!isLoggedIn) {
    window.showToast('请先登录，才能执行此操作', 'error');
    return;
  }
  
  try {
    // 显示加载动画
    window.showLoading('正在处理点赞操作...');
    
    // 调用点赞API
    const response = await fetch(`/api/files/${fileId}/like`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (data.success) {
      // 更新点赞按钮状态和数量
      const countElement = btn.querySelector('.count');
      countElement.textContent = data.data.count;
      
      // 更新按钮样式
      const iconElement = btn.querySelector('.icon-like');
      if (data.data.liked) {
        iconElement.style.color = '#EF4444'; // 红色表示已点赞
        window.showToast('点赞成功', 'success');
      } else {
        iconElement.style.color = ''; // 默认颜色表示未点赞
        window.showToast('取消点赞成功', 'success');
      }
    } else {
      window.showToast('操作失败: ' + data.message, 'error');
    }
  } catch (error) {
    console.error('点赞操作失败:', error);
    window.showToast('点赞操作失败: ' + error.message, 'error');
  } finally {
    // 隐藏加载动画
    window.hideLoading();
  }
}

// 处理收藏按钮点击事件
async function handleFavorite(fileId, btn) {
  if (!isLoggedIn) {
    window.showToast('请先登录，才能执行此操作', 'error');
    return;
  }
  
  try {
    // 显示加载动画
    window.showLoading('正在处理收藏操作...');
    
    // 调用收藏API
    const response = await fetch(`/api/files/${fileId}/favorite`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (data.success) {
      // 更新收藏按钮状态和数量
      const countElement = btn.querySelector('.count');
      countElement.textContent = data.data.count;
      
      // 更新按钮样式
      const iconElement = btn.querySelector('.icon-favorite');
      if (data.data.favorited) {
        iconElement.style.color = '#F59E0B'; // 黄色表示已收藏
        window.showToast('收藏成功', 'success');
      } else {
        iconElement.style.color = ''; // 默认颜色表示未收藏
        window.showToast('取消收藏成功', 'success');
      }
    } else {
      window.showToast('操作失败: ' + data.message, 'error');
    }
  } catch (error) {
    console.error('收藏操作失败:', error);
    window.showToast('收藏操作失败: ' + error.message, 'error');
  } finally {
    // 隐藏加载动画
    window.hideLoading();
  }
}

// 绑定事件监听 - 简化版，只显示功能未实现提示
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

// 搜索历史记录功能
const SEARCH_HISTORY_KEY = 'search_history';
const MAX_HISTORY_ITEMS = 10;

// 获取搜索历史
function getSearchHistory() {
  const history = localStorage.getItem(SEARCH_HISTORY_KEY);
  return history ? JSON.parse(history) : [];
}

// 保存搜索历史
function saveSearchHistory(term) {
  if (!term || term.trim() === '') {
    return;
  }
  
  const history = getSearchHistory();
  // 移除重复项
  const filteredHistory = history.filter(item => item.toLowerCase() !== term.toLowerCase());
  // 添加到开头
  filteredHistory.unshift(term);
  // 限制数量
  const limitedHistory = filteredHistory.slice(0, MAX_HISTORY_ITEMS);
  // 保存到localStorage
  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(limitedHistory));
}

// 使用搜索历史
function useSearchHistory(term) {
  const searchInput = document.getElementById('file-search');
  if (searchInput) {
    searchInput.value = term;
    searchFiles();
  }
}

// 检查文件是否符合日期筛选条件
function isDateMatch(fileDate, filterValue) {
  if (!filterValue || !fileDate) {
    return true;
  }
  
  const now = new Date();
  const fileDateObj = new Date(fileDate);
  
  switch (filterValue) {
    case 'today':
      return now.toDateString() === fileDateObj.toDateString();
    case 'week':
      const weekAgo = new Date();
      weekAgo.setDate(now.getDate() - 7);
      return fileDateObj >= weekAgo;
    case 'month':
      const monthAgo = new Date();
      monthAgo.setMonth(now.getMonth() - 1);
      return fileDateObj >= monthAgo;
    case 'year':
      const yearAgo = new Date();
      yearAgo.setFullYear(now.getFullYear() - 1);
      return fileDateObj >= yearAgo;
    default:
      return true;
  }
}

// 检查文件是否符合大小筛选条件
function isSizeMatch(fileSize, filterValue) {
  if (!filterValue || fileSize === undefined) {
    return true;
  }
  
  const sizeInBytes = parseInt(fileSize);
  const oneMB = 1024 * 1024;
  const oneGB = oneMB * 1024;
  
  switch (filterValue) {
    case 'small':
      return sizeInBytes < oneMB;
    case 'medium':
      return sizeInBytes >= oneMB && sizeInBytes < 10 * oneMB;
    case 'large':
      return sizeInBytes >= 10 * oneMB && sizeInBytes < 100 * oneMB;
    case 'xlarge':
      return sizeInBytes >= 100 * oneMB;
    default:
      return true;
  }
}

// 更新搜索功能，结合基本搜索和高级筛选
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
    
    // 基本搜索匹配
    const searchMatch = searchTerm === '' || (searchData && searchData.includes(searchTerm));
    
    // 同时满足所有筛选条件
    if (searchMatch) {
      card.style.display = 'block';
    } else {
      card.style.display = 'none';
    }
  });
  
  // 保存到搜索历史
  if (searchTerm) {
    saveSearchHistory(searchTerm);
  }
}

// 防抖函数
function debounce(func, wait) {
  return function executedFunction(...args) {
    const context = this;
    if (searchTimeout) {
      clearTimeout(searchTimeout);
    }
    searchTimeout = setTimeout(() => func.apply(context, args), wait);
  };
}

// 实时搜索 - 必须在searchFiles之后定义
const debouncedSearch = debounce(searchFiles, 300);

// 清除搜索内容
function clearSearch() {
  const searchInput = document.getElementById('file-search');
  if (!searchInput) {
    return;
  }
  
  // 清除输入内容
  searchInput.value = '';
  
  // 调用searchFiles函数，让它处理清除逻辑，包括显示/隐藏清除按钮和应用所有筛选条件
  searchFiles();
}



// 分类筛选功能
function initCategoryFilter() {
  const categoryBtns = document.querySelectorAll('.category-btn');
  const fileCards = document.querySelectorAll('.file-card');
  
  categoryBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      // 移除所有按钮的active类
      categoryBtns.forEach(b => b.classList.remove('active'));
      // 添加当前按钮的active类
      btn.classList.add('active');
      
      const selectedCategory = btn.dataset.category;
      
      // 过滤文件卡片
      fileCards.forEach(card => {
        const cardCategories = card.dataset.categories || '';
        const categoriesList = cardCategories.split(',').map(cat => cat.trim().toLowerCase());
        
        if (selectedCategory === 'all') {
          // 显示所有文件
          card.style.display = 'block';
        } else {
          // 根据分类过滤
          if (categoriesList.includes(selectedCategory.toLowerCase())) {
            card.style.display = 'block';
          } else {
            card.style.display = 'none';
          }
        }
      });
    });
  });
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', () => {
  // 初始化导航栏汉堡菜单
  initNavBar();
  
  // 初始化登录状态
  initLoginStatus();
  
  // 处理文件操作事件
  initFileActions();
  
  // 初始化文件互动状态
  initFileInteractions();
  
  // 绑定事件监听
  bindInteractionEvents();
  
  // 初始化分类筛选功能
  initCategoryFilter();
  
  const searchInput = document.getElementById('file-search');
  const clearBtn = document.getElementById('clear-search');
  const searchBtn = document.querySelector('.search-btn');
  
  // 创建搜索历史下拉容器
  const historyContainer = document.createElement('div');
  historyContainer.id = 'search-history';
  historyContainer.className = 'search-history-dropdown hidden';
  
  // 将搜索历史容器添加到搜索框父元素
  const searchBox = document.querySelector('.search-box');
  if (searchBox) {
    searchBox.appendChild(historyContainer);
  }
  
  // 添加搜索框回车键事件监听
  if (searchInput) {
    // 实时搜索 - 添加防抖
    searchInput.addEventListener('input', debouncedSearch);
    
    // 回车键触发
    searchInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        searchFiles();
      }
    });
    
    // 搜索框获得焦点 - 显示搜索历史
    searchInput.addEventListener('focus', function() {
      if (getSearchHistory().length > 0) {
        renderSearchHistory();
        historyContainer.classList.remove('hidden');
      }
    });
    
    // 点击搜索按钮 - 隐藏搜索历史
    if (searchBtn) {
      searchBtn.addEventListener('click', function() {
        historyContainer.classList.add('hidden');
      });
    }
    
    // 监听输入变化，显示/隐藏清除按钮
    searchInput.addEventListener('input', function() {
      if (this.value === '') {
        if (clearBtn) {
          clearBtn.classList.add('hidden');
        }
      } else {
        if (clearBtn) {
          clearBtn.classList.remove('hidden');
        }
      }
    });
  }
  
  // 点击页面其他区域 - 隐藏搜索历史
  document.addEventListener('click', function(e) {
    const isClickInside = searchBox && searchBox.contains(e.target);
    if (!isClickInside) {
      historyContainer.classList.add('hidden');
    }
  });
});

// 渲染搜索历史
function renderSearchHistory() {
  const history = getSearchHistory();
  const historyContainer = document.getElementById('search-history');
  
  if (!historyContainer) {
    return;
  }
  
  if (history.length === 0) {
    historyContainer.innerHTML = '<div class="search-history-empty">暂无搜索历史</div>';
    return;
  }
  
  const historyHtml = history.map(term => `
    <div class="search-history-item" onclick="useSearchHistory('${term}')">
      <span class="history-term">${term}</span>
      <button class="remove-history-btn" onclick="removeSearchHistory('${term}'); event.stopPropagation();">×</button>
    </div>
  `).join('');
  
  historyContainer.innerHTML = `
    <div class="search-history-header">
      <span>搜索历史</span>
      <button class="clear-history-btn" onclick="clearSearchHistory()">清空</button>
    </div>
    <div class="search-history-list">${historyHtml}</div>
  `;
}

// 移除单个搜索历史
function removeSearchHistory(term) {
  const history = getSearchHistory();
  const filteredHistory = history.filter(item => item !== term);
  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(filteredHistory));
  renderSearchHistory();
}

// 清空搜索历史
function clearSearchHistory() {
  localStorage.removeItem(SEARCH_HISTORY_KEY);
  renderSearchHistory();
}