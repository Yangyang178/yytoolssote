// 文件上传拖拽功能
const fileInput = document.querySelector('.file-input');
const fileLabel = document.querySelector('.file-label');
const fileText = document.querySelector('.file-text');

// 监听文件选择
fileInput.addEventListener('change', function(e) {
    if (this.files.length > 0) {
        fileText.textContent = this.files[0].name;
    } else {
        fileText.textContent = '点击选择文件或拖拽文件到此处';
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
        fileInput.files = e.dataTransfer.files;
        fileText.textContent = e.dataTransfer.files[0].name;
    }
});
