#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小Flask应用测试
用于验证Flask基本功能是否正常
"""

from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return '<h1>✅ 网站运行正常！</h1>'

if __name__ == '__main__':
    print("启动最小Flask应用...")
    print("访问地址: http://localhost:9876")
    app.run(host='0.0.0.0', port=9876, debug=True)