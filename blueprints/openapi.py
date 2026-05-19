from flask import Blueprint, request, render_template, redirect, url_for, jsonify, session, send_from_directory
import os, json, sqlite3, shutil, base64, uuid, hashlib, time
from datetime import datetime, timedelta
from pathlib import Path
import jwt
from functools import wraps
from werkzeug.security import check_password_hash

class _LazyAppImports:
    def __getattr__(self, name):
        from app import (app as _flask_app, get_db, log_message,
                        page_error_response, api_response)
        _mapping = {
            'app': _flask_app,
            'get_db': get_db,
            'log_message': log_message,
            'page_error_response': page_error_response,
            'api_response': api_response,
        }
        if name not in _mapping:
            raise AttributeError(f"module 'app' has no attribute '{name}'")
        return _mapping[name]

_app = _LazyAppImports()
openapi_bp = Blueprint('openapi', __name__)

JWT_SECRET = None
JWT_ACCESS_EXPIRY = timedelta(hours=1)
JWT_REFRESH_EXPIRY = timedelta(days=30)


def _get_jwt_secret():
    global JWT_SECRET
    if JWT_SECRET is None:
        try:
            JWT_SECRET = _app.app.config.get('SECRET_KEY', 'yytools-api-secret-key-2024')
        except Exception:
            JWT_SECRET = 'yytools-api-secret-key-2024'
    return JWT_SECRET


def _generate_access_token(user_id, email, username, role):
    now = datetime.utcnow()
    payload = {
        'sub': user_id,
        'email': email,
        'username': username,
        'role': role,
        'type': 'access',
        'iat': now,
        'exp': now + JWT_ACCESS_EXPIRY,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm='HS256')


def _generate_refresh_token(user_id):
    now = datetime.utcnow()
    payload = {
        'sub': user_id,
        'type': 'refresh',
        'iat': now,
        'exp': now + JWT_REFRESH_EXPIRY,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm='HS256')


def _decode_token(token):
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _require_api_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            payload = _decode_token(token)
            if payload and payload.get('type') == 'access':
                request.api_user = {
                    'id': payload['sub'],
                    'email': payload.get('email', ''),
                    'username': payload.get('username', ''),
                    'role': payload.get('role', 'user'),
                    'auth_type': 'jwt',
                }
                return f(*args, **kwargs)
            return jsonify({'error': '令牌无效或已过期', 'code': 401}), 401

        api_key = request.headers.get('X-API-Key', '')
        if api_key:
            key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
            key_prefix = api_key[:8]
            conn = _app.get_db()
            try:
                row = conn.execute(
                    'SELECT * FROM api_keys WHERE key_hash = ? AND key_prefix = ? AND is_active = 1',
                    (key_hash, key_prefix)
                ).fetchone()
                if row:
                    if row['expires_at']:
                        try:
                            expires = datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S')
                            if datetime.now() > expires:
                                return jsonify({'error': 'API密钥已过期', 'code': 401}), 401
                        except ValueError:
                            pass
                    user = conn.execute('SELECT * FROM users WHERE id = ?', (row['user_id'],)).fetchone()
                    if user:
                        conn.execute(
                            'UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?',
                            (row['id'],)
                        )
                        conn.commit()
                        request.api_user = {
                            'id': user['id'],
                            'email': user['email'],
                            'username': user['username'],
                            'role': user['role'] if user['role'] else 'user',
                            'auth_type': 'api_key',
                            'permissions': row['permissions'],
                        }
                        return f(*args, **kwargs)
            finally:
                conn.close()
            return jsonify({'error': 'API密钥无效', 'code': 401}), 401

        return jsonify({'error': '未提供认证信息', 'code': 401}), 401
    return decorated


@openapi_bp.route('/api/v1/auth/token', methods=['POST'], endpoint='api_v1_auth_token')
def api_v1_auth_token():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': '请提供邮箱和密码', 'code': 400}), 400

    conn = _app.get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if not user:
            return jsonify({'error': '邮箱或密码错误', 'code': 401}), 401

        if not check_password_hash(user['password'], password):
            return jsonify({'error': '邮箱或密码错误', 'code': 401}), 401

        user_id = user['id']
        user_email = user['email']
        username = user['username']
        role = user['role'] if user['role'] else 'user'

        access_token = _generate_access_token(user_id, user_email, username, role)
        refresh_token = _generate_refresh_token(user_id)

        _app.log_message(
            log_type='operation',
            log_level='INFO',
            message='API令牌认证成功',
            user_id=user_id,
            action='api_token_auth',
            request=request
        )

        return jsonify({
            'data': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': int(JWT_ACCESS_EXPIRY.total_seconds()),
            },
            'meta': {
                'user_id': user_id,
                'username': username,
            }
        })
    finally:
        conn.close()


@openapi_bp.route('/api/v1/auth/refresh', methods=['POST'], endpoint='api_v1_auth_refresh')
def api_v1_auth_refresh():
    data = request.get_json(silent=True) or {}
    refresh_token = data.get('refresh_token') or ''

    if not refresh_token:
        return jsonify({'error': '请提供刷新令牌', 'code': 400}), 400

    payload = _decode_token(refresh_token)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({'error': '刷新令牌无效或已过期', 'code': 401}), 401

    user_id = payload['sub']
    conn = _app.get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            return jsonify({'error': '用户不存在', 'code': 401}), 401

        access_token = _generate_access_token(
            user['id'], user['email'], user['username'],
            user['role'] if user['role'] else 'user'
        )
        new_refresh_token = _generate_refresh_token(user_id)

        return jsonify({
            'data': {
                'access_token': access_token,
                'refresh_token': new_refresh_token,
                'token_type': 'Bearer',
                'expires_in': int(JWT_ACCESS_EXPIRY.total_seconds()),
            }
        })
    finally:
        conn.close()


@openapi_bp.route('/api/v1/keys', methods=['GET'], endpoint='api_v1_list_keys')
def api_v1_list_keys():
    if 'user_id' not in session:
        return jsonify({'error': '请先登录', 'code': 401}), 401

    conn = _app.get_db()
    try:
        rows = conn.execute(
            'SELECT id, name, key_prefix, permissions, last_used_at, created_at, expires_at, is_active FROM api_keys WHERE user_id = ? ORDER BY created_at DESC',
            (session['user_id'],)
        ).fetchall()
        keys = [dict(r) for r in rows]
        return jsonify({
            'data': keys,
            'meta': {'total': len(keys)}
        })
    finally:
        conn.close()


@openapi_bp.route('/api/v1/keys', methods=['POST'], endpoint='api_v1_create_key')
def api_v1_create_key():
    if 'user_id' not in session:
        return jsonify({'error': '请先登录', 'code': 401}), 401

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    permissions = data.get('permissions', 'read')
    expires_days = data.get('expires_days')

    if not name:
        return jsonify({'error': '请输入密钥名称', 'code': 400}), 400

    raw_key = uuid.uuid4().hex + uuid.uuid4().hex
    key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    key_prefix = raw_key[:8]
    key_id = uuid.uuid4().hex

    expires_at = None
    if expires_days:
        expires_at = (datetime.now() + timedelta(days=int(expires_days))).strftime('%Y-%m-%d %H:%M:%S')

    conn = _app.get_db()
    try:
        conn.execute(
            'INSERT INTO api_keys (id, user_id, name, key_hash, key_prefix, permissions, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (key_id, session['user_id'], name, key_hash, key_prefix, permissions, expires_at)
        )
        conn.commit()

        _app.log_message(
            log_type='security',
            log_level='INFO',
            message=f'创建API密钥: {name}',
            user_id=session['user_id'],
            action='create_api_key',
            request=request
        )

        return jsonify({
            'data': {
                'id': key_id,
                'name': name,
                'key': raw_key,
                'key_prefix': key_prefix,
                'permissions': permissions,
                'expires_at': expires_at,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
            'meta': {
                'warning': '请妥善保存API密钥，创建后仅显示一次'
            }
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'创建失败: {str(e)}', 'code': 500}), 500
    finally:
        conn.close()


@openapi_bp.route('/api/v1/keys/<key_id>', methods=['DELETE'], endpoint='api_v1_delete_key')
def api_v1_delete_key(key_id):
    if 'user_id' not in session:
        return jsonify({'error': '请先登录', 'code': 401}), 401

    conn = _app.get_db()
    try:
        row = conn.execute(
            'SELECT * FROM api_keys WHERE id = ? AND user_id = ?',
            (key_id, session['user_id'])
        ).fetchone()
        if not row:
            return jsonify({'error': '密钥不存在或无权限', 'code': 404}), 404

        conn.execute('UPDATE api_keys SET is_active = 0 WHERE id = ?', (key_id,))
        conn.commit()

        _app.log_message(
            log_type='security',
            log_level='WARNING',
            message=f'撤销API密钥: {row["name"]}',
            user_id=session['user_id'],
            action='revoke_api_key',
            request=request
        )

        return jsonify({
            'data': {'id': key_id, 'revoked': True},
            'meta': {'message': 'API密钥已撤销'}
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'撤销失败: {str(e)}', 'code': 500}), 500
    finally:
        conn.close()


@openapi_bp.route('/api/v1/files', methods=['GET'], endpoint='api_v1_list_files')
@_require_api_auth
def api_v1_list_files():
    user_id = request.api_user['id']
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    folder_id = request.args.get('folder_id', '')
    search = request.args.get('search', '')

    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    offset = (page - 1) * per_page
    where_clauses = ['user_id = ?']
    params = [user_id]

    if folder_id:
        where_clauses.append('folder_id = ?')
        params.append(folder_id)
    else:
        where_clauses.append('(folder_id IS NULL OR folder_id = "")')

    if search:
        where_clauses.append('(filename LIKE ? OR project_name LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%'])

    where_sql = ' AND '.join(where_clauses)
    count_sql = f'SELECT COUNT(*) FROM files WHERE {where_sql}'
    data_sql = f'SELECT id, filename, size, folder_id, project_name, project_desc, created_at FROM files WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?'

    conn = _app.get_db()
    try:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = conn.execute(data_sql, params + [per_page, offset]).fetchall()
        files = [dict(r) for r in rows]
        return jsonify({
            'data': files,
            'meta': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page if total > 0 else 0,
            }
        })
    finally:
        conn.close()


@openapi_bp.route('/api/v1/files/<file_id>', methods=['GET'], endpoint='api_v1_get_file')
@_require_api_auth
def api_v1_get_file(file_id):
    user_id = request.api_user['id']
    conn = _app.get_db()
    try:
        row = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, user_id)).fetchone()
        if not row:
            return jsonify({'error': '文件不存在或无权限访问', 'code': 404}), 404
        return jsonify({
            'data': dict(row)
        })
    finally:
        conn.close()


@openapi_bp.route('/api/v1/files', methods=['POST'], endpoint='api_v1_upload_file')
@_require_api_auth
def api_v1_upload_file():
    user_id = request.api_user['id']

    uploaded_file = request.files.get('file')
    if not uploaded_file or uploaded_file.filename == '':
        return jsonify({'error': '请选择要上传的文件', 'code': 400}), 400

    folder_id = request.form.get('folder_id')
    project_name = request.form.get('project_name', '')
    project_desc = request.form.get('project_desc', '')

    file_id = uuid.uuid4().hex
    ext = os.path.splitext(uploaded_file.filename)[1]
    stored_name = f"{file_id}{ext}"

    upload_folder = _app.app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, stored_name)
    uploaded_file.save(file_path)
    file_size = os.path.getsize(file_path)

    conn = _app.get_db()
    try:
        conn.execute(
            'INSERT INTO files (id, user_id, filename, stored_name, path, size, dkfile, project_name, project_desc, folder_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)',
            (file_id, user_id, uploaded_file.filename, stored_name, file_path, file_size, '{}', project_name, project_desc, folder_id)
        )
        conn.commit()

        _app.log_message(
            log_type='operation',
            log_level='INFO',
            message=f'API上传文件: {uploaded_file.filename}',
            user_id=user_id,
            action='api_upload_file',
            target_id=file_id,
            target_type='file',
            request=request
        )

        return jsonify({
            'data': {
                'id': file_id,
                'filename': uploaded_file.filename,
                'size': file_size,
                'folder_id': folder_id,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        }), 201
    except Exception as e:
        conn.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'error': f'上传失败: {str(e)}', 'code': 500}), 500
    finally:
        conn.close()


@openapi_bp.route('/api/v1/files/<file_id>', methods=['DELETE'], endpoint='api_v1_delete_file')
@_require_api_auth
def api_v1_delete_file(file_id):
    user_id = request.api_user['id']
    conn = _app.get_db()
    try:
        row = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, user_id)).fetchone()
        if not row:
            return jsonify({'error': '文件不存在或无权限删除', 'code': 404}), 404

        file_dict = dict(row)
        trash_id = uuid.uuid4().hex
        expire_at = (datetime.now() + timedelta(days=30)).isoformat()
        conn.execute(
            'INSERT INTO trash (id, file_id, user_id, filename, stored_name, file_path, file_size, file_type, folder_id, expire_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (trash_id, file_id, user_id, file_dict['filename'], file_dict['stored_name'],
             file_dict.get('path', ''), file_dict.get('size', 0), '', file_dict.get('folder_id'), expire_at)
        )
        conn.execute('DELETE FROM files WHERE id = ? AND user_id = ?', (file_id, user_id))
        conn.commit()

        _app.log_message(
            log_type='operation',
            log_level='WARNING',
            message=f'API删除文件: {file_dict["filename"]}',
            user_id=user_id,
            action='api_delete_file',
            target_id=file_id,
            target_type='file',
            request=request
        )

        return jsonify({
            'data': {'id': file_id, 'deleted': True},
            'meta': {'message': '文件已移至回收站，30天后自动清除'}
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'删除失败: {str(e)}', 'code': 500}), 500
    finally:
        conn.close()


@openapi_bp.route('/api/v1/files/<file_id>/download', methods=['GET'], endpoint='api_v1_download_file')
@_require_api_auth
def api_v1_download_file(file_id):
    user_id = request.api_user['id']
    conn = _app.get_db()
    try:
        row = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, user_id)).fetchone()
        if not row:
            return jsonify({'error': '文件不存在或无权限下载', 'code': 404}), 404

        upload_folder = _app.app.config.get('UPLOAD_FOLDER', 'uploads')
        return send_from_directory(
            upload_folder,
            row['stored_name'],
            as_attachment=True,
            download_name=row['filename']
        )
    finally:
        conn.close()


@openapi_bp.route('/api/v1/folders', methods=['GET'], endpoint='api_v1_list_folders')
@_require_api_auth
def api_v1_list_folders():
    user_id = request.api_user['id']
    parent_id = request.args.get('parent_id', '')

    conn = _app.get_db()
    try:
        if parent_id:
            rows = conn.execute(
                'SELECT * FROM folders WHERE user_id = ? AND parent_id = ? ORDER BY created_at DESC',
                (user_id, parent_id)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM folders WHERE user_id = ? AND (parent_id IS NULL OR parent_id = "") ORDER BY created_at DESC',
                (user_id,)
            ).fetchall()
        folders = [dict(r) for r in rows]
        return jsonify({
            'data': folders,
            'meta': {'total': len(folders)}
        })
    finally:
        conn.close()


@openapi_bp.route('/api/v1/folders', methods=['POST'], endpoint='api_v1_create_folder')
@_require_api_auth
def api_v1_create_folder():
    user_id = request.api_user['id']
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    purpose = (data.get('purpose') or '').strip()
    parent_id = data.get('parent_id')

    if not name:
        return jsonify({'error': '请输入文件夹名称', 'code': 400}), 400

    folder_id = uuid.uuid4().hex

    conn = _app.get_db()
    try:
        conn.execute(
            'INSERT INTO folders (id, user_id, name, purpose, parent_id) VALUES (?, ?, ?, ?, ?)',
            (folder_id, user_id, name, purpose or '', parent_id)
        )
        conn.commit()

        return jsonify({
            'data': {
                'id': folder_id,
                'name': name,
                'purpose': purpose,
                'parent_id': parent_id,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'创建失败: {str(e)}', 'code': 500}), 500
    finally:
        conn.close()


@openapi_bp.route('/api/v1/folders/<folder_id>', methods=['GET'], endpoint='api_v1_get_folder')
@_require_api_auth
def api_v1_get_folder(folder_id):
    user_id = request.api_user['id']
    conn = _app.get_db()
    try:
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', (folder_id, user_id)).fetchone()
        if not folder:
            return jsonify({'error': '文件夹不存在或无权限访问', 'code': 404}), 404

        files = conn.execute('SELECT id, filename, size, created_at FROM files WHERE folder_id = ?', (folder_id,)).fetchall()
        subfolders = conn.execute('SELECT * FROM folders WHERE parent_id = ? AND user_id = ?', (folder_id, user_id)).fetchall()

        return jsonify({
            'data': {
                **dict(folder),
                'files': [dict(f) for f in files],
                'subfolders': [dict(s) for s in subfolders],
            }
        })
    finally:
        conn.close()


@openapi_bp.route('/api/v1/search', methods=['GET'], endpoint='api_v1_search')
@_require_api_auth
def api_v1_search():
    user_id = request.api_user['id']
    q = (request.args.get('q') or '').strip()

    if not q:
        return jsonify({'error': '请提供搜索关键词', 'code': 400}), 400

    keyword = f'%{q}%'
    conn = _app.get_db()
    try:
        files = conn.execute(
            'SELECT id, filename, size, folder_id, project_name, created_at FROM files WHERE user_id = ? AND (filename LIKE ? OR project_name LIKE ? OR project_desc LIKE ?) ORDER BY created_at DESC',
            (user_id, keyword, keyword, keyword)
        ).fetchall()

        folders = conn.execute(
            'SELECT id, name, purpose, created_at FROM folders WHERE user_id = ? AND (name LIKE ? OR purpose LIKE ?) ORDER BY created_at DESC',
            (user_id, keyword, keyword)
        ).fetchall()

        return jsonify({
            'data': {
                'files': [dict(f) for f in files],
                'folders': [dict(f) for f in folders],
            },
            'meta': {
                'query': q,
                'total_files': len(files),
                'total_folders': len(folders),
            }
        })
    finally:
        conn.close()
