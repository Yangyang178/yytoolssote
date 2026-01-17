# 路由定义文件
# 基于模板文件和现有功能重构路由

# 导入必要的模块和函数
from flask import request, render_template, redirect, url_for, flash, send_from_directory, jsonify, session
from app import app, get_db, get_all_files, get_access_logs, generate_verification_code, send_verification_email, save_verification_code, verify_code, log_message, log_login_attempt, log_access, page_error_response, api_response
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import uuid
import sqlite3
from pathlib import Path


# 登录/注册页面
@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        action = request.form.get('action')
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        code = request.form.get('code')
        
        if action == 'register':
            # 注册逻辑
            if not all([email, username, password, code]):
                flash('请填写所有必填项')
                return redirect(url_for('auth'))
            
            if not verify_code(email, code, 'register'):
                flash('验证码无效或已过期')
                return redirect(url_for('auth'))
            
            conn = get_db()
            try:
                # 检查邮箱是否已存在
                existing = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                if existing:
                    flash('该邮箱已被注册')
                    return redirect(url_for('auth'))
                
                # 创建新用户
                user_id = str(uuid.uuid4())
                hashed_password = generate_password_hash(password)
                conn.execute('INSERT INTO users (id, email, username, password) VALUES (?, ?, ?, ?)', 
                           (user_id, email, username, hashed_password))
                conn.commit()
                
                # 登录用户
                session['user_id'] = user_id
                session['username'] = username
                session['email'] = email
                
                # 记录操作日志
                log_message(
                    log_type='operation',
                    log_level='INFO',
                    message='用户注册成功',
                    user_id=user_id,
                    action='register',
                    request=request
                )
                
                flash('注册成功')
                return redirect(url_for('index'))
            except Exception as e:
                conn.rollback()
                flash(f'注册失败: {str(e)}')
                return redirect(url_for('auth'))
            finally:
                conn.close()
        
        elif action == 'login':
            # 登录逻辑
            if not all([email, password]):
                flash('请填写邮箱和密码')
                return redirect(url_for('auth'))
            
            conn = get_db()
            try:
                user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                
                if not user:
                    log_login_attempt(email, 0, request)
                    flash('邮箱或密码错误')
                    return redirect(url_for('auth'))
                
                if not check_password_hash(user['password'], password):
                    log_login_attempt(email, 0, request)
                    flash('邮箱或密码错误')
                    return redirect(url_for('auth'))
                
                # 登录成功
                log_login_attempt(email, 1, request)
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']
                
                # 记录操作日志
                log_message(
                    log_type='operation',
                    log_level='INFO',
                    message='用户登录成功',
                    user_id=user['id'],
                    action='login',
                    request=request
                )
                
                flash('登录成功')
                return redirect(url_for('index'))
            except Exception as e:
                flash(f'登录失败: {str(e)}')
                return redirect(url_for('auth'))
            finally:
                conn.close()
        
        elif action == 'login_with_code':
            # 验证码登录逻辑
            print(f"DEBUG: 进入login_with_code，email: {email}, code: {code}")
            
            # 检查必填项
            terms = request.form.get('terms')
            print(f"DEBUG: terms: {terms}")
            
            if not all([email, code]):
                print(f"DEBUG: 邮箱或验证码为空")
                flash('请填写邮箱和验证码')
                return redirect(url_for('auth'))
            
            if not terms:
                print(f"DEBUG: 未同意隐私政策和服务条款")
                flash('请同意隐私政策和服务条款')
                return redirect(url_for('auth'))
            
            # 验证验证码 - 使用'login'作为purpose
            print(f"DEBUG: 开始验证验证码，email: {email}, code: {code}, purpose: login")
            if not verify_code(email, code, 'login'):
                print(f"DEBUG: 验证码验证失败")
                flash('验证码无效或已过期')
                return redirect(url_for('auth'))
            
            print(f"DEBUG: 验证码验证成功")
            conn = get_db()
            try:
                user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                
                if not user:
                    print(f"DEBUG: 用户不存在")
                    log_login_attempt(email, 0, request)
                    flash('该邮箱尚未注册')
                    return redirect(url_for('auth'))
                
                print(f"DEBUG: 用户存在，id: {user['id']}")
                # 登录成功
                log_login_attempt(email, 1, request)
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']
                
                print(f"DEBUG: Session设置成功，user_id: {session['user_id']}")
                # 记录操作日志
                log_message(
                    log_type='operation',
                    log_level='INFO',
                    message='用户验证码登录成功',
                    user_id=user['id'],
                    action='login_with_code',
                    request=request
                )
                
                flash('登录成功')
                print(f"DEBUG: 准备跳转到首页")
                return redirect(url_for('index'))
            except Exception as e:
                print(f"DEBUG: 登录异常: {str(e)}")
                flash(f'登录失败: {str(e)}')
                return redirect(url_for('auth'))
            finally:
                conn.close()
        
        elif action == 'send_code':
            # 发送验证码
            if not email:
                return api_response(success=False, message='请输入邮箱地址', code=400)
            
            conn = get_db()
            try:
                # 获取当前模式和目的
                mode = request.args.get('mode', 'login')
                # 根据模式设置验证码用途
                purpose = 'register' if mode == 'register' else 'login'
                
                # 检查邮箱是否已被使用（仅针对注册场景）
                login_method = request.form.get('login_method', '')
                existing = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                
                # 只有在注册场景下才检查邮箱是否已存在
                if login_method != 'password' and mode == 'register' and existing:
                    return api_response(success=False, message='该邮箱已被使用', code=400)
                
                # 生成验证码
                code = generate_verification_code()
                # 先保存验证码到数据库
                save_verification_code(email, code, purpose)
                # 异步发送验证码邮件
                import threading
                email_thread = threading.Thread(target=send_verification_email, args=(email, code, purpose))
                email_thread.daemon = True
                email_thread.start()
                
                return api_response(success=True, message='验证码已发送')
            except Exception as e:
                return api_response(success=False, message=f'发送验证码失败: {str(e)}', code=500)
            finally:
                conn.close()
    
    # GET请求时，获取URL参数
    mode = request.args.get('mode', 'login')
    login_method = request.args.get('login_method', 'password')
    page_title = '注册账号' if mode == 'register' else '登录账号'
    
    return render_template('auth.html', 
                           username=session.get('username'),
                           mode=mode,
                           login_method=login_method,
                           page_title=page_title)

# 用户中心
@app.route('/user-center')
def user_center():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    # 获取用户信息和相关数据
    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not user:
            # 用户不存在，清除session并跳转登录
            session.clear()
            return redirect(url_for('auth'))
        
        # 获取用户文件（带分类和标签）
        files = get_all_files(session['user_id'])
        
        # 统计文件夹数量
        folder_count = conn.execute('SELECT COUNT(*) FROM folders WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
        
        # 统计收藏数量
        favorite_count = conn.execute('SELECT COUNT(*) FROM favorites WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
        
        # 获取收藏文件（只包括不在项目文件夹中的文件）
        favorite_files = []
        favorite_files_raw = conn.execute('''
            SELECT f.* FROM files f
            JOIN favorites fav ON f.id = fav.file_id
            WHERE fav.user_id = ? AND (f.folder_id IS NULL OR f.folder_id = "")
            ORDER BY fav.created_at DESC
        ''', (session['user_id'],)).fetchall()
        for file in favorite_files_raw:
            # 使用get_all_files函数获取完整的文件信息，包括分类、标签、点赞数和收藏数
            file_dict = next((f for f in files if f['id'] == file['id']), dict(file))
            # 确保dkfile字段是字典类型
            if 'dkfile' in file_dict and file_dict['dkfile']:
                if isinstance(file_dict['dkfile'], str):
                    try:
                        file_dict['dkfile'] = json.loads(file_dict['dkfile'])
                    except json.JSONDecodeError:
                        file_dict['dkfile'] = {}
            else:
                file_dict['dkfile'] = {}
            favorite_files.append(file_dict)
        
        # 获取操作日志
        operation_logs = conn.execute('''
            SELECT * FROM operation_logs 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 50
        ''', (session['user_id'],)).fetchall()
        
        # 获取访问日志 - 通过JOIN files表获取文件名，基于access_logs中的user_id
        access_logs_raw = conn.execute('''
            SELECT al.*, f.filename 
            FROM access_logs al 
            JOIN files f ON al.file_id = f.id 
            WHERE al.user_id = ? 
            ORDER BY al.access_time DESC 
            LIMIT 50
        ''', (session['user_id'],)).fetchall()
        
        # 转换访问时间为本地时间
        access_logs = []
        from datetime import datetime, timedelta
        for log in access_logs_raw:
            log_dict = dict(log)
            if log_dict.get('access_time'):
                try:
                    # 解析ISO格式的时间字符串
                    utc_dt = datetime.fromisoformat(log_dict['access_time'])
                    # 转换为东八区时间
                    local_dt = utc_dt + timedelta(hours=8)
                    log_dict['access_time'] = local_dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    # 如果解析失败，保持原格式
                    pass
            access_logs.append(log_dict)
    finally:
        conn.close()
    
    return render_template('user_center.html', 
                           username=session.get('username'), 
                           user=user, 
                           files=files,
                           folder_count=folder_count,
                           favorite_count=favorite_count,
                           favorite_files=favorite_files,
                           operation_logs=operation_logs,
                           access_logs=access_logs)

# 更新用户资料
@app.route('/update-profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    user_id = session['user_id']
    username = request.form.get('username')
    avatar = request.files.get('avatar')
    remove_avatar = request.form.get('remove_avatar')
    
    if not username:
        flash('用户名不能为空')
        return redirect(url_for('user_center'))
    
    conn = get_db()
    try:
        # 确保avatars目录存在
        avatars_dir = os.path.join(app.config['STATIC_FOLDER'], 'avatars') if 'STATIC_FOLDER' in app.config else os.path.join(app.static_folder, 'avatars')
        os.makedirs(avatars_dir, exist_ok=True)
        
        avatar_filename = None
        
        # 处理头像
        if remove_avatar == '1':
            # 移除头像
            conn.execute('UPDATE users SET avatar = NULL WHERE id = ?', (user_id,))
        elif avatar and avatar.filename != '':
            # 上传新头像
            ext = os.path.splitext(avatar.filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.gif']:
                flash('只支持JPG、PNG和GIF格式的头像')
                return redirect(url_for('user_center'))
            
            # 生成唯一文件名
            avatar_filename = f"{user_id}{ext}"
            avatar_path = os.path.join(avatars_dir, avatar_filename)
            avatar.save(avatar_path)
            
            # 更新数据库
            conn.execute('UPDATE users SET avatar = ? WHERE id = ?', (avatar_filename, user_id))
        
        # 更新用户名
        conn.execute('UPDATE users SET username = ? WHERE id = ?', (username, user_id))
        conn.commit()
        
        # 更新session中的用户名
        session['username'] = username
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='更新用户资料',
            user_id=user_id,
            action='edit',
            target_id=user_id,
            target_type='user',
            details=f'用户名: {username}',
            request=request
        )
        
        flash('资料更新成功')
    except Exception as e:
        conn.rollback()
        flash(f'更新失败: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('user_center'))

# 退出登录
@app.route('/logout')
def logout():
    # 记录操作日志
    if 'user_id' in session:
        log_message(
            log_type='operation',
            log_level='INFO',
            message='用户退出登录',
            user_id=session['user_id'],
            action='logout',
            request=request
        )
    
    session.clear()
    flash('已退出登录')
    return redirect(url_for('index'))

# 我的反馈页面
@app.route('/my-feedback')
def my_feedback():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        feedbacks = conn.execute('SELECT * FROM feedbacks WHERE user_id = ? ORDER BY created_at DESC', 
                                (session['user_id'],)).fetchall()
        return render_template('my_feedback.html', username=session.get('username'), feedbacks=feedbacks)
    finally:
        conn.close()

# 新反馈页面
@app.route('/new-feedback', methods=['GET', 'POST'])
def new_feedback():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        feedback_type = request.form.get('feedback_type', '问题反馈')
        content = request.form.get('content')
        
        if not all([title, content]):
            flash('请填写标题和内容')
            return redirect(url_for('new_feedback'))
        
        conn = get_db()
        try:
            feedback_id = str(uuid.uuid4())
            conn.execute('''INSERT INTO feedbacks (id, user_id, title, feedback_type, content, status) 
                           VALUES (?, ?, ?, ?, ?, 'pending')''', 
                       (feedback_id, session['user_id'], title, feedback_type, content))
            conn.commit()
            
            # 记录操作日志
            log_message(
                log_type='operation',
                log_level='INFO',
                message='提交反馈',
                user_id=session['user_id'],
                action='create',
                target_id=feedback_id,
                target_type='feedback',
                details=f'标题: {title}',
                request=request
            )
            
            flash('反馈提交成功')
            return redirect(url_for('my_feedback'))
        except Exception as e:
            conn.rollback()
            flash(f'提交失败: {str(e)}')
            return redirect(url_for('new_feedback'))
        finally:
            conn.close()
    
    return render_template('new_feedback.html', username=session.get('username'))

# 删除反馈API
@app.route('/api/feedback/<feedback_id>/delete', methods=['POST'])
def delete_feedback(feedback_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        # 检查反馈是否存在且属于当前用户
        feedback = conn.execute('SELECT * FROM feedbacks WHERE id = ? AND user_id = ?', 
                              (feedback_id, session['user_id'])).fetchone()
        
        if not feedback:
            return api_response(success=False, message='反馈不存在或无权限', code=404)
        
        # 删除反馈
        conn.execute('DELETE FROM feedbacks WHERE id = ?', (feedback_id,))
        conn.commit()
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='删除反馈',
            user_id=session['user_id'],
            action='delete',
            target_id=feedback_id,
            target_type='feedback',
            details=f'标题: {feedback["title"]}',
            request=request
        )
        
        return api_response(success=True, message='反馈删除成功')
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'删除失败: {str(e)}', code=500)
    finally:
        conn.close()

# 简单反馈页面
@app.route('/feedback')
def feedback_simple():
    return render_template('feedback_simple.html', username=session.get('username'))

# 上传页面
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        # 处理文件上传逻辑
        files = request.files.getlist('file')
        project_name = request.form.get('project_name')
        project_desc = request.form.get('project_desc')
        
        if not files or files[0].filename == '':
            flash('请选择文件')
            return redirect(url_for('upload'))
        
        # 处理文件上传（简化版，实际应包含安全检查）
        conn = get_db()
        try:
            for file in files:
                if file.filename == '':
                    continue
                
                # 生成唯一文件名
                file_id = str(uuid.uuid4())
                ext = os.path.splitext(file.filename)[1]
                stored_name = f"{file_id}{ext}"
                
                # 保存文件
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
                file.save(file_path)
                
                # 计算文件大小
                file_size = os.path.getsize(file_path)
                
                # 插入数据库，包含created_at字段
                conn.execute('''INSERT INTO files (id, user_id, filename, stored_name, path, size, project_name, project_desc, created_at) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                           (file_id, session['user_id'], file.filename, stored_name, file_path, file_size, 
                            project_name, project_desc))
            
            conn.commit()
            flash('文件上传成功')
            return redirect(url_for('index'))
        except Exception as e:
            conn.rollback()
            flash(f'上传失败: {str(e)}')
            return redirect(url_for('upload'))
        finally:
            conn.close()
    
    return render_template('upload_page.html', username=session.get('username'))

# 文件详情页面
@app.route('/detail/<file_id>')
def detail(file_id):
    conn = get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
        if not file:
            return page_error_response('index', '文件不存在', 404)
        
        return render_template('detail.html', username=session.get('username'), file=file)
    finally:
        conn.close()

# 账户设置页面
@app.route('/account-settings')
def account_settings():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        # 获取当前用户信息
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        return render_template('account_settings.html', username=session.get('username'), user=user)
    finally:
        conn.close()

# 修改密码
@app.route('/change-password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        flash('请填写所有必填字段')
        return redirect(url_for('account_settings'))
    
    if new_password != confirm_password:
        flash('新密码和确认密码不一致')
        return redirect(url_for('account_settings'))
    
    conn = get_db()
    try:
        # 获取当前用户信息
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not user:
            flash('用户不存在')
            return redirect(url_for('account_settings'))
        
        # 验证当前密码
        if not check_password_hash(user['password'], current_password):
            flash('当前密码错误')
            return redirect(url_for('account_settings'))
        
        # 更新密码
        hashed_password = generate_password_hash(new_password)
        conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, session['user_id']))
        conn.commit()
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='修改密码',
            user_id=session['user_id'],
            action='update',
            target_id=session['user_id'],
            target_type='user',
            details='用户修改了密码',
            request=request
        )
        
        flash('密码修改成功')
    except Exception as e:
        conn.rollback()
        flash(f'修改失败: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('account_settings'))

# 修改邮箱
@app.route('/change-email', methods=['POST'])
def change_email():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    new_email = request.form.get('new_email')
    code = request.form.get('code')
    
    if not all([new_email, code]):
        flash('请填写所有必填字段')
        return redirect(url_for('account_settings'))
    
    conn = get_db()
    try:
        # 验证验证码
        if not verify_code(new_email, code, 'email_change'):
            flash('验证码无效或已过期')
            return redirect(url_for('account_settings'))
        
        # 检查邮箱是否已被使用
        existing = conn.execute('SELECT * FROM users WHERE email = ?', (new_email,)).fetchone()
        if existing:
            flash('该邮箱已被使用')
            return redirect(url_for('account_settings'))
        
        # 更新邮箱
        conn.execute('UPDATE users SET email = ? WHERE id = ?', (new_email, session['user_id']))
        conn.commit()
        
        # 更新session中的邮箱
        session['email'] = new_email
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='修改邮箱',
            user_id=session['user_id'],
            action='update',
            target_id=session['user_id'],
            target_type='user',
            details=f'邮箱从 {session.get("email")} 更改为 {new_email}',
            request=request
        )
        
        flash('邮箱修改成功')
    except Exception as e:
        conn.rollback()
        flash(f'修改失败: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('account_settings'))

# 发送邮箱验证码
@app.route('/send-email-code', methods=['POST'])
def send_email_code():
    try:
        data = request.get_json()
        new_email = data.get('new_email')
        
        if not new_email:
            return api_response(success=False, message='请输入邮箱地址', code=400)
        
        # 检查邮箱是否已被使用
        conn = get_db()
        existing = conn.execute('SELECT * FROM users WHERE email = ?', (new_email,)).fetchone()
        conn.close()
        
        if existing:
            return api_response(success=False, message='该邮箱已被使用', code=400)
        
        # 生成并发送验证码
        code = generate_verification_code()
        send_verification_email(new_email, code, 'email_change')
        save_verification_code(new_email, code, 'email_change')
        
        return api_response(success=True, message='验证码已发送', data={'code': code})
    except Exception as e:
        return api_response(success=False, message=f'发送验证码失败: {str(e)}', code=500)

# AI页面
@app.route('/ai')
def ai():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    return render_template('ai_page.html', username=session.get('username'))

# 博客页面
@app.route('/blog')
def blog_page():
    # 示例技术文章数据
    posts = [
        {
            "id": "1",
            "title": "HTML5 新特性详解",
            "date": "2026-01-10",
            "category": "前端开发",
            "summary": "HTML5 带来了许多令人兴奋的新特性，包括语义化标签、Canvas 绘图、本地存储等。本文将详细介绍这些新特性及其应用场景。"
        },
        {
            "id": "2",
            "title": "Python 装饰器的高级应用",
            "date": "2026-01-09",
            "category": "后端开发",
            "summary": "Python 装饰器是一种强大的编程工具，可以在不修改原函数代码的情况下，为函数添加额外的功能。本文将介绍装饰器的高级应用技巧。"
        },
        {
            "id": "3",
            "title": "Flask 框架入门指南",
            "date": "2026-01-08",
            "category": "后端开发",
            "summary": "Flask 是一个轻量级的 Python Web 框架，易于学习和使用。本文将带你从零开始学习 Flask，构建你的第一个 Web 应用。"
        },
        {
            "id": "4",
            "title": "JavaScript 异步编程",
            "date": "2026-01-07",
            "category": "前端开发",
            "summary": "异步编程是 JavaScript 的核心特性之一，本文将详细介绍回调函数、Promise、async/await 等异步编程模式，帮助你更好地理解和应用异步编程。"
        },
        {
            "id": "5",
            "title": "CSS Grid 布局完全指南",
            "date": "2026-01-06",
            "category": "前端开发",
            "summary": "CSS Grid 是一种强大的二维布局系统，可以轻松实现复杂的网页布局。本文将带你全面了解 CSS Grid 的各种属性和用法。"
        },
        {
            "id": "6",
            "title": "Git 版本控制最佳实践",
            "date": "2026-01-05",
            "category": "开发工具",
            "summary": "Git 是目前最流行的版本控制系统，掌握 Git 的最佳实践对于团队协作和项目管理至关重要。本文将分享一些 Git 使用的最佳实践和技巧。"
        }
    ]
    return render_template('blog_page.html', username=session.get('username'), posts=posts)

# 博客详情页面
@app.route('/blog/<blog_id>')
def blog_detail(blog_id):
    # 完整的文章数据
    posts = {
        "1": {
            "id": "1",
            "title": "HTML5 新特性详解",
            "subtitle": "探索HTML5带来的革命性变化",
            "date": "2026-01-10",
            "category": "前端开发",
            "content": "<h3>1. HTML5 概述</h3><p>HTML5 是 HTML 的第五个主要版本，它带来了许多革命性的变化，使 Web 开发更加丰富和强大。</p><h3>2. 语义化标签</h3><p>HTML5 引入了一系列语义化标签，如 &lt;header&gt;、&lt;nav&gt;、&lt;main&gt;、&lt;footer&gt; 等，使网页结构更加清晰，有利于搜索引擎优化和无障碍访问。</p><h3>3. Canvas 绘图</h3><p>Canvas API 允许开发者使用 JavaScript 在网页上绘制图形、动画和游戏，为 Web 应用带来了更丰富的视觉体验。</p><h3>4. 本地存储</h3><p>HTML5 提供了 localStorage 和 sessionStorage 等本地存储方案，允许网页在用户浏览器中存储数据，减少了对服务器的请求，提高了应用性能。</p><h3>5. 多媒体支持</h3><p>HTML5 原生支持音频和视频播放，无需依赖第三方插件，如 Flash，使网页多媒体内容更加易于实现和访问。</p><h3>6. 响应式设计</h3><p>HTML5 与 CSS3 配合，支持响应式设计，使网页能够自适应不同屏幕尺寸和设备，提供更好的移动端体验。</p><h3>7. 总结</h3><p>HTML5 为 Web 开发带来了许多强大的新特性，使开发者能够创建更加丰富、交互性更强的 Web 应用。掌握 HTML5 对于现代 Web 开发者来说至关重要。"
        },
        "2": {
            "id": "2",
            "title": "Python 装饰器的高级应用",
            "subtitle": "深入理解和应用 Python 装饰器",
            "date": "2026-01-09",
            "category": "后端开发",
            "content": "<h3>1. Python 装饰器简介</h3><p>装饰器是 Python 中一种强大的编程工具，它允许我们在不修改原函数代码的情况下，为函数添加额外的功能。装饰器本质上是一个函数，它接受一个函数作为参数，并返回一个新的函数。</p><h3>2. 装饰器的基本语法</h3><p>装饰器使用 @ 符号来应用，放在函数定义的上方。例如：</p><pre><code>@decorator\ndef function():\n    pass</code></pre><h3>3. 高级装饰器技巧</h3><h4>3.1 带参数的装饰器</h4><p>装饰器可以接受参数，这允许我们创建更加灵活和可配置的装饰器。</p><h4>3.2 类装饰器</h4><p>除了函数装饰器，Python 还支持类装饰器，使用类来实现装饰器功能。</p><h4>3.3 装饰器链</h4><p>可以将多个装饰器应用到同一个函数上，形成装饰器链，函数会依次经过每个装饰器的处理。</p><h3>4. 装饰器的应用场景</h3><ul><li>日志记录</li><li>性能监控</li><li>权限验证</li><li>缓存</li><li>事务处理</li></ul><h3>5. 总结</h3><p>Python 装饰器是一种强大的编程工具，掌握装饰器的高级应用技巧可以让我们的代码更加简洁、优雅和可维护。通过合理使用装饰器，我们可以实现代码的解耦和复用，提高开发效率。"
        },
        "3": {
            "id": "3",
            "title": "Flask 框架入门指南",
            "subtitle": "从零开始学习 Flask 开发",
            "date": "2026-01-08",
            "category": "后端开发",
            "content": "<h3>1. Flask 简介</h3><p>Flask 是一个轻量级的 Python Web 框架，它基于 Werkzeug WSGI 工具箱和 Jinja2 模板引擎。Flask 被设计为简单易用，同时保持足够的灵活性，允许开发者根据需要扩展功能。</p><h3>2. Flask 的特点</h3><ul><li>轻量级：Flask 核心非常小，只包含必要的功能，其他功能可以通过扩展添加。</li><li>易于学习：Flask 的 API 设计简洁明了，学习曲线平缓。</li><li>灵活：Flask 允许开发者根据需要选择扩展，而不是强制使用特定的库。</li><li>强大：虽然 Flask 核心简单，但通过扩展可以实现复杂的功能，如数据库集成、用户认证、API 开发等。</li></ul><h3>3. 第一个 Flask 应用</h3><p>以下是一个简单的 Flask 应用示例：</p><pre><code>from flask import Flask\n\napp = Flask(__name__)\n\n@app.route('/')\ndef hello():\n    return 'Hello, Flask!'\n\nif __name__ == '__main__':\n    app.run(debug=True)</code></pre><h3>4. 总结</h3><p>Flask 是一个强大而灵活的 Python Web 框架，非常适合构建各种规模的 Web 应用。通过学习 Flask，你可以掌握现代 Web 开发的核心概念和技术，为进一步学习其他框架和技术打下坚实的基础。"
        },
        "4": {
            "id": "4",
            "title": "JavaScript 异步编程",
            "subtitle": "深入理解 JavaScript 异步编程模型",
            "date": "2026-01-07",
            "category": "前端开发",
            "content": "<h3>1. JavaScript 异步编程简介</h3><p>JavaScript 是一门单线程语言，这意味着它一次只能执行一个任务。为了处理耗时操作（如网络请求、文件 I/O 等），JavaScript 采用了异步编程模型，允许在等待耗时操作完成的同时继续执行其他任务。</p><h3>2. 异步编程的发展历程</h3><h4>2.1 回调函数</h4><p>回调函数是 JavaScript 中最早的异步编程模式，它允许我们在异步操作完成后执行特定的代码。</p><h4>2.2 Promise</h4><p>Promise 是 ES6 引入的异步编程解决方案，它提供了更加优雅和可控的方式来处理异步操作。</p><h4>2.3 async/await</h4><p>async/await 是 ES2017 引入的语法糖，它基于 Promise，提供了更加直观和同步化的异步编程体验。</p><h3>3. 总结</h3><p>异步编程是 JavaScript 开发中的核心概念，掌握不同的异步编程模式对于构建高效、可靠的 Web 应用至关重要。通过理解和应用回调函数、Promise 和 async/await，你可以编写出更加优雅、可维护的异步代码。"
        },
        "5": {
            "id": "5",
            "title": "CSS Grid 布局完全指南",
            "subtitle": "掌握 CSS Grid 实现复杂网页布局",
            "date": "2026-01-06",
            "category": "前端开发",
            "content": "<h3>1. CSS Grid 简介</h3><p>CSS Grid 是 CSS 中一种强大的二维布局系统，它允许我们同时在行和列两个维度上布局元素，轻松实现复杂的网页布局。CSS Grid 是 CSS 布局的未来，它提供了比传统布局方法（如浮动、定位等）更加直观和强大的布局能力。</p><h3>2. CSS Grid 的核心概念</h3><h4>2.1 网格容器和网格项</h4><p>使用 display: grid 或 display: inline-grid 将元素定义为网格容器，网格容器的直接子元素将成为网格项。</p><h4>2.2 网格线</h4><p>网格线是网格的分隔线，包括水平网格线和垂直网格线，用于定位网格项。</p><h4>2.3 网格轨道</h4><p>网格轨道是两条相邻网格线之间的空间，包括行轨道和列轨道。</p><h4>2.4 网格单元格</h4><p>网格单元格是行轨道和列轨道的交叉区域，是网格布局中的最小单位。</p><h4>2.5 网格区域</h4><p>网格区域是由多条网格线围成的矩形区域，可以包含一个或多个网格单元格。</p><h3>3. 总结</h3><p>CSS Grid 是一种强大的二维布局系统，它彻底改变了我们构建网页布局的方式。通过掌握 CSS Grid 的核心概念和主要属性，你可以轻松实现各种复杂的网页布局，创建更加灵活、响应式的网页设计。CSS Grid 是现代 Web 开发中不可或缺的技能，值得每个前端开发者深入学习和掌握。"
        },
        "6": {
            "id": "6",
            "title": "Git 版本控制最佳实践",
            "subtitle": "提高团队协作效率的 Git 使用技巧",
            "date": "2026-01-05",
            "category": "开发工具",
            "content": "<h3>1. Git 简介</h3><p>Git 是目前最流行的分布式版本控制系统，它允许开发者跟踪文件的变化，协作开发，管理不同版本的代码。Git 由 Linus Torvalds 于 2005 年创建，最初用于 Linux 内核开发，现在已成为软件开发行业的标准版本控制工具。</p><h3>2. Git 的核心概念</h3><h4>2.1 仓库（Repository）</h4><p>仓库是 Git 存储代码和历史记录的地方，包括本地仓库和远程仓库。</p><h4>2.2 提交（Commit）</h4><p>提交是 Git 中的基本操作，用于将文件的变化保存到仓库中，每个提交都有一个唯一的哈希值。</p><h4>2.3 分支（Branch）</h4><p>分支是 Git 中用于并行开发的机制，允许开发者在不影响主分支的情况下进行功能开发或 bug 修复。</p><h4>2.4 合并（Merge）</h4><p>合并是将一个分支的更改集成到另一个分支的操作。</p><h4>2.5 拉取（Pull）和推送（Push）</h4><p>拉取是从远程仓库获取更改并合并到本地仓库的操作，推送是将本地仓库的更改上传到远程仓库的操作。</p><h3>3. Git 最佳实践</h3><h4>3.1 提交规范</h4><ul><li>提交信息要清晰、简洁，描述提交的内容和目的</li><li>使用语义化的提交信息，如 feat: 添加新功能，fix: 修复 bug，docs: 更新文档等</li><li>每个提交只包含一个逻辑上的更改，避免一次提交多个不相关的更改</li><li>提交前检查代码，确保没有语法错误和不必要的文件</li></ul><h4>3.2 分支管理</h4><ul><li>使用主分支（如 main 或 master）作为稳定版本，只用于发布</li><li>使用功能分支（feature branch）开发新功能，分支名应清晰描述功能</li><li>使用修复分支（hotfix branch）修复生产环境中的 bug</li><li>定期合并主分支到功能分支，保持功能分支与主分支同步</li><li>功能开发完成后，通过 Pull Request 进行代码审查和合并</li></ul><h3>4. 总结</h3><p>Git 是现代软件开发中不可或缺的工具，掌握 Git 的最佳实践对于提高团队协作效率和代码质量至关重要。通过遵循 Git 最佳实践，如提交规范、分支管理、代码审查等，你可以更好地管理代码库，减少错误，提高开发效率。Git 的学习曲线虽然有些陡峭，但一旦掌握，它将成为你开发工作中的得力助手。"
        }
    }
    
    # 根据blog_id查找对应的文章
    post = posts.get(blog_id)
    
    # 如果找不到文章，返回默认文章
    if not post:
        post = {
            "id": "0",
            "title": "文章未找到",
            "subtitle": "抱歉，您请求的文章不存在",
            "date": "2026-01-10",
            "category": "系统消息",
            "content": "<p>抱歉，您请求的文章不存在或已被删除。</p><p><a href='/blog'>返回博客列表</a></p>"
        }
    
    return render_template('blog_detail.html', username=session.get('username'), blog_id=blog_id, post=post)

# 隐私政策
@app.route('/privacy')
def privacy_policy():
    return render_template('privacy_policy.html', username=session.get('username'))

# 服务条款
@app.route('/terms')
def service_terms():
    return render_template('service_terms.html', username=session.get('username'))

# 文件下载路由
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 删除文件夹
@app.route('/delete-folder/<folder_id>', methods=['POST'])
def delete_folder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        # 检查文件夹是否存在且属于当前用户
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                           (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('文件夹不存在或无权限')
            return redirect(url_for('project_folders'))
        
        # 递归删除所有子文件夹
        def delete_subfolders(parent_folder_id):
            # 获取所有子文件夹
            subfolders = conn.execute('SELECT id FROM folders WHERE parent_id = ? AND user_id = ?', 
                                     (parent_folder_id, session['user_id'])).fetchall()
            for subfolder in subfolders:
                subfolder_id = subfolder['id']
                # 递归删除子文件夹
                delete_subfolders(subfolder_id)
                # 删除子文件夹下的所有文件
                conn.execute('UPDATE files SET folder_id = NULL WHERE folder_id = ?', (subfolder_id,))
                # 删除子文件夹
                conn.execute('DELETE FROM folders WHERE id = ?', (subfolder_id,))
        
        # 调用递归函数删除所有子文件夹
        delete_subfolders(folder_id)
        
        # 删除当前文件夹下的所有文件
        conn.execute('UPDATE files SET folder_id = NULL WHERE folder_id = ?', (folder_id,))
        
        # 删除当前文件夹
        conn.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
        conn.commit()
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='删除文件夹',
            user_id=session['user_id'],
            action='delete',
            target_id=folder_id,
            target_type='folder',
            details=f'文件夹名称: {folder["name"]}',
            request=request
        )
        
        flash('文件夹删除成功')
    except Exception as e:
        conn.rollback()
        flash(f'删除失败: {str(e)}')
    finally:
        conn.close()
    
    # 根据请求来源决定跳转页面
    referrer = request.headers.get('Referer')
    if referrer and 'folder' in referrer:
        return redirect(url_for('project_folders'))
    return redirect(url_for('project_folders'))

# 上传文件到指定文件夹
@app.route('/upload-to-folder/<folder_id>', methods=['POST'])
def upload_to_folder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    file = request.files.get('file')
    description = request.form.get('description')
    
    if not file or file.filename == '':
        flash('请选择文件')
        return redirect(url_for('folder_detail', folder_id=folder_id))
    
    conn = get_db()
    try:
        # 检查文件夹是否存在且属于当前用户
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                           (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('文件夹不存在或无权限')
            return redirect(url_for('folder_detail', folder_id=folder_id))
        
        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1]
        stored_name = f"{file_id}{ext}"
        
        # 保存文件
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
        file.save(file_path)
        
        # 计算文件大小
        file_size = os.path.getsize(file_path)
        
        # 插入数据库
        conn.execute('''INSERT INTO files (id, user_id, filename, stored_name, path, size, project_desc, folder_id, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                   (file_id, session['user_id'], file.filename, stored_name, file_path, file_size, 
                    description, folder_id))
        
        conn.commit()
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='上传文件到文件夹',
            user_id=session['user_id'],
            action='upload',
            target_id=file_id,
            target_type='file',
            details=f'文件名: {file.filename}, 文件夹: {folder["name"]}',
            request=request
        )
        
        flash('文件上传成功')
    except Exception as e:
        conn.rollback()
        flash(f'上传失败: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('folder_detail', folder_id=folder_id))

# 上传文件夹到指定文件夹
@app.route('/upload-folder-to-folder/<folder_id>', methods=['POST'])
def upload_folder_to_folder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    files = request.files.getlist('folder')
    description = request.form.get('description')
    
    if not files or files[0].filename == '':
        flash('请选择文件夹')
        return redirect(url_for('folder_detail', folder_id=folder_id))
    
    conn = get_db()
    try:
        # 检查文件夹是否存在且属于当前用户
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                           (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('文件夹不存在或无权限')
            return redirect(url_for('folder_detail', folder_id=folder_id))
        
        uploaded_files_count = 0
        
        for file in files:
            if file.filename == '' or not hasattr(file, 'filename'):
                continue
            
            # 获取文件的相对路径（包含文件夹结构）
            relative_path = file.filename
            
            # 生成唯一文件名
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(relative_path)[1]
            stored_name = f"{file_id}{ext}"
            
            # 保存文件
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
            file.save(file_path)
            
            # 计算文件大小
            file_size = os.path.getsize(file_path)
            
            # 插入数据库，保存相对路径作为项目名称，方便识别文件夹结构
            conn.execute('''INSERT INTO files (id, user_id, filename, stored_name, path, size, project_name, project_desc, folder_id, created_at) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                       (file_id, session['user_id'], os.path.basename(relative_path), stored_name, file_path, file_size, 
                        relative_path, description, folder_id))
            
            uploaded_files_count += 1
        
        conn.commit()
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='上传文件夹到文件夹',
            user_id=session['user_id'],
            action='upload',
            target_id=folder_id,
            target_type='folder',
            details=f'上传文件数量: {uploaded_files_count}, 文件夹: {folder["name"]}',
            request=request
        )
        
        flash(f'成功上传 {uploaded_files_count} 个文件')
    except Exception as e:
        conn.rollback()
        flash(f'上传失败: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('folder_detail', folder_id=folder_id))

# 在指定文件夹中创建子文件夹
@app.route('/create-subfolder/<folder_id>', methods=['POST'])
def create_subfolder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    name = request.form.get('name')
    purpose = request.form.get('purpose')
    
    if not all([name, purpose]):
        flash('请填写文件夹名称和用途')
        return redirect(url_for('folder_detail', folder_id=folder_id))
    
    conn = get_db()
    try:
        # 检查父文件夹是否存在且属于当前用户
        parent_folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                           (folder_id, session['user_id'])).fetchone()
        if not parent_folder:
            flash('父文件夹不存在或无权限')
            return redirect(url_for('folder_detail', folder_id=folder_id))
        
        # 创建子文件夹
        subfolder_id = str(uuid.uuid4())
        conn.execute('INSERT INTO folders (id, user_id, name, purpose, parent_id) VALUES (?, ?, ?, ?, ?)', 
                   (subfolder_id, session['user_id'], name, purpose, folder_id))
        conn.commit()
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='创建子文件夹',
            user_id=session['user_id'],
            action='create',
            target_id=subfolder_id,
            target_type='folder',
            details=f'文件夹名称: {name}, 父文件夹: {parent_folder["name"]}',
            request=request
        )
        
        flash('子文件夹创建成功')
    except Exception as e:
        conn.rollback()
        flash(f'创建失败: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('folder_detail', folder_id=folder_id))

# 批量删除文件
@app.route('/batch-delete-files', methods=['POST'])
def batch_delete_files():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    file_ids = request.form.get('file_ids', '').split(',')
    folder_id = request.form.get('folder_id')
    
    if not file_ids or file_ids == ['']:
        flash('请选择要删除的文件')
        return redirect(url_for('folder_detail', folder_id=folder_id))
    
    conn = get_db()
    try:
        # 删除选中的文件
        for file_id in file_ids:
            if file_id:
                conn.execute('DELETE FROM files WHERE id = ? AND user_id = ?', (file_id, session['user_id']))
        
        conn.commit()
        
        # 获取本地时间
        from datetime import datetime
        local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 直接记录操作日志，使用本地时间
        conn.execute('''INSERT INTO operation_logs (user_id, action, target_id, target_type, message, details, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                   (session['user_id'], 'delete', None, 'file', '批量删除文件', f'删除文件数量: {len(file_ids)}', local_time))
        
        flash(f'成功删除 {len(file_ids)} 个文件')
    except Exception as e:
        conn.rollback()
        flash(f'删除失败: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('folder_detail', folder_id=folder_id))

# 项目文件夹页面
@app.route('/project-folders')
def project_folders():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        folders = conn.execute('SELECT * FROM folders WHERE user_id = ? AND (parent_id IS NULL OR parent_id = "") ORDER BY created_at DESC', 
                              (session['user_id'],)).fetchall()
        return render_template('project_folders.html', username=session.get('username'), user=user, folders=folders)
    finally:
        conn.close()

# 文件夹详情页面
@app.route('/folder/<folder_id>')
def folder_detail(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        # 获取当前用户信息
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                            (folder_id, session['user_id'])).fetchone()
        if not folder:
            return page_error_response('project_folders', '文件夹不存在或无权限', 404)
        
        files = conn.execute('SELECT * FROM files WHERE folder_id = ?', (folder_id,)).fetchall()
        
        # 获取子文件夹
        subfolders = conn.execute('SELECT * FROM folders WHERE parent_id = ? AND user_id = ?', 
                               (folder_id, session['user_id'])).fetchall()
        
        return render_template('folder_detail.html', username=session.get('username'), user=user, folder=folder, files=files, subfolders=subfolders)
    finally:
        conn.close()

# 创建文件夹
@app.route('/create-folder', methods=['POST'])
def create_folder():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    name = request.form.get('name')
    purpose = request.form.get('purpose')
    
    if not all([name, purpose]):
        flash('请填写文件夹名称和用途')
        return redirect(url_for('project_folders'))
    
    conn = get_db()
    try:
        folder_id = str(uuid.uuid4())
        conn.execute('INSERT INTO folders (id, user_id, name, purpose) VALUES (?, ?, ?, ?)', 
                   (folder_id, session['user_id'], name, purpose))
        conn.commit()
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='创建文件夹',
            user_id=session['user_id'],
            action='create',
            target_id=folder_id,
            target_type='folder',
            details=f'文件夹名称: {name}',
            request=request
        )
        
        flash('文件夹创建成功')
        return redirect(url_for('project_folders'))
    except Exception as e:
        conn.rollback()
        flash(f'创建文件夹失败: {str(e)}')
        return redirect(url_for('project_folders'))
    finally:
        conn.close()

# API: 获取所有文件
@app.route('/api/files')
def api_get_files():
    files = get_all_files()
    return api_response(success=True, data={'files': files})

# API: 检查登录状态
@app.route('/api/check-login')
def check_login():
    if 'user_id' in session:
        return api_response(success=True, data={'logged_in': True, 'username': session.get('username')})
    return api_response(success=True, data={'logged_in': False})

# API: 获取所有分类
@app.route('/api/categories', methods=['GET'])
def api_get_categories():
    conn = get_db()
    try:
        rows = conn.execute('SELECT id, name, description, created_at FROM categories').fetchall()
        categories = [{
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'created_at': row['created_at']
        } for row in rows]
        return api_response(success=True, data={'categories': categories})
    finally:
        conn.close()

# API: 创建分类
@app.route('/api/categories', methods=['POST'])
def api_create_category():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')
    
    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')
    
    if not name:
        return api_response(success=False, message='分类名称不能为空')
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO categories (name, description, user_id) VALUES (?, ?, ?)',
                   (name, description, session['user_id']))
        conn.commit()
        return api_response(success=True, message='分类创建成功')
    finally:
        conn.close()

# API: 获取所有标签
@app.route('/api/tags', methods=['GET'])
def api_get_tags():
    conn = get_db()
    try:
        rows = conn.execute('SELECT id, name, created_at FROM tags').fetchall()
        tags = [{
            'id': row['id'],
            'name': row['name'],
            'created_at': row['created_at']
        } for row in rows]
        return api_response(success=True, data={'tags': tags})
    finally:
        conn.close()

# API: 创建标签
@app.route('/api/tags', methods=['POST'])
def api_create_tag():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')
    
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return api_response(success=False, message='标签名称不能为空')
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO tags (name, user_id) VALUES (?, ?)',
                   (name, session['user_id']))
        conn.commit()
        return api_response(success=True, message='标签创建成功')
    finally:
        conn.close()

# API: 获取文件的分类
@app.route('/api/files/<file_id>/categories', methods=['GET'])
def api_get_file_categories(file_id):
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT c.id, c.name, c.description, c.created_at 
            FROM categories c
            JOIN file_categories fc ON c.id = fc.category_id
            WHERE fc.file_id = ?
        ''', (file_id,)).fetchall()
        categories = [{
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'created_at': row['created_at']
        } for row in rows]
        return api_response(success=True, data={'categories': categories})
    finally:
        conn.close()

# API: 添加文件分类
@app.route('/api/files/<file_id>/categories', methods=['POST'])
def api_add_file_category(file_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')
    
    data = request.get_json()
    category_id = data.get('category_id')
    
    if not category_id:
        return api_response(success=False, message='分类ID不能为空')
    
    conn = get_db()
    try:
        # 检查分类是否已存在
        existing = conn.execute('SELECT * FROM file_categories WHERE file_id = ? AND category_id = ?',
                               (file_id, category_id)).fetchone()
        if not existing:
            conn.execute('INSERT INTO file_categories (file_id, category_id) VALUES (?, ?)',
                       (file_id, category_id))
            conn.commit()
        return api_response(success=True, message='分类添加成功')
    finally:
        conn.close()

# API: 移除文件分类
@app.route('/api/files/<file_id>/categories/<category_id>', methods=['DELETE'])
def api_remove_file_category(file_id, category_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')
    
    conn = get_db()
    try:
        conn.execute('DELETE FROM file_categories WHERE file_id = ? AND category_id = ?',
                   (file_id, category_id))
        conn.commit()
        return api_response(success=True, message='分类移除成功')
    finally:
        conn.close()

# API: 获取文件的标签
@app.route('/api/files/<file_id>/tags', methods=['GET'])
def api_get_file_tags(file_id):
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT t.id, t.name, t.created_at 
            FROM tags t
            JOIN file_tags ft ON t.id = ft.tag_id
            WHERE ft.file_id = ?
        ''', (file_id,)).fetchall()
        tags = [{
            'id': row['id'],
            'name': row['name'],
            'created_at': row['created_at']
        } for row in rows]
        return api_response(success=True, data={'tags': tags})
    finally:
        conn.close()

# API: 添加文件标签
@app.route('/api/files/<file_id>/tags', methods=['POST'])
def api_add_file_tag(file_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')
    
    data = request.get_json()
    tag_id = data.get('tag_id')
    
    if not tag_id:
        return api_response(success=False, message='标签ID不能为空')
    
    conn = get_db()
    try:
        # 检查标签是否已存在
        existing = conn.execute('SELECT * FROM file_tags WHERE file_id = ? AND tag_id = ?',
                               (file_id, tag_id)).fetchone()
        if not existing:
            conn.execute('INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)',
                       (file_id, tag_id))
            conn.commit()
        return api_response(success=True, message='标签添加成功')
    finally:
        conn.close()

# API: 移除文件标签
@app.route('/api/files/<file_id>/tags/<tag_id>', methods=['DELETE'])
def api_remove_file_tag(file_id, tag_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')
    
    conn = get_db()
    try:
        conn.execute('DELETE FROM file_tags WHERE file_id = ? AND tag_id = ?',
                   (file_id, tag_id))
        conn.commit()
        return api_response(success=True, message='标签移除成功')
    finally:
        conn.close()

# API: 点赞文件
@app.route('/api/files/<file_id>/like', methods=['POST'])
def api_like_file(file_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')
    
    conn = get_db()
    try:
        # 检查是否已经点赞
        existing = conn.execute('SELECT * FROM likes WHERE file_id = ? AND user_id = ?',
                               (file_id, session['user_id'])).fetchone()
        
        if existing:
            # 已经点赞，取消点赞
            conn.execute('DELETE FROM likes WHERE file_id = ? AND user_id = ?',
                       (file_id, session['user_id']))
            # 获取当前点赞数
            like_count = conn.execute('SELECT COUNT(*) as count FROM likes WHERE file_id = ?',
                                    (file_id,)).fetchone()['count']
            conn.commit()
            return api_response(success=True, data={'liked': False, 'count': like_count})
        else:
            # 未点赞，添加点赞
            conn.execute('INSERT INTO likes (file_id, user_id) VALUES (?, ?)',
                       (file_id, session['user_id']))
            # 获取当前点赞数
            like_count = conn.execute('SELECT COUNT(*) as count FROM likes WHERE file_id = ?',
                                    (file_id,)).fetchone()['count']
            conn.commit()
            return api_response(success=True, data={'liked': True, 'count': like_count})
    finally:
        conn.close()

# API: 收藏文件
@app.route('/api/files/<file_id>/favorite', methods=['POST'])
def api_favorite_file(file_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录')
    
    conn = get_db()
    try:
        # 检查是否已经收藏
        existing = conn.execute('SELECT * FROM favorites WHERE file_id = ? AND user_id = ?',
                               (file_id, session['user_id'])).fetchone()
        
        if existing:
            # 已经收藏，取消收藏
            conn.execute('DELETE FROM favorites WHERE file_id = ? AND user_id = ?',
                       (file_id, session['user_id']))
            # 获取当前收藏数
            favorite_count = conn.execute('SELECT COUNT(*) as count FROM favorites WHERE file_id = ?',
                                         (file_id,)).fetchone()['count']
            conn.commit()
            return api_response(success=True, data={'favorited': False, 'count': favorite_count})
        else:
            # 未收藏，添加收藏
            conn.execute('INSERT INTO favorites (file_id, user_id) VALUES (?, ?)',
                       (file_id, session['user_id']))
            # 获取当前收藏数
            favorite_count = conn.execute('SELECT COUNT(*) as count FROM favorites WHERE file_id = ?',
                                         (file_id,)).fetchone()['count']
            conn.commit()
            return api_response(success=True, data={'favorited': True, 'count': favorite_count})
    finally:
        conn.close()

# API: 获取文件的点赞和收藏状态
@app.route('/api/files/<file_id>/interaction-status', methods=['GET'])
def api_get_file_interaction_status(file_id):
    conn = get_db()
    try:
        # 获取点赞数
        like_count = conn.execute('SELECT COUNT(*) as count FROM likes WHERE file_id = ?',
                                (file_id,)).fetchone()['count']
        
        # 获取收藏数
        favorite_count = conn.execute('SELECT COUNT(*) as count FROM favorites WHERE file_id = ?',
                                     (file_id,)).fetchone()['count']
        
        # 检查当前用户是否点赞
        liked = False
        favorited = False
        if 'user_id' in session:
            liked = conn.execute('SELECT * FROM likes WHERE file_id = ? AND user_id = ?',
                               (file_id, session['user_id'])).fetchone() is not None
            favorited = conn.execute('SELECT * FROM favorites WHERE file_id = ? AND user_id = ?',
                                   (file_id, session['user_id'])).fetchone() is not None
        
        return api_response(success=True, data={
            'like_count': like_count,
            'favorite_count': favorite_count,
            'liked': liked,
            'favorited': favorited
        })
    finally:
        conn.close()

# 打开本地文件
@app.route('/open/<stored_name>')
def open_local(stored_name):
    # 记录访问日志
    conn = get_db()
    try:
        file = conn.execute('SELECT id FROM files WHERE stored_name = ?', (stored_name,)).fetchone()
        if file:
            log_access(file['id'], 'open', request)
    finally:
        conn.close()
    return send_from_directory(app.config['UPLOAD_FOLDER'], stored_name)

# 沙盒运行环境
@app.route('/sandbox/<stored_name>')
def sandbox(stored_name):
    # 记录访问日志
    conn = get_db()
    try:
        file = conn.execute('SELECT id FROM files WHERE stored_name = ?', (stored_name,)).fetchone()
        if file:
            log_access(file['id'], 'sandbox', request)
    finally:
        conn.close()
    
    # 获取文件名
    conn = get_db()
    try:
        file = conn.execute('SELECT filename FROM files WHERE stored_name = ?', (stored_name,)).fetchone()
        file_name = file['filename'] if file else stored_name
    finally:
        conn.close()
    
    # 生成iframe的src路径
    iframe_src = url_for('open_local', stored_name=stored_name)
    
    return render_template('sandbox.html', 
                          tool_name=file_name, 
                          iframe_src=iframe_src, 
                          username=session.get('username'))

# 下载本地文件
@app.route('/download/<stored_name>')
def download_local(stored_name):
    # 记录访问日志
    conn = get_db()
    try:
        file = conn.execute('SELECT id FROM files WHERE stored_name = ?', (stored_name,)).fetchone()
        if file:
            log_access(file['id'], 'download', request)
    finally:
        conn.close()
    return send_from_directory(app.config['UPLOAD_FOLDER'], stored_name, as_attachment=True)

# 文件详情页面
@app.route('/file/<file_id>')
def file_detail(file_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        # 允许查看当前用户的文件或default_user的公开文件
        item = conn.execute('SELECT * FROM files WHERE id = ? AND (user_id = ? OR user_id = "default_user")', 
                           (file_id, session['user_id'])).fetchone()
        if not item:
            return page_error_response('index', '文件不存在或无权限', 404)
        
        # 记录访问日志
        log_access(file_id, 'view', request)
        
        # 解析dkfile字段
        item_dict = dict(item)
        item_dict['dkfile'] = json.loads(item_dict['dkfile'] if item_dict['dkfile'] else '{}')
        
        return render_template('detail.html', username=session.get('username'), item=item_dict)
    finally:
        conn.close()

# 删除文件
@app.route('/file/<file_id>/delete', methods=['POST'])
@app.route('/delete-file/<file_id>', methods=['POST'])
def file_delete(file_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', 
                           (file_id, session['user_id'])).fetchone()
        if not file:
            flash('文件不存在或无权限')
            return redirect(url_for('user_center'))
        
        # 删除文件
        conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
        
        # 获取本地时间
        from datetime import datetime
        local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 在同一个数据库连接中直接记录操作日志
        conn.execute('''INSERT INTO operation_logs (user_id, action, target_id, target_type, message, details, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                   (session['user_id'], 'delete', file_id, 'file', '删除文件', f'文件名: {file["filename"]}', local_time))
        
        # 提交所有更改
        conn.commit()
        
        flash('文件删除成功')
        
        # 根据请求来源决定跳转页面
        referrer = request.headers.get('Referer')
        if referrer and 'folder' in referrer:
            # 从文件夹详情页删除的，跳回文件夹详情页
            # 提取folder_id
            folder_id = referrer.split('/')[-1]
            return redirect(url_for('folder_detail', folder_id=folder_id))
        else:
            # 从其他页面删除的，跳回用户中心
            return redirect(url_for('user_center'))
    except Exception as e:
        conn.rollback()
        flash(f'删除文件失败: {str(e)}')
        
        # 根据请求来源决定跳转页面
        referrer = request.headers.get('Referer')
        if referrer and 'folder' in referrer:
            # 从文件夹详情页删除的，跳回文件夹详情页
            folder_id = referrer.split('/')[-1]
            return redirect(url_for('folder_detail', folder_id=folder_id))
        else:
            # 从其他页面删除的，跳回用户中心
            return redirect(url_for('user_center'))
    finally:
        conn.close()

# 替换文件
@app.route('/file/replace', methods=['POST'])
def file_replace():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    file_id = request.form.get('file_id')
    file = request.files.get('file')
    comment = request.form.get('comment')
    
    if not file_id or not file or file.filename == '':
        flash('请选择文件')
        return redirect(url_for('user_center'))
    
    conn = get_db()
    try:
        # 检查文件是否存在且属于当前用户
        existing_file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', 
                                   (file_id, session['user_id'])).fetchone()
        if not existing_file:
            flash('文件不存在或无权限')
            return redirect(url_for('user_center'))
        
        # 生成唯一文件名
        ext = os.path.splitext(file.filename)[1]
        stored_name = f"{file_id}{ext}"
        
        # 保存文件
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
        file.save(file_path)
        
        # 更新文件信息
        conn.execute('UPDATE files SET stored_name = ?, path = ?, size = ? WHERE id = ?', 
                   (stored_name, file_path, os.path.getsize(file_path), file_id))
        conn.commit()
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='替换文件',
            user_id=session['user_id'],
            action='edit',
            target_id=file_id,
            target_type='file',
            details=f'文件名: {file.filename}',
            request=request
        )
        
        flash('文件替换成功')
        return redirect(url_for('user_center'))
    except Exception as e:
        conn.rollback()
        flash(f'替换文件失败: {str(e)}')
        return redirect(url_for('user_center'))
    finally:
        conn.close()
