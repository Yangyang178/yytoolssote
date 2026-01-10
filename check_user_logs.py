#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查特定用户的操作日志
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import get_db

def check_user_logs(user_id):
    """检查特定用户的操作日志"""
    print(f"检查用户 {user_id} 的操作日志...")
    
    # 连接数据库
    conn = get_db()
    try:
        # 查询该用户的所有日志
        logs = conn.execute('SELECT * FROM operation_logs WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
        print(f"找到 {len(logs)} 条日志")
        
        for log in logs:
            print(f"ID: {log['id']}, 操作: {log['action']}, 消息: {log['message']}, 详情: {log['details']}, 时间: {log['created_at']}")
        
        # 查询所有日志，看看是否有该用户的日志
        all_logs = conn.execute('SELECT * FROM operation_logs ORDER BY created_at DESC').fetchall()
        print(f"\n所有日志总数: {len(all_logs)}")
        
        # 统计每个用户的日志数量
        user_log_counts = conn.execute('SELECT user_id, COUNT(*) as count FROM operation_logs GROUP BY user_id').fetchall()
        print("\n每个用户的日志数量:")
        for user_log_count in user_log_counts:
            print(f"用户 {user_log_count['user_id']}: {user_log_count['count']} 条日志")
            
    except Exception as e:
        print(f"查询日志时出错: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        # 默认使用测试用户ID
        user_id = "84603e1bb00944bba4fe08ce55ab3552"
    
    check_user_logs(user_id)