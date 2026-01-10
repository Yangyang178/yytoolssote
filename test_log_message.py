#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试log_message函数是否能正确记录日志到数据库
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import log_message, get_db

# 测试用的用户ID
TEST_USER_ID = "test_user_123"

def test_log_message():
    """测试log_message函数"""
    print("开始测试log_message函数...")
    
    # 调用log_message函数记录一条日志
    log_message(
        log_type='operation',
        log_level='INFO',
        message='测试删除文件',
        user_id=TEST_USER_ID,
        action='delete',
        target_id='test_file_456',
        target_type='file',
        details='文件名: 测试文件.txt',
        request=None
    )
    
    print("\n测试查询操作日志...")
    # 连接数据库查询日志
    conn = get_db()
    try:
        # 查询所有操作日志
        all_logs = conn.execute('SELECT * FROM operation_logs ORDER BY created_at DESC').fetchall()
        print(f"总共找到 {len(all_logs)} 条日志")
        
        # 打印所有日志
        for log in all_logs:
            print(f"ID: {log['id']}, UserID: {log['user_id']}, Action: {log['action']}, Message: {log['message']}, Details: {log['details']}, Time: {log['created_at']}")
        
        # 查询特定用户的日志
        test_logs = conn.execute('SELECT * FROM operation_logs WHERE user_id = ? ORDER BY created_at DESC', (TEST_USER_ID,)).fetchall()
        print(f"\n用户 {TEST_USER_ID} 的日志: {len(test_logs)} 条")
        
        for log in test_logs:
            print(f"ID: {log['id']}, Action: {log['action']}, Message: {log['message']}, Time: {log['created_at']}")
            
    except Exception as e:
        print(f"查询日志时出错: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    test_log_message()