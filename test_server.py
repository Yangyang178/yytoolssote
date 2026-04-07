import http.server
import socketserver
import threading
import webbrowser
import time

PORT = 9876

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>网站测试成功</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    text-align: center;
                    color: white;
                    padding: 40px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 20px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                }
                h1 { font-size: 48px; margin-bottom: 20px; }
                p { font-size: 18px; opacity: 0.9; }
                .success { color: #4ade80; font-size: 64px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>服务器运行成功！</h1>
                <p>如果你能看到这个页面，说明 Python Web 服务器已经成功启动。</p>
                <p>端口: ''' + str(PORT) + ''' | 时间: ''' + time.strftime('%Y-%m-%d %H:%M:%S') + '''</p>
                <p style="margin-top: 30px; font-size: 14px;">现在可以关闭此窗口，然后启动完整的 Flask 网站。</p>
            </div>
        </body>
        </html>
        '''
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] %s - %s" % (self.client_address[0], format%args))

print("=" * 60)
print("🚀 简易 HTTP 服务器测试")
print("=" * 60)
print(f"📍 启动地址: http://localhost:{PORT}")
print(f"📂 工作目录: http://localhost:{PORT}/static/")
print("⏹️  按 Ctrl+C 停止服务")
print("=" * 60)
print()

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"✅ 服务器已启动！正在监听端口 {PORT}")
    print()
    print("💡 提示：浏览器应该会自动打开...")
    print("   如果没有自动打开，请手动访问上面的地址")
    print()
    
    threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n⏹️  服务器已停止")
