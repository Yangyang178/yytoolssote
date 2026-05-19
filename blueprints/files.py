from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session, send_from_directory, make_response, Response
import os
import uuid
import json
import shutil
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path

files_bp = Blueprint('files', __name__)


class _LazyAppImports:
    """懒加载代理，避免循环导入"""
    def __getattr__(self, name):
        if name == 'app':
            from app import app as _app
            return _app
        from app import (
            get_db, get_all_files, log_message, log_access,
            page_error_response, api_response,
            get_file_by_id, get_like_count, get_favorite_count,
            is_liked, is_favorited,
            get_user_storage_usage
        )
        locals_dict = locals()
        if name in locals_dict:
            return locals_dict[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


_app = _LazyAppImports()


@files_bp.route('/download/<stored_name>', endpoint='download_local')
def download(stored_name):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE stored_name = ?', (stored_name,)).fetchone()
        if not file:
            return _app.page_error_response('index', '文件不存在', 404)

        _app.log_access(file['id'], 'download', request)
        conn.execute('UPDATE files SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?', (file['id'],))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'下载文件: {file["filename"]}',
                   user_id=session['user_id'], action='download',
                   target_id=file['id'], target_type='file', request=request)

        return send_from_directory(_app.app.config['UPLOAD_FOLDER'], stored_name,
                                  as_attachment=True, download_name=file['filename'])
    finally:
        conn.close()


PREVIEW_MIME_OVERRIDES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff',
    '.tif': 'image/tiff',
    '.webp': 'image/webp',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.avif': 'image/avif',
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.ogg': 'video/ogg',
    '.ogv': 'video/ogg',
    '.mkv': 'video/x-matroska',
    '.wmv': 'video/x-ms-wmv',
    '.flv': 'video/x-flv',
    '.m4v': 'video/x-m4v',
    '.3gp': 'video/3gpp',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.flac': 'audio/flac',
    '.aac': 'audio/aac',
    '.m4a': 'audio/mp4',
    '.ogg': 'audio/ogg',
    '.wma': 'audio/x-ms-wma',
    '.opus': 'audio/opus',
    '.mid': 'audio/midi',
    '.midi': 'audio/midi',
    '.aiff': 'audio/aiff',
    '.aif': 'audio/aiff',
    '.py': 'text/x-python',
    '.pyw': 'text/x-python',
    '.js': 'text/javascript',
    '.mjs': 'text/javascript',
    '.ts': 'text/typescript',
    '.tsx': 'text/typescript',
    '.jsx': 'text/jsx',
    '.vue': 'text/x-vue',
    '.svelte': 'text/x-svelte',
    '.css': 'text/css',
    '.scss': 'text/x-scss',
    '.sass': 'text/x-sass',
    '.less': 'text/x-less',
    '.html': 'text/html',
    '.htm': 'text/html',
    '.json': 'application/json',
    '.xml': 'text/xml',
    '.yaml': 'text/yaml',
    '.yml': 'text/yaml',
    '.toml': 'text/x-toml',
    '.ini': 'text/plain',
    '.cfg': 'text/plain',
    '.conf': 'text/plain',
    '.sh': 'text/x-shellscript',
    '.bash': 'text/x-shellscript',
    '.zsh': 'text/x-shellscript',
    '.ps1': 'text/plain',
    '.bat': 'text/plain',
    '.cmd': 'text/plain',
    '.sql': 'text/x-sql',
    '.md': 'text/markdown',
    '.markdown': 'text/markdown',
    '.csv': 'text/csv',
    '.tsv': 'text/tab-separated-values',
    '.log': 'text/plain',
    '.txt': 'text/plain',
    '.rtf': 'text/rtf',
    '.env': 'text/plain',
    '.gitignore': 'text/plain',
    '.dockerignore': 'text/plain',
    '.editorconfig': 'text/plain',
    '.properties': 'text/plain',
    '.java': 'text/x-java-source',
    '.c': 'text/x-c',
    '.h': 'text/x-c',
    '.cpp': 'text/x-c++src',
    '.hpp': 'text/x-c++src',
    '.cs': 'text/x-csharp',
    '.go': 'text/x-go',
    '.rs': 'text/x-rust',
    '.php': 'text/x-php',
    '.rb': 'text/x-ruby',
    '.swift': 'text/x-swift',
    '.kt': 'text/x-kotlin',
    '.kts': 'text/x-kotlin',
    '.scala': 'text/x-scala',
    '.lua': 'text/x-lua',
    '.r': 'text/x-r',
    '.pl': 'text/x-perl',
    '.pm': 'text/x-perl',
    '.ex': 'text/x-elixir',
    '.exs': 'text/x-elixir',
    '.erl': 'text/x-erlang',
    '.hs': 'text/x-haskell',
    '.dart': 'text/x-dart',
    '.proto': 'text/x-protobuf',
    '.graphql': 'text/graphql',
    '.gql': 'text/graphql',
    '.tf': 'text/x-hcl',
    '.hcl': 'text/x-hcl',
    '.gradle': 'text/x-groovy',
    '.groovy': 'text/x-groovy',
    '.asm': 'text/x-asm',
    '.s': 'text/x-asm',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.odt': 'application/vnd.oasis.opendocument.text',
    '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
    '.odp': 'application/vnd.oasis.opendocument.presentation',
    '.pdf': 'application/pdf',
    '.zip': 'application/zip',
    '.rar': 'application/x-rar-compressed',
    '.7z': 'application/x-7z-compressed',
    '.tar': 'application/x-tar',
    '.gz': 'application/gzip',
    '.bz2': 'application/x-bzip2',
    '.xz': 'application/x-xz',
}


@files_bp.route('/preview/<stored_name>', endpoint='preview_file')
def preview_file(stored_name):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE stored_name = ? AND COALESCE(is_deleted, 0) = 0', (stored_name,)).fetchone()
        if not file:
            return _app.page_error_response('index', '文件不存在', 404)

        _app.log_access(file['id'], 'view', request)

        upload_folder = _app.app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, stored_name)

        if not os.path.isfile(file_path):
            return _app.page_error_response('index', '文件不存在', 404)

        ext = os.path.splitext(file['filename'])[1].lower()

        mime_type, _ = mimetypes.guess_type(file['filename'])
        if ext in PREVIEW_MIME_OVERRIDES:
            mime_type = PREVIEW_MIME_OVERRIDES[ext]
        if not mime_type:
            mime_type = 'application/octet-stream'

        try:
            with open(file_path, 'rb') as f:
                data = f.read()
        except Exception:
            return _app.page_error_response('index', '文件读取失败', 500)

        response = Response(data, mimetype=mime_type)
        response.headers['Content-Disposition'] = 'inline'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    finally:
        conn.close()


@files_bp.route('/file-detail/<file_id>', endpoint='folder_file_detail')
def folder_file_detail(file_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        file = _app.get_file_by_id(file_id)
        if not file:
            return _app.page_error_response('index', '文件不存在', 404)

        _app.log_access(file_id, 'view', request)
        conn.execute('UPDATE files SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?', (file_id,))
        conn.commit()

        is_owner = file['user_id'] == session.get('user_id') or session.get('role') == 'admin'

        file['like_count'] = _app.get_like_count(file_id)
        file['favorite_count'] = _app.get_favorite_count(file_id)
        file['is_liked'] = _app.is_liked(file_id, session.get('user_id'))
        file['is_favorited'] = _app.is_favorited(file_id, session.get('user_id'))

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

        file['categories'] = categories
        file['tags'] = tags

        return render_template(
            'detail.html',
            username=session.get('username'),
            item=file,
            categories=categories,
            tags=tags,
            all_tags=all_tags,
            all_categories=all_categories,
            is_owner=is_owner
        )
    finally:
        conn.close()


@files_bp.route('/api/share-file', methods=['POST'], endpoint='api_share_file')
def api_share_file():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    file_id = data.get('file_id')
    expires_hours = data.get('expires_hours', 24)

    if not file_id:
        return _app.api_response(success=False, message='缺少文件ID')

    conn = _app.get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?',
                           (file_id, session['user_id'])).fetchone()
        if not file:
            return _app.api_response(success=False, message='文件不存在或无权限分享')

        share_token = str(uuid.uuid4())
        share_url = f"{request.url_root}shared_file/{share_token}"

        from datetime import timedelta
        expires_at = (datetime.now() + timedelta(hours=expires_hours)).strftime('%Y-%m-%d %H:%M:%S')

        conn.execute('''INSERT INTO file_shares (id, file_id, token, share_url, password,
                       download_count, download_limit, expires_at, created_by, created_at)
                       VALUES (?, ?, ?, ?, NULL, 0, NULL, ?, ?, CURRENT_TIMESTAMP)''',
                    (str(uuid.uuid4()), file_id, share_token, share_url,
                     expires_at, session['user_id']))
        conn.commit()

        return _app.api_response(success=True, data={
            'share_url': share_url,
            'expires_at': expires_at,
            'token': share_token
        })
    finally:
        conn.close()


@files_bp.route('/api/files/<file_id>/interaction-status', methods=['GET'], endpoint='api_interaction_status')
def api_interaction_status(file_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    like_count = _app.get_like_count(file_id)
    favorite_count = _app.get_favorite_count(file_id)
    liked = _app.is_liked(file_id, session.get('user_id'))
    favorited = _app.is_favorited(file_id, session.get('user_id'))

    return _app.api_response(success=True, data={
        'like_count': like_count,
        'favorite_count': favorite_count,
        'liked': liked,
        'favorited': favorited
    })


@files_bp.route('/open/<stored_name>', endpoint='open_local')
def open_file(stored_name):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE stored_name = ?', (stored_name,)).fetchone()
        if not file:
            return _app.page_error_response('index', '文件不存在', 404)

        _app.log_access(file['id'], 'open', request)

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'打开文件: {file["filename"]}',
                   user_id=session['user_id'], action='open_file',
                   target_id=file['id'], target_type='file', request=request)

        return send_from_directory(_app.app.config['UPLOAD_FOLDER'], stored_name)
    finally:
        conn.close()


@files_bp.route('/sandbox/<stored_name>', endpoint='sandbox')
def sandbox(stored_name):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    conn = _app.get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE stored_name = ?', (stored_name,)).fetchone()
        if not file:
            return _app.page_error_response('index', '文件不存在', 404)

        _app.log_access(file['id'], 'sandbox', request)

        return send_from_directory(_app.app.config['UPLOAD_FOLDER'], stored_name)
    finally:
        conn.close()


@files_bp.route('/delete-file/<file_id>', methods=['POST'], endpoint='delete_file')
def delete_file(file_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?',
                           (file_id, session['user_id'])).fetchone()

        if not file:
            flash('文件不存在或无权限删除')
            return redirect(url_for('index'))

        file = dict(file)

        trash_id = str(uuid.uuid4())
        expire_at = (datetime.now() + timedelta(days=30)).isoformat()
        conn.execute('''INSERT INTO trash (id, file_id, user_id, filename, stored_name, file_path, file_size, file_type, folder_id, expire_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (trash_id, file_id, session['user_id'], file['filename'], file['stored_name'],
                     file.get('path', ''), file.get('size', 0), '', file.get('folder_id'), expire_at))

        conn.execute('DELETE FROM files WHERE id = ? AND user_id = ?', (file_id, session['user_id']))
        conn.commit()

        _app.log_message(log_type='operation', log_level='WARNING',
                   message=f'删除文件到回收站: {file["filename"]}',
                   user_id=session['user_id'], action='delete_to_trash',
                   target_id=file_id, target_type='file', request=request)

        flash(f'文件 "{file["filename"]}" 已移至回收站（30天后自动清除）')
        referrer = request.headers.get('Referer', '')
        if referrer:
            return redirect(referrer)
        return redirect(url_for('index'))
    except Exception as e:
        conn.rollback()
        flash(f'删除失败: {str(e)}')
        return redirect(url_for('index'))
    finally:
        conn.close()


@files_bp.route('/file/<file_id>', methods=['GET'], endpoint='file_info')
def file_info(file_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    conn = _app.get_db()
    try:
        file = _app.get_file_by_id(file_id)
        if not file:
            return _app.api_response(success=False, message="文件不存在", code=404)

        file['like_count'] = _app.get_like_count(file_id)
        file['favorite_count'] = _app.get_favorite_count(file_id)
        file['is_liked'] = _app.is_liked(file_id, session.get('user_id'))
        file['is_favorited'] = _app.is_favorited(file_id, session.get('user_id'))

        return _app.api_response(success=True, data={'file': dict(file)})
    finally:
        conn.close()


@files_bp.route('/file/<file_id>/delete', methods=['POST'], endpoint='file_delete')
def file_delete(file_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message="请先登录", code=401)

    conn = _app.get_db()
    try:
        file = conn.execute("SELECT * FROM files WHERE id = ? AND user_id = ?", (file_id, session['user_id'])).fetchone()
        if not file:
            return _app.api_response(success=False, message="文件不存在或无权限", code=404)

        file = dict(file)

        trash_id = str(uuid.uuid4())
        expire_at = (datetime.now() + timedelta(days=30)).isoformat()
        conn.execute("""INSERT INTO trash (id, file_id, user_id, filename, stored_name, file_path, file_size, file_type, folder_id, expire_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (trash_id, file_id, session['user_id'], file['filename'], file['stored_name'],
                     file.get('path', ''), file.get('size', 0), '', file.get('folder_id'), expire_at))
        conn.execute("DELETE FROM files WHERE id = ? AND user_id = ?", (file_id, session['user_id']))
        conn.commit()

        _app.log_message(log_type='operation', log_level='WARNING',
                   message=f"API删除文件到回收站: {file['filename']}",
                   user_id=session['user_id'], action='api_delete_to_trash',
                   target_id=file_id, target_type='file', request=request)

        return _app.api_response(success=True, message="文件已移至回收站")
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f"删除失败: {str(e)}")
    finally:
        conn.close()


@files_bp.route('/file/replace', methods=['POST'], endpoint='file_replace')
def file_replace():
    if 'user_id' not in session:
        return _app.api_response(success=False, message="请先登录", code=401)

    file_id = request.form.get('file_id')
    new_file = request.files.get('file')

    if not file_id or not new_file or new_file.filename == '':
        return _app.api_response(success=False, message="参数不完整")

    conn = _app.get_db()
    try:
        existing = conn.execute("SELECT * FROM files WHERE id = ? AND user_id = ?", (file_id, session['user_id'])).fetchone()
        if not existing:
            return _app.api_response(success=False, message="原文件不存在或无权限")

        old_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], existing['stored_name'])
        if os.path.exists(old_path):
            os.remove(old_path)

        ext = os.path.splitext(new_file.filename)[1]
        new_stored_name = f"{uuid.uuid4()}{ext}"
        new_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], new_stored_name)
        new_file.save(new_path)
        new_size = os.path.getsize(new_path)

        dkfile_info = "{}"

        conn.execute("""UPDATE files SET filename=?, stored_name=?, path=?, size=?,
                       dkfile=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (new_file.filename, new_stored_name, new_path, new_size, dkfile_info, file_id))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f"替换文件: {existing['filename']} -> {new_file.filename}",
                   user_id=session['user_id'], action='replace_file',
                   target_id=file_id, target_type='file', request=request)

        return _app.api_response(success=True, message="替换成功",
                          data={"new_filename": new_file.filename, "new_size": new_size})
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f"替换失败: {str(e)}")
    finally:
        conn.close()


@files_bp.route('/share_file', methods=['GET', 'POST'], endpoint='share_file')
def share_file():
    if request.method == 'POST':
        if 'user_id' not in session:
            return redirect(url_for('auth'))

        file_id = request.form.get('file_id')

        conn = _app.get_db()
        try:
            file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?',
                               (file_id, session['user_id'])).fetchone()

            if not file:
                flash('文件不存在或无权限分享')
                return redirect(url_for('detail', file_id=file_id))

            share_token = str(uuid.uuid4())
            share_url = f"{request.url_root}shared_file/{share_token}"

            expires_at_str = request.form.get('expires_at')
            if expires_at_str:
                expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
            else:
                expires_at = None

            password = request.form.get('share_password') or None
            download_limit = request.form.get('download_limit') or None

            conn.execute('''INSERT INTO file_shares (id, file_id, token, share_url, password,
                           download_count, download_limit, expires_at, created_by, created_at)
                           VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, CURRENT_TIMESTAMP)''',
                        (str(uuid.uuid4()), file_id, share_token, share_url,
                         password, download_limit, expires_at, session['user_id']))
            conn.commit()

            _app.log_message(log_type='operation', log_level='INFO',
                       message=f'创建分享链接: {file["filename"]}',
                       user_id=session['user_id'], action='create_share_link',
                       target_id=file_id, target_type='file', details=share_url, request=request)

            flash(f'分享链接已生成: {share_url}')
            return redirect(url_for('detail', file_id=file_id))
        except Exception as e:
            conn.rollback()
            flash(f'创建分享链接失败: {e}')
            return redirect(url_for('detail', file_id=file_id))
        finally:
            conn.close()

    file_id = request.args.get('file_id')
    if not file_id:
        return redirect(url_for('index'))

    conn = _app.get_db()
    try:
        file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
        if not file:
            flash('文件不存在')
            return redirect(url_for('index'))

        shares = conn.execute('''SELECT * FROM file_shares WHERE file_id = ?
                               ORDER BY created_at DESC''', (file_id,)).fetchall()

        return render_template('share.html',
                             username=session.get('username'),
                             file=dict(file),
                             shares=[dict(s) for s in shares])
    finally:
        conn.close()


@files_bp.route('/shared_file/<token>', endpoint='shared_file')
def shared_file(token):
    conn = _app.get_db()
    try:
        share = conn.execute('''SELECT fs.*, f.filename, f.stored_name, f.size, f.project_name, f.project_desc
                               FROM file_shares fs JOIN files f ON fs.file_id = f.id
                               WHERE fs.token = ?''', (token,)).fetchone()

        if not share:
            return _app.page_error_response('auth', '分享链接无效或已过期', 404)

        share_dict = dict(share)
        sharer = conn.execute('SELECT username FROM users WHERE id = ?', (share['user_id'],)).fetchone()
        share_dict['username'] = sharer['username'] if sharer else '未知用户'

        if share['expires_at']:
            try:
                expires_dt = datetime.strptime(share['expires_at'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() > expires_dt:
                    return _app.page_error_response('auth', '分享链接已过期', 410)
            except ValueError:
                pass

        if share['password']:
            if request.method == 'POST':
                input_password = request.form.get('password', '')
                if input_password != share['password']:
                    flash('密码错误')
                    return render_template('shared_file.html',
                                         file=share_dict,
                                         share=share_dict,
                                         requires_password=True,
                                         token=token)
            else:
                return render_template('shared_file.html',
                                     file=share_dict,
                                     share=share_dict,
                                     requires_password=True,
                                     token=token)

        if share['download_limit'] and share['download_count'] >= int(share['download_limit']):
            return _app.page_error_response('auth', '下载次数已达上限', 410)

        return render_template('shared_file.html',
                             file=share_dict,
                             share=share_dict,
                             requires_password=False,
                             token=token)
    finally:
        conn.close()


@files_bp.route('/download-shared/<token>', endpoint='download_shared_file')
def download_shared(token):
    conn = _app.get_db()
    try:
        share = conn.execute('''SELECT fs.*, f.stored_name, f.filename
                               FROM file_shares fs JOIN files f ON fs.file_id = f.id
                               WHERE fs.token = ?''', (token,)).fetchone()

        if not share:
            return _app.page_error_response('auth', '分享链接无效或已过期', 404)

        if share['expires_at']:
            try:
                if datetime.now() > datetime.strptime(share['expires_at'], '%Y-%m-%d %H:%M:%S'):
                    return _app.page_error_response('auth', '分享链接已过期', 410)
            except ValueError:
                pass

        if share['download_limit'] and share['download_count'] >= int(share['download_limit']):
            return _app.page_error_response('auth', '下载次数已达上限', 410)

        conn.execute('UPDATE file_shares SET download_count = download_count + 1 WHERE id = ?',
                    (share['id'],))
        conn.commit()

        _app.log_access(share['file_id'], 'download', request)

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'通过分享链接下载: {share["filename"]}',
                   action='download_shared', target_id=share['file_id'],
                   target_type='file', request=request)

        return send_from_directory(_app.app.config['UPLOAD_FOLDER'], share['stored_name'],
                                  as_attachment=True, download_name=share['filename'])
    finally:
        conn.close()


@files_bp.route('/uploads/<path:filename>', endpoint='uploads_serve')
def uploaded_files(filename):
    return send_from_directory(_app.app.config['UPLOAD_FOLDER'], filename)


@files_bp.route('/batch-upload-files/<folder_id>', methods=['POST'], endpoint='batch_upload_files')
def batch_upload_files(folder_id):
    return upload_to_folder(folder_id)


@files_bp.route('/upload-to-folder/<folder_id>', methods=['POST'], endpoint='upload_to_folder')
def upload_to_folder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?',
                            (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('文件夹不存在或无权限')
            return redirect(url_for('project_folders'))

        files = request.files.getlist('file')
        if not files or files[0].filename == '':
            flash('请选择要上传的文件')
            return redirect(url_for('folder_detail', folder_id=folder_id))

        html_exts = ('.html', '.htm')
        html_files = [f for f in files if f.filename and os.path.splitext(f.filename)[1].lower() in html_exts]
        if html_files:
            html_names = ', '.join(f.filename for f in html_files)
            flash('HTML 文件（{}）不能上传到项目文件夹，请在用户中心"我的文件"中上传'.format(html_names))
            return redirect(url_for('folder_detail', folder_id=folder_id))

        storage_usage = _app.get_user_storage_usage(session['user_id'])

        uploaded_count = 0
        total_upload_size = 0
        for file in files:
            if file.filename == '' or not hasattr(file, 'filename'):
                continue
            file_size = len(file.read())
            file.seek(0)
            total_upload_size += file_size

        if storage_usage['total_size'] + total_upload_size > storage_usage['max_storage']:
            flash(f'存储空间不足！已使用 {storage_usage["total_size"] / (1024*1024):.2f}MB，剩余空间不足')
            return redirect(url_for('folder_detail', folder_id=folder_id))

        for file in files:
            if file.filename == '' or not hasattr(file, 'filename'):
                continue

            file_id = str(uuid.uuid4())
            ext = os.path.splitext(file.filename)[1]
            stored_name = f"{file_id}{ext}"

            file_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)
            file.save(file_path)
            file_size = os.path.getsize(file_path)

            conn.execute('''INSERT INTO files (id, user_id, filename, stored_name, path, size,
                           project_name, project_desc, folder_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                        (file_id, session['user_id'], file.filename, stored_name,
                         file_path, file_size, '', '', folder_id))

            uploaded_count += 1

        conn.commit()
        flash(f'成功上传 {uploaded_count} 个文件到文件夹: {folder["name"]}')
    except Exception as e:
        conn.rollback()
        flash(f'上传失败: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('folder_detail', folder_id=folder_id))


@files_bp.route('/upload-folder-to-folder/<folder_id>', methods=['POST'], endpoint='upload_folder_to_folder')
def upload_folder_to_folder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?',
                            (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('文件夹不存在或无权限')
            return redirect(url_for('project_folders'))

        files = request.files.getlist('file')
        description = request.form.get('description', '')

        if not files or files[0].filename == '':
            flash('请选择要上传的文件')
            return redirect(url_for('folder_detail', folder_id=folder_id))

        html_exts = ('.html', '.htm')
        html_files = [f for f in files if f.filename and os.path.splitext(f.filename)[1].lower() in html_exts]
        if html_files:
            html_names = ', '.join(f.filename for f in html_files)
            flash('HTML 文件（{}）不能上传到项目文件夹，请在用户中心"我的文件"中上传'.format(html_names))
            return redirect(url_for('folder_detail', folder_id=folder_id))

        temp_files = []
        for file in files:
            if file.filename == '' or not hasattr(file, 'filename'):
                continue

            import tempfile
            fd, tmp_path = tempfile.mkstemp()
            try:
                file.save(tmp_path)
            finally:
                os.close(fd)

            file_size = os.path.getsize(tmp_path)
            temp_files.append((tmp_path, file.filename, file_size))

        total_upload_size = sum(t[2] for t in temp_files)

        storage_usage = _app.get_user_storage_usage(session['user_id'])

        if storage_usage['total_size'] + total_upload_size > storage_usage['max_storage']:
            for tmp_path, _, _ in temp_files:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            flash('存储空间不足！')
            return redirect(url_for('folder_detail', folder_id=folder_id))

        uploaded_files_count = 0
        for tmp_path, relative_path, file_size in temp_files:
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(relative_path)[1]
            stored_name = f"{file_id}{ext}"
            file_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)
            import shutil
            shutil.move(tmp_path, file_path)

            conn.execute('''INSERT INTO files (id, user_id, filename, stored_name, path, size,
                           project_name, project_desc, folder_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                        (file_id, session['user_id'], os.path.basename(relative_path),
                         stored_name, file_path, file_size, relative_path, description, folder_id))
            uploaded_files_count += 1

        conn.commit()
        flash(f'成功上传 {uploaded_files_count} 个文件')
    except Exception as e:
        conn.rollback()
        flash(f'上传失败: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('folder_detail', folder_id=folder_id))


@files_bp.route('/create-subfolder/<folder_id>', methods=['POST'], endpoint='create_subfolder')
def create_subfolder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    name = request.form.get('name')
    purpose = request.form.get('purpose')

    if not all([name, purpose]):
        flash('请填写文件夹名称和用途')
        return redirect(url_for('folder_detail', folder_id=folder_id))

    conn = _app.get_db()
    try:
        parent_folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?',
                                   (folder_id, session['user_id'])).fetchone()
        if not parent_folder:
            flash('父文件夹不存在或无权限')
            return redirect(url_for('folder_detail', folder_id=folder_id))

        subfolder_id = str(uuid.uuid4())
        conn.execute('INSERT INTO folders (id, user_id, name, purpose, parent_id) VALUES (?, ?, ?, ?, ?)',
                   (subfolder_id, session['user_id'], name, purpose, folder_id))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO', message='创建子文件夹',
                   user_id=session['user_id'], action='create',
                   target_id=subfolder_id, target_type='folder',
                   details=f'文件夹名称: {name}', request=request)

        flash('子文件夹创建成功')
    except Exception as e:
        conn.rollback()
        flash(f'创建失败: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('folder_detail', folder_id=folder_id))


@files_bp.route('/batch-delete-files', methods=['POST'], endpoint='batch_delete_files')
def batch_delete_files():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    file_ids = request.form.get('file_ids', '').split(',')
    folder_id = request.form.get('folder_id')

    if not file_ids or file_ids == ['']:
        flash('请选择要删除的文件')
        return redirect(url_for('folder_detail', folder_id=folder_id))

    conn = _app.get_db()
    try:
        deleted_count = 0
        for fid in file_ids:
            if fid:
                file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?',
                                   (fid, session['user_id'])).fetchone()
                if file:
                    file = dict(file)
                    trash_id = str(uuid.uuid4())
                    expire_at = (datetime.now() + timedelta(days=30)).isoformat()
                    conn.execute('''INSERT INTO trash (id, file_id, user_id, filename, stored_name, file_path, file_size, file_type, folder_id, expire_at)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (trash_id, fid, session['user_id'], file['filename'], file['stored_name'],
                                 file.get('path', ''), file.get('size', 0), '', file.get('folder_id'), expire_at))
                    conn.execute('DELETE FROM files WHERE id = ? AND user_id = ?', (fid, session['user_id']))
                    deleted_count += 1

        conn.commit()

        _app.log_message(log_type='operation', log_level='WARNING',
                        message=f'批量删除文件到回收站: {deleted_count}个文件',
                        user_id=session['user_id'], action='batch_delete_to_trash',
                        target_type='file', request=request)

        flash(f'成功将 {deleted_count} 个文件移至回收站')
    except Exception as e:
        conn.rollback()
        flash(f'删除失败: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('folder_detail', folder_id=folder_id))


@files_bp.route('/project-folders', endpoint='project_folders')
def project_folders():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        conn.execute(
            "UPDATE files SET folder_id = NULL WHERE (filename LIKE '%.html' OR filename LIKE '%.htm') AND folder_id IS NOT NULL AND user_id = ?",
            (session['user_id'],))
        conn.commit()

        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        folders = conn.execute(
            "SELECT * FROM folders WHERE user_id = ? AND (parent_id IS NULL OR parent_id = '') ORDER BY created_at DESC",
            (session['user_id'],)).fetchall()

        storage_usage = _app.get_user_storage_usage(session['user_id'])

        return render_template('project_folders.html',
                             username=session.get('username'), user=dict(user) if user else None,
                             folders=[dict(f) for f in folders], storage_usage=storage_usage)
    finally:
        conn.close()


@files_bp.route('/folder/<folder_id>', endpoint='folder_detail')
def folder_detail(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?',
                            (folder_id, session['user_id'])).fetchone()
        if not folder:
            return _app.page_error_response('project_folders', '文件夹不存在或无权限', 404)

        files = conn.execute(
            "SELECT * FROM files WHERE folder_id = ? AND (filename NOT LIKE '%.html' AND filename NOT LIKE '%.htm')",
            (folder_id,)).fetchall()
        subfolders = conn.execute('SELECT * FROM folders WHERE parent_id = ? AND user_id = ?',
                                 (folder_id, session['user_id'])).fetchall()
        user_folders = conn.execute(
            "SELECT id, name FROM folders WHERE user_id = ? AND id != ? ORDER BY name",
            (session['user_id'], folder_id)).fetchall()

        return render_template('folder_detail.html', username=session.get('username'),
                             user=dict(user) if user else None,
                             folder=dict(folder) if folder else None,
                             files=[dict(f) for f in files],
                             subfolders=[dict(s) for s in subfolders],
                             user_folders=[dict(uf) for uf in user_folders])
    finally:
        conn.close()


@files_bp.route('/delete-folder/<folder_id>', methods=['POST'], endpoint='delete_folder')
def delete_folder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?',
                             (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('文件夹不存在或无权限')
            return redirect(url_for('project_folders'))

        folder = dict(folder)

        def move_files_to_trash(parent_folder_id):
            subfolders = conn.execute('SELECT id FROM folders WHERE parent_id = ? AND user_id = ?',
                                     (parent_folder_id, session['user_id'])).fetchall()
            for subfolder in subfolders:
                move_files_to_trash(subfolder['id'])
                sub_files = conn.execute('SELECT * FROM files WHERE folder_id = ? AND user_id = ?',
                                        (subfolder['id'], session['user_id'])).fetchall()
                for f in sub_files:
                    f = dict(f)
                    trash_id = str(uuid.uuid4())
                    expire_at = (datetime.now() + timedelta(days=30)).isoformat()
                    conn.execute('''INSERT INTO trash (id, file_id, user_id, filename, stored_name, file_path, file_size, file_type, folder_id, expire_at)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (trash_id, f['id'], session['user_id'], f['filename'], f['stored_name'],
                                 f.get('path', ''), f.get('size', 0), '', f.get('folder_id'), expire_at))
                conn.execute('DELETE FROM files WHERE folder_id = ? AND user_id = ?',
                            (subfolder['id'], session['user_id']))
                conn.execute('DELETE FROM folders WHERE id = ?', (subfolder['id'],))

        move_files_to_trash(folder_id)

        files_in_folder = conn.execute('SELECT * FROM files WHERE folder_id = ? AND user_id = ?',
                                       (folder_id, session['user_id'])).fetchall()
        for f in files_in_folder:
            f = dict(f)
            trash_id = str(uuid.uuid4())
            expire_at = (datetime.now() + timedelta(days=30)).isoformat()
            conn.execute('''INSERT INTO trash (id, file_id, user_id, filename, stored_name, file_path, file_size, file_type, folder_id, expire_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (trash_id, f['id'], session['user_id'], f['filename'], f['stored_name'],
                         f.get('path', ''), f.get('size', 0), '', f.get('folder_id'), expire_at))

        conn.execute('DELETE FROM files WHERE folder_id = ? AND user_id = ?',
                    (folder_id, session['user_id']))
        conn.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
        conn.commit()

        _app.log_message(log_type='operation', log_level='WARNING',
                        message=f'删除文件夹: {folder["name"]}',
                        user_id=session['user_id'], action='delete_folder',
                        target_id=folder_id, target_type='folder', request=request)

        flash(f'文件夹 "{folder["name"]}" 及其内容已移至回收站')
    except Exception as e:
        conn.rollback()
        flash(f'删除失败: {str(e)}')
    finally:
        conn.close()

    referrer = request.headers.get('Referer', '')
    if 'folder' in referrer:
        return redirect(url_for('project_folders'))
    return redirect(url_for('project_folders'))


@files_bp.route('/create-folder', methods=['POST'], endpoint='create_folder')
def create_folder():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    name = request.form.get('name')
    purpose = request.form.get('purpose')

    if not all([name, purpose]):
        flash('请填写文件夹名称和用途')
        return redirect(url_for('project_folders'))

    conn = _app.get_db()
    try:
        folder_id = str(uuid.uuid4())
        conn.execute('INSERT INTO folders (id, user_id, name, purpose) VALUES (?, ?, ?, ?)',
                   (folder_id, session['user_id'], name, purpose))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO', message='创建文件夹',
                   user_id=session['user_id'], action='create',
                   target_id=folder_id, target_type='folder',
                   details=f'文件夹名称: {name}', request=request)

        flash('文件夹创建成功')
        return redirect(url_for('project_folders'))
    except Exception as e:
        conn.rollback()
        flash(f'创建文件夹失败: {str(e)}')
        return redirect(url_for('project_folders'))
    finally:
        conn.close()


@files_bp.route('/api/files', endpoint='api_get_files')
def api_get_files():
    files = _app.get_all_files()
    return _app.api_response(success=True, data={'files': files})


@files_bp.route('/api/check-login', endpoint='check_login')
def check_login():
    if 'user_id' in session:
        return _app.api_response(success=True, data={'logged_in': True, 'username': session.get('username')})
    return _app.api_response(success=True, data={'logged_in': False})


@files_bp.route('/api/my-files', methods=['GET'], endpoint='api_my_files')
def api_my_files():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    tag = request.args.get('tag', '')

    offset = (page - 1) * per_page
    where_clauses = ['f.user_id = ?']
    params = [session['user_id']]

    if search:
        where_clauses.append('(f.filename LIKE ? OR f.project_name LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%'])

    if category:
        where_clauses.append('EXISTS (SELECT 1 FROM file_categories fc WHERE fc.file_id = f.id AND fc.category_id = ?)')
        params.append(category)

    if tag:
        where_clauses.append('EXISTS (SELECT 1 FROM file_tags ft WHERE ft.file_id = f.id AND ft.tag_id = ?)')
        params.append(tag)

    where_sql = ' AND '.join(where_clauses)
    count_sql = f'SELECT COUNT(*) FROM files f WHERE {where_sql}'
    data_sql = f'''SELECT f.* FROM files f WHERE {where_sql}
                  ORDER BY f.created_at DESC LIMIT ? OFFSET ?'''

    conn = _app.get_db()
    try:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = conn.execute(data_sql, params + [per_page, offset]).fetchall()

        files = []
        for row in rows:
            f = dict(row)
            f['like_count'] = _app.get_like_count(f['id'])
            f['favorite_count'] = _app.get_favorite_count(f['id'])
            f['is_liked'] = _app.is_liked(f['id'], session.get('user_id'))
            f['is_favorited'] = _app.is_favorited(f['id'], session.get('user_id'))
            file_tags = conn.execute(
                """SELECT t.id, t.name FROM tags t JOIN file_tags ft ON t.id = ft.tag_id
                   WHERE ft.file_id = ?""", (f['id'],)).fetchall()
            f['tags'] = [dict(t) for t in file_tags]
            files.append(f)

        return _app.api_response(success=True, data={
            'files': files,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    finally:
        conn.close()


@files_bp.route('/api/files/<file_id>/like', methods=['POST'], endpoint='api_like_file')
def api_like_file(file_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        file = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if not file:
            return _app.api_response(success=False, message='文件不存在', code=404)

        existing = conn.execute("SELECT * FROM likes WHERE user_id = ? AND file_id = ?",
                              (session['user_id'], file_id)).fetchone()
        if existing:
            conn.execute("DELETE FROM likes WHERE id = ?", (existing['id'],))
            liked = False
        else:
            conn.execute("INSERT INTO likes (user_id, file_id) VALUES (?, ?)",
                        (session['user_id'], file_id))
            liked = True
        conn.commit()

        like_count = _app.get_like_count(file_id)
        return _app.api_response(success=True, data={'liked': liked, 'like_count': like_count})
    finally:
        conn.close()


@files_bp.route('/api/files/<file_id>/favorite', methods=['POST'], endpoint='api_favorite_file')
def api_favorite_file(file_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        file = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if not file:
            return _app.api_response(success=False, message='文件不存在', code=404)

        existing = conn.execute("SELECT * FROM favorites WHERE user_id = ? AND file_id = ?",
                              (session['user_id'], file_id)).fetchone()
        if existing:
            conn.execute("DELETE FROM favorites WHERE id = ?", (existing['id'],))
            favorited = False
        else:
            conn.execute("INSERT INTO favorites (user_id, file_id) VALUES (?, ?)",
                        (session['user_id'], file_id))
            favorited = True
        conn.commit()

        favorite_count = _app.get_favorite_count(file_id)
        return _app.api_response(success=True, data={'favorited': favorited, 'favorite_count': favorite_count})
    finally:
        conn.close()


@files_bp.route('/batch-download', methods=['POST'], endpoint='batch_download')
def batch_download():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    file_ids = request.form.get('file_ids', '').split(',')
    if not file_ids or file_ids == ['']:
        flash('请选择要下载的文件')
        return redirect(url_for('index'))

    conn = _app.get_db()
    try:
        files = []
        for fid in file_ids:
            if fid:
                f = conn.execute("SELECT * FROM files WHERE id = ? AND user_id = ?",
                               (fid, session['user_id'])).fetchone()
                if f:
                    files.append(dict(f))

        if not files:
            flash('未找到有效文件')
            return redirect(url_for('index'))

        import zipfile, io
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                file_path = f['path']
                if os.path.exists(file_path):
                    zf.write(file_path, f['filename'])

        buffer.seek(0)
        zip_name = f"batch_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = f'attachment; filename="{zip_name}"'

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'批量下载: {len(files)} 个文件',
                   user_id=session['user_id'], action='batch_download', request=request)

        return response
    finally:
        conn.close()


@files_bp.route('/batch-move', methods=['POST'], endpoint='batch_move')
def batch_move():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    file_ids = data.get('file_ids', [])
    target_folder_id = data.get('target_folder_id')

    if not file_ids or not target_folder_id:
        return _app.api_response(success=False, message='请选择文件和目标文件夹')

    conn = _app.get_db()
    try:
        html_exts = ('.html', '.htm')
        if target_folder_id != 'root':
            for fid in file_ids:
                if fid:
                    file_row = conn.execute("SELECT filename FROM files WHERE id = ? AND user_id = ?", (fid, session['user_id'])).fetchone()
                    if file_row and os.path.splitext(file_row['filename'])[1].lower() in html_exts:
                        return _app.api_response(success=False, message='HTML 文件（{}）不能移动到项目文件夹'.format(file_row['filename']))

            target_folder = conn.execute("SELECT * FROM folders WHERE id = ? AND user_id = ?",
                                        (target_folder_id, session['user_id'])).fetchone()
            if not target_folder:
                return _app.api_response(success=False, message='目标文件夹不存在或无权限')

        moved_count = 0
        for fid in file_ids:
            if fid:
                result = conn.execute("UPDATE files SET folder_id = ? WHERE id = ? AND user_id = ?",
                                    (target_folder_id if target_folder_id != 'root' else None, fid, session['user_id']))
                if result.rowcount > 0:
                    moved_count += 1

        conn.commit()
        folder_name = '根目录' if target_folder_id == 'root' else target_folder['name'] if target_folder_id != 'root' else ''
        return _app.api_response(success=True, message='成功移动 {} 个文件到文件夹: {}'.format(moved_count, folder_name), data={'moved_count': moved_count})
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message='移动失败: {}'.format(str(e)))
    finally:
        conn.close()


@files_bp.route('/api/upload/chunk/init', methods=['POST'], endpoint='chunk_init')
def chunk_init():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    filename = data.get('filename', '')
    total_size = data.get('totalSize', 0)
    chunk_size = data.get('chunkSize', 5 * 1024 * 1024)
    file_hash = data.get('hash', '')

    upload_id = str(uuid.uuid4())

    conn = _app.get_db()
    try:
        conn.execute("""INSERT INTO chunk_uploads (id, user_id, filename, total_size, chunk_size,
                       file_hash, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'uploading', CURRENT_TIMESTAMP)""",
                    (upload_id, session['user_id'], filename, total_size, chunk_size, file_hash))
        conn.commit()
        return _app.api_response(success=True, data={'uploadId': upload_id})
    finally:
        conn.close()


@files_bp.route('/api/upload/chunk/upload', methods=['POST'], endpoint='chunk_upload')
def chunk_upload():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    upload_id = request.form.get('uploadId')
    chunk_index = request.form.get('chunkIndex', type=int)
    chunk_data = request.files.get('chunk')

    if not upload_id or chunk_data is None:
        return _app.api_response(success=False, message='参数缺失')

    conn = _app.get_db()
    try:
        upload = conn.execute("SELECT * FROM chunk_uploads WHERE id = ? AND user_id = ?",
                             (upload_id, session['user_id'])).fetchone()
        if not upload:
            return _app.api_response(success=False, message='上传任务不存在')

        chunk_dir = Path(_app.app.config['CHUNK_UPLOAD_DIR']) / upload_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_path = chunk_dir / str(chunk_index)
        chunk_data.save(str(chunk_path))

        conn.execute("UPDATE chunk_uploads SET uploaded_chunks = uploaded_chunks || ?, last_activity = CURRENT_TIMESTAMP WHERE id = ?",
                    (f",{chunk_index}", upload_id))
        conn.commit()

        return _app.api_response(success=True, message='分片上传成功')
    finally:
        conn.close()


@files_bp.route('/api/upload/chunk/merge', methods=['POST'], endpoint='chunk_merge')
def chunk_merge():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    upload_id = data.get('uploadId')

    conn = _app.get_db()
    try:
        upload = conn.execute("SELECT * FROM chunk_uploads WHERE id = ? AND user_id = ?",
                             (upload_id, session['user_id'])).fetchone()
        if not upload:
            return _app.api_response(success=False, message='上传任务不存在')

        chunk_dir = Path(_app.app.config['CHUNK_UPLOAD_DIR']) / upload_id
        chunks = sorted(chunk_dir.glob('*'), key=lambda x: int(x.name))

        file_id = str(uuid.uuid4())
        ext = os.path.splitext(upload['filename'])[1]
        stored_name = f"{file_id}{ext}"
        final_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)

        with open(final_path, 'wb') as outf:
            for chunk in chunks:
                with open(chunk, 'rb') as cf:
                    shutil.copyfileobj(cf, outf)

        actual_size = os.path.getsize(final_path)
        dkfile_info = "{}"

        conn.execute("""INSERT INTO files (id, user_id, filename, stored_name, path, size, dkfile,
                       project_name, project_desc, folder_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, CURRENT_TIMESTAMP)""",
                    (file_id, session['user_id'], upload['filename'], stored_name,
                     final_path, actual_size, dkfile_info, '', ''))

        conn.execute("UPDATE chunk_uploads SET status = 'completed' WHERE id = ?", (upload_id,))
        conn.commit()

        shutil.rmtree(str(chunk_dir), ignore_errors=True)

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'分片合并完成: {upload["filename"]}, 大小: {actual_size}',
                   user_id=session['user_id'], action='chunk_merge',
                   target_id=file_id, target_type='file', request=request)

        return _app.api_response(success=True, data={
            'fileId': file_id, 'filename': upload['filename'], 'size': actual_size
        })
    finally:
        conn.close()
