#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库结构和数据
"""

import sys
import os
import sqlite3

# 数据库文件路径
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'db.sqlite')

def check_db_structure():
    """检查数据库结构和数据"""
    print(f"数据库文件: {DB_FILE}")
    print(f"数据库是否存在: {os.path.exists(DB_FILE)}")
    
    # 连接数据库
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        print("\n1. 检查operation_logs表结构:")
        cursor.execute("PRAGMA table_info(operation_logs)")
        columns = cursor.fetchall()
        for column in columns:
            print(f"   {column[1]}: {column[2]} (PK: {column[5]})")
        
        print("\n2. 检查operation_logs表数据:")
        cursor.execute("SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 10")
        logs = cursor.fetchall()
        print(f"   共有 {len(logs)} 条日志")
        # 打印字段索引，以便调试
        print(f"   字段索引: id[0], user_id[1], action[2], target_id[3], target_type[4], message[5], details[6], created_at[7]")
        for log in logs:
            print(f"   ID: {log[0]}, UserID: {log[1]} (类型: {type(log[1])}), Action: {log[2]}, Message: {log[5]}, Details: {log[6]}, 时间: {log[7]}")
        
        print("\n3. 检查users表结构:")
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        for column in columns:
            print(f"   {column[1]}: {column[2]} (PK: {column[5]})")
        
        print("\n4. 检查users表数据:")
        cursor.execute("SELECT id, username FROM users LIMIT 10")
        users = cursor.fetchall()
        print(f"   共有 {len(users)} 个用户")
        for user in users:
            print(f"   UserID: {user[0]} (类型: {type(user[0])}), Username: {user[1]}")
        
        print("\n5. 检查files表中folder_id字段:")
        cursor.execute("SELECT id, filename, folder_id FROM files WHERE folder_id IS NOT NULL AND folder_id != '' LIMIT 5")
        files = cursor.fetchall()
        print(f"   共有 {len(files)} 个文件带有folder_id")
        for file in files:
            print(f"   FileID: {file[0]}, Filename: {file[1]}, FolderID: {file[2]} (类型: {type(file[2])})")
        
        # 检查用户ID格式是否一致
        print("\n6. 检查用户ID格式一致性:")
        cursor.execute("SELECT DISTINCT LENGTH(user_id) FROM users")
        user_id_lengths = cursor.fetchall()
        print(f"   用户ID长度: {[l[0] for l in user_id_lengths]}")
        
        cursor.execute("SELECT DISTINCT LENGTH(user_id) FROM operation_logs")
        log_user_id_lengths = cursor.fetchall()
        print(f"   日志中用户ID长度: {[l[0] for l in log_user_id_lengths]}")
        
        # 检查是否有不匹配的用户ID
        cursor.execute("SELECT DISTINCT user_id FROM operation_logs WHERE user_id NOT IN (SELECT id FROM users)")
        unknown_users = cursor.fetchall()
        if unknown_users:
            print(f"   发现未知用户ID: {[u[0] for u in unknown_users]}")
        else:
            print("   所有日志中的用户ID都存在于users表中")
            
    except Exception as e:
        print(f"\n检查数据库时出错: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    check_db_structure()