# 读取routes.py文件
with open('routes.py', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 权限管理路由
permission_routes = '''

# 权限管理页面
@app.route('/permission-management')
def permission_management():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    # 检查是否为管理员
    conn = get_db()
    try:
        current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not current_user or current_user['role'] != 'admin':
            flash('无权限访问此页面')
            return redirect(url_for('user_center'))
        
        # 获取所有用户列表
        users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    finally:
        conn.close()
    
    return render_template('permission_management.html', 
                           username=session.get('username'), 
                           users=users,
                           current_user=current_user)

# 更新用户角色
@app.route('/update-user-role/<user_id>', methods=['POST'])
def update_user_role(user_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    # 检查是否为管理员
    conn = get_db()
    try:
        current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'success': False, 'message': '无权限'}), 403
        
        # 不能修改自己的角色
        if user_id == session['user_id']:
            return jsonify({'success': False, 'message': '不能修改自己的角色'}), 400
        
        # 获取新角色
        new_role = request.form.get('role')
        if new_role not in ['user', 'admin']:
            return jsonify({'success': False, 'message': '无效的角色'}), 400
        
        # 更新用户角色
        conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': '角色更新成功'})
    finally:
        conn.close()

# 删除用户
@app.route('/delete-user/<user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    # 检查是否为管理员
    conn = get_db()
    try:
        current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'success': False, 'message': '无权限'}), 403
        
        # 不能删除自己
        if user_id == session['user_id']:
            return jsonify({'success': False, 'message': '不能删除自己'}), 400
        
        # 删除用户
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': '用户删除成功'})
    finally:
        conn.close()
'''

# 将权限管理路由添加到文件末尾
with open('routes.py', 'w', encoding='utf-8') as f:
    f.write(content + permission_routes)

print("权限管理路由已成功添加到routes.py")
