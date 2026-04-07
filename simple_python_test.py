print("Python 启动测试")
print("=" * 50)

import sys
print(f"Python 版本: {sys.version}")
print(f"Python 路径: {sys.executable}")
print()

import os
print(f"当前目录: {os.getcwd()}")
print()

print("测试导入 Flask...")
try:
    from flask import Flask
    print("✅ Flask 导入成功")
    print(f"Flask 版本: {Flask.__version__}")
except Exception as e:
    print(f"❌ Flask 导入失败: {e}")

print()
print("测试完成！")
