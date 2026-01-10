#!/usr/bin/env python3
# 检查日志数据是否正确插入到数据库

import sqlite3
import os

# 数据库路径
DB_FILE = 'data/db.sqlite'

def check_logs():
    if not os.path.exists(DB_FILE):
        print(f"数据库文件不存在: {DB_FILE}")
        return
    
    # 连接到数据库
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print("=== 检查logs表结构 ===")
    cursor.execute("PRAGMA table_info(logs)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"列名: {col[1]}, 类型: {col[2]}")
    
    print("\n=== 检查login_attempts表结构 ===")
    cursor.execute("PRAGMA table_info(login_attempts)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"列名: {col[1]}, 类型: {col[2]}")
    
    print("\n=== 检查操作日志数据 ===")
    cursor.execute("SELECT log_type, message, created_at FROM logs ORDER BY created_at DESC LIMIT 10")
    logs = cursor.fetchall()
    if logs:
        print(f"共找到 {len(logs)} 条日志")
        for log in logs:
            print(f"类型: {log[0]}, 消息: {log[1]}, 时间: {log[2]}")
    else:
        print("未找到日志记录")
    
    print("\n=== 检查登录尝试数据 ===")
    cursor.execute("SELECT email, success, ip_address, attempt_time FROM login_attempts ORDER BY attempt_time DESC LIMIT 10")
    attempts = cursor.fetchall()
    if attempts:
        print(f"共找到 {len(attempts)} 条登录尝试")
        for attempt in attempts:
            print(f"邮箱: {attempt[0]}, 成功: {'是' if attempt[1] else '否'}, IP: {attempt[2]}, 时间: {attempt[3]}")
    else:
        print("未找到登录尝试记录")
    
    # 关闭连接
    conn.close()

if __name__ == "__main__":
    check_logs()
