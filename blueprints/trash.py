from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
from app import (app, get_db, log_message, page_error_response, api_response)
import os
import json
import uuid

trash_bp = Blueprint('trash', __name__)


@trash_bp.route('/trash', endpoint='trash')
def trash():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = get_db()
    try:
        trash_items = []
        rows = conn.execute(
            "SELECT * FROM trash WHERE created_by = ? ORDER BY created_at DESC",
            (session['user_id'],)).fetchall()

        for row in rows:
            item = dict(row)
            try:
                data = json.loads(row['data_json'])
                if isinstance(data, dict):
                    item['original_data'] = data
                    item['display_name'] = data.get('filename', data.get('name', '未知'))
                else:
                    item['original_data'] = {}
                    item['display_name'] = '未知'
            except (json.JSONDecodeError, TypeError):
                item['original_data'] = {}
                item['display_name'] = '未知'

            if row.get('expire_at'):
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

        from app import get_user_storage_usage
        storage_usage = get_user_storage_usage(session['user_id'])

        return render_template('trash.html',
                             username=session.get('username'),
                             trash_items=trash_items,
                             storage_usage=storage_usage)
    finally:
        conn.close()


@trash_bp.route('/api/trash', methods=['GET'], endpoint='api_get_trash')
def api_get_trash():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM trash WHERE created_by = ?",
                            (session['user_id'],)).fetchone()[0]

        rows = conn.execute("SELECT * FROM trash WHERE created_by = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                           (session['user_id'], per_page, offset)).fetchall()

        items = []
        for r in rows:
            item = dict(r)
            try:
                data = json.loads(r['data_json']) if r.get('data_json') else {}
                item['original_data'] = data if isinstance(data, dict) else {}
                item['display_name'] = data.get('filename', data.get('name', '未知'))
            except Exception:
                item['original_data'] = {}
                item['display_name'] = '未知'
            items.append(item)

        return api_response(success=True, data={
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
        return api_response(success=False, message='请先登录', code=401)

    conn = get_db()
    try:
        item = conn.execute("SELECT * FROM trash WHERE id = ? AND created_by = ?",
                           (item_id, session['user_id'])).fetchone()

        if not item:
            return api_response(success=False, message='回收站项不存在', code=404)

        original_data = {}
        try:
            original_data = json.loads(item['data_json']) if item['data_json'] else {}
        except Exception:
            pass

        table = item.get('original_table', '')
        original_id = item.get('original_id', '')

        if not table or not original_id:
            return api_response(success=False, message='无效的回收站数据')

        columns = ', '.join([f'"{k}"' for k in original_data.keys()])
        placeholders = ', '.join(['?' for _ in original_data.values()])

        try:
            conn.execute(f'INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders}',
                        list(original_data.values()))
        except Exception as e:
            return api_response(success=False, message=f'恢复失败: {str(e)}')

        conn.execute("DELETE FROM trash WHERE id = ?", (item_id,))
        conn.commit()

        display_name = original_data.get('filename', original_data.get('name', '未知'))
        log_message(log_type='operation', log_level='INFO',
                   message=f'从回收站恢复: {display_name}',
                   user_id=session['user_id'], action='restore_from_trash',
                   target_id=item_id, target_type='trash_item', request=request)

        return api_response(success=True, message=f'{display_name} 已恢复')
    finally:
        conn.close()


@trash_bp.route('/api/trash/delete/<item_id>', methods=['DELETE'], endpoint='api_delete_from_trash_permanent')
def api_delete_from_trash_permanent(item_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    conn = get_db()
    try:
        item = conn.execute("SELECT * FROM trash WHERE id = ? AND created_by = ?",
                           (item_id, session['user_id'])).fetchone()

        if not item:
            return api_response(success=False, message='回收站项不存在', code=404)

        original_data = {}
        try:
            original_data = json.loads(item['data_json']) if item['data_json'] else {}
        except Exception:
            pass

        stored_name = original_data.get('stored_name', '')
        if stored_name:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
            if os.path.exists(file_path):
                os.remove(file_path)

        conn.execute("DELETE FROM trash WHERE id = ?", (item_id,))
        conn.commit()

        display_name = original_data.get('filename', original_data.get('name', '未知'))
        log_message(log_type='operation', log_level='WARNING',
                   message=f'永久删除: {display_name}',
                   user_id=session['user_id'], action='permanent_delete',
                   target_id=item_id, target_type='trash_item', request=request)

        return api_response(success=True, message=f'{display_name} 已被永久删除')
    finally:
        conn.close()


@trash_bp.route('/api/trash/clear-expired', methods=['POST'], endpoint='api_clear_expired_trash')
def api_clear_expired_trash():
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    from datetime import datetime
    now_iso = datetime.now().isoformat()

    conn = get_db()
    try:
        expired_items = conn.execute(
            "SELECT * FROM trash WHERE expire_at IS NOT NULL AND expire_at < ?", (now_iso,)).fetchall()

        deleted_count = 0
        for item in expired_items:
            try:
                original_data = json.loads(item['data_json']) if item.get('data_json') else {}
                stored_name = original_data.get('stored_name', '')
                if stored_name:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
            except Exception:
                pass

            conn.execute("DELETE FROM trash WHERE id = ?", (item['id'],))
            deleted_count += 1

        conn.commit()

        log_message(log_type='operation', log_level='INFO',
                   message=f'清理过期回收站项: {deleted_count} 个',
                   user_id=session['user_id'], action='clear_expired_trash', request=request)

        return api_response(success=True, data={'deleted_count': deleted_count},
                          message=f'已清理 {deleted_count} 个过期项')
    finally:
        conn.close()


@trash_bp.route('/api/trash/clear-all', methods=['POST'], endpoint='api_clear_all_trash')
def api_clear_all_trash():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    conn = get_db()
    try:
        items = conn.execute("SELECT * FROM trash WHERE created_by = ?",
                            (session['user_id'],)).fetchall()

        deleted_count = 0
        for item in items:
            try:
                original_data = json.loads(item['data_json']) if item.get('data_json') else {}
                stored_name = original_data.get('stored_name', '')
                if stored_name:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
            except Exception:
                pass

            conn.execute("DELETE FROM trash WHERE id = ?", (item['id'],))
            deleted_count += 1

        conn.commit()

        log_message(log_type='operation', log_level='WARNING',
                   message=f'清空回收站: {deleted_count} 个项目',
                   user_id=session['user_id'], action='clear_all_trash', request=request)

        return api_response(success=True, data={'deleted_count': deleted_count},
                          message=f'已永久删除 {deleted_count} 个项目')
    finally:
        conn.close()
