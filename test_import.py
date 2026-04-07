import sys
import os

os.chdir(r'D:\Trae\接口文件')
sys.path.insert(0, r'D:\Trae\接口文件')

print("开始导入模块...")

try:
    print("1. 导入 flask...")
    from flask import Flask
    print("   ✓ Flask 导入成功")
    
    print("2. 导入其他依赖...")
    import sqlite3
    import json
    import uuid
    import hashlib
    import smtplib
    import random
    import time
    import re
    from datetime import datetime, timedelta
    from pathlib import Path
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import requests
    from werkzeug.security import generate_password_hash, check_password_hash
    from dotenv import load_dotenv
    print("   ✓ 所有依赖导入成功")
    
    print("3. 加载 .env 文件...")
    BASE_DIR = Path(r'D:\Trae\接口文件')
    load_dotenv(BASE_DIR / ".env")
    print("   ✓ .env 文件加载成功")
    
    print("4. 创建 Flask 应用...")
    app = Flask(__name__)
    print("   ✓ Flask 应用创建成功")
    
    print("\n" + "="*50)
    print("✅ 所有检查通过！可以启动网站")
    print("="*50)
    
except Exception as e:
    print(f"\n❌ 错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
