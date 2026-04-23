from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
from app import (app, get_db, get_all_files, generate_verification_code,
                send_verification_email, save_verification_code, verify_code,
                log_message, log_login_attempt, api_response)
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
import json

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth', methods=['GET', 'POST'], endpoint='auth')
def auth():
    if request.method == 'POST':
        action = request.form.get('action')
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        code = request.form.get('code')

        if action == 'register':
            if not all([email, username, password, code]):
                flash('请填写所有必填项')
                return redirect(url_for('auth'))

            if not verify_code(email, code, 'register'):
                flash('验证码无效或已过期')
                return redirect(url_for('auth'))

            conn = get_db()
            try:
                existing = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                if existing:
                    flash('该邮箱已被注册')
                    return redirect(url_for('auth'))

                user_id = str(uuid.uuid4())
                hashed_password = generate_password_hash(password)
                conn.execute('INSERT INTO users (id, email, username, password) VALUES (?, ?, ?, ?)',
                           (user_id, email, username, hashed_password))
                conn.commit()

                session['user_id'] = user_id
                session['username'] = username
                session['email'] = email

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

                log_login_attempt(email, 1, request)

                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']

                if user.get('role'):
                    session['role'] = user['role']

                log_message(
                    log_type='operation',
                    log_level='INFO',
                    message=f'用户登录: {user["username"]}',
                    user_id=user['id'],
                    action='login',
                    request=request
                )

                flash('登录成功')
                next_url = request.args.get('next') or url_for('index')
                return redirect(next_url)
            except Exception as e:
                flash(f'登录失败: {str(e)}')
                return redirect(url_for('auth'))
            finally:
                conn.close()

    return render_template('auth.html')


@auth_bp.route('/user-center', endpoint='user_center')
def user_center():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

        files = get_all_files(user_id=session['user_id'])

        total_size = sum(f.get('size', 0) for f in files)

        like_count = sum(f.get('like_count', 0) for f in files)
        favorite_count = sum(f.get('favorite_count', 0) for f in files)

        access_logs = get_access_logs(session['user_id'])

        recent_logs = sorted(access_logs, key=lambda x: x.get('access_time', ''), reverse=True)[:10]

        return render_template(
            'user_center.html',
            username=session.get('username'),
            user=dict(user),
            files=files,
            file_count=len(files),
            total_size=total_size,
            like_count=like_count,
            favorite_count=favorite_count,
            access_log_count=len(access_logs),
            recent_logs=recent_logs
        )
    finally:
        conn.close()


@auth_bp.route('/update-profile', methods=['POST'], endpoint='update_profile')
def update_profile():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    data = request.get_json() or {}
    username = data.get('username', '').strip()
    avatar_data = data.get('avatar')

    if not username:
        return jsonify({'success': False, 'message': '用户名不能为空'})
    if len(username) < 2 or len(username) > 20:
        return jsonify({'success': False, 'message': '用户名长度需在2-20个字符之间'})

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?",
            (username, session['user_id'])
        ).fetchone()
        if existing:
            return jsonify({'success': False, 'message': '用户名已被使用'})

        avatar_path = None
        if avatar_data and avatar_data.startswith('data:image'):
            import base64
            header, encoded = avatar_data.split(',', 1)
            ext = 'png' if 'png' in header else 'jpg'
            avatar_filename = f"avatar_{session['user_id']}.{ext}"
            avatar_dir = Path(app.static_folder) / 'avatars'
            avatar_dir.mkdir(parents=True, exist_ok=True)
            avatar_path = str(avatar_dir / avatar_filename)
            with open(avatar_path, 'wb') as f:
                f.write(base64.b64decode(encoded))

        if avatar_path:
            conn.execute("UPDATE users SET username=?, avatar=? WHERE id=?",
                       (username, avatar_path, session['user_id']))
        else:
            conn.execute("UPDATE users SET username=? WHERE id=?",
                       (username, session['user_id']))

        conn.commit()

        session['username'] = username

        log_message(
            log_type='operation',
            log_level='INFO',
            message='用户更新个人资料',
            user_id=session['user_id'],
            action='update_profile',
            request=request
        )

        return jsonify({
            'success': True,
            'message': '资料更新成功',
            'data': {'username': username}
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})


@auth_bp.route('/logout', endpoint='logout')
def logout():
    user_id = session.pop('user_id', None)
    username = session.pop('username', None)

    if user_id:
        log_message(
            log_type='operation',
            log_level='INFO',
            message=f'用户退出登录: {username or "未知"}',
            user_id=user_id,
            action='logout',
            request=request
        )

    flash('已安全退出')
    return redirect(url_for('auth'))


@auth_bp.route('/my-feedback', endpoint='my_feedback')
def my_feedback():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    conn = get_db()
    try:
        feedbacks = conn.execute(
            "SELECT * FROM operation_logs WHERE user_id = ? AND action LIKE '%feedback%' ORDER BY created_at DESC",
            (session['user_id'],)
        ).fetchall()
        return render_template('my_feedback.html', username=session.get('username'), feedbacks=[dict(f) for f in feedbacks])
    finally:
        conn.close()


@auth_bp.route('/new-feedback', methods=['GET', 'POST'], endpoint='new_feedback')
def new_feedback():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    if request.method == 'POST':
        title = request.form.get('title', '')
        content = request.form.get('content', '')
        category = request.form.get('category', 'bug')

        if not content.strip():
            flash('反馈内容不能为空')
            return redirect(url_for('new_feedback'))

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO operation_logs (user_id, action, target_type, message, details, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (session['user_id'], 'new_feedback', category, title[:100] if title else '无标题', content))
            conn.commit()
            flash('感谢您的反馈！我们会尽快处理。')
        except Exception as e:
            flash(f'提交失败: {e}')
        finally:
            conn.close()
        return redirect(url_for('new_feedback'))

    return render_template('new_feedback.html', username=session.get('username'))


@auth_bp.route('/api/feedback/<feedback_id>/delete', methods=['POST'], endpoint='delete_feedback')
def delete_feedback(feedback_id):
    if 'user_id' not in session:
        return jsonify(success=False, message="未登录", code=401)
    conn = get_db()
    try:
        feedback = conn.execute("SELECT * FROM operation_logs WHERE id = ?", (feedback_id,)).fetchone()
        if not feedback or feedback['user_id'] != session['user_id']:
            return jsonify(success=False, message="无权限删除", code=403)
        conn.execute("DELETE FROM operation_logs WHERE id = ?", (feedback_id,))
        conn.commit()
        return jsonify(success=True, message="删除成功")
    finally:
        conn.close()


@auth_bp.route('/feedback', endpoint='feedback_simple')
def feedback_simple():
    return render_template('feedback_simple.html', username=session.get('username'))


@auth_bp.route('/upload', methods=['GET', 'POST'], endpoint='upload')
def upload():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    if request.method == 'POST':
        files = request.files.getlist('file')
        project_name = request.form.get('project_name')
        project_desc = request.form.get('project_desc')
        upload_target = request.form.get('upload_target', 'user')
        file_category = request.form.get('file_category')

        if not files or files[0].filename == '':
            flash('请选择文件')
            return redirect(url_for('upload'))

        conn = get_db()
        try:
            current_user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
            is_admin = current_user and current_user['role'] == 'admin'

            target_user_id = session['user_id']
            if is_admin and upload_target == 'home':
                target_user_id = "default_user"

            for file in files:
                if file.filename == '':
                    continue

                file_id = str(uuid.uuid4())
                ext = os.path.splitext(file.filename)[1]
                stored_name = f"{file_id}{ext}"

                file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
                file.save(file_path)

                file_size = os.path.getsize(file_path)

                dkfile_info = "{}"
                try:
                    from app import upload_to_dkfile
                    dkfile_info = upload_to_dkfile(file, stored_name, file_path)
                except:
                    pass

                conn.execute('''INSERT INTO files (id, user_id, filename, stored_name, path, size, dkfile, project_name, project_desc, folder_id, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, CURRENT_TIMESTAMP)''',
                           (file_id, target_user_id, file.filename, stored_name, file_path, file_size,
                            dkfile_info, project_name, project_desc))

                if file_category:
                    assign_category_to_file(conn, file_id, file_category, target_user_id)

            conn.commit()

            log_message(log_type='operation', log_level='INFO',
                       message='文件上传完成', user_id=session['user_id'],
                       action='upload', request=request)

            flash('文件上传成功!')
            return redirect(url_for('user_center'))
        except Exception as e:
            conn.rollback()
            flash(f'上传失败: {str(e)}')
            return redirect(url_for('upload'))
        finally:
            conn.close()

    return render_template('upload_page.html', username=session.get('username'))


@auth_bp.route('/detail/<file_id>', endpoint='detail')
def detail(file_id):
    conn = get_db()
    try:
        file = get_file_by_id(file_id)
        if not file:
            return page_error_response('index', '文件不存在', 404)

        is_owner = file['user_id'] == session.get('user_id') or session.get('role') == 'admin'
        if not is_owner:
            return page_error_response('index', '无权访问此文件', 403)

        file['like_count'] = get_like_count(file_id)
        file['favorite_count'] = get_favorite_count(file_id)
        file['is_liked'] = is_liked(file_id, session.get('user_id'))
        file['is_favorited'] = is_favorited(file_id, session.get('user_id'))

        categories = []
        cat_rows = conn.execute('''SELECT c.* FROM categories c
                                       JOIN file_categories fc ON c.id = fc.category_id
                                       WHERE fc.file_id = ?''', (file_id,)).fetchall()
        for cr in cat_rows:
            categories.append({"id": cr["id"], "name": cr["name"], "description": cr["description"]})

        tags = []
        tag_rows = conn.execute('''SELECT t.* FROM tags t
                                 JOIN file_tags ft ON t.id = ft.tag_id
                                 WHERE ft.file_id = ?''', (file_id,)).fetchall()
        for tr in tag_rows:
            tags.append({"id": tr["id"], "name": tr["name"]})

        all_tags = [dict(t) for t in conn.execute("SELECT * FROM tags").fetchall()]
        all_categories = [dict(c) for c in conn.execute("SELECT * FROM categories").fetchall()]

        return render_template(
            'detail.html',
            username=session.get('username'),
            file=file,
            categories=categories,
            tags=tags,
            all_tags=all_tags,
            all_categories=all_categories
        )
    finally:
        conn.close()


@auth_bp.route('/account-settings', endpoint='account_settings')
def account_settings():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        return render_template('account_settings.html', username=session.get('username'), user=dict(user))
    finally:
        conn.close()


@auth_bp.route('/change-password', methods=['POST'], endpoint='change_password')
def change_password():
    if 'user_id' not in session:
        return jsonify(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return jsonify(success=False, message='请填写旧密码和新密码')

    if len(new_password) < 6:
        return jsonify(success=False, message='新密码至少需要6个字符')

    conn = get_db()
    try:
        user = conn.execute('SELECT password FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not check_password_hash(user['password'], old_password):
            return jsonify(success=False, message='旧密码不正确')

        new_hash = generate_password_hash(new_password)
        conn.execute('UPDATE users SET password = ? WHERE id = ?', (new_hash, session['user_id']))
        conn.commit()

        log_message(log_type='security', log_level='INFO',
                   message='用户修改了密码', user_id=session['user_id'],
                   action='change_password', request=request)

        return jsonify(success=True, message='密码修改成功')
    finally:
        conn.close()


@auth_bp.route('/change-email', methods=['POST'], endpoint='change_email')
def change_email():
    if 'user_id' not in session:
        return jsonify(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    new_email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not new_email or not password:
        return jsonify(success=False, message='请填写新邮箱和确认密码')

    if '@' not in new_email or '.' not in new_email:
        return jsonify(success=False, message='邮箱格式不正确')

    conn = get_db()
    try:
        user = conn.execute('SELECT password, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not check_password_hash(user['password'], password):
            return jsonify(success=False, message='密码不正确')

        if user['email'].lower() == new_email:
            return jsonify(success=False, message='新邮箱不能与当前相同')

        existing = conn.execute('SELECT id FROM users WHERE email = ?', (new_email,)).fetchone()
        if existing:
            return jsonify(success=False, message='该邮箱已被使用')

        conn.execute('UPDATE users SET email = ? WHERE id = ?', (new_email, session['user_id']))
        conn.commit()
        session['email'] = new_email

        log_message(log_type='security', log_level='INFO',
                   message=f'用户修改邮箱: {user["email"]} -> {new_email}',
                   user_id=session['user_id'], action='change_email', request=request)

        return jsonify(success=True, message='邮箱修改成功')
    finally:
        conn.close()


@auth_bp.route('/send-email-code', methods=['POST'], endpoint='send_email_code')
def send_email_code():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    purpose = data.get('purpose', 'register')

    if not email:
        return jsonify(success=False, message='请输入邮箱地址')
    if '@' not in email:
        return jsonify(success=False, message='邮箱格式不正确')

    conn = get_db()
    try:
        user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if purpose == 'register' and user:
            return jsonify(success=False, message='该邮箱已被注册')
        if purpose in ('reset_email', 'change_email') and not user:
            return jsonify(success=False, message='该邮箱未注册')

        code = generate_verification_code(email, purpose)
        send_verification_email(email, code, purpose)
        save_verification_code(email, code, purpose)

        return jsonify(success=True, message='验证码已发送，请查收邮件')
    finally:
        conn.close()
