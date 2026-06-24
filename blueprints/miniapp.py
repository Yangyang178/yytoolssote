from flask import Blueprint, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import uuid
import json
import os
import requests as http_requests
from datetime import datetime, timedelta

miniapp_bp = Blueprint('miniapp', __name__)


class _LazyAppImports:
    def __getattr__(self, name):
        if name == 'app':
            from app import app as _app
            return _app
        from app import (
            get_db, get_all_files, log_message, log_access,
            api_response, get_file_by_id,
            get_like_count, get_favorite_count,
            is_liked, is_favorited,
            deepseek_chat,
        )
        locals_dict = locals()
        if name in locals_dict:
            return locals_dict[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


_app = _LazyAppImports()


def _get_token_from_request():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return request.args.get('token', '')


def _get_user_by_token(token):
    if not token:
        return None
    conn = _app.get_db()
    try:
        sess = conn.execute(
            "SELECT * FROM miniapp_sessions WHERE token = ? AND expires_at > datetime('now')",
            (token,)
        ).fetchone()
        if not sess:
            return None
        user = conn.execute("SELECT * FROM users WHERE id = ?", (sess['user_id'],)).fetchone()
        if user:
            return dict(user)
        return None
    finally:
        conn.close()


def miniapp_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token_from_request()
        user = _get_user_by_token(token)
        if not user:
            return jsonify(success=False, message='请先登录', code=401), 401
        request.miniapp_user = user
        return f(*args, **kwargs)
    return decorated


def _create_session(conn, user_id):
    token = str(uuid.uuid4())
    expires_at = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        "INSERT INTO miniapp_sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, datetime('now'))",
        (token, user_id, expires_at)
    )
    conn.commit()
    return token


def _ensure_tables(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS miniapp_sessions (
        id TEXT PRIMARY KEY,
        token TEXT UNIQUE NOT NULL,
        user_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    try:
        conn.execute("ALTER TABLE users ADD COLUMN wx_openid TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN wx_unionid TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN wx_phone TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    except Exception:
        pass
    conn.commit()


@miniapp_bp.route('/miniapp/api/auth/wx-login', methods=['POST'])
def wx_login():
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    if not code:
        return jsonify(success=False, message='缺少code参数')

    conn = _app.get_db()
    try:
        _ensure_tables(conn)

        wx_appid = _app.app.config.get('WX_APPID', '')
        wx_secret = _app.app.config.get('WX_SECRET', '')

        if wx_appid and wx_secret:
            url = f"https://api.weixin.qq.com/sns/jscode2session?appid={wx_appid}&secret={wx_secret}&js_code={code}&grant_type=authorization_code"
            try:
                resp = http_requests.get(url, timeout=10)
                wx_data = resp.json()
                openid = wx_data.get('openid', '')
                unionid = wx_data.get('unionid', '')
                if not openid:
                    return jsonify(success=False, message='微信登录失败: ' + wx_data.get('errmsg', '未知错误'))
            except Exception as e:
                return jsonify(success=False, message=f'微信接口请求失败: {str(e)}')
        else:
            openid = f"wx_dev_{code[:16]}"
            unionid = ''

        user = conn.execute("SELECT * FROM users WHERE wx_openid = ?", (openid,)).fetchone()

        if user:
            user = dict(user)
            conn.execute("DELETE FROM miniapp_sessions WHERE user_id = ? AND expires_at < datetime('now')", (user['id'],))
            token = _create_session(conn, user['id'])
            return jsonify(success=True, data={
                'token': token,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user.get('email', ''),
                    'avatar': user.get('avatar_url', '') or user.get('avatar', ''),
                    'role': user.get('role', 'user'),
                }
            })
        else:
            user_id = str(uuid.uuid4())
            username = f"微信用户_{user_id[:6]}"
            conn.execute(
                "INSERT INTO users (id, username, wx_openid, wx_unionid, email, password) VALUES (?, ?, ?, ?, '', '')",
                (user_id, username, openid, unionid)
            )
            conn.commit()
            token = _create_session(conn, user_id)
            return jsonify(success=True, data={
                'token': token,
                'user': {
                    'id': user_id,
                    'username': username,
                    'email': '',
                    'avatar': '',
                    'role': 'user',
                }
            })
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=f'登录失败: {str(e)}')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/auth/login', methods=['POST'])
def account_login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify(success=False, message='请填写邮箱和密码')

    conn = _app.get_db()
    try:
        _ensure_tables(conn)
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            return jsonify(success=False, message='邮箱或密码错误')
        user = dict(user)

        if not user.get('password') or not check_password_hash(user['password'], password):
            return jsonify(success=False, message='邮箱或密码错误')

        conn.execute("DELETE FROM miniapp_sessions WHERE user_id = ? AND expires_at < datetime('now')", (user['id'],))
        token = _create_session(conn, user['id'])

        return jsonify(success=True, data={
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user.get('email', ''),
                'avatar': user.get('avatar_url', '') or user.get('avatar', ''),
                'role': user.get('role', 'user'),
            }
        })
    except Exception as e:
        return jsonify(success=False, message=f'登录失败: {str(e)}')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/auth/profile', methods=['GET'])
@miniapp_login_required
def get_profile():
    user = request.miniapp_user
    return jsonify(success=True, data={
        'id': user['id'],
        'username': user['username'],
        'email': user.get('email', ''),
        'avatar': user.get('avatar_url', '') or user.get('avatar', ''),
        'role': user.get('role', 'user'),
    })


@miniapp_bp.route('/miniapp/api/auth/profile', methods=['POST'])
@miniapp_login_required
def update_profile():
    user = request.miniapp_user
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    avatar = data.get('avatar', '').strip()

    conn = _app.get_db()
    try:
        updates = []
        params = []
        if username:
            if len(username) < 2 or len(username) > 20:
                return jsonify(success=False, message='用户名长度需在2-20个字符之间')
            existing = conn.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, user['id'])).fetchone()
            if existing:
                return jsonify(success=False, message='用户名已被使用')
            updates.append("username = ?")
            params.append(username)
        if avatar:
            updates.append("avatar_url = ?")
            params.append(avatar)

        if updates:
            params.append(user['id'])
            conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

        return jsonify(success=True, message='更新成功')
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=f'更新失败: {str(e)}')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/auth/change-password', methods=['POST'])
@miniapp_login_required
def change_password():
    user = request.miniapp_user
    data = request.get_json(silent=True) or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return jsonify(success=False, message='请填写旧密码和新密码')
    if len(new_password) < 6:
        return jsonify(success=False, message='新密码至少需要6个字符')

    conn = _app.get_db()
    try:
        if not user.get('password') or not check_password_hash(user['password'], old_password):
            return jsonify(success=False, message='旧密码不正确')

        new_hash = generate_password_hash(new_password)
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_hash, user['id']))
        conn.commit()
        return jsonify(success=True, message='密码修改成功')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/auth/logout', methods=['POST'])
@miniapp_login_required
def logout():
    token = _get_token_from_request()
    conn = _app.get_db()
    try:
        conn.execute("DELETE FROM miniapp_sessions WHERE token = ?", (token,))
        conn.commit()
        return jsonify(success=True, message='已退出登录')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files', methods=['GET'])
@miniapp_login_required
def get_files():
    user = request.miniapp_user
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    conn = _app.get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM files WHERE (user_id = ? OR user_id = 'default_user') AND is_deleted = 0
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (user['id'], per_page, offset)
        ).fetchall()

        files = []
        for row in rows:
            f = dict(row)
            f['like_count'] = _app.get_like_count(f['id'])
            f['favorite_count'] = _app.get_favorite_count(f['id'])
            f['is_liked'] = _app.is_liked(f['id'], user['id'])
            f['is_favorited'] = _app.is_favorited(f['id'], user['id'])
            files.append(f)

        return jsonify(success=True, data={'files': files})
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/<file_id>', methods=['GET'])
@miniapp_login_required
def get_file_detail(file_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        file = conn.execute("SELECT * FROM files WHERE id = ? AND is_deleted = 0", (file_id,)).fetchone()
        if not file:
            return jsonify(success=False, message='文件不存在'), 404

        f = dict(file)
        f['like_count'] = _app.get_like_count(f['id'])
        f['favorite_count'] = _app.get_favorite_count(f['id'])
        f['is_liked'] = _app.is_liked(f['id'], user['id'])
        f['is_favorited'] = _app.is_favorited(f['id'], user['id'])

        tags = conn.execute("""SELECT t.* FROM tags t JOIN file_tags ft ON t.id = ft.tag_id WHERE ft.file_id = ?""", (file_id,)).fetchall()
        f['tags'] = [dict(t) for t in tags]

        categories = conn.execute("""SELECT c.* FROM categories c JOIN file_categories fc ON c.id = fc.category_id WHERE fc.file_id = ?""", (file_id,)).fetchall()
        f['categories'] = [dict(c) for c in categories]

        _app.log_access(file_id, 'view', request)
        conn.execute("UPDATE files SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?", (file_id,))
        conn.commit()

        return jsonify(success=True, data=f)
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/upload', methods=['POST'])
@miniapp_login_required
def upload_file():
    user = request.miniapp_user
    files = request.files.getlist('file')
    project_name = request.form.get('project_name', '')
    project_desc = request.form.get('project_desc', '')

    if not files or files[0].filename == '':
        return jsonify(success=False, message='请选择文件')

    conn = _app.get_db()
    try:
        uploaded = []
        for file in files:
            if file.filename == '':
                continue
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(file.filename)[1]
            stored_name = f"{file_id}{ext}"
            file_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)
            file.save(file_path)
            file_size = os.path.getsize(file_path)

            conn.execute(
                """INSERT INTO files (id, user_id, filename, stored_name, path, size, project_name, project_desc, folder_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, CURRENT_TIMESTAMP)""",
                (file_id, user['id'], file.filename, stored_name, file_path, file_size, project_name, project_desc)
            )
            uploaded.append({'id': file_id, 'filename': file.filename})

        conn.commit()
        return jsonify(success=True, message=f'成功上传 {len(uploaded)} 个文件', data={'files': uploaded})
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=f'上传失败: {str(e)}')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/<file_id>', methods=['DELETE'])
@miniapp_login_required
def delete_file(file_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        file = conn.execute("SELECT * FROM files WHERE id = ? AND is_deleted = 0", (file_id,)).fetchone()
        if not file:
            return jsonify(success=False, message='文件不存在'), 404
        file = dict(file)
        if file['user_id'] != user['id'] and user.get('role') != 'admin':
            return jsonify(success=False, message='无权限删除'), 403

        conn.execute("UPDATE files SET is_deleted = 1 WHERE id = ?", (file_id,))
        conn.commit()
        return jsonify(success=True, message='删除成功')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/search', methods=['GET'])
@miniapp_login_required
def search_files():
    user = request.miniapp_user
    keyword = request.args.get('keyword', '').strip()
    if not keyword:
        return jsonify(success=False, message='请输入搜索关键词')

    conn = _app.get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM files WHERE (user_id = ? OR user_id = 'default_user') AND is_deleted = 0
               AND filename LIKE ? ORDER BY created_at DESC""",
            (user['id'], f'%{keyword}%')
        ).fetchall()

        files = []
        for row in rows:
            f = dict(row)
            f['like_count'] = _app.get_like_count(f['id'])
            f['favorite_count'] = _app.get_favorite_count(f['id'])
            f['is_liked'] = _app.is_liked(f['id'], user['id'])
            f['is_favorited'] = _app.is_favorited(f['id'], user['id'])
            files.append(f)

        return jsonify(success=True, data={'files': files})
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/<file_id>/like', methods=['POST'])
@miniapp_login_required
def like_file(file_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        existing = conn.execute("SELECT id FROM likes WHERE user_id = ? AND file_id = ?", (user['id'], file_id)).fetchone()
        if existing:
            return jsonify(success=False, message='已点赞')
        like_id = str(uuid.uuid4())
        conn.execute("INSERT INTO likes (id, user_id, file_id) VALUES (?, ?, ?)", (like_id, user['id'], file_id))
        conn.commit()
        return jsonify(success=True, message='点赞成功')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/<file_id>/like', methods=['DELETE'])
@miniapp_login_required
def unlike_file(file_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        conn.execute("DELETE FROM likes WHERE user_id = ? AND file_id = ?", (user['id'], file_id))
        conn.commit()
        return jsonify(success=True, message='取消点赞')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/<file_id>/favorite', methods=['POST'])
@miniapp_login_required
def favorite_file(file_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        existing = conn.execute("SELECT id FROM favorites WHERE user_id = ? AND file_id = ?", (user['id'], file_id)).fetchone()
        if existing:
            return jsonify(success=False, message='已收藏')
        fav_id = str(uuid.uuid4())
        conn.execute("INSERT INTO favorites (id, user_id, file_id) VALUES (?, ?, ?)", (fav_id, user['id'], file_id))
        conn.commit()
        return jsonify(success=True, message='收藏成功')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/<file_id>/favorite', methods=['DELETE'])
@miniapp_login_required
def unfavorite_file(file_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        conn.execute("DELETE FROM favorites WHERE user_id = ? AND file_id = ?", (user['id'], file_id))
        conn.commit()
        return jsonify(success=True, message='取消收藏')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/favorites', methods=['GET'])
@miniapp_login_required
def get_favorite_files():
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        rows = conn.execute(
            """SELECT f.* FROM files f JOIN favorites fav ON f.id = fav.file_id
               WHERE fav.user_id = ? AND f.is_deleted = 0 ORDER BY fav.created_at DESC""",
            (user['id'],)
        ).fetchall()
        files = [dict(r) for r in rows]
        return jsonify(success=True, data={'files': files})
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/download/<stored_name>')
@miniapp_login_required
def download_file(stored_name):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        file = conn.execute("SELECT * FROM files WHERE stored_name = ? AND is_deleted = 0", (stored_name,)).fetchone()
        if not file:
            return jsonify(success=False, message='文件不存在'), 404

        _app.log_access(file['id'], 'download', request)
        conn.execute("UPDATE files SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?", (file['id'],))
        conn.commit()

        return send_from_directory(_app.app.config['UPLOAD_FOLDER'], stored_name,
                                  as_attachment=True, download_name=file['filename'])
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/files/preview/<stored_name>')
@miniapp_login_required
def preview_file(stored_name):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        file = conn.execute("SELECT * FROM files WHERE stored_name = ? AND is_deleted = 0", (stored_name,)).fetchone()
        if not file:
            return jsonify(success=False, message='文件不存在'), 404

        _app.log_access(file['id'], 'view', request)
        return send_from_directory(_app.app.config['UPLOAD_FOLDER'], stored_name)
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/folders', methods=['GET'])
@miniapp_login_required
def get_folders():
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        rows = conn.execute(
            """SELECT f.*, (SELECT COUNT(*) FROM files WHERE folder_id = f.id AND is_deleted = 0) as file_count
               FROM folders f WHERE f.user_id = ? ORDER BY f.created_at DESC""",
            (user['id'],)
        ).fetchall()
        folders = [dict(r) for r in rows]
        return jsonify(success=True, data={'folders': folders})
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/folders/<folder_id>', methods=['GET'])
@miniapp_login_required
def get_folder_detail(folder_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        folder = conn.execute("SELECT * FROM folders WHERE id = ? AND user_id = ?", (folder_id, user['id'])).fetchone()
        if not folder:
            return jsonify(success=False, message='文件夹不存在'), 404

        files = conn.execute(
            """SELECT * FROM files WHERE folder_id = ? AND is_deleted = 0 AND (filename NOT LIKE '%.html' AND filename NOT LIKE '%.htm')
               ORDER BY created_at DESC""",
            (folder_id,)
        ).fetchall()

        return jsonify(success=True, data={
            'folder': dict(folder),
            'files': [dict(f) for f in files]
        })
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/folders', methods=['POST'])
@miniapp_login_required
def create_folder():
    user = request.miniapp_user
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not name:
        return jsonify(success=False, message='请输入文件夹名称')

    conn = _app.get_db()
    try:
        folder_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO folders (id, user_id, name, description, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (folder_id, user['id'], name, description)
        )
        conn.commit()
        return jsonify(success=True, message='创建成功', data={'id': folder_id, 'name': name})
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=f'创建失败: {str(e)}')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/tags', methods=['GET'])
@miniapp_login_required
def get_tags():
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        rows = conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
        tags = [dict(r) for r in rows]
        return jsonify(success=True, data={'tags': tags})
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/tags', methods=['POST'])
@miniapp_login_required
def create_tag():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify(success=False, message='请输入标签名称')

    conn = _app.get_db()
    try:
        existing = conn.execute("SELECT * FROM tags WHERE name = ?", (name,)).fetchone()
        if existing:
            return jsonify(success=False, message='标签已存在')
        tag_id = str(uuid.uuid4())
        conn.execute("INSERT INTO tags (id, name) VALUES (?, ?)", (tag_id, name))
        conn.commit()
        return jsonify(success=True, message='创建成功', data={'id': tag_id, 'name': name})
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=f'创建失败: {str(e)}')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/workspaces', methods=['GET'])
@miniapp_login_required
def get_workspaces():
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        owned = conn.execute(
            """SELECT w.*, (SELECT COUNT(*) FROM workspace_members WHERE workspace_id = w.id) as member_count,
                      (SELECT COUNT(*) FROM workspace_files WHERE workspace_id = w.id) as file_count
               FROM workspaces w WHERE w.owner_id = ? ORDER BY w.updated_at DESC""",
            (user['id'],)
        ).fetchall()

        joined = conn.execute(
            """SELECT w.*, wm.role as member_role,
                      (SELECT COUNT(*) FROM workspace_members WHERE workspace_id = w.id) as member_count,
                      (SELECT COUNT(*) FROM workspace_files WHERE workspace_id = w.id) as file_count
               FROM workspaces w JOIN workspace_members wm ON w.id = wm.workspace_id
               WHERE wm.user_id = ? ORDER BY w.updated_at DESC""",
            (user['id'],)
        ).fetchall()

        return jsonify(success=True, data={
            'owned': [dict(r) for r in owned],
            'joined': [dict(r) for r in joined]
        })
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/workspaces', methods=['POST'])
@miniapp_login_required
def create_workspace():
    user = request.miniapp_user
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not name:
        return jsonify(success=False, message='请输入空间名称')

    conn = _app.get_db()
    try:
        ws_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO workspaces (id, name, description, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (ws_id, name, description, user['id'])
        )
        member_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO workspace_members (id, workspace_id, user_id, role, joined_at) VALUES (?, ?, ?, 'owner', CURRENT_TIMESTAMP)",
            (member_id, ws_id, user['id'])
        )
        conn.commit()
        return jsonify(success=True, message='创建成功', data={'id': ws_id, 'name': name})
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=f'创建失败: {str(e)}')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/workspaces/<workspace_id>', methods=['GET'])
@miniapp_login_required
def get_workspace_detail(workspace_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        ws = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if not ws:
            return jsonify(success=False, message='空间不存在'), 404

        member_count = conn.execute("SELECT COUNT(*) as cnt FROM workspace_members WHERE workspace_id = ?", (workspace_id,)).fetchone()['cnt']
        file_count = conn.execute("SELECT COUNT(*) as cnt FROM workspace_files WHERE workspace_id = ?", (workspace_id,)).fetchone()['cnt']

        files = conn.execute(
            """SELECT f.* FROM files f JOIN workspace_files wf ON f.id = wf.file_id
               WHERE wf.workspace_id = ? AND f.is_deleted = 0""",
            (workspace_id,)
        ).fetchall()

        return jsonify(success=True, data={
            'workspace': {**dict(ws), 'member_count': member_count, 'file_count': file_count},
            'files': [dict(f) for f in files]
        })
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/workspaces/<workspace_id>/members', methods=['GET'])
@miniapp_login_required
def get_workspace_members(workspace_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        members = conn.execute(
            """SELECT wm.*, u.username, u.email FROM workspace_members wm
               JOIN users u ON wm.user_id = u.id WHERE wm.workspace_id = ?""",
            (workspace_id,)
        ).fetchall()
        return jsonify(success=True, data={'members': [dict(m) for m in members]})
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/workspaces/<workspace_id>/members', methods=['POST'])
@miniapp_login_required
def invite_member(workspace_id):
    user = request.miniapp_user
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    role = data.get('role', 'viewer')

    if not email:
        return jsonify(success=False, message='请输入邮箱')

    conn = _app.get_db()
    try:
        ws = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if not ws:
            return jsonify(success=False, message='空间不存在'), 404

        if ws['owner_id'] != user['id']:
            caller = conn.execute("SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                                 (workspace_id, user['id'])).fetchone()
            if not caller or caller['role'] not in ('owner', 'admin'):
                return jsonify(success=False, message='权限不足'), 403

        target = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not target:
            return jsonify(success=False, message='该邮箱用户不存在')

        existing = conn.execute("SELECT id FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                               (workspace_id, target['id'])).fetchone()
        if existing:
            return jsonify(success=False, message='该用户已在空间中')

        member_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO workspace_members (id, workspace_id, user_id, role, joined_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (member_id, workspace_id, target['id'], role)
        )
        conn.commit()
        return jsonify(success=True, message='邀请成功')
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=f'邀请失败: {str(e)}')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/workspaces/<workspace_id>/members/<user_id>', methods=['DELETE'])
@miniapp_login_required
def remove_member(workspace_id, user_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        ws = conn.execute("SELECT owner_id FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if not ws:
            return jsonify(success=False, message='空间不存在'), 404

        if ws['owner_id'] != user['id']:
            return jsonify(success=False, message='仅创建者可移除成员'), 403

        if ws['owner_id'] == user_id:
            return jsonify(success=False, message='不能移除创建者'), 403

        conn.execute("DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?", (workspace_id, user_id))
        conn.commit()
        return jsonify(success=True, message='已移除')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/ai/chat', methods=['POST'])
@miniapp_login_required
def ai_chat():
    user = request.miniapp_user
    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    model = data.get('model', 'deepseek-chat')

    if not message:
        return jsonify(success=False, message='请输入消息')

    try:
        result = _app.deepseek_chat([{"role": "user", "content": message}], model=model)
        response_text = result.get('choices', [{}])[0].get('message', {}).get('content', str(result))

        conn = _app.get_db()
        try:
            content_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO ai_contents (id, user_id, ai_function, prompt, response, created_at)
                   VALUES (?, ?, 'chat', ?, ?, CURRENT_TIMESTAMP)""",
                (content_id, user['id'], message, response_text)
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify(success=True, data={'response': response_text, 'id': content_id})
    except Exception as e:
        return jsonify(success=False, message=f'AI对话失败: {str(e)}')


@miniapp_bp.route('/miniapp/api/ai/history', methods=['GET'])
@miniapp_login_required
def get_ai_history():
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        rows = conn.execute(
            "SELECT id, ai_function, prompt, response, created_at FROM ai_contents WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user['id'],)
        ).fetchall()
        return jsonify(success=True, data=[dict(r) for r in rows])
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/ai/history/<content_id>', methods=['DELETE'])
@miniapp_login_required
def delete_ai_history(content_id):
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        conn.execute("DELETE FROM ai_contents WHERE id = ? AND user_id = ?", (content_id, user['id']))
        conn.commit()
        return jsonify(success=True, message='已删除')
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/user/stats', methods=['GET'])
@miniapp_login_required
def get_user_stats():
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        file_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM files WHERE user_id = ? AND is_deleted = 0",
            (user['id'],)
        ).fetchone()['cnt']

        total_size = conn.execute(
            "SELECT COALESCE(SUM(size), 0) as total FROM files WHERE user_id = ? AND is_deleted = 0",
            (user['id'],)
        ).fetchone()['total']

        folder_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM folders WHERE user_id = ?",
            (user['id'],)
        ).fetchone()['cnt']

        return jsonify(success=True, data={
            'file_count': file_count,
            'total_size': total_size,
            'folder_count': folder_count,
        })
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/user/access-logs', methods=['GET'])
@miniapp_login_required
def get_access_logs():
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM access_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
            (user['id'],)
        ).fetchall()
        return jsonify(success=True, data={'logs': [dict(r) for r in rows]})
    except Exception:
        rows = conn.execute(
            "SELECT * FROM logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
            (user['id'],)
        ).fetchall()
        return jsonify(success=True, data={'logs': [dict(r) for r in rows]})
    finally:
        conn.close()


@miniapp_bp.route('/miniapp/api/user/operation-logs', methods=['GET'])
@miniapp_login_required
def get_operation_logs():
    user = request.miniapp_user
    conn = _app.get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM operation_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
            (user['id'],)
        ).fetchall()
        return jsonify(success=True, data={'logs': [dict(r) for r in rows]})
    except Exception:
        rows = conn.execute(
            "SELECT * FROM logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
            (user['id'],)
        ).fetchall()
        return jsonify(success=True, data={'logs': [dict(r) for r in rows]})
    finally:
        conn.close()
