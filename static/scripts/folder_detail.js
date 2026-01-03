// 文件夹详情页面脚本

// 页面加载完成后添加事件监听器
document.addEventListener('DOMContentLoaded', function() {
    // 返回按钮事件监听器
    const backButton = document.querySelector('.back-btn');
    if (backButton) {
        backButton.addEventListener('click', function() {
            window.history.back();
        });
    }
    
    // 上传文件按钮事件监听器
    const uploadFileBtn = document.getElementById('upload-file-btn');
    const uploadFileForm = document.getElementById('upload-file-form');
    const cancelUploadBtn = document.getElementById('cancel-upload-btn');
    
    // 上传文件夹按钮事件监听器
    const uploadFolderBtn = document.getElementById('upload-folder-btn');
    const uploadFolderForm = document.getElementById('upload-folder-form');
    const cancelFolderUploadBtn = document.getElementById('cancel-folder-upload-btn');
    
    // 创建子文件夹按钮事件监听器
    const createSubfolderBtn = document.getElementById('create-subfolder-btn');
    const createSubfolderForm = document.getElementById('create-subfolder-form');
    const cancelSubfolderBtn = document.getElementById('cancel-subfolder-btn');
    
    if (uploadFileBtn && uploadFileForm && cancelUploadBtn) {
        uploadFileBtn.addEventListener('click', function() {
            uploadFileForm.style.display = 'block';
            uploadFolderForm.style.display = 'none';
            createSubfolderForm.style.display = 'none';
        });
        
        cancelUploadBtn.addEventListener('click', function() {
            uploadFileForm.style.display = 'none';
        });
    }
    
    if (uploadFolderBtn && uploadFolderForm && cancelFolderUploadBtn) {
        uploadFolderBtn.addEventListener('click', function() {
            uploadFolderForm.style.display = 'block';
            uploadFileForm.style.display = 'none';
            createSubfolderForm.style.display = 'none';
        });
        
        cancelFolderUploadBtn.addEventListener('click', function() {
            uploadFolderForm.style.display = 'none';
        });
    }
    
    if (createSubfolderBtn && createSubfolderForm && cancelSubfolderBtn) {
        createSubfolderBtn.addEventListener('click', function() {
            createSubfolderForm.style.display = 'block';
            uploadFileForm.style.display = 'none';
            uploadFolderForm.style.display = 'none';
        });
        
        cancelSubfolderBtn.addEventListener('click', function() {
            createSubfolderForm.style.display = 'none';
        });
    }
    
    // 删除按钮事件监听器
    const deleteButtons = document.querySelectorAll('.btn-delete');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            // 检查是文件夹还是文件
            const folderId = this.getAttribute('data-folder-id');
            const folderName = this.getAttribute('data-folder-name');
            const fileId = this.getAttribute('data-file-id');
            const fileName = this.getAttribute('data-file-name');
            
            if (folderId && folderName) {
                // 文件夹删除
                confirmDeleteFolder(folderId, folderName);
            } else if (fileId && fileName) {
                // 文件删除
                confirmDeleteFile(fileId, fileName);
            }
        });
    });
});

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

function confirmDeleteFile(fileId, fileName) {
    // 获取弹窗元素
    const modal = document.getElementById('delete-confirm-modal');
    const deleteMessage = document.getElementById('delete-message');
    const deleteForm = document.getElementById('delete-form');
    
    // 设置删除消息
    deleteMessage.textContent = `确定要删除文件 "${fileName}" 吗？`;
    
    // 设置表单的action
    deleteForm.action = `/delete-file/${fileId}`;
    
    // 显示弹窗
    modal.style.display = 'flex';
}

function closeDeleteModal() {
    // 获取弹窗元素
    const modal = document.getElementById('delete-confirm-modal');
    
    // 隐藏弹窗
    modal.style.display = 'none';
}