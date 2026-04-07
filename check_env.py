import sys
import os

print("=" * 50)
print("网站环境检查")
print("=" * 50)
print(f"Python 版本: {sys.version}")
print(f"工作目录: {os.getcwd()}")
print()

try:
    import flask
    print(f"✓ Flask 版本: {flask.__version__}")
except ImportError:
    print("✗ Flask 未安装")

try:
    import requests
    print(f"✓ requests 已安装")
except ImportError:
    print("✗ requests 未安装")

try:
    from dotenv import load_dotenv
    print("✓ python-dotenv 已安装")
except ImportError:
    print("✗ python-dotenv 未安装")

print()
print("检查 .env 文件...")
if os.path.exists('.env'):
    print("✓ .env 文件存在")
else:
    print("✗ .env 文件不存在")

if os.path.exists('data'):
    print("✓ data 目录存在")
else:
    print("✗ data 目录不存在")

if os.path.exists('uploads'):
    print("✓ uploads 目录存在")
else:
    print("✗ uploads 目录不存在")

print()
print("=" * 50)
