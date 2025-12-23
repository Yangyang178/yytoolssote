// 文件上传拖拽功能
const fileInput = document.querySelector('.file-input');
const fileLabel = document.querySelector('.file-label');
const fileText = document.querySelector('.file-text');
const fileSizeElement = document.querySelector('.file-size');

// 预览相关元素
const filePreviewContainer = document.getElementById('filePreviewContainer');
const filePreviewContent = document.getElementById('filePreviewContent');
const clearPreviewBtn = document.getElementById('clearPreview');

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

// 显示预览容器
function showPreviewContainer() {
    filePreviewContainer.style.display = 'block';
}

// 隐藏预览容器
function hidePreviewContainer() {
    filePreviewContainer.style.display = 'none';
}

// 清除预览内容
function clearPreviewContent() {
    filePreviewContent.innerHTML = '';
    hidePreviewContainer();
}

// 清除预览
function clearPreview() {
    clearPreviewContent();
    fileInput.value = '';
    fileText.textContent = '点击选择文件或拖拽文件到此处';
    fileSizeElement.textContent = '';
    clearError();
}

// 获取文档图标
function getDocumentIcon(fileName) {
    const ext = fileName.split('.').pop().toLowerCase();
    const icons = {
        'pdf': '📄',
        'doc': '📝',
        'docx': '📝',
        'xls': '📊',
        'xlsx': '📊',
        'ppt': '📈',
        'pptx': '📈',
        'json': '🔧',
        'xml': '🔧',
        'zip': '📦',
        'rar': '📦',
        '7z': '📦'
    };
    return icons[ext] || '📁';
}

// 生成文件预览
function generateFilePreview(file) {
    clearPreviewContent();
    
    const previewItem = document.createElement('div');
    previewItem.className = 'preview-item';
    
    // 根据文件类型生成不同的预览
    const fileExtension = file.name.split('.').pop().toLowerCase();
    const mimeType = file.type;
    
    let previewContent;
    let actionText;
    let actionHandler;
    
    if (mimeType.startsWith('image/')) {
        // 图片预览
        previewContent = document.createElement('img');
        previewContent.className = 'preview-image';
        previewContent.alt = file.name;
        
        const reader = new FileReader();
        reader.onload = function(e) {
            previewContent.src = e.target.result;
        };
        reader.readAsDataURL(file);
        
        actionText = '在新窗口打开';
        actionHandler = function() {
            const reader = new FileReader();
            reader.onload = function(e) {
                // 创建Blob对象
                const blob = new Blob([e.target.result], { type: mimeType });
                // 创建URL
                const url = URL.createObjectURL(blob);
                // 在新窗口打开
                window.open(url, '_blank');
            };
            reader.readAsDataURL(file);
        };
    } else if (mimeType.startsWith('video/')) {
        // 视频预览
        previewContent = document.createElement('video');
        previewContent.className = 'preview-video';
        previewContent.controls = true;
        previewContent.muted = true;
        
        const reader = new FileReader();
        reader.onload = function(e) {
            previewContent.src = e.target.result;
        };
        reader.readAsDataURL(file);
        
        actionText = '在新窗口打开';
        actionHandler = function() {
            const reader = new FileReader();
            reader.onload = function(e) {
                // 创建Blob对象
                const blob = new Blob([e.target.result], { type: mimeType });
                // 创建URL
                const url = URL.createObjectURL(blob);
                // 在新窗口打开
                window.open(url, '_blank');
            };
            reader.readAsDataURL(file);
        };
    } else if (mimeType.startsWith('audio/')) {
        // 音频预览
        previewContent = document.createElement('audio');
        previewContent.className = 'preview-audio';
        previewContent.controls = true;
        
        const reader = new FileReader();
        reader.onload = function(e) {
            previewContent.src = e.target.result;
        };
        reader.readAsDataURL(file);
        
        actionText = '在新窗口打开';
        actionHandler = function() {
            const reader = new FileReader();
            reader.onload = function(e) {
                // 创建Blob对象
                const blob = new Blob([e.target.result], { type: mimeType });
                // 创建URL
                const url = URL.createObjectURL(blob);
                // 在新窗口打开
                window.open(url, '_blank');
            };
            reader.readAsDataURL(file);
        };
    } else if (mimeType.startsWith('text/') || mimeType === 'application/json' || mimeType === 'application/xml') {
        // 文本文件预览
        previewContent = document.createElement('div');
        previewContent.className = 'preview-text-container';
        
        const reader = new FileReader();
        reader.onload = function(e) {
            const content = e.target.result;
            
            if (fileExtension === 'html') {
                // HTML文件使用iframe预览
                const iframe = document.createElement('iframe');
                iframe.className = 'preview-iframe';
                iframe.style.width = '100%';
                iframe.style.height = '300px';
                iframe.style.border = '1px solid #e2e8f0';
                iframe.style.borderRadius = '8px';
                
                iframe.onload = function() {
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                    iframeDoc.open();
                    iframeDoc.write(content);
                    iframeDoc.close();
                };
                
                previewContent.appendChild(iframe);
            } else {
                // 其他文本文件显示代码
                const pre = document.createElement('pre');
                pre.className = 'preview-text';
                pre.textContent = content;
                pre.style.maxHeight = '300px';
                pre.style.overflow = 'auto';
                
                previewContent.appendChild(pre);
            }
        };
        reader.readAsText(file);
        
        actionText = '查看完整内容';
        actionHandler = function() {
            const reader = new FileReader();
            reader.onload = function(e) {
                // 创建Blob对象
                const blob = new Blob([e.target.result], { type: fileExtension === 'html' ? 'text/html' : 'text/plain' });
                // 创建URL
                const url = URL.createObjectURL(blob);
                // 在新窗口打开
                window.open(url, '_blank');
            };
            reader.readAsText(file);
        };
    } else {
        // 文档预览
        previewContent = document.createElement('div');
        previewContent.className = 'preview-document';
        
        const icon = document.createElement('div');
        icon.className = 'document-icon';
        icon.textContent = getDocumentIcon(file.name);
        
        const name = document.createElement('div');
        name.className = 'document-name';
        name.textContent = file.name;
        
        const info = document.createElement('div');
        info.className = 'document-info';
        info.textContent = `${formatFileSize(file.size)}`;
        
        previewContent.appendChild(icon);
        previewContent.appendChild(name);
        previewContent.appendChild(info);
        
        actionText = '上传后查看';
        actionHandler = function() {
            alert('文件上传后才能查看完整内容');
        };
    }
    
    // 添加操作按钮
    const actionButton = document.createElement('button');
    actionButton.type = 'button'; // 设置为button类型，避免提交表单
    actionButton.className = 'preview-action-btn';
    actionButton.textContent = actionText;
    actionButton.addEventListener('click', actionHandler);
    
    // 添加到预览项目
    previewItem.appendChild(previewContent);
    previewItem.appendChild(actionButton);
    
    filePreviewContent.appendChild(previewItem);
    showPreviewContainer();
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
            clearPreviewContent();
            return;
        }
        
        // 验证文件大小
        if (!isFileSizeAllowed(file)) {
            showError('文件大小超过限制，单个文件不超过200MB');
            this.value = '';
            fileText.textContent = '点击选择文件或拖拽文件到此处';
            fileSizeElement.textContent = '';
            clearPreviewContent();
            return;
        }
        
        // 验证通过，显示文件名和大小
        updateFileDisplay(file);
        
        // 生成预览
        generateFilePreview(file);
    } else {
        fileText.textContent = '点击选择文件或拖拽文件到此处';
        fileSizeElement.textContent = '';
        clearError();
        clearPreviewContent();
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
            clearPreviewContent();
            return;
        }
        
        // 验证文件大小
        if (!isFileSizeAllowed(file)) {
            showError('文件大小超过限制，单个文件不超过200MB');
            clearPreviewContent();
            return;
        }
        
        // 验证通过，设置文件并显示文件名和大小
        fileInput.files = e.dataTransfer.files;
        updateFileDisplay(file);
        
        // 生成预览
        generateFilePreview(file);
    }
});

// 清除预览按钮事件
clearPreviewBtn.addEventListener('click', clearPreview);