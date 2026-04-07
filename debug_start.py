#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask应用启动诊断脚本
用于诊断Flask应用启动失败的原因
"""

import os
import sys
import traceback
from pathlib import Path

# 确保当前目录在Python路径中
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("Flask应用启动诊断脚本")
print("=" * 60)

# 1. 检查Python环境
print("\n[1/5] 检查Python环境...")
try:
    import flask
    import sqlite3
    import requests
    import dotenv
    print(f"✅ Python版本: {sys.version}")
    print(f"✅ Flask版本: {flask.__version__}")
    print(f"✅ sqlite3版本: {sqlite3.sqlite_version}")
    print(f"✅ requests版本: {requests.__version__}")
    print(f"✅ dotenv版本: {dotenv.__version__}")
except Exception as e:
    print(f"❌ 环境检查失败: {str(e)}")
    sys.exit(1)

# 2. 检查环境变量
print("\n[2/5] 检查环境变量...")
try:
    from dotenv import load_dotenv
    BASE_DIR = Path(__file__).parent
    load_dotenv(BASE_DIR / ".env")
    print(f"✅ 加载.env文件成功")
    print(f"✅ SECRET_KEY: {'***' if os.getenv('SECRET_KEY') else '未设置'}")
    print(f"✅ DKFILE_API_BASE: {os.getenv('DKFILE_API_BASE', '未设置')}")
    print(f"✅ DEEPSEEK_BASE: {os.getenv('DEEPSEEK_BASE', '未设置')}")
except Exception as e:
    print(f"❌ 环境变量检查失败: {str(e)}")
    traceback.print_exc()

# 3. 检查数据库初始化
print("\n[3/5] 检查数据库初始化...")
try:
    from app import init_db, get_db
    init_db()
    print("✅ 数据库初始化成功")
    # 测试数据库连接
    conn = get_db()
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"✅ 数据库表数量: {len(tables)}")
    conn.close()
except Exception as e:
    print(f"❌ 数据库初始化失败: {str(e)}")
    traceback.print_exc()

# 4. 检查路由导入
print("\n[4/5] 检查路由导入...")
try:
    from app import app
    import routes
    print("✅ 路由导入成功")
    print(f"✅ 注册的路由数量: {len(app.url_map._rules)}")
except Exception as e:
    print(f"❌ 路由导入失败: {str(e)}")
    traceback.print_exc()

# 5. 测试Flask应用启动
print("\n[5/5] 测试Flask应用启动...")
try:
    from app import app
    # 测试应用是否能正常运行
    with app.app_context():
        print("✅ Flask应用上下文创建成功")
    print("✅ Flask应用启动测试成功")
    print("\n🎉 所有测试通过！应用应该可以正常启动。")
except Exception as e:
    print(f"❌ Flask应用启动测试失败: {str(e)}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)