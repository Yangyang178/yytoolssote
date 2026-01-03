# 备份脚本 - 用于备份数据库文件、上传文件和用户头像

# 定义备份目录和文件名
$backupDir = "D:\Trae\接口文件"
$timestamp = Get-Date -Format yyyyMMdd_HHmmss
$backupFileName = "backup_$timestamp.zip"
$backupPath = Join-Path $backupDir $backupFileName

# 要备份的目录
$directoriesToBackup = @("data", "uploads", "static/avatars")

# 创建备份
Write-Host "开始备份..."
Compress-Archive -Path $directoriesToBackup -DestinationPath $backupPath -Force

# 检查备份是否成功
if (Test-Path $backupPath) {
    Write-Host "备份成功！文件路径：$backupPath"
    
    # 删除7天前的旧备份文件
    Write-Host "清理旧备份文件..."
    $oldBackups = Get-ChildItem -Path $backupDir -Filter "backup_*.zip" | Where-Object {
        $_.LastWriteTime -lt (Get-Date).AddDays(-7)
    }
    
    foreach ($oldBackup in $oldBackups) {
        Remove-Item $oldBackup.FullName -Force
        Write-Host "已删除旧备份：$($oldBackup.Name)"
    }
    
    Write-Host "备份完成！"
} else {
    Write-Host "备份失败！"
    exit 1
}