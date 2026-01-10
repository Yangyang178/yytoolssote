#!/usr/bin/env python3
# 测试日志系统功能

import sys
import os
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, init_db, log_message, log_login_attempt
from flask import Flask

# 初始化数据库
init_db()
print("数据库初始化完成")

# 创建测试请求对象
class MockRequest:
    def __init__(self, remote_addr, user_agent):
        self.remote_addr = remote_addr
        self.user_agent = type('obj', (object,), {'string': user_agent})()

# 测试记录操作日志
print("\n测试记录操作日志...")
test_request = MockRequest('127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

log_message(
    log_type='operation',
    log_level='INFO',
    message='测试操作日志',
    request=test_request,
    user_id='test_user_123',
    action='test',
    target_id='test_target_456',
    target_type='test_type',
    details='这是一条测试操作日志'
)
print("操作日志记录完成")

# 测试记录错误日志
print("\n测试记录错误日志...")
log_message(
    log_type='error',
    log_level='ERROR',
    message='测试错误日志',
    request=test_request,
    user_id='test_user_123',
    action='test',
    target_type='test_type',
    details='这是一条测试错误日志'
)
print("错误日志记录完成")

# 测试记录安全日志
print("\n测试记录安全日志...")
log_message(
    log_type='security',
    log_level='WARNING',
    message='测试安全日志',
    request=test_request,
    details='这是一条测试安全日志'
)
print("安全日志记录完成")

# 测试记录登录尝试
print("\n测试记录登录尝试...")
# 测试成功登录
log_login_attempt('test@example.com', 1, test_request)
print("成功登录尝试记录完成")

# 测试失败登录
log_login_attempt('test@example.com', 0, test_request)
print("失败登录尝试记录完成")

print("\n所有测试完成！")
print("\n您可以通过以下SQL查询验证日志是否被正确记录：")
print("1. 查询所有日志：SELECT * FROM logs ORDER BY created_at DESC")
print("2. 查询登录尝试：SELECT * FROM login_attempts ORDER BY attempt_time DESC")
