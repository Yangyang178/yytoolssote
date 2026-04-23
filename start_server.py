#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
网站服务器启动脚本
提供可靠的启动方式，自动检测和解决常见问题
"""

import sys
import os
import socket
import subprocess
import time

# 设置编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 服务器配置
HOST = '0.0.0.0'
PORT = 9876


def check_port_available(host, port):
    """检查端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def kill_process_on_port(port):
    """终止占用端口的进程"""
    print(f"⚠️  端口 {port} 被占用，尝试终止...")
    
    if sys.platform == 'win32':
        # Windows系统
        try:
            # 使用netstat找到PID
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                encoding='gbk',
                errors='ignore'
            )
            
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    pid = line.strip().split()[-1]
                    print(f"  找到进程 PID: {pid}")
                    
                    # 终止进程
                    subprocess.run(
                        ['taskkill', '/F', '/PID', pid],
                        capture_output=True,
                        text=True,
                        encoding='gbk',
                        errors='ignore'
                    )
                    print(f"  已终止进程 {pid}")
                    time.sleep(1)
        except Exception as e:
            print(f"  ❌ 终止进程失败: {e}")
            return False
    
    return True


def check_dependencies():
    """检查必要的依赖包"""
    required_packages = ['flask']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ 缺少依赖包:")
        for pkg in missing_packages:
            print(f"  - {pkg}")
        
        # 尝试安装
        install = input("\n是否自动安装? (y/n): ").lower().strip()
        if install == 'y':
            for pkg in missing_packages:
                print(f"\n📦 安装 {pkg}...")
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', pkg],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print(f"  ✅ {pkg} 安装成功")
                else:
                    print(f"  ❌ {pkg} 安装失败: {result.stderr}")
                    return False
        else:
            return False
    
    return True


def fix_file_encoding():
    """修复Python文件的BOM编码问题"""
    print("\n🔍 检查文件编码...")
    
    bom_files = []
    for root, dirs, files in os.walk('.'):
        # 跳过虚拟环境目录
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv', '.venv']]
        
        for f in files:
            if f.endswith('.py'):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, 'rb') as file:
                        content = file.read(3)
                        if content.startswith(b'\xef\xbb\xbf'):
                            bom_files.append(filepath)
                except Exception:
                    pass
    
    if bom_files:
        print(f"  发现 {len(bom_files)} 个带BOM的文件:")
        for f in bom_files:
            print(f"    - {f}")
        
        # 自动修复
        print("\n  🔧 正在修复...")
        for filepath in bom_files:
            try:
                with open(filepath, 'rb') as f:
                    content = f.read()
                
                content = content.replace(b'\xef\xbb\xbf', b'')
                
                with open(filepath, 'wb') as f:
                    f.write(content)
                
                print(f"    ✅ 已修复: {filepath}")
            except Exception as e:
                print(f"    ❌ 修复失败: {filepath} - {e}")
    else:
        print("  ✅ 文件编码正常")


def start_server():
    """启动服务器"""
    print("=" * 60)
    print("🚀 网站服务器启动工具")
    print("=" * 60)
    
    # 1. 检查依赖
    print("\n[1/4] 检查依赖包...")
    if not check_dependencies():
        print("\n❌ 依赖检查失败，无法启动")
        input("\n按回车键退出...")
        sys.exit(1)
    print("  ✅ 依赖检查通过")
    
    # 2. 修复文件编码
    print("\n[2/4] 检查文件编码...")
    fix_file_encoding()
    
    # 3. 检查端口
    print(f"\n[3/4] 检查端口 {PORT}...")
    if not check_port_available(HOST, PORT):
        print(f"  ⚠️  端口 {PORT} 被占用")
        kill_process_on_port(PORT)
        
        if not check_port_available(HOST, PORT):
            print(f"\n❌ 端口 {PORT} 无法使用")
            input("\n按回车键退出...")
            sys.exit(1)
    print(f"  ✅ 端口 {PORT} 可用")
    
    # 4. 启动服务器
    print(f"\n[4/4] 启动服务器...")
    print("-" * 60)
    print(f"  📍 访问地址: http://127.0.0.1:{PORT}")
    print(f"  📍 局域网地址: http://{get_local_ip()}:{PORT}")
    print(f"  ⏹️  按 Ctrl+C 停止服务器")
    print("-" * 60)
    print()
    
    # 导入并运行应用
    try:
        from app import app, init_db, cleanup_old_logs, cleanup_expired_trash
        
        # 初始化数据库
        print("📊 初始化数据库...")
        init_db()
        print("  ✅ 数据库初始化完成")
        
        # 清理日志和回收站
        print("🧹 清理过期数据...")
        with app.app_context():
            cleanup_old_logs()
            cleanup_expired_trash()
        print("  ✅ 清理完成\n")
        
        # 启动Flask应用
        app.run(debug=True, host=HOST, port=PORT)
        
    except KeyboardInterrupt:
        print("\n\n✅ 服务器已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def main():
    """主函数"""
    start_server()


if __name__ == "__main__":
    main()
