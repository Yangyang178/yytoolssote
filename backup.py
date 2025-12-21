import os
import shutil
import datetime
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据库和上传文件目录
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"

# 备份目录
BACKUP_DIR = BASE_DIR / "backup"


def backup():
    """备份数据库和上传文件"""
    # 确保备份目录存在
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # 创建带有时间戳的备份子目录
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = BACKUP_DIR / timestamp
    backup_subdir.mkdir(parents=True, exist_ok=True)
    
    print(f"开始备份到目录: {backup_subdir}")
    
    # 备份数据库文件
    db_file = DATA_DIR / "db.sqlite"
    if db_file.exists():
        backup_db = backup_subdir / "db.sqlite"
        shutil.copy2(db_file, backup_db)
        print(f"✅ 数据库备份完成: {backup_db}")
    else:
        print(f"⚠️  数据库文件不存在: {db_file}")
    
    # 备份上传文件目录
    if UPLOAD_DIR.exists():
        backup_upload = backup_subdir / "uploads"
        shutil.copytree(UPLOAD_DIR, backup_upload, dirs_exist_ok=True)
        print(f"✅ 上传文件备份完成: {backup_upload}")
    else:
        print(f"⚠️  上传文件目录不存在: {UPLOAD_DIR}")
    
    # 统计备份文件大小
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(backup_subdir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    
    print(f"\n📊 备份统计信息:")
    print(f"   备份目录: {backup_subdir}")
    print(f"   备份大小: {total_size / (1024 * 1024):.2f} MB")
    print(f"   备份时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 提示用户可以压缩备份目录
    print(f"\n💡 提示: 你可以使用以下命令压缩备份目录:")
    print(f"   tar -czf {backup_subdir}.tar.gz {backup_subdir}")
    print(f"   或使用Windows压缩工具右键压缩")
    
    return backup_subdir


def list_backups():
    """列出所有备份"""
    if not BACKUP_DIR.exists():
        print(f"⚠️  备份目录不存在: {BACKUP_DIR}")
        return
    
    backups = sorted(BACKUP_DIR.iterdir(), reverse=True)  # 按时间倒序排列
    
    if not backups:
        print(f"⚠️  没有找到备份文件")
        return
    
    print(f"📋 备份列表 (共 {len(backups)} 个):")
    for i, backup_dir in enumerate(backups, 1):
        if backup_dir.is_dir():
            # 计算备份大小
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(backup_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
            
            # 解析时间戳
            timestamp = backup_dir.name
            try:
                backup_time = datetime.datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                time_str = backup_time.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                time_str = timestamp
            
            print(f"   {i:2d}. {time_str} - {total_size / (1024 * 1024):.2f} MB - {backup_dir}")


def main():
    """主函数"""
    print("====================================")
    print("         数据库和文件备份工具        ")
    print("====================================")
    print()
    
    # 执行备份
    backup_subdir = backup()
    
    print()
    print("====================================")
    print("         备份完成！                  ")
    print("====================================")
    print()
    
    # 列出所有备份
    list_backups()


if __name__ == "__main__":
    main()
