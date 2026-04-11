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
from datetime import datetime


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
                session['role'] = user['role']
                
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
                session['role'] = user['role']
                
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
                
                # 同步发送验证码邮件，捕获异常
                try:
                    send_verification_email(email, code, purpose)
                    return api_response(success=True, message='验证码已发送，请查收邮件')
                except Exception as email_error:
                    # 邮件发送失败，返回错误信息
                    error_msg = str(email_error)
                    if 'SMTP配置不完整' in error_msg:
                        return api_response(success=False, message='邮件服务未配置，请联系管理员配置SMTP邮箱服务', code=500)
                    else:
                        return api_response(success=False, message=f'验证码发送失败: {error_msg}', code=500)
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
        upload_target = request.form.get('upload_target', 'user')
        file_category = request.form.get('file_category')
        
        if not files or files[0].filename == '':
            flash('请选择文件')
            return redirect(url_for('upload'))
        
        # 处理文件上传（简化版，实际应包含安全检查）
        conn = get_db()
        try:
            # 检查用户是否为管理员
            current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
            is_admin = current_user and current_user['role'] == 'admin'
            
            # 确定上传目标用户ID
            target_user_id = session['user_id']
            if is_admin and upload_target == 'home':
                target_user_id = 'default_user'
            
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
                           (file_id, target_user_id, file.filename, stored_name, file_path, file_size, 
                            project_name, project_desc))
                
                # 使用用户选择的分类（仅管理员）
                if is_admin and file_category:
                    from app import get_or_create_category, assign_category_to_file
                    assign_category_to_file(conn, file_id, file_category, target_user_id)
            
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
@app.route('/ai', methods=['GET', 'POST'])
def ai():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    saved_contents = []
    
    try:
        # 获取用户保存的AI内容
        rows = conn.execute('''SELECT id, ai_function, prompt, response, created_at 
                          FROM ai_contents 
                          WHERE user_id = ? 
                          ORDER BY created_at DESC''', (session['user_id'],)).fetchall()
        
        saved_contents = [{
            'id': row['id'],
            'ai_function': row['ai_function'],
            'prompt': row['prompt'],
            'response': row['response'],
            'created_at': row['created_at']
        } for row in rows]
    except Exception as e:
        print(f"获取AI内容失败: {e}")
    finally:
        conn.close()
    
    # POST请求处理
    if request.method == 'POST':
        return handle_ai_request()
    
    return render_template('ai_page.html', username=session.get('username'), saved_contents=saved_contents)


def handle_ai_request():
    """处理AI请求"""
    from app import deepseek_chat
    import uuid
    
    ai_function = request.form.get('ai_function', 'chat')
    prompt = request.form.get('prompt', '').strip()
    model = request.form.get('model', 'deepseek-chat')
    temperature = request.form.get('temperature', '0.5')
    
    if not prompt:
        return render_template('ai_page.html', 
                            username=session.get('username'),
                            saved_contents=get_saved_ai_contents(),
                            ai_error='请输入问题或内容')
    
    try:
        # 根据功能类型构建消息
        messages = build_ai_messages(ai_function, prompt)
        
        # 调用DeepSeek API
        result = deepseek_chat(messages, model, temperature)
        
        # 解析回复
        if result and 'choices' in result and len(result['choices']) > 0:
            ai_output = result['choices'][0]['message']['content']
        else:
            raise Exception("AI返回格式异常")
        
        return render_template('ai_page.html',
                            username=session.get('username'),
                            saved_contents=get_saved_ai_contents(),
                            ai_output=ai_output,
                            last_request={
                                'ai_function': ai_function,
                                'prompt': prompt,
                                'model': model,
                                'temperature': temperature
                            })
    
    except Exception as e:
        error_msg = str(e)
        if 'API_KEY' in error_msg or '401' in error_msg:
            error_msg = 'API密钥配置错误或无效，请联系管理员'
        elif 'timeout' in error_msg.lower() or '连接' in error_msg.lower():
            error_msg = 'AI服务连接超时，请稍后重试'
        elif '429' in error_msg or 'rate' in error_msg.lower():
            error_msg = '请求过于频繁，请稍后重试'
        else:
            error_msg = f'AI请求失败: {error_msg}'
        
        return render_template('ai_page.html',
                            username=session.get('username'),
                            saved_contents=get_saved_ai_contents(),
                            ai_error=error_msg)


def build_ai_messages(ai_function, prompt):
    """根据AI功能类型构建消息"""
    system_prompts = {
        'chat': '你是一个专业的AI助手，请用中文回答用户的问题，回答要准确、详细、有条理。',
        'file_analysis': '你是一个专业的文件内容分析专家，请仔细分析用户提供的内容，给出详细的解读和建议。',
        'smart_categorization': '你是一个文本分类专家，请对用户提供的文本进行智能分类，并说明分类依据。',
        'text_summarization': '你是一个文本摘要专家，请为用户提供的长文本生成简洁、准确的摘要，保留关键信息。',
        'code_explanation': '你是一个编程专家，请详细解释用户提供的代码，包括功能、逻辑、使用场景等。'
    }
    
    system_prompt = system_prompts.get(ai_function, system_prompts['chat'])
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    return messages


def get_saved_ai_contents():
    """获取用户保存的AI内容"""
    if 'user_id' not in session:
        return []
    
    conn = get_db()
    try:
        rows = conn.execute('''SELECT id, ai_function, prompt, response, created_at 
                          FROM ai_contents 
                          WHERE user_id = ? 
                          ORDER BY created_at DESC''', (session['user_id'],)).fetchall()
        
        return [{
            'id': row['id'],
            'ai_function': row['ai_function'],
            'prompt': row['prompt'],
            'response': row['response'],
            'created_at': row['created_at']
        } for row in rows]
    finally:
        conn.close()


# 保存AI内容
@app.route('/save-ai-content', methods=['POST'])
def save_ai_content():
    if 'user_id' not in session:
        if request.is_json:
            return api_response(success=False, message='请先登录', code=401)
        return redirect(url_for('auth'))
    
    data = request.form if request.method == 'POST' and not request.is_json else (request.get_json(silent=True) or {})
    
    ai_function = data.get('ai_function', 'chat')
    prompt = data.get('prompt', '')
    response = data.get('response', '')
    
    if not prompt or not response:
        if request.is_json:
            return api_response(success=False, message='参数不完整')
        flash('保存失败：缺少必要参数')
        return redirect(url_for('ai'))
    
    import uuid
    content_id = str(uuid.uuid4())
    
    conn = get_db()
    try:
        conn.execute('''INSERT INTO ai_contents (id, user_id, ai_function, prompt, response) 
                       VALUES (?, ?, ?, ?, ?)''', 
                   (content_id, session['user_id'], ai_function, prompt, response))
        conn.commit()
        
        if request.is_json:
            return api_response(success=True, message='保存成功')
        flash('AI内容保存成功')
        return redirect(url_for('ai'))
    
    except Exception as e:
        if request.is_json:
            return api_response(success=False, message=f'保存失败: {str(e)}')
        flash(f'保存失败: {str(e)}')
        return redirect(url_for('ai'))
    finally:
        conn.close()


# 删除AI内容
@app.route('/delete-ai-content', methods=['POST'])
def delete_ai_content():
    if 'user_id' not in session:
        if request.is_json:
            return api_response(success=False, message='请先登录', code=401)
        return redirect(url_for('auth'))
    
    data = request.form if request.method == 'POST' and not request.is_json else (request.get_json(silent=True) or {})
    content_id = data.get('content_id')
    
    if not content_id:
        if request.is_json:
            return api_response(success=False, message='缺少内容ID')
        flash('删除失败：缺少内容ID')
        return redirect(url_for('ai'))
    
    conn = get_db()
    try:
        # 验证内容属于当前用户
        content = conn.execute('SELECT * FROM ai_contents WHERE id = ? AND user_id = ?', 
                             (content_id, session['user_id'])).fetchone()
        
        if not content:
            if request.is_json:
                return api_response(success=False, message='内容不存在或无权删除')
            flash('内容不存在或无权删除')
            return redirect(url_for('ai'))
        
        conn.execute('DELETE FROM ai_contents WHERE id = ? AND user_id = ?', 
                   (content_id, session['user_id']))
        conn.commit()
        
        if request.is_json:
            return api_response(success=True, message='删除成功')
        flash('AI内容已删除')
        return redirect(url_for('ai'))
    
    except Exception as e:
        if request.is_json:
            return api_response(success=False, message=f'删除失败: {str(e)}')
        flash(f'删除失败: {str(e)}')
        return redirect(url_for('ai'))
    finally:
        conn.close()


# 查看AI内容详情（返回JSON）
@app.route('/api/ai-content/<content_id>')
def get_ai_content_detail(content_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        content = conn.execute('''SELECT * FROM ai_contents 
                                  WHERE id = ? AND user_id = ?''', 
                             (content_id, session['user_id'])).fetchone()
        
        if not content:
            return api_response(success=False, message='内容不存在')
        
        return api_response(success=True, data={
            'id': content['id'],
            'ai_function': content['ai_function'],
            'prompt': content['prompt'],
            'response': content['response'],
            'created_at': content['created_at']
        })
    finally:
        conn.close()


# ==================== AI功能增强 - 第二阶段 ====================

# API: 流式AI对话 (SSE)
@app.route('/api/ai/chat/stream', methods=['POST'])
def ai_chat_stream():
    """流式AI对话接口 - Server-Sent Events"""
    print(f"[AI Stream] === New Request ===")

    # 检查登录状态
    if 'user_id' not in session:
        print(f"[AI Stream] ERROR: User not logged in")
        return api_response(success=False, message='请先登录', code=401)

    print(f"[AI Stream] User ID: {session.get('user_id')}")

    from app import DEEPSEEK_BASE, DEEPSEEK_API_KEY
    import requests
    import json

    # 检查API Key
    if not DEEPSEEK_API_KEY:
        print(f"[AI Stream] ERROR: API Key not configured")
        return api_response(success=False, message='DeepSeek API Key未配置，请在.env文件中设置DEEPSEEK_API_KEY')

    data = request.get_json(silent=True) or {}

    prompt = data.get('prompt', '').strip()
    model = data.get('model', 'deepseek-chat')
    temperature = float(data.get('temperature', '0.5'))
    ai_function = data.get('ai_function', 'chat')
    conversation_id = data.get('conversation_id')

    if not prompt:
        return api_response(success=False, message='请输入内容')

    print(f"[AI Stream] Prompt: {prompt[:50]}...")
    print(f"[AI Stream] Model: {model}, Temperature: {temperature}")
    print(f"[AI Stream] API Key: {DEEPSEEK_API_KEY[:10]}...{DEEPSEEK_API_KEY[-4:]}")

    # 获取或创建对话上下文
    if conversation_id and 'ai_conversations' in session:
        conversations = session.get('ai_conversations', {})
        messages = conversations.get(conversation_id, [])
        print(f"[AI Stream] Loaded existing conversation: {conversation_id[:8]}... ({len(messages)} messages)")
    else:
        messages = []
        conversation_id = str(uuid.uuid4())
        print(f"[AI Stream] Creating new conversation: {conversation_id[:8]}...")

    # 添加系统提示
    try:
        system_prompt = build_ai_messages(ai_function, '')[0]['content']
    except Exception as e:
        print(f"[AI Stream] ERROR building system prompt: {e}")
        system_prompt = "你是一个有用的AI助手。"

    # 构建消息列表
    full_messages = [{"role": "system", "content": system_prompt}]
    full_messages.extend(messages)
    full_messages.append({"role": "user", "content": prompt})

    def generate():
        try:
            print(f"[AI Stream] Starting request to DeepSeek API...")
            url = f"{DEEPSEEK_BASE}/chat/completions"
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            payload = {
                "model": model,
                "messages": full_messages,
                "stream": True,
                "temperature": temperature
            }

            response = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)

            if response.status_code != 200:
                error_msg = f'API错误 ({response.status_code}): {response.text[:200]}'
                print(f"[AI Stream] ERROR: {error_msg}")
                yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
                return

            print(f"[AI Stream] Connected! Status: {response.status_code}")
            full_response = ""
            chunk_count = 0

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: ') and line != 'data: [DONE]':
                        chunk_data = line[6:]
                        try:
                            chunk = json.loads(chunk_data)
                            content = chunk['choices'][0].get('delta', {}).get('content', '')
                            if content:
                                full_response += content
                                chunk_count += 1
                                yield f"data: {json.dumps({'content': content, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            print(f"[AI Stream] Chunk parse error: {e}")

            print(f"[AI Stream] Completed! Chunks: {chunk_count}, Length: {len(full_response)}")
            yield f"data: {json.dumps({'done': True, 'full_response': full_response, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"

            # 保存到对话历史
            try:
                if 'ai_conversations' not in session:
                    session['ai_conversations'] = {}

                messages.append({"role": "user", "content": prompt})
                messages.append({"role": "assistant", "content": full_response})

                # 保持最近20轮对话
                if len(messages) > 40:
                    messages = messages[-40:]

                session['ai_conversations'][conversation_id] = messages
                session.modified = True
                print(f"[AI Stream] Conversation saved: {conversation_id[:8]}...")
            except Exception as e:
                print(f"[AI Stream] Session save error: {e}")

        except requests.exceptions.Timeout:
            error_msg = '请求超时（60秒），请稍后重试'
            print(f"[AI Stream] Timeout error")
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
        except requests.exceptions.ConnectionError as e:
            error_msg = f'网络连接失败，请检查网络: {str(e)[:100]}'
            print(f"[AI Stream] Connection error: {e}")
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
        except Exception as e:
            error_msg = f'服务器内部错误: {type(e).__name__}: {str(e)[:100]}'
            print(f"[AI Stream] Unexpected error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    from flask import Response
    return Response(generate(), mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache',
                           'X-Accel-Buffering': 'no',
                           'Connection': 'keep-alive'})


# API: 获取对话列表
@app.route('/api/ai/conversations')
def get_ai_conversations():
    """获取用户的AI对话列表"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conversations = session.get('ai_conversations', {})
    
    result = []
    for conv_id, messages in conversations.items():
        if messages:
            first_user_msg = next((m['content'] for m in messages if m['role'] == 'user'), '新对话')
            result.append({
                'id': conv_id,
                'title': first_user_msg[:50] + ('...' if len(first_user_msg) > 50 else ''),
                'message_count': len([m for m in messages if m['role'] == 'user']),
                'created_at': messages[0].get('timestamp', '')
            })
    
    return api_response(success=True, data={'conversations': result})


# API: 获取对话详情
@app.route('/api/ai/conversation/<conv_id>')
def get_ai_conversation_detail(conv_id):
    """获取指定对话的详细消息"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conversations = session.get('ai_conversations', {})
    messages = conversations.get(conv_id, [])
    
    return api_response(success=True, data={
        'id': conv_id,
        'messages': messages
    })


# API: 删除对话
@app.route('/api/ai/conversation/<conv_id>', methods=['DELETE'])
def delete_ai_conversation(conv_id):
    """删除指定对话"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conversations = session.get('ai_conversations', {})
    
    if conv_id in conversations:
        del conversations[conv_id]
        session['ai_conversations'] = conversations
        session.modified = True
    
    return api_response(success=True, message='删除成功')


# API: 清空所有对话
@app.route('/api/ai/conversations/clear', methods=['POST'])
def clear_all_conversations():
    """清空所有AI对话"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    session['ai_conversations'] = {}
    session.modified = True
    
    return api_response(success=True, message='已清空所有对话')


# API: 导出对话为Markdown
@app.route('/api/ai/export/<format_type>')
def export_ai_content(format_type):
    """导出AI内容为指定格式"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    content_id = request.args.get('id')
    conv_id = request.args.get('conversation_id')
    
    if format_type == 'markdown':
        if conv_id:
            conversations = session.get('ai_conversations', {})
            messages = conversations.get(conv_id, [])
            
            md_content = "# AI对话记录\n\n"
            for msg in messages:
                role = "用户" if msg['role'] == 'user' else "AI助手"
                md_content += f"## {role}\n\n{msg['content']}\n\n---\n\n"
            
            from flask import Response as FlaskResponse
            response = FlaskResponse(md_content, mimetype='text/markdown')
            response.headers['Content-Disposition'] = f'attachment; filename=ai_conversation_{conv_id[:8]}.md'
            return response
        
        elif content_id:
            conn = get_db()
            try:
                content = conn.execute('''SELECT * FROM ai_contents 
                                          WHERE id = ? AND user_id = ?''', 
                                     (content_id, session['user_id'])).fetchone()
                
                if content:
                    md_content = f"# AI{content['ai_function']}记录\n\n"
                    md_content += f"**时间**: {content['created_at']}\n\n"
                    md_content += f"## 用户输入\n\n{content['prompt']}\n\n---\n\n"
                    md_content += f"## AI回复\n\n{content['response']}\n"
                    
                    from flask import Response as FlaskResponse
                    response = FlaskResponse(md_content, mimetype='text/markdown')
                    response.headers['Content-Disposition'] = f'attachment; filename=ai_content_{content_id[:8]}.md'
                    return response
            finally:
                conn.close()
    
    elif format_type == 'txt':
        if conv_id:
            conversations = session.get('ai_conversations', {})
            messages = conversations.get(conv_id, [])
            
            txt_content = "AI对话记录\n" + "=" * 30 + "\n\n"
            for msg in messages:
                role = "用户" if msg['role'] == 'user' else "AI助手"
                txt_content += f"[{role}]\n{msg['content']}\n\n"
            
            from flask import Response as FlaskResponse
            response = FlaskResponse(txt_content, mimetype='text/plain')
            response.headers['Content-Disposition'] = f'attachment; filename=ai_conversation_{conv_id[:8]}.txt'
            return response
        
        elif content_id:
            conn = get_db()
            try:
                content = conn.execute('''SELECT * FROM ai_contents 
                                          WHERE id = ? AND user_id = ?''', 
                                     (content_id, session['user_id'])).fetchone()
                
                if content:
                    txt_content = f"AI{content['ai_function']}记录\n"
                    txt_content += "=" * 30 + "\n"
                    txt_content += f"时间: {content['created_at']}\n\n"
                    txt_content += "[用户输入]\n{content['prompt']}\n\n"
                    txt_content += "[AI回复]\n{content['response']}\n"
                    
                    from flask import Response as FlaskResponse
                    response = FlaskResponse(txt_content, mimetype='text/plain')
                    response.headers['Content-Disposition'] = f'attachment; filename=ai_content_{content_id[:8]}.txt'
                    return response
            finally:
                conn.close()
    
    return api_response(success=False, message='不支持的导出格式')


# ==================== 数据库优化管理API ====================

@app.route('/api/db/stats')
def get_db_stats():
    """获取数据库统计信息（需要管理员权限）"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_database_stats, query_monitor
        stats = get_database_stats()
        return api_response(success=True, data=stats)
    except Exception as e:
        return api_response(success=False, message=f'获取统计失败: {str(e)}')


@app.route('/api/db/optimize', methods=['POST'])
def optimize_db():
    """执行数据库优化（VACUUM + ANALYZE）"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import optimize_database
        result = optimize_database()

        if result.get('success'):
            return api_response(
                success=True,
                message=result.get('message', '优化完成'),
                data={
                    'vacuum_time': result.get('vacuum_time'),
                    'analyze_time': result.get('analyze_time'),
                    'db_size_mb': result.get('db_size_mb')
                }
            )
        else:
            return api_response(success=False, message=result.get('error', '优化失败'))

    except Exception as e:
        return api_response(success=False, message=f'优化失败: {str(e)}')


@app.route('/api/db/archive', methods=['POST'])
def archive_logs():
    """执行数据归档"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    days_to_keep = int(data.get('days_to_keep', 90))

    try:
        from app import archive_old_logs
        result = archive_old_logs(days_to_keep=days_to_keep)

        if result.get('success'):
            return api_response(
                success=True,
                message=f"归档完成，共处理 {result.get('archived_count', 0)} 条记录",
                data=result
            )
        else:
            return api_response(success=False, message=result.get('error', '归档失败'))

    except Exception as e:
        return api_response(success=False, message=f'归档失败: {str(e)}')


@app.route('/api/db/cleanup-archive', methods=['POST'])
def cleanup_archive():
    """清理过期归档数据"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    max_age_days = int(data.get('max_age_days', 365))

    try:
        from app import cleanup_archive_tables
        result = cleanup_archive_tables(max_age_days=max_age_days)

        if result.get('success'):
            return api_response(
                success=True,
                message=f"已删除 {result.get('total_deleted', 0)} 条过期归档",
                data=result
            )
        else:
            return api_response(success=False, message=result.get('error', '清理失败'))

    except Exception as e:
        return api_response(success=False, message=f'清理失败: {str(e)}')


@app.route('/api/db/query-stats')
def get_query_stats():
    """获取查询性能统计"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import query_monitor
        stats = query_monitor.get_stats()
        return api_response(success=True, data=stats)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/db/reset-query-stats', methods=['POST'])
def reset_query_stats():
    """重置查询性能统计"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import query_monitor
        query_monitor.reset_stats()
        return api_response(success=True, message='查询统计已重置')
    except Exception as e:
        return api_response(success=False, message=str(e))


# ==================== 缓存管理API ====================

@app.route('/api/cache/stats')
def get_cache_stats():
    """获取缓存统计信息"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_cache
        cache = get_cache()
        stats = cache.get_stats()

        # 添加热点数据统计
        if 'hot_data_cache' in dir():
            from app import hot_data_cache
            if hot_data_cache:
                stats['hot_data'] = hot_data_cache.get_top_hot_data(10)

        return api_response(success=True, data=stats)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/cache/clear', methods=['POST'])
def clear_all_cache():
    """清空所有缓存"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_cache, hot_data_cache
        cache = get_cache()

        cleared = cache.clear()
        if hot_data_cache:
            hot_data_cache.clear_access_stats()

        return api_response(
            success=True,
            message=f'缓存已清空',
            data={'cleared': True}
        )
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/cache/invalidate', methods=['POST'])
def invalidate_cache_pattern():
    """批量清除匹配模式的缓存"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    pattern = data.get('pattern', '')

    if not pattern:
        return api_response(success=False, message='请提供pattern参数')

    try:
        from app import get_cache
        cache = get_cache()
        deleted_count = cache.invalidate_pattern(pattern)

        return api_response(
            success=True,
            message=f'已删除 {deleted_count} 个匹配缓存项',
            data={'deleted_count': deleted_count}
        )
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/cache/preview/cleanup', methods=['POST'])
def cleanup_preview_cache():
    """清理过期预览文件"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    days = int(data.get('days', 7))

    try:
        from app import preview_cache
        if preview_cache:
            deleted = preview_cache.clear_old_previews(days=days)
            return api_response(
                success=True,
                message=f'已清理 {deleted} 个过期预览文件',
                data={'deleted_count': deleted}
            )
        else:
            return api_response(success=False, message='预览缓存未初始化')
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/cache/hot-data')
def get_hot_data_stats():
    """获取热点数据统计"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import hot_data_cache
        if hot_data_cache:
            top_data = hot_data_cache.get_top_hot_data(20)
            return api_response(
                success=True,
                data={'hot_data': top_data, 'total_tracked': len(hot_data_cache.access_counts)}
            )
        else:
            return api_response(success=False, message='热点数据缓存未初始化')
    except Exception as e:
        return api_response(success=False, message=str(e))


# ==================== 文件存储优化API ====================

@app.route('/api/storage/info')
def get_storage_info():
    """获取存储系统信息"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_storage
        storage = get_storage()

        info = {
            'storage_type': storage.storage_type,
            'primary': str(type(storage.primary).__name__),
            'has_fallback': storage.fallback is not None,
            'chunk_temp_dir': str(storage.chunk_temp_dir)
        }

        if hasattr(storage, 'oss_storage') and storage.oss_storage:
            info['oss_available'] = storage.oss_storage._available

        return api_response(success=True, data=info)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/upload/chunk/session', methods=['POST'])
def create_chunk_upload_session():
    """创建分片上传会话"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_chunk_manager
        chunk_mgr = get_chunk_manager()

        data = request.get_json(silent=True) or {}
        file_id = data.get('file_id') or str(uuid.uuid4())
        filename = data.get('filename', 'unknown')
        total_size = int(data.get('total_size', 0))
        chunk_count = int(data.get('chunk_count', 1))
        file_hash = data.get('file_hash')

        session = chunk_mgr.create_session(
            file_id=file_id,
            filename=filename,
            total_size=total_size,
            chunk_count=chunk_count,
            file_hash=file_hash
        )

        return api_response(success=True, data=session)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/upload/chunk/<file_id>/<int:chunk_index>', methods=['POST'])
def upload_chunk(file_id, chunk_index):
    """上传单个分片"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_chunk_manager
        chunk_mgr = get_chunk_manager()

        # 获取分片数据
        if 'chunk' in request.files:
            chunk_data = request.files['chunk'].read()
        elif request.data:
            chunk_data = request.data
        else:
            return api_response(success=False, message='未找到分片数据')

        result = chunk_mgr.upload_chunk(file_id, chunk_index, chunk_data)
        return api_response(success=result['success'], data=result)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/upload/chunk/<file_id>/progress')
def get_chunk_upload_progress(file_id):
    """获取分片上传进度"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_chunk_manager
        chunk_mgr = get_chunk_manager()

        result = chunk_mgr.get_upload_progress(file_id)
        return api_response(success=result.get('success', True), data=result)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/upload/chunk/<file_id>/merge', methods=['POST'])
def merge_uploaded_chunks(file_id):
    """合并已上传的分片"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_chunk_manager
        chunk_mgr = get_chunk_manager()

        data = request.get_json(silent=True) or {}
        target_path = data.get('target_path')

        result = chunk_mgr.merge_chunks(file_id, target_path)
        return api_response(success=result['success'], data=result)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/upload/chunk/<file_id>/resume')
def resume_chunk_upload(file_id):
    """断点续传：获取上传状态"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_chunk_manager
        chunk_mgr = get_chunk_manager()

        result = chunk_mgr.resume_upload(file_id)
        return api_response(success=result.get('success', True), data=result)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/upload/chunk/<file_id>', methods=['DELETE'])
def cancel_chunk_upload(file_id):
    """取消分片上传"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import get_chunk_manager
        chunk_mgr = get_chunk_manager()

        result = chunk_mgr.cancel_upload(file_id)
        return api_response(success=result['success'], data=result)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/image/process', methods=['POST'])
def process_image():
    """图片处理（压缩/转换/缩放）"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import ImageProcessor

        data = request.get_json(silent=True) or {}
        image_path = data.get('image_path')

        if not image_path:
            # 如果提供了图片文件
            if 'image' in request.files:
                image_file = request.files['image']
                temp_path = UPLOAD_DIR / f"temp_{uuid.uuid4()}{Path(image_file.filename).suffix}"
                image_file.save(str(temp_path))

                options = {
                    'quality': int(data.get('quality', 85)),
                    'format': data.get('format'),
                    'max_width': int(data.get('max_width', 1920)),
                    'max_height': int(data.get('max_height', 1920)),
                    'thumbnail': data.get('thumbnail', False),
                    'thumbnail_size': tuple(map(int, data.get('thumbnail_size', '200,200').split(',')))
                    if data.get('thumbnail_size') else (200, 200)
                }

                result = ImageProcessor.process_image(temp_path, **options)

                # 清理临时文件
                if temp_path.exists():
                    temp_path.unlink()
            else:
                return api_response(success=False, message='请提供图片文件或路径')
        else:
            full_path = UPLOAD_DIR / image_path
            options = {
                'quality': int(data.get('quality', 85)),
                'format': data.get('format'),
                'max_width': int(data.get('max_width', 1920)),
                'max_height': int(data.get('max_height', 1920)),
                'thumbnail': data.get('thumbnail', False)
            }

            result = ImageProcessor.process_image(full_path, **options)

        return api_response(success=result.get('success', False), data=result)
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/image/thumbnail/<path:image_path>')
def generate_thumbnail(image_path):
    """生成并返回缩略图"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import ImageProcessor

        full_path = UPLOAD_DIR / image_path
        size = request.args.get('size', '200x200')
        width, height = map(int, size.split('x'))

        result = ImageProcessor.generate_thumbnail(full_path, (width, height))

        if result.get('success') and result.get('thumbnail_path'):
            thumb_path = Path(result['thumbnail_path'])
            return send_from_directory(thumb_path.parent, thumb_path.name)
        else:
            return jsonify(result), 400
    except Exception as e:
        return api_response(success=False, message=str(e))


@app.route('/api/storage/test-oss', methods=['POST'])
def test_oss_connection():
    """测试OSS连接（仅管理员）"""
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    try:
        from app import OSSStorage
        oss = OSSStorage()

        if oss._available:
            # 测试上传
            test_key = f"test/connection_test_{int(time.time())}.txt"
            oss.client.put_object(test_key, b"connection test")
            oss.client.delete_object(test_key)

            return api_response(
                success=True,
                message='OSS连接正常',
                data={
                    'bucket': oss.bucket_name,
                    'endpoint': oss.endpoint
                }
            )
        else:
            return api_response(success=False, message='OSS未配置或连接失败')
    except Exception as e:
        return api_response(success=False, message=f'OSS测试失败: {str(e)}')


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
    tmp_file_path = None
    try:
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                           (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('文件夹不存在或无权限')
            return redirect(url_for('folder_detail', folder_id=folder_id))
        
        from app import get_user_storage_usage
        storage_usage = get_user_storage_usage(session['user_id'])
        
        import tempfile
        fd, tmp_file_path = tempfile.mkstemp()
        try:
            file.save(tmp_file_path)
        finally:
            os.close(fd)
        
        file_size = os.path.getsize(tmp_file_path)
        
        if storage_usage['total_size'] + file_size > storage_usage['max_storage']:
            os.unlink(tmp_file_path)
            flash(f'存储空间不足！已使用 {storage_usage["total_size"] / (1024*1024):.2f}MB，剩余空间不足以存储此文件（{file_size / (1024*1024):.2f}MB）')
            return redirect(url_for('folder_detail', folder_id=folder_id))
        
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1]
        stored_name = f"{file_id}{ext}"
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
        import shutil
        shutil.move(tmp_file_path, file_path)
        tmp_file_path = None
        
        conn.execute('''INSERT INTO files (id, user_id, filename, stored_name, path, size, project_desc, folder_id, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                   (file_id, session['user_id'], file.filename, stored_name, file_path, file_size, 
                    description, folder_id))
        
        conn.commit()
        
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
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
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
    temp_files = []
    try:
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                           (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('文件夹不存在或无权限')
            return redirect(url_for('folder_detail', folder_id=folder_id))
        
        from app import get_user_storage_usage
        storage_usage = get_user_storage_usage(session['user_id'])
        
        uploaded_files_count = 0
        total_upload_size = 0
        
        import tempfile
        for file in files:
            if file.filename == '' or not hasattr(file, 'filename'):
                continue
            
            fd, tmp_path = tempfile.mkstemp()
            try:
                file.save(tmp_path)
            finally:
                os.close(fd)
            
            file_size = os.path.getsize(tmp_path)
            temp_files.append((tmp_path, file.filename, file_size))
            total_upload_size += file_size
        
        if storage_usage['total_size'] + total_upload_size > storage_usage['max_storage']:
            for tmp_path, _, _ in temp_files:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            flash(f'存储空间不足！已使用 {storage_usage["total_size"] / (1024*1024):.2f}MB，剩余空间不足以存储此文件夹（{total_upload_size / (1024*1024):.2f}MB）')
            return redirect(url_for('folder_detail', folder_id=folder_id))
        
        for tmp_path, relative_path, file_size in temp_files:
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(relative_path)[1]
            stored_name = f"{file_id}{ext}"
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
            import shutil
            shutil.move(tmp_path, file_path)
            
            conn.execute('''INSERT INTO files (id, user_id, filename, stored_name, path, size, project_name, project_desc, folder_id, created_at) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                       (file_id, session['user_id'], os.path.basename(relative_path), stored_name, file_path, file_size, 
                        relative_path, description, folder_id))
            
            uploaded_files_count += 1
        
        conn.commit()
        
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
        
        # 获取用户存储空间使用情况
        from app import get_user_storage_usage
        storage_usage = get_user_storage_usage(session['user_id'])
        
        return render_template('project_folders.html', 
                             username=session.get('username'), 
                             user=user, 
                             folders=folders,
                             storage_usage=storage_usage)
    finally:
        conn.close()

# 文件夹详情页面
@app.route('/folder/<folder_id>')
def folder_detail(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                            (folder_id, session['user_id'])).fetchone()
        if not folder:
            return page_error_response('project_folders', '文件夹不存在或无权限', 404)
        
        files = conn.execute('SELECT * FROM files WHERE folder_id = ?', (folder_id,)).fetchall()
        
        subfolders = conn.execute('SELECT * FROM folders WHERE parent_id = ? AND user_id = ?', 
                               (folder_id, session['user_id'])).fetchall()
        
        user_folders = conn.execute('SELECT id, name FROM folders WHERE user_id = ? AND id != ? ORDER BY name', 
                                  (session['user_id'], folder_id)).fetchall()
        
        return render_template('folder_detail.html', username=session.get('username'), user=user, folder=folder, files=files, subfolders=subfolders, user_folders=user_folders)
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
            # 更新访问计数
            conn.execute('UPDATE files SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?', (file['id'],))
            conn.commit()
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
        
        # 更新访问计数
        conn.execute('UPDATE files SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?', (file_id,))
        conn.commit()
        
        # 解析dkfile字段
        item_dict = dict(item)
        item_dict['dkfile'] = json.loads(item_dict['dkfile'] if item_dict['dkfile'] else '{}')
        
        return render_template('detail.html', username=session.get('username'), item=item_dict)
    finally:
        conn.close()

# 删除文件（移动到回收站）
@app.route('/file/<file_id>/delete', methods=['POST'])
@app.route('/delete-file/<file_id>', methods=['POST'])
def file_delete(file_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    referrer = request.headers.get('Referer')
    
    conn = get_db()
    try:
        current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        is_admin = current_user and current_user['role'] == 'admin'
        
        file = conn.execute('SELECT * FROM files WHERE id = ? AND (user_id = ? OR user_id = "default_user")', 
                           (file_id, session['user_id'])).fetchone()
        if not file:
            flash('文件不存在或无权限')
            return redirect(url_for('index'))
        
        if file['user_id'] == 'default_user' and not is_admin:
            flash('无权限删除首页文件')
            return redirect(url_for('index'))
        
        if file['user_id'] != session['user_id'] and file['user_id'] != 'default_user':
            flash('无权限删除此文件')
            return redirect(url_for('index'))
        
        # 移动文件到回收站而不是直接删除
        trash_id = str(uuid.uuid4())
        
        folder_name = None
        if file['folder_id']:
            folder = conn.execute('SELECT name FROM folders WHERE id = ?', (file['folder_id'],)).fetchone()
            folder_name = folder['name'] if folder else None
        
        from datetime import datetime, timedelta
        expire_at = datetime.now() + timedelta(days=30)
        
        conn.execute('''
            INSERT INTO trash (id, file_id, user_id, filename, stored_name, file_path, 
                             file_size, file_type, folder_id, original_folder_name, deleted_at, expire_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (trash_id, file_id, session['user_id'], file['filename'], file['stored_name'],
              file['path'], file['size'], file['filename'].split('.')[-1] if '.' in file['filename'] else '',
              file['folder_id'], folder_name, expire_at))
        
        conn.execute('UPDATE files SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ?', (file_id,))
        
        local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn.execute('''INSERT INTO operation_logs (user_id, action, target_id, target_type, message, details, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                   (session['user_id'], 'trash', file_id, 'file', '文件移至回收站', f'文件名: {file["filename"]}', local_time))
        
        conn.commit()
        
        flash('文件已移至回收站')
        
        if referrer and 'folder' in referrer:
            folder_id = referrer.split('/')[-1]
            return redirect(url_for('folder_detail', folder_id=folder_id))
        elif referrer and 'user_center' in referrer:
            return redirect(url_for('user_center'))
        else:
            return redirect(url_for('index'))
    except Exception as e:
        conn.rollback()
        flash(f'删除文件失败: {str(e)}')
        
        if referrer and 'folder' in referrer:
            folder_id = referrer.split('/')[-1]
            return redirect(url_for('folder_detail', folder_id=folder_id))
        elif referrer and 'user_center' in referrer:
            return redirect(url_for('user_center'))
        else:
            return redirect(url_for('index'))
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

# 权限管理页面
@app.route('/permission-management')
def permission_management():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not current_user or current_user['role'] != 'admin':
            flash('无权限访问此页面')
            return redirect(url_for('user_center'))
        
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
    
    conn = get_db()
    try:
        current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'success': False, 'message': '无权限'}), 403
        
        if user_id == session['user_id']:
            return jsonify({'success': False, 'message': '不能修改自己的角色'}), 400
        
        new_role = request.form.get('role')
        if new_role not in ['user', 'admin']:
            return jsonify({'success': False, 'message': '无效的角色'}), 400
        
        # 检查是否为特定管理员账号
        if current_user['email'] != 'yhz2024_2024@qq.com':
            return jsonify({'success': False, 'message': '只有特定管理员账号才能修改其他用户的角色'}), 403
        
        # 检查被修改的用户是否为管理员
        target_user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if target_user and target_user['role'] == 'admin':
            return jsonify({'success': False, 'message': '不能修改管理员的角色'}), 400
        
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
    
    conn = get_db()
    try:
        current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'success': False, 'message': '无权限'}), 403
        
        if user_id == session['user_id']:
            return jsonify({'success': False, 'message': '不能删除自己'}), 400
        
        # 检查是否为特定管理员账号
        if current_user['email'] != 'yhz2024_2024@qq.com':
            return jsonify({'success': False, 'message': '只有特定管理员账号才能删除其他用户'}), 403
        
        # 检查被删除的用户是否为管理员
        target_user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if target_user and target_user['role'] == 'admin':
            return jsonify({'success': False, 'message': '不能删除管理员'}), 400
        
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': '用户删除成功'})
    finally:
        conn.close()


# File Share Functions

# Generate share link
@app.route('/api/share-file', methods=['POST'])
def share_file():
    if 'user_id' not in session:
        return api_response(success=False, message='Please login first', code=401)
    
    data = request.get_json()
    file_id = data.get('file_id')
    expires_hours = data.get('expires_hours', 24)
    
    if not file_id:
        return api_response(success=False, message='File ID is required', code=400)
    
    conn = get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
        if not file:
            return api_response(success=False, message='File not found', code=404)
        
        import secrets
        share_code = secrets.token_urlsafe(8)
        share_id = str(uuid.uuid4())
        
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(hours=expires_hours)
        
        conn.execute('''INSERT INTO file_shares (id, file_id, user_id, share_code, expires_at)
                       VALUES (?, ?, ?, ?, ?)''',
                    (share_id, file_id, session['user_id'], share_code, expires_at))
        conn.commit()
        
        share_url = url_for('shared_file', share_code=share_code, _external=True)
        
        return api_response(success=True, message='Share link generated successfully', data={
            'share_url': share_url,
            'share_code': share_code,
            'expires_at': expires_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'Failed to generate share link: {str(e)}', code=500)
    finally:
        conn.close()

# Access shared file page
@app.route('/s/<share_code>')
def shared_file(share_code):
    conn = get_db()
    try:
        share = conn.execute('''SELECT fs.*, f.filename, f.stored_name, f.size, f.project_name, f.project_desc, u.username
                              FROM file_shares fs
                              JOIN files f ON fs.file_id = f.id
                              JOIN users u ON fs.user_id = u.id
                              WHERE fs.share_code = ?''', (share_code,)).fetchone()
        
        if not share:
            return render_template('share_error.html', error='Share link does not exist or has expired')
        
        from datetime import datetime
        if share['expires_at']:
            expires_at = datetime.fromisoformat(str(share['expires_at']))
            if datetime.now() > expires_at:
                return render_template('share_error.html', error='Share link has expired')
        
        conn.execute('UPDATE file_shares SET access_count = access_count + 1 WHERE share_code = ?', (share_code,))
        conn.commit()
        
        return render_template('shared_file.html',
                             share=share,
                             file=share)
    finally:
        conn.close()

# Download shared file
@app.route('/download-shared/<share_code>')
def download_shared_file(share_code):
    conn = get_db()
    try:
        share = conn.execute('''SELECT fs.*, f.stored_name, f.filename
                              FROM file_shares fs
                              JOIN files f ON fs.file_id = f.id
                              WHERE fs.share_code = ?''', (share_code,)).fetchone()
        
        if not share:
            flash('Share link does not exist or has expired')
            return redirect(url_for('index'))
        
        from datetime import datetime
        if share['expires_at']:
            expires_at = datetime.fromisoformat(str(share['expires_at']))
            if datetime.now() > expires_at:
                flash('Share link has expired')
                return redirect(url_for('index'))
        
        from flask import send_from_directory
        upload_folder = app.config['UPLOAD_FOLDER']
        return send_from_directory(upload_folder, share['stored_name'], 
                                 as_attachment=True, 
                                 download_name=share['filename'])
    finally:
        conn.close()

# Batch upload files
@app.route('/batch-upload/<folder_id>', methods=['POST'])
def batch_upload_files(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    files = request.files.getlist('files')
    description = request.form.get('description', '')
    
    if not files or files[0].filename == '':
        flash('请选择文件')
        return redirect(url_for('folder_detail', folder_id=folder_id))
    
    conn = get_db()
    try:
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                           (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('文件夹不存在或无权限')
            return redirect(url_for('folder_detail', folder_id=folder_id))
        
        from app import get_user_storage_usage
        storage_usage = get_user_storage_usage(session['user_id'])
        
        uploaded_count = 0
        total_size = 0
        
        for file in files:
            if file.filename == '':
                continue
            
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(file.filename)[1]
            stored_name = f"{file_id}{ext}"
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
            file.save(file_path)
            
            file_size = os.path.getsize(file_path)
            total_size += file_size
            
            conn.execute('''INSERT INTO files (id, user_id, filename, stored_name, path, size, project_desc, folder_id, created_at) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                       (file_id, session['user_id'], file.filename, stored_name, file_path, file_size, 
                        description, folder_id))
            
            uploaded_count += 1
        
        conn.commit()
        
        log_message(
            log_type='operation',
            log_level='INFO',
            message='批量上传文件',
            user_id=session['user_id'],
            action='upload',
            target_id=folder_id,
            target_type='folder',
            details=f'上传文件数量: {uploaded_count}, 总大小: {total_size} bytes',
            request=request
        )
        
        flash(f'成功上传 {uploaded_count} 个文件')
    except Exception as e:
        conn.rollback()
        flash(f'上传失败: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('folder_detail', folder_id=folder_id))

# Batch download files as ZIP
@app.route('/batch-download', methods=['POST'])
def batch_download():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    data = request.get_json()
    file_ids = data.get('file_ids', [])
    
    if not file_ids:
        return api_response(success=False, message='请选择要下载的文件', code=400)
    
    conn = get_db()
    try:
        import zipfile
        import io
        from flask import send_file
        
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_id in file_ids:
                file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', 
                                  (file_id, session['user_id'])).fetchone()
                if file and os.path.exists(file['path']):
                    zf.write(file['path'], file['filename'])
        
        memory_file.seek(0)
        
        log_message(
            log_type='operation',
            log_level='INFO',
            message='批量下载文件',
            user_id=session['user_id'],
            action='download',
            target_type='file',
            details=f'下载文件数量: {len(file_ids)}',
            request=request
        )
        
        return send_file(
            memory_file,
            download_name=f'files_{int(datetime.now().timestamp())}.zip',
            as_attachment=True,
            mimetype='application/zip'
        )
    except Exception as e:
        return api_response(success=False, message=f'下载失败: {str(e)}', code=500)
    finally:
        conn.close()

# Batch move files
@app.route('/batch-move', methods=['POST'])
def batch_move():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    data = request.get_json()
    file_ids = data.get('file_ids', [])
    target_folder_id = data.get('target_folder_id')
    
    if not file_ids:
        return api_response(success=False, message='请选择要移动的文件', code=400)
    
    conn = get_db()
    try:
        if target_folder_id:
            target_folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', 
                                       (target_folder_id, session['user_id'])).fetchone()
            if not target_folder:
                return api_response(success=False, message='目标文件夹不存在或无权限', code=404)
        
        moved_count = 0
        for file_id in file_ids:
            file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', 
                              (file_id, session['user_id'])).fetchone()
            if file:
                conn.execute('UPDATE files SET folder_id = ? WHERE id = ?', 
                           (target_folder_id, file_id))
                moved_count += 1
        
        conn.commit()
        
        log_message(
            log_type='operation',
            log_level='INFO',
            message='批量移动文件',
            user_id=session['user_id'],
            action='move',
            target_type='file',
            details=f'移动文件数量: {moved_count}, 目标文件夹: {target_folder_id or "根目录"}',
            request=request
        )
        
        return api_response(success=True, message=f'成功移动 {moved_count} 个文件')
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'移动失败: {str(e)}', code=500)
    finally:
        conn.close()

# ==================== 回收站功能 ====================

# 回收站页面
@app.route('/trash')
def trash():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        
        trash_items = conn.execute('''
            SELECT t.*, 
                   (julianday(t.expire_at) - julianday('now')) * 24 as remaining_hours
            FROM trash t
            WHERE t.user_id = ?
            ORDER BY t.deleted_at DESC
        ''', (session['user_id'],)).fetchall()
        
        total_size = sum(item['file_size'] or 0 for item in trash_items)
        
        return render_template('trash.html', username=session.get('username'), user=user, trash_items=trash_items, total_size=total_size)
    finally:
        conn.close()

# 移动文件到回收站
@app.route('/api/trash/move', methods=['POST'])
def move_to_trash():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    file_id = request.form.get('file_id') or request.get_json().get('file_id')
    
    if not file_id:
        return api_response(success=False, message='文件ID不能为空', code=400)
    
    conn = get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', 
                          (file_id, session['user_id'])).fetchone()
        
        if not file:
            return api_response(success=False, message='文件不存在或无权限', code=404)
        
        trash_id = str(uuid.uuid4())
        
        folder_name = None
        if file['folder_id']:
            folder = conn.execute('SELECT name FROM folders WHERE id = ?', (file['folder_id'],)).fetchone()
            folder_name = folder['name'] if folder else None
        
        from datetime import datetime, timedelta
        expire_at = datetime.now() + timedelta(days=30)
        
        conn.execute('''
            INSERT INTO trash (id, file_id, user_id, filename, stored_name, file_path, 
                             file_size, file_type, folder_id, original_folder_name, expire_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trash_id, file_id, session['user_id'], file['filename'], file['stored_name'],
              file['path'], file['size'], file['filename'].split('.')[-1] if '.' in file['filename'] else '',
              file['folder_id'], folder_name, expire_at))
        
        conn.execute('UPDATE files SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ?', (file_id,))
        
        conn.commit()
        
        log_message(
            log_type='operation',
            log_level='INFO',
            message='文件移至回收站',
            user_id=session['user_id'],
            action='trash',
            target_id=file_id,
            target_type='file',
            details=f'文件名: {file["filename"]}',
            request=request
        )
        
        return api_response(success=True, message='文件已移至回收站')
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'操作失败: {str(e)}', code=500)
    finally:
        conn.close()

# 从回收站恢复文件
@app.route('/api/trash/restore', methods=['POST'])
def restore_from_trash():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    data = request.get_json() if request.is_json else request.form
    trash_id = data.get('trash_id')
    
    if not trash_id:
        return api_response(success=False, message='回收站记录ID不能为空', code=400)
    
    conn = get_db()
    try:
        trash_item = conn.execute('SELECT * FROM trash WHERE id = ? AND user_id = ?', 
                                 (trash_id, session['user_id'])).fetchone()
        
        if not trash_item:
            return api_response(success=False, message='回收站记录不存在', code=404)
        
        if trash_item['folder_id']:
            folder = conn.execute('SELECT id FROM folders WHERE id = ? AND user_id = ?', 
                                (trash_item['folder_id'], session['user_id'])).fetchone()
            if not folder:
                conn.execute('UPDATE files SET is_deleted = 0, deleted_at = NULL, folder_id = NULL WHERE id = ?', 
                           (trash_item['file_id'],))
            else:
                conn.execute('UPDATE files SET is_deleted = 0, deleted_at = NULL WHERE id = ?', 
                           (trash_item['file_id'],))
        else:
            conn.execute('UPDATE files SET is_deleted = 0, deleted_at = NULL WHERE id = ?', 
                       (trash_item['file_id'],))
        
        conn.execute('DELETE FROM trash WHERE id = ?', (trash_id,))
        
        conn.commit()
        
        log_message(
            log_type='operation',
            log_level='INFO',
            message='从回收站恢复文件',
            user_id=session['user_id'],
            action='restore',
            target_id=trash_item['file_id'],
            target_type='file',
            details=f'文件名: {trash_item["filename"]}',
            request=request
        )
        
        return api_response(success=True, message='文件已恢复')
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'恢复失败: {str(e)}', code=500)
    finally:
        conn.close()

# 彻底删除文件
@app.route('/api/trash/delete-permanent', methods=['POST'])
def delete_permanent():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    data = request.get_json() if request.is_json else request.form
    trash_id = data.get('trash_id')
    
    if not trash_id:
        return api_response(success=False, message='回收站记录ID不能为空', code=400)
    
    conn = get_db()
    try:
        trash_item = conn.execute('SELECT * FROM trash WHERE id = ? AND user_id = ?', 
                                 (trash_id, session['user_id'])).fetchone()
        
        if not trash_item:
            return api_response(success=False, message='回收站记录不存在', code=404)
        
        if os.path.exists(trash_item['file_path']):
            os.unlink(trash_item['file_path'])
        
        conn.execute('DELETE FROM files WHERE id = ?', (trash_item['file_id'],))
        conn.execute('DELETE FROM trash WHERE id = ?', (trash_id,))
        
        conn.commit()
        
        log_message(
            log_type='operation',
            log_level='INFO',
            message='彻底删除文件',
            user_id=session['user_id'],
            action='delete_permanent',
            target_id=trash_item['file_id'],
            target_type='file',
            details=f'文件名: {trash_item["filename"]}',
            request=request
        )
        
        return api_response(success=True, message='文件已彻底删除')
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'删除失败: {str(e)}', code=500)
    finally:
        conn.close()

# 清空回收站
@app.route('/api/trash/empty', methods=['POST'])
def empty_trash():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        trash_items = conn.execute('SELECT * FROM trash WHERE user_id = ?', 
                                  (session['user_id'],)).fetchall()
        
        deleted_count = 0
        for item in trash_items:
            if os.path.exists(item['file_path']):
                os.unlink(item['file_path'])
            conn.execute('DELETE FROM files WHERE id = ?', (item['file_id'],))
            deleted_count += 1
        
        conn.execute('DELETE FROM trash WHERE user_id = ?', (session['user_id'],))
        
        conn.commit()
        
        log_message(
            log_type='operation',
            log_level='INFO',
            message='清空回收站',
            user_id=session['user_id'],
            action='empty_trash',
            target_type='trash',
            details=f'删除文件数量: {deleted_count}',
            request=request
        )
        
        return api_response(success=True, message=f'回收站已清空，共删除 {deleted_count} 个文件')
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'清空失败: {str(e)}', code=500)
    finally:
        conn.close()

# 批量恢复
@app.route('/api/trash/batch-restore', methods=['POST'])
def batch_restore():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    data = request.get_json() if request.is_json else request.form
    trash_ids = data.get('trash_ids', [])
    
    if not trash_ids:
        return api_response(success=False, message='请选择要恢复的文件', code=400)
    
    conn = get_db()
    try:
        restored_count = 0
        for trash_id in trash_ids:
            trash_item = conn.execute('SELECT * FROM trash WHERE id = ? AND user_id = ?', 
                                     (trash_id, session['user_id'])).fetchone()
            if trash_item:
                conn.execute('UPDATE files SET is_deleted = 0, deleted_at = NULL WHERE id = ?', 
                           (trash_item['file_id'],))
                conn.execute('DELETE FROM trash WHERE id = ?', (trash_id,))
                restored_count += 1
        
        conn.commit()
        
        return api_response(success=True, message=f'成功恢复 {restored_count} 个文件')
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'恢复失败: {str(e)}', code=500)
    finally:
        conn.close()

# 批量彻底删除
@app.route('/api/trash/batch-delete', methods=['POST'])
def batch_delete_permanent():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    data = request.get_json() if request.is_json else request.form
    trash_ids = data.get('trash_ids', [])
    
    if not trash_ids:
        return api_response(success=False, message='请选择要删除的文件', code=400)
    
    conn = get_db()
    try:
        deleted_count = 0
        for trash_id in trash_ids:
            trash_item = conn.execute('SELECT * FROM trash WHERE id = ? AND user_id = ?', 
                                     (trash_id, session['user_id'])).fetchone()
            if trash_item:
                if os.path.exists(trash_item['file_path']):
                    os.unlink(trash_item['file_path'])
                conn.execute('DELETE FROM files WHERE id = ?', (trash_item['file_id'],))
                conn.execute('DELETE FROM trash WHERE id = ?', (trash_id,))
                deleted_count += 1
        
        conn.commit()
        
        return api_response(success=True, message=f'成功删除 {deleted_count} 个文件')
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'删除失败: {str(e)}', code=500)
    finally:
        conn.close()

# ==================== 存储空间可视化功能 ====================

@app.route('/api/storage-stats')
def api_storage_stats():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        user_id = session['user_id']
        
        type_stats = conn.execute('''
            SELECT 
                CASE 
                    WHEN filename LIKE '%.html' OR filename LIKE '%.htm' THEN 'HTML'
                    WHEN filename LIKE '%.css' THEN 'CSS'
                    WHEN filename LIKE '%.js' THEN 'JavaScript'
                    WHEN filename LIKE '%.py' THEN 'Python'
                    WHEN filename LIKE '%.jpg' OR filename LIKE '%.jpeg' OR filename LIKE '%.png' OR filename LIKE '%.gif' OR filename LIKE '%.webp' OR filename LIKE '%.svg' THEN '图片'
                    WHEN filename LIKE '%.mp4' OR filename LIKE '%.avi' OR filename LIKE '%.mov' OR filename LIKE '%.webm' OR filename LIKE '%.mkv' THEN '视频'
                    WHEN filename LIKE '%.mp3' OR filename LIKE '%.wav' OR filename LIKE '%.flac' OR filename LIKE '%.aac' THEN '音频'
                    WHEN filename LIKE '%.pdf' THEN 'PDF'
                    WHEN filename LIKE '%.doc' OR filename LIKE '%.docx' THEN 'Word'
                    WHEN filename LIKE '%.xls' OR filename LIKE '%.xlsx' THEN 'Excel'
                    WHEN filename LIKE '%.ppt' OR filename LIKE '%.pptx' THEN 'PPT'
                    WHEN filename LIKE '%.zip' OR filename LIKE '%.rar' OR filename LIKE '%.7z' OR filename LIKE '%.tar' OR filename LIKE '%.gz' THEN '压缩包'
                    ELSE '其他'
                END as file_type,
                COUNT(*) as count,
                SUM(size) as total_size
            FROM files 
            WHERE user_id = ? AND (is_deleted = 0 OR is_deleted IS NULL)
            GROUP BY file_type
            ORDER BY total_size DESC
        ''', (user_id,)).fetchall()
        
        large_files = conn.execute('''
            SELECT id, filename, size, created_at, folder_id
            FROM files 
            WHERE user_id = ? AND (is_deleted = 0 OR is_deleted IS NULL)
            ORDER BY size DESC
            LIMIT 10
        ''', (user_id,)).fetchall()
        
        large_files_list = []
        for f in large_files:
            folder_name = '根目录'
            if f['folder_id']:
                folder = conn.execute('SELECT name FROM folders WHERE id = ?', (f['folder_id'],)).fetchone()
                folder_name = folder['name'] if folder else '根目录'
            large_files_list.append({
                'id': f['id'],
                'filename': f['filename'],
                'size': f['size'],
                'created_at': f['created_at'],
                'folder_name': folder_name
            })
        
        from datetime import datetime, timedelta
        trend_data = []
        for i in range(30, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            result = conn.execute('''
                SELECT COALESCE(SUM(size), 0) as total_size
                FROM files 
                WHERE user_id = ? 
                AND (is_deleted = 0 OR is_deleted IS NULL)
                AND DATE(created_at) <= ?
            ''', (user_id, date)).fetchone()
            trend_data.append({
                'date': date,
                'size': result['total_size'] if result else 0
            })
        
        total_stats = conn.execute('''
            SELECT 
                COUNT(*) as total_files,
                COALESCE(SUM(size), 0) as total_size
            FROM files 
            WHERE user_id = ? AND (is_deleted = 0 OR is_deleted IS NULL)
        ''', (user_id,)).fetchone()
        
        folder_stats = conn.execute('''
            SELECT 
                COALESCE(f.name, '根目录') as folder_name,
                COUNT(fi.id) as file_count,
                COALESCE(SUM(fi.size), 0) as total_size
            FROM files fi
            LEFT JOIN folders f ON fi.folder_id = f.id
            WHERE fi.user_id = ? AND (fi.is_deleted = 0 OR fi.is_deleted IS NULL)
            GROUP BY fi.folder_id
            ORDER BY total_size DESC
        ''', (user_id,)).fetchall()
        
        return api_response(success=True, data={
            'type_stats': [dict(row) for row in type_stats],
            'large_files': large_files_list,
            'trend_data': trend_data,
            'total_stats': {
                'total_files': total_stats['total_files'] if total_stats else 0,
                'total_size': total_stats['total_size'] if total_stats else 0
            },
            'folder_stats': [dict(row) for row in folder_stats]
        })
    except Exception as e:
        return api_response(success=False, message=f'获取统计数据失败: {str(e)}', code=500)
    finally:
        conn.close()

# ==================== 文件标签系统增强功能 ====================

# API: 获取用户的所有标签（带统计信息）
@app.route('/api/tags/stats')
def api_get_tags_with_stats():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        user_id = session['user_id']
        
        rows = conn.execute('''
            SELECT t.id, t.name, t.created_at, COUNT(ft.file_id) as file_count
            FROM tags t
            LEFT JOIN file_tags ft ON t.id = ft.tag_id
            WHERE t.user_id = ?
            GROUP BY t.id, t.name, t.created_at
            ORDER BY file_count DESC, t.name ASC
        ''', (user_id,)).fetchall()
        
        tags = [{
            'id': row['id'],
            'name': row['name'],
            'created_at': row['created_at'],
            'file_count': row['file_count']
        } for row in rows]
        
        return api_response(success=True, data={'tags': tags})
    except Exception as e:
        return api_response(success=False, message=f'获取标签统计失败: {str(e)}', code=500)
    finally:
        conn.close()

# API: 搜索标签（模糊搜索）
@app.route('/api/tags/search')
def api_search_tags():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 1:
        return api_response(success=False, message='搜索关键词不能为空')
    
    conn = get_db()
    try:
        user_id = session['user_id']
        
        rows = conn.execute('''
            SELECT t.id, t.name, t.created_at, COUNT(ft.file_id) as file_count
            FROM tags t
            LEFT JOIN file_tags ft ON t.id = ft.tag_id
            WHERE t.user_id = ? AND t.name LIKE ?
            GROUP BY t.id, t.name, t.created_at
            ORDER BY file_count DESC
            LIMIT 20
        ''', (user_id, f'%{query}%')).fetchall()
        
        tags = [{
            'id': row['id'],
            'name': row['name'],
            'created_at': row['created_at'],
            'file_count': row['file_count']
        } for row in rows]
        
        return api_response(success=True, data={'tags': tags, 'query': query})
    except Exception as e:
        return api_response(success=False, message=f'搜索失败: {str(e)}', code=500)
    finally:
        conn.close()

# API: 按标签筛选文件
@app.route('/api/files/by-tag/<tag_id>')
def api_get_files_by_tag(tag_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        user_id = session['user_id']
        
        files = conn.execute('''
            SELECT f.id, f.filename, f.size, f.created_at, f.path, 
                   f.stored_name, f.folder_id, f.view_count,
                   COALESCE(f.is_deleted, 0) as is_deleted
            FROM files f
            JOIN file_tags ft ON f.id = ft.file_id
            WHERE ft.tag_id = ? AND f.user_id = ? AND (f.is_deleted = 0 OR f.is_deleted IS NULL)
            ORDER BY f.created_at DESC
        ''', (tag_id, user_id)).fetchall()
        
        result_files = []
        for f in files:
            # 获取文件标签
            tags = []
            tag_rows = conn.execute('''SELECT t.* FROM tags t 
                                     JOIN file_tags ft ON t.id = ft.tag_id 
                                     WHERE ft.file_id = ?''', (f['id'],)).fetchall()
            for tr in tag_rows:
                tags.append({'id': tr['id'], 'name': tr['name']})
            
            result_files.append({
                'id': f['id'],
                'filename': f['filename'],
                'size': f['size'],
                'created_at': f['created_at'],
                'path': f['path'],
                'stored_name': f['stored_name'],
                'folder_id': f['folder_id'],
                'view_count': f['view_count'] if f['view_count'] else 0,
                'tags': tags
            })
        
        # 获取标签信息
        tag_info = conn.execute('SELECT * FROM tags WHERE id = ?', (tag_id,)).fetchone()
        
        return api_response(success=True, data={
            'files': result_files,
            'tag_info': {
                'id': tag_info['id'],
                'name': tag_info['name']
            } if tag_info else None,
            'total': len(result_files)
        })
    except Exception as e:
        return api_response(success=False, message=f'获取文件列表失败: {str(e)}', code=500)
    finally:
        conn.close()

# API: 标签云数据
@app.route('/api/tags/cloud')
def api_tags_cloud():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        user_id = session['user_id']
        
        rows = conn.execute('''
            SELECT t.id, t.name, COUNT(ft.file_id) as weight
            FROM tags t
            LEFT JOIN file_tags ft ON t.id = ft.tag_id
            WHERE t.user_id = ?
            GROUP BY t.id, t.name
            HAVING weight > 0
            ORDER BY weight DESC
            LIMIT 50
        ''', (user_id,)).fetchall()
        
        cloud_data = []
        max_weight = 0
        min_weight = float('inf')
        
        for row in rows:
            weight = row['weight']
            if weight > max_weight:
                max_weight = weight
            if weight < min_weight:
                min_weight = weight
        
        for row in rows:
            # 计算字体大小（基于权重）
            if max_weight > min_weight:
                normalized = (row['weight'] - min_weight) / (max_weight - min_weight)
            else:
                normalized = 0.5
            
            cloud_data.append({
                'id': row['id'],
                'name': row['name'],
                'count': row['weight'],
                'size': int(12 + normalized * 24),  # 字体大小范围：12-36px
                'color_index': hash(row['name']) % 10  # 用于颜色分配
            })
        
        return api_response(success=True, data={
            'cloud': cloud_data,
            'total_tags': len(cloud_data),
            'total_files_tagged': sum(item['count'] for item in cloud_data)
        })
    except Exception as e:
        return api_response(success=False, message=f'获取标签云失败: {str(e)}', code=500)
    finally:
        conn.close()

# API: 标签统计概览
@app.route('/api/tags/overview')
def api_tags_overview():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        user_id = session['user_id']
        
        # 总体统计
        total_stats = conn.execute('''
            SELECT 
                COUNT(DISTINCT t.id) as total_tags,
                COUNT(DISTINCT ft.file_id) as tagged_files,
                COUNT(ft.id) as total_assignments
            FROM tags t
            LEFT JOIN file_tags ft ON t.id = ft.tag_id
            WHERE t.user_id = ?
        ''', (user_id,)).fetchone()
        
        # 最热门标签 TOP 10
        top_tags = conn.execute('''
            SELECT t.name, COUNT(ft.file_id) as count
            FROM tags t
            LEFT JOIN file_tags ft ON t.id = ft.tag_id
            WHERE t.user_id = ?
            GROUP BY t.id, t.name
            ORDER BY count DESC
            LIMIT 10
        ''', (user_id,)).fetchall()
        
        # 未打标签的文件数量
        untagged_count = conn.execute('''
            SELECT COUNT(*) as count
            FROM files f
            LEFT JOIN file_tags ft ON f.id = ft.file_id
            WHERE f.user_id = ? AND (f.is_deleted = 0 OR f.is_deleted IS NULL)
            AND ft.tag_id IS NULL
        ''', (user_id,)).fetchone()['count']
        
        # 最近使用的标签
        recent_tags = conn.execute('''
            SELECT DISTINCT t.id, t.name, t.created_at
            FROM tags t
            JOIN file_tags ft ON t.id = ft.tag_id
            WHERE t.user_id = ?
            ORDER BY t.created_at DESC
            LIMIT 5
        ''', (user_id,)).fetchall()
        
        return api_response(success=True, data={
            'total_tags': total_stats['total_tags'] if total_stats else 0,
            'tagged_files': total_stats['tagged_files'] if total_stats else 0,
            'total_assignments': total_stats['total_assignments'] if total_stats else 0,
            'untagged_files': untagged_count,
            'top_tags': [{'name': r['name'], 'count': r['count']} for r in top_tags],
            'recent_tags': [{'id': r['id'], 'name': r['name']} for r in recent_tags]
        })
    except Exception as e:
        return api_response(success=False, message=f'获取统计概览失败: {str(e)}', code=500)
    finally:
        conn.close()

# API: 自动推荐标签（基于文件内容）
@app.route('/api/files/<file_id>/recommend-tags')
def api_recommend_tags(file_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        user_id = session['user_id']
        
        # 获取文件信息
        file_info = conn.execute('''
            SELECT id, filename, path, size, created_at
            FROM files 
            WHERE id = ? AND user_id = ?
        ''', (file_id, user_id)).fetchone()
        
        if not file_info:
            return api_response(success=False, message='文件不存在')
        
        filename = file_info['filename'].lower()
        ext = filename.split('.')[-1] if '.' in filename else ''
        
        # 基于文件扩展名的推荐规则
        extension_rules = {
            'html': ['网页', '前端', 'HTML', '网页开发'],
            'htm': ['网页', '前端', 'HTML'],
            'css': ['样式', 'CSS', '前端', '设计'],
            'js': ['JavaScript', '脚本', '前端', '交互'],
            'py': ['Python', '脚本', '后端', '代码'],
            'java': ['Java', '后端', '代码'],
            'php': ['PHP', '后端', '网站'],
            'sql': ['数据库', 'SQL', '查询'],
            'json': ['配置', 'JSON', '数据'],
            'xml': ['配置', 'XML', '数据'],
            'md': ['文档', 'Markdown', '笔记'],
            'txt': ['文本', '文档', '日志'],
            'pdf': ['PDF', '文档', '阅读'],
            'doc': ['Word', '文档', '办公'],
            'docx': ['Word', '文档', '办公'],
            'xls': ['Excel', '表格', '数据'],
            'xlsx': ['Excel', '表格', '数据'],
            'ppt': ['PPT', '演示', '办公'],
            'pptx': ['PPT', '演示', '办公'],
            'jpg': ['图片', '照片', '素材'],
            'jpeg': ['图片', '照片', '素材'],
            'png': ['图片', '图标', '素材'],
            'gif': ['GIF', '动图', '表情'],
            'svg': ['SVG', '矢量图', '图标'],
            'mp4': ['视频', '多媒体'],
            'mp3': ['音频', '音乐'],
            'zip': ['压缩包', '归档'],
            'rar': ['压缩包', '归档'],
            '7z': ['压缩包', '归档'],
        }
        
        recommended = set()
        
        # 1. 基于扩展名推荐
        if ext in extension_rules:
            for tag_name in extension_rules[ext]:
                recommended.add(tag_name)
        
        # 2. 基于文件名关键词推荐
        keywords_map = {
            'index': ['首页', '主页', '入口'],
            'main': ['主程序', '主要', '核心'],
            'config': ['配置', '设置'],
            'test': ['测试', '验证'],
            'demo': ['示例', '演示', 'Demo'],
            'backup': ['备份', '存档'],
            'log': ['日志', '记录'],
            'report': ['报告', '报表'],
            'data': ['数据', '资料'],
            'temp': ['临时', '缓存'],
            'cache': ['缓存', '临时'],
            'readme': ['说明', '文档', 'ReadMe'],
            'install': ['安装', '部署'],
            'update': ['更新', '升级'],
            'fix': ['修复', '补丁'],
            'bug': ['Bug', '问题', '修复'],
            'feature': ['功能', '特性', '新功能'],
            'api': ['API', '接口'],
            'auth': ['认证', '授权', '登录'],
            'user': ['用户', '账户'],
            'admin': ['管理', '后台'],
            'login': ['登录', '认证'],
            'register': ['注册', '账号'],
        }
        
        for keyword, tags in keywords_map.items():
            if keyword in filename:
                for tag_name in tags:
                    recommended.add(tag_name)
        
        # 3. 基于文件大小推荐
        size = file_info['size']
        if size > 100 * 1024 * 1024:  # > 100MB
            recommended.add('大文件')
        elif size > 10 * 1024 * 1024:  # > 10MB
            recommended.add('中等大小')
        elif size < 1024:  # < 1KB
            recommended.add('小文件')
        
        # 4. 基于创建时间推荐
        from datetime import datetime, timedelta
        created_at = file_info['created_at']
        if created_at:
            try:
                file_date = datetime.strptime(created_at[:19], '%Y-%m-%d %H:%M:%S') if 'T' not in created_at else datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                days_ago = (datetime.now() - file_date).days
                if days_ago <= 7:
                    recommended.add('最近新增')
                elif days_ago <= 30:
                    recommended.add('本月新增')
            except:
                pass
        
        # 5. 排除已添加的标签
        existing_tags = conn.execute('''
            SELECT t.name FROM tags t
            JOIN file_tags ft ON t.id = ft.tag_id
            WHERE ft.file_id = ?
        ''', (file_id,)).fetchall()
        
        existing_names = {t['name'] for t in existing_tags}
        recommended = recommended - existing_names
        
        # 6. 过滤掉系统中不存在的标签，并检查是否需要自动创建
        final_recommendations = []
        for tag_name in list(recommended)[:8]:  # 最多推荐8个
            existing_tag = conn.execute(
                'SELECT id, name FROM tags WHERE name = ? AND user_id = ?', 
                (tag_name, user_id)
            ).fetchone()
            
            if existing_tag:
                final_recommendations.append({
                    'id': existing_tag['id'],
                    'name': existing_tag['name'],
                    'exists': True
                })
            else:
                # 可以建议创建新标签
                final_recommendations.append({
                    'id': None,
                    'name': tag_name,
                    'exists': False
                })
        
        return api_response(success=True, data={
            'recommendations': final_recommendations,
            'filename': file_info['filename']
        })
    except Exception as e:
        return api_response(success=False, message=f'推荐失败: {str(e)}', code=500)
    finally:
        conn.close()

# API: 批量添加标签到多个文件
@app.route('/api/batch-add-tag', methods=['POST'])
def api_batch_add_tag():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    data = request.get_json()
    tag_id = data.get('tag_id')
    file_ids = data.get('file_ids', [])
    
    if not tag_id:
        return api_response(success=False, message='标签ID不能为空')
    
    if not file_ids or not isinstance(file_ids, list):
        return api_response(success=False, message='文件ID列表不能为空')
    
    conn = get_db()
    try:
        added_count = 0
        for file_id in file_ids:
            existing = conn.execute(
                'SELECT * FROM file_tags WHERE file_id = ? AND tag_id = ?',
                (file_id, tag_id)
            ).fetchone()
            
            if not existing:
                conn.execute(
                    'INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)',
                    (file_id, tag_id)
                )
                added_count += 1
        
        conn.commit()
        return api_response(success=True, message=f'成功为 {added_count} 个文件添加标签')
    except Exception as e:
        conn.rollback()
        return api_response(success=False, message=f'批量添加失败: {str(e)}', code=500)
    finally:
        conn.close()

# API: 获取当前用户的所有文件（用于标签管理）
@app.route('/api/my-files')
def api_get_my_files():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)
    
    conn = get_db()
    try:
        user_id = session['user_id']
        
        files = conn.execute('''
            SELECT f.id, f.filename, f.size, f.created_at, f.path, 
                   f.stored_name, f.folder_id, f.view_count
            FROM files f
            WHERE f.user_id = ? AND (f.is_deleted = 0 OR f.is_deleted IS NULL)
            ORDER BY f.created_at DESC
        ''', (user_id,)).fetchall()
        
        result_files = []
        for f in files:
            # 获取文件标签
            tags = []
            tag_rows = conn.execute('''SELECT t.* FROM tags t 
                                     JOIN file_tags ft ON t.id = ft.tag_id 
                                     WHERE ft.file_id = ?''', (f['id'],)).fetchall()
            for tr in tag_rows:
                tags.append({'id': tr['id'], 'name': tr['name']})
            
            result_files.append({
                'id': f['id'],
                'filename': f['filename'],
                'size': f['size'],
                'created_at': f['created_at'],
                'path': f['path'],
                'stored_name': f['stored_name'],
                'folder_id': f['folder_id'],
                'view_count': f['view_count'] if f['view_count'] else 0,
                'tags': tags
            })
        
        return api_response(success=True, data={
            'files': result_files,
            'total': len(result_files)
        })
    except Exception as e:
        return api_response(success=False, message=f'获取文件列表失败: {str(e)}', code=500)
    finally:
        conn.close()
