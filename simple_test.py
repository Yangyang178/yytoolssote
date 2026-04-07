print("测试开始")
import sys
sys.stdout.flush()

print("导入 os...")
import os
sys.stdout.flush()

os.chdir(r'D:\Trae\接口文件')
print(f"工作目录: {os.getcwd()}")
sys.stdout.flush()

print("导入 flask...")
from flask import Flask
print("Flask 导入成功")
sys.stdout.flush()

print("导入 app 模块...")
import app
print("app 模块导入成功")
sys.stdout.flush()

print(f"Flask app 对象: {app.app}")
sys.stdout.flush()

print("\n启动服务器在 http://localhost:9876 ...")
sys.stdout.flush()

if __name__ == "__main__":
    app.app.run(host='0.0.0.0', port=9876, debug=True)
