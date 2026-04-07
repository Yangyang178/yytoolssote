import sys
import os

os.chdir(r'D:\Trae\接口文件')
sys.path.insert(0, r'D:\Trae\接口文件\venv\Lib\site-packages')
sys.path.insert(0, r'D:\Trae\接口文件')

print("正在启动网站...")
print("=" * 60)

try:
    import app
    print("✓ 模块加载成功")
    print("✓ 正在启动服务器...")
    print()
    print("访问地址: http://localhost:9876")
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    print()
    
    if __name__ == "__main__":
        app.app.run(
            debug=True,
            host='0.0.0.0',
            port=9876,
            use_reloader=False
        )
        
except Exception as e:
    print(f"❌ 启动失败: {e}")
    import traceback
    traceback.print_exc()
    input("\n按回车键退出...")
