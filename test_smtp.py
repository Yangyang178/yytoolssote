#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMTP邮件发送测试脚本
用于验证SMTP配置是否正确
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv

# 设置控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 加载环境变量
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

print("=" * 60)
print("SMTP邮件发送测试")
print("=" * 60)

# 读取配置
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")

print(f"\n配置信息：")
print(f"SMTP服务器: {SMTP_HOST}")
print(f"端口: {SMTP_PORT}")
print(f"发件邮箱: {SMTP_USERNAME}")
print(f"授权码: {'*' * len(SMTP_PASSWORD) if SMTP_PASSWORD else '未设置'}")
print(f"发件人: {SMTP_FROM}")

# 检查配置是否完整
if not all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM]):
    print("\n[错误] SMTP配置不完整！")
    print("请检查 .env 文件中的SMTP配置")
    sys.exit(1)

# 测试发送邮件
print("\n正在测试邮件发送...")
print(f"收件邮箱: {SMTP_USERNAME}")  # 发送给自己

try:
    # 创建邮件
    msg = MIMEText('这是一封SMTP配置测试邮件，如果您收到此邮件，说明SMTP配置成功！', 'plain', 'utf-8')
    msg['From'] = SMTP_FROM
    msg['To'] = SMTP_USERNAME
    msg['Subject'] = 'yytoolssite-aipro SMTP配置测试'
    
    # 尝试TLS连接
    print(f"\n尝试TLS连接...")
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
    server.ehlo()
    server.starttls()
    server.ehlo()
    print(f"[成功] TLS连接成功")
    
    # 登录
    print(f"正在登录...")
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    print(f"[成功] 登录成功")
    
    # 发送邮件
    print(f"正在发送邮件...")
    server.sendmail(SMTP_FROM, [SMTP_USERNAME], msg.as_string())
    print(f"[成功] 邮件发送成功")
    
    server.quit()
    
    print("\n" + "=" * 60)
    print("[成功] SMTP配置测试成功！")
    print("=" * 60)
    print(f"\n请检查您的邮箱 {SMTP_USERNAME} 查看测试邮件")
    print("（可能在垃圾邮件文件夹中）")
    
except smtplib.SMTPAuthenticationError as e:
    print(f"\n[错误] 登录失败：邮箱或授权码错误")
    print(f"错误详情: {str(e)}")
    print("\n请检查：")
    print("1. 邮箱地址是否正确")
    print("2. 授权码是否正确（不是邮箱密码）")
    print("3. 是否已开启SMTP服务")
    
except smtplib.SMTPException as e:
    print(f"\n[错误] SMTP错误: {str(e)}")
    
except Exception as e:
    print(f"\n[错误] 发送失败: {str(e)}")
    print("\n可能的原因：")
    print("1. 网络连接问题")
    print("2. SMTP服务器地址错误")
    print("3. 端口号错误")

print("\n" + "=" * 60)