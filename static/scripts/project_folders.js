// 项目文件夹页面脚本

// 删除确认弹窗功能
function confirmDeleteFolder(folderId, folderName) {
    // 获取弹窗元素
    const modal = document.getElementById('delete-confirm-modal');
    const deleteMessage = document.getElementById('delete-message');
    const deleteForm = document.getElementById('delete-form');
    
    // 设置删除消息
    deleteMessage.textContent = `确定要删除文件夹 "${folderName}" 及其所有内容吗？`;
    
    // 设置表单的action
    deleteForm.action = `/delete-folder/${folderId}`;
    
    // 显示弹窗
    modal.style.display = 'flex';
}

// 关闭删除弹窗功能
function closeDeleteModal() {
    // 获取弹窗元素
    const modal = document.getElementById('delete-confirm-modal');
    
    // 隐藏弹窗
    modal.style.display = 'none';
}

// 页面加载完成后添加事件监听器
document.addEventListener('DOMContentLoaded', function() {
    // 返回按钮事件监听器
    const backButton = document.querySelector('.back-btn');
    if (backButton) {
        backButton.addEventListener('click', function() {
            window.history.back();
        });
    }
    
    // 创建文件夹按钮事件监听器
    const createFolderBtn = document.getElementById('create-folder-btn');
    const createFolderForm = document.getElementById('create-folder-form');
    const cancelCreateBtn = document.getElementById('cancel-create-btn');
    
    if (createFolderBtn && createFolderForm && cancelCreateBtn) {
        createFolderBtn.addEventListener('click', function() {
            createFolderForm.style.display = 'block';
        });
        
        cancelCreateBtn.addEventListener('click', function() {
            createFolderForm.style.display = 'none';
        });
    }
    
    // 删除按钮事件监听器
    const deleteButtons = document.querySelectorAll('.btn-delete');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const folderId = this.getAttribute('data-folder-id');
            const folderName = this.getAttribute('data-folder-name');
            confirmDeleteFolder(folderId, folderName);
        });
    });
});