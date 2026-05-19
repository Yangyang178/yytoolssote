from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
import os
import json
import uuid


class _LazyAppImports:
    def __getattr__(self, name):
        from app import app as _flask_app, get_db, log_message, page_error_response, api_response, get_user_storage_usage
        _mapping = {
            'app': _flask_app,
            'get_db': get_db,
            'log_message': log_message,
            'page_error_response': page_error_response,
            'api_response': api_response,
            'get_user_storage_usage': get_user_storage_usage,
        }
        if name not in _mapping:
            raise AttributeError(f"module 'app' has no attribute '{name}'")
        return _mapping[name]


_app = _LazyAppImports()

trash_bp = Blueprint('trash', __name__)


@trash_bp.route('/trash', endpoint='trash')
def trash():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = _app.get_db()
    try:
        trash_items = []
        rows = conn.execute(
            "SELECT * FROM trash WHERE user_id = ? ORDER BY deleted_at DESC",
            (session['user_id'],)).fetchall()

        for row in rows:
            item = dict(row)
            item['original_data'] = {
                'filename': row['filename'],
                'stored_name': row['stored_name'],
                'file_path': row['file_path'],
                'file_size': row['file_size'],
                'file_type': row['file_type'],
            }
            item['display_name'] = row['filename'] or '未知'

            if item.get('expire_at'):
                try:
                    from datetime import datetime
                    expire_dt = datetime.fromisoformat(row['expire_at'])
                    remaining = expire_dt - datetime.now()
                    item['days_remaining'] = max(0, remaining.days)
                    item['is_expired'] = datetime.now() > expire_dt
                except (ValueError, TypeError):
                    item['days_remaining'] = 30
                    item['is_expired'] = False
            else:
                item['days_remaining'] = 30
                item['is_expired'] = False

            trash_items.append(item)

        storage_usage = _app.get_user_storage_usage(session['user_id'])

        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        user_dict = dict(user) if user else None

        total_size = sum(item.get('file_size', 0) or 0 for item in trash_items)

        return render_template('trash.html',
                             username=session.get('username'),
                             user=user_dict,
                             trash_items=trash_items,
                             total_size=total_size,
                             storage_usage=storage_usage)
    finally:
        conn.close()


@trash_bp.route('/api/trash', methods=['GET'], endpoint='api_get_trash')
def api_get_trash():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    conn = _app.get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM trash WHERE user_id = ?",
                            (session['user_id'],)).fetchone()[0]

        rows = conn.execute("SELECT * FROM trash WHERE user_id = ? ORDER BY deleted_at DESC LIMIT ? OFFSET ?",
                           (session['user_id'], per_page, offset)).fetchall()

        items = []
        for r in rows:
            item = dict(r)
            item['original_data'] = {
                'filename': r['filename'],
                'stored_name': r['stored_name'],
                'file_path': r['file_path'],
                'file_size': r['file_size'],
                'file_type': r['file_type'],
            }
            item['display_name'] = r['filename'] or '未知'
            items.append(item)

        return _app.api_response(success=True, data={
            'items': items,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    finally:
        conn.close()


@trash_bp.route('/api/trash/restore/<item_id>', methods=['POST'], endpoint='api_restore_from_trash')
def api_restore_from_trash(item_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        item = conn.execute("SELECT * FROM trash WHERE id = ? AND user_id = ?",
                           (item_id, session['user_id'])).fetchone()

        if not item:
            return _app.api_response(success=False, message='回收站项不存在', code=404)

        if not item['file_id']:
            return _app.api_response(success=False, message='无效的回收站数据')

        existing = conn.execute("SELECT id FROM files WHERE id = ?", (item['file_id'],)).fetchone()
        if existing:
            conn.execute("DELETE FROM trash WHERE id = ?", (item_id,))
            conn.commit()
            return _app.api_response(success=True, message=f'{item["filename"] or "未知"} 已恢复')

        try:
            conn.execute(
                "INSERT OR IGNORE INTO files (id, user_id, filename, stored_name, file_path, file_size, file_type, folder_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (item['file_id'], item['user_id'], item['filename'], item['stored_name'],
                 item['file_path'], item['file_size'], item['file_type'], item['folder_id']))
        except Exception as e:
            return _app.api_response(success=False, message=f'恢复失败: {str(e)}')

        conn.execute("DELETE FROM trash WHERE id = ?", (item_id,))
        conn.commit()

        display_name = item['filename'] or '未知'
        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'从回收站恢复: {display_name}',
                   user_id=session['user_id'], action='restore_from_trash',
                   target_id=item_id, target_type='trash_item', request=request)

        return _app.api_response(success=True, message=f'{display_name} 已恢复')
    finally:
        conn.close()


@trash_bp.route('/api/trash/delete/<item_id>', methods=['DELETE'], endpoint='api_delete_from_trash_permanent')
def api_delete_from_trash_permanent(item_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        item = conn.execute("SELECT * FROM trash WHERE id = ? AND user_id = ?",
                           (item_id, session['user_id'])).fetchone()

        if not item:
            return _app.api_response(success=False, message='回收站项不存在', code=404)

        stored_name = item['stored_name'] or ''
        if stored_name:
            file_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)
            if os.path.exists(file_path):
                os.remove(file_path)

        conn.execute("DELETE FROM trash WHERE id = ?", (item_id,))
        conn.commit()

        display_name = item['filename'] or '未知'
        _app.log_message(log_type='operation', log_level='WARNING',
                   message=f'永久删除: {display_name}',
                   user_id=session['user_id'], action='permanent_delete',
                   target_id=item_id, target_type='trash_item', request=request)

        return _app.api_response(success=True, message=f'{display_name} 已被永久删除')
    finally:
        conn.close()


@trash_bp.route('/api/trash/clear-expired', methods=['POST'], endpoint='api_clear_expired_trash')
def api_clear_expired_trash():
    if 'user_id' not in session or session.get('role') != 'admin':
        return _app.api_response(success=False, message='权限不足', code=403)

    from datetime import datetime
    now_iso = datetime.now().isoformat()

    conn = _app.get_db()
    try:
        expired_items = conn.execute(
            "SELECT * FROM trash WHERE expire_at IS NOT NULL AND expire_at < ?", (now_iso,)).fetchall()

        deleted_count = 0
        for item in expired_items:
            stored_name = item['stored_name'] or ''
            if stored_name:
                file_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)
                if os.path.exists(file_path):
                    os.remove(file_path)

            conn.execute("DELETE FROM trash WHERE id = ?", (item['id'],))
            deleted_count += 1

        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'清理过期回收站项: {deleted_count} 个',
                   user_id=session['user_id'], action='clear_expired_trash', request=request)

        return _app.api_response(success=True, data={'deleted_count': deleted_count},
                          message=f'已清理 {deleted_count} 个过期项')
    finally:
        conn.close()


@trash_bp.route('/api/trash/clear-all', methods=['POST'], endpoint='api_clear_all_trash')
def api_clear_all_trash():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        items = conn.execute("SELECT * FROM trash WHERE user_id = ?",
                            (session['user_id'],)).fetchall()

        deleted_count = 0
        for item in items:
            stored_name = item['stored_name'] or ''
            if stored_name:
                file_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)
                if os.path.exists(file_path):
                    os.remove(file_path)

            conn.execute("DELETE FROM trash WHERE id = ?", (item['id'],))
            deleted_count += 1

        conn.commit()

        _app.log_message(log_type='operation', log_level='WARNING',
                   message=f'清空回收站: {deleted_count} 个项目',
                   user_id=session['user_id'], action='clear_all_trash', request=request)

        return _app.api_response(success=True, data={'deleted_count': deleted_count},
                          message=f'已永久删除 {deleted_count} 个项目')
    finally:
        conn.close()


@trash_bp.route('/api/trash/restore', methods=['POST'], endpoint='api_trash_restore')
def api_trash_restore():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    trash_id = data.get('trash_id')
    if not trash_id:
        return _app.api_response(success=False, message='缺少参数')

    conn = _app.get_db()
    try:
        item = conn.execute("SELECT * FROM trash WHERE id = ? AND user_id = ?",
                           (trash_id, session['user_id'])).fetchone()
        if not item:
            return _app.api_response(success=False, message='回收站项不存在', code=404)

        if item['file_id']:
            existing = conn.execute("SELECT id FROM files WHERE id = ?", (item['file_id'],)).fetchone()
            if not existing:
                conn.execute(
                    "INSERT OR IGNORE INTO files (id, user_id, filename, stored_name, file_path, file_size, file_type, folder_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (item['file_id'], item['user_id'], item['filename'], item['stored_name'],
                     item['file_path'], item['file_size'], item['file_type'], item['folder_id']))

        conn.execute("DELETE FROM trash WHERE id = ?", (trash_id,))
        conn.commit()

        display_name = item['filename'] or '未知'
        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'从回收站恢复: {display_name}',
                   user_id=session['user_id'], action='restore_from_trash',
                   target_id=trash_id, target_type='trash_item', request=request)

        return _app.api_response(success=True, message=f'{display_name} 已恢复')
    finally:
        conn.close()


@trash_bp.route('/api/trash/delete-permanent', methods=['POST'], endpoint='api_trash_delete_permanent')
def api_trash_delete_permanent():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    trash_id = data.get('trash_id')
    if not trash_id:
        return _app.api_response(success=False, message='缺少参数')

    conn = _app.get_db()
    try:
        item = conn.execute("SELECT * FROM trash WHERE id = ? AND user_id = ?",
                           (trash_id, session['user_id'])).fetchone()
        if not item:
            return _app.api_response(success=False, message='回收站项不存在', code=404)

        stored_name = item['stored_name'] or ''
        if stored_name:
            file_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)
            if os.path.exists(file_path):
                os.remove(file_path)

        conn.execute("DELETE FROM trash WHERE id = ?", (trash_id,))
        conn.commit()

        display_name = item['filename'] or '未知'
        return _app.api_response(success=True, message=f'{display_name} 已被永久删除')
    finally:
        conn.close()


@trash_bp.route('/api/trash/batch-restore', methods=['POST'], endpoint='api_trash_batch_restore')
def api_trash_batch_restore():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    trash_ids = data.get('trash_ids', [])
    if not trash_ids:
        return _app.api_response(success=False, message='未选择项目')

    conn = _app.get_db()
    try:
        restored = 0
        for tid in trash_ids:
            item = conn.execute("SELECT * FROM trash WHERE id = ? AND user_id = ?",
                               (tid, session['user_id'])).fetchone()
            if not item:
                continue
            if item['file_id']:
                existing = conn.execute("SELECT id FROM files WHERE id = ?", (item['file_id'],)).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT OR IGNORE INTO files (id, user_id, filename, stored_name, file_path, file_size, file_type, folder_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (item['file_id'], item['user_id'], item['filename'], item['stored_name'],
                         item['file_path'], item['file_size'], item['file_type'], item['folder_id']))
            conn.execute("DELETE FROM trash WHERE id = ?", (tid,))
            restored += 1
        conn.commit()
        return _app.api_response(success=True, message=f'已恢复 {restored} 个项目')
    finally:
        conn.close()


@trash_bp.route('/api/trash/batch-delete', methods=['POST'], endpoint='api_trash_batch_delete')
def api_trash_batch_delete():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    trash_ids = data.get('trash_ids', [])
    if not trash_ids:
        return _app.api_response(success=False, message='未选择项目')

    conn = _app.get_db()
    try:
        deleted = 0
        for tid in trash_ids:
            item = conn.execute("SELECT * FROM trash WHERE id = ? AND user_id = ?",
                               (tid, session['user_id'])).fetchone()
            if not item:
                continue
            stored_name = item['stored_name'] or ''
            if stored_name:
                file_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            conn.execute("DELETE FROM trash WHERE id = ?", (tid,))
            deleted += 1
        conn.commit()
        return _app.api_response(success=True, message=f'已永久删除 {deleted} 个项目')
    finally:
        conn.close()


@trash_bp.route('/api/trash/empty', methods=['POST'], endpoint='api_trash_empty')
def api_trash_empty():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        items = conn.execute("SELECT * FROM trash WHERE user_id = ?",
                            (session['user_id'],)).fetchall()
        deleted_count = 0
        for item in items:
            stored_name = item['stored_name'] or ''
            if stored_name:
                file_path = os.path.join(_app.app.config['UPLOAD_FOLDER'], stored_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            conn.execute("DELETE FROM trash WHERE id = ?", (item['id'],))
            deleted_count += 1
        conn.commit()
        return _app.api_response(success=True, message=f'已清空回收站，删除 {deleted_count} 个项目')
    finally:
        conn.close()
