#!/usr/bin/env python3
# 恢复备份文件中的app.py

import zipfile
import os

# 备份文件路径
BACKUP_FILE = 'backup_20251227.zip'
# 目标文件路径
TARGET_FILE = 'app.py'

# 检查备份文件是否存在
if not os.path.exists(BACKUP_FILE):
    print(f"备份文件不存在: {BACKUP_FILE}")
    exit(1)

# 打开备份文件
with zipfile.ZipFile(BACKUP_FILE, 'r') as zip_ref:
    # 查看备份文件中的内容
    print("备份文件中的内容:")
    for item in zip_ref.namelist():
        print(f"  - {item}")
    
    # 检查是否包含app.py文件
    if TARGET_FILE in zip_ref.namelist():
        # 提取app.py文件
        print(f"\n正在从备份文件中提取 {TARGET_FILE}...")
        zip_ref.extract(TARGET_FILE, '.')
        print(f"成功提取 {TARGET_FILE}")
    else:
        print(f"\n备份文件中不包含 {TARGET_FILE}")
