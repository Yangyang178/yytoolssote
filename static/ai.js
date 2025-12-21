// AI页面逻辑
const appData = document.getElementById('app-data');
const isLoggedIn = JSON.parse(appData.dataset.isLoggedIn);
const aiForm = document.querySelector('.ai-form');

// AI表单提交事件
aiForm.addEventListener('submit', (e) => {
  if (!isLoggedIn) {
    alert('请先登录，才能使用AI对话功能');
    e.preventDefault();
    return;
  }
});
