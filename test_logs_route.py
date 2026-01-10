#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试操作日志功能的简单路由
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, log_message, get_db
from flask import request

@app.route('/test-logs')
def test_logs():
    """测试操作日志功能"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>测试操作日志</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .test-section { margin: 20px 0; padding: 15px; border: 1px solid #ccc; border-radius: 5px; }
            button { padding: 10px 20px; margin: 5px; cursor: pointer; }
            .logs { margin-top: 20px; padding: 10px; background: #f5f5f5; border-radius: 5px; }
            .log-item { margin: 5px 0; padding: 5px; border-bottom: 1px solid #ddd; }
        </style>
    </head>
    <body>
        <h1>测试操作日志功能</h1>
        
        <div class="test-section">
            <h2>1. 记录测试日志</h2>
            <form action="/test-logs/log" method="post">
                <button type="submit" name="action" value="delete">记录删除文件日志</button>
                <button type="submit" name="action" value="upload">记录上传文件日志</button>
                <button type="submit" name="action" value="edit">记录编辑文件日志</button>
            </form>
        </div>
        
        <div class="test-section">
            <h2>2. 查看操作日志</h2>
            <form action="/test-logs/view" method="get">
                <label for="user_id">用户ID:</label>
                <input type="text" id="user_id" name="user_id" value="test_user_123" style="margin: 0 10px; padding: 5px;">
                <button type="submit">查看日志</button>
            </form>
        </div>
        
        <div id="logs" class="logs"></div>
        
        <script>
            // 提交表单后刷新页面
            document.querySelectorAll('form').forEach(form => {
                form.addEventListener('submit', function(e) {
                    e.preventDefault();
                    const formData = new FormData(this);
                    fetch(this.action, {
                        method: this.method,
                        body: formData
                    }).then(response => response.text())
                      .then(html => {
                          document.getElementById('logs').innerHTML = html;
                      });
                });
            });
        </script>
    </body>
    </html>
    '''

@app.route('/test-logs/log', methods=['POST'])
def test_log():
    """记录测试日志"""
    action = request.form.get('action', 'test')
    user_id = 'test_user_123'
    
    # 调用log_message函数
    log_message(
        log_type='operation',
        log_level='INFO',
        message=f'测试{action}文件',
        user_id=user_id,
        action=action,
        target_id=f'test_file_{action}',
        target_type='file',
        details=f'文件名: 测试文件_{action}.txt',
        request=request
    )
    
    return f'<div class="log-item">已记录{action}日志</div>'

@app.route('/test-logs/view')
def view_logs():
    """查看操作日志"""
    user_id = request.args.get('user_id', 'test_user_123')
    
    # 连接数据库查询日志
    conn = get_db()
    logs = conn.execute('SELECT * FROM operation_logs WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
    conn.close()
    
    if not logs:
        return '<div class="log-item">没有找到日志</div>'
    
    html = '<h3>操作日志列表:</h3>'
    for log in logs:
        html += f'''<div class="log-item">
            <strong>ID:</strong> {log['id']} | 
            <strong>操作:</strong> {log['action']} | 
            <strong>消息:</strong> {log['message']} | 
            <strong>详情:</strong> {log['details']} | 
            <strong>时间:</strong> {log['created_at']}
        </div>'''
    
    return html

if __name__ == '__main__':
    app.run(debug=True, port=9877)