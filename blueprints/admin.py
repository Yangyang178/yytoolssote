from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
from app import (get_db, log_message, api_response)
import uuid

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/permission-management', endpoint='permission_management')
def permission_management():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('权限不足')
        return redirect(url_for('index'))

    conn = get_db()
    try:
        users = conn.execute("SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC").fetchall()
        return render_template('permission_management.html',
                             username=session.get('username'),
                             users=[dict(u) for u in users])
    finally:
        conn.close()


@admin_bp.route('/update-user-role/<user_id>', methods=['POST'], endpoint='update_user_role')
def update_user_role(user_id):
    if session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    data = request.get_json(silent=True) or {}
    new_role = data.get('role', '')

    if new_role not in ('user', 'admin'):
        return api_response(success=False, message='无效的角色')

    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return api_response(success=False, message='用户不存在', code=404)

        old_role = user['role']
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
        conn.commit()

        log_message(log_type='security', log_level='WARNING',
                   message=f'管理员修改用户角色: {user["username"]} ({old_role} -> {new_role})',
                   user_id=session['user_id'], action='update_user_role',
                   target_id=user_id, target_type='user', request=request)

        return api_response(success=True, message=f'用户角色已更新为: {new_role}')
    finally:
        conn.close()


@admin_bp.route('/delete-user/<user_id>', methods=['POST'], endpoint='delete_user')
def delete_user(user_id):
    if session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    if user_id == session.get('user_id'):
        return api_response(success=False, message='不能删除自己的账号')

    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return api_response(success=False, message='用户不存在', code=404)

        tables_to_clean = [
            ("files", "user_id"), ("folders", "user_id"),
            ("categories", "user_id"), ("tags", "user_id"),
            ("likes", "user_id"), ("favorites", "user_id"),
            ("ai_contents", "user_id"), ("file_shares", "user_id"),
            ("trash", "user_id"), ("access_logs", "user_id"),
            ("operation_logs", "user_id")
        ]

        for table, fk_col in tables_to_clean:
            try:
                conn.execute(f"DELETE FROM {table} WHERE {fk_col} = ?", (user_id,))
            except Exception:
                pass

        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

        log_message(log_type='security', log_level='CRITICAL',
                   message=f'管理员删除用户: {user["username"]}',
                   user_id=session['user_id'], action='delete_user',
                   target_id=user_id, target_type='user', request=request)

        return api_response(success=True, message=f'用户 {user["username"]} 已被删除')
    finally:
        conn.close()
