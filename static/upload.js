// 文件上传拖拽功能
const fileInput = document.querySelector('.file-input');
const fileLabel = document.querySelector('.file-label');
const fileText = document.querySelector('.file-text');
const fileSizeElement = document.querySelector('.file-size');

// 格式化文件大小为人类可读格式
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[Math.min(i, sizes.length - 1)];
}

// 定义允许的文件类型和大小限制
const MAX_FILE_SIZE = 200 * 1024 * 1024; // 200MB
const ALLOWED_MIME_TYPES = {
    'image/': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg'],
    'application/': ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'json', 'xml'],
    'text/': ['txt', 'csv', 'html', 'css', 'js', 'ts', 'py', 'java', 'c', 'cpp', 'php'],
    'video/': ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm'],
    'audio/': ['mp3', 'wav', 'ogg', 'wma', 'aac']
};

// 检查文件类型是否允许
function isFileTypeAllowed(file) {
    const mimeType = file.type;
    const fileExtension = file.name.split('.').pop().toLowerCase();
    
    // 检查MIME类型前缀
    for (const [mimePrefix, extensions] of Object.entries(ALLOWED_MIME_TYPES)) {
        if (mimeType.startsWith(mimePrefix) || extensions.includes(fileExtension)) {
            return true;
        }
    }
    return false;
}

// 检查文件大小是否允许
function isFileSizeAllowed(file) {
    return file.size <= MAX_FILE_SIZE;
}

// 显示错误信息
function showError(message) {
    let errorElement = document.querySelector('.file-error');
    if (!errorElement) {
        errorElement = document.createElement('p');
        errorElement.className = 'file-error';
        errorElement.style.color = '#ef4444';
        errorElement.style.marginTop = '8px';
        fileLabel.parentElement.appendChild(errorElement);
    }
    errorElement.textContent = message;
}

// 清除错误信息
function clearError() {
    const errorElement = document.querySelector('.file-error');
    if (errorElement) {
        errorElement.remove();
    }
}

// 更新文件显示
function updateFileDisplay(file) {
    fileText.textContent = file.name;
    fileSizeElement.textContent = formatFileSize(file.size);
}

// 监听文件选择
fileInput.addEventListener('change', function(e) {
    if (this.files.length > 0) {
        const file = this.files[0];
        
        // 清除之前的错误
        clearError();
        
        // 验证文件类型
        if (!isFileTypeAllowed(file)) {
            showError('不支持的文件类型，请上传图片、文档、视频或音频文件');
            this.value = '';
            fileText.textContent = '点击选择文件或拖拽文件到此处';
            fileSizeElement.textContent = '';
            return;
        }
        
        // 验证文件大小
        if (!isFileSizeAllowed(file)) {
            showError('文件大小超过限制，单个文件不超过200MB');
            this.value = '';
            fileText.textContent = '点击选择文件或拖拽文件到此处';
            fileSizeElement.textContent = '';
            return;
        }
        
        // 验证通过，显示文件名和大小
        updateFileDisplay(file);
    } else {
        fileText.textContent = '点击选择文件或拖拽文件到此处';
        fileSizeElement.textContent = '';
        clearError();
    }
});

// 拖拽功能
fileLabel.addEventListener('dragover', function(e) {
    e.preventDefault();
    this.classList.add('dragover');
});

fileLabel.addEventListener('dragleave', function(e) {
    e.preventDefault();
    this.classList.remove('dragover');
});

fileLabel.addEventListener('drop', function(e) {
    e.preventDefault();
    this.classList.remove('dragover');
    
    if (e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        
        // 清除之前的错误
        clearError();
        
        // 验证文件类型
        if (!isFileTypeAllowed(file)) {
            showError('不支持的文件类型，请上传图片、文档、视频或音频文件');
            return;
        }
        
        // 验证文件大小
        if (!isFileSizeAllowed(file)) {
            showError('文件大小超过限制，单个文件不超过200MB');
            return;
        }
        
        // 验证通过，设置文件并显示文件名和大小
        fileInput.files = e.dataTransfer.files;
        updateFileDisplay(file);
    }
});