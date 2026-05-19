from flask import Blueprint, request, render_template, redirect, url_for, jsonify, session, send_from_directory
import os, json, sqlite3, shutil, base64, uuid
from datetime import datetime
from pathlib import Path

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
workspace_bp = Blueprint('workspace', __name__)


def _get_workspace_role(workspace_id, user_id):
    conn = _app.get_db()
    try:
        ws = conn.execute("SELECT owner_id FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if not ws:
            return None
        if ws['owner_id'] == user_id:
            return 'owner'
        member = conn.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id)).fetchone()
        if member:
            return member['role']
        return None
    finally:
        conn.close()


def _check_permission(workspace_id, user_id, required_roles):
    role = _get_workspace_role(workspace_id, user_id)
    if role is None:
        return False, '工作空间不存在或无权限访问'
    if role not in required_roles:
        return False, '权限不足，无法执行此操作'
    return True, role


@workspace_bp.route('/workspaces', endpoint='workspaces_list')
def workspaces_list():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    user_id = session['user_id']
    conn = _app.get_db()
    try:
        owned = conn.execute(
            """SELECT w.*, (SELECT COUNT(*) FROM workspace_members WHERE workspace_id = w.id) as member_count,
                      (SELECT COUNT(*) FROM workspace_files WHERE workspace_id = w.id) as file_count
               FROM workspaces w WHERE w.owner_id = ? ORDER BY w.updated_at DESC""",
            (user_id,)).fetchall()

        joined = conn.execute(
            """SELECT w.*, wm.role as member_role,
                      (SELECT COUNT(*) FROM workspace_members WHERE workspace_id = w.id) as member_count,
                      (SELECT COUNT(*) FROM workspace_files WHERE workspace_id = w.id) as file_count
               FROM workspaces w JOIN workspace_members wm ON w.id = wm.workspace_id
               WHERE wm.user_id = ? ORDER BY w.updated_at DESC""",
            (user_id,)).fetchall()

        return render_template('workspaces.html',
                             username=session.get('username'),
                             owned_workspaces=[dict(r) for r in owned],
                             joined_workspaces=[dict(r) for r in joined])
    finally:
        conn.close()


@workspace_bp.route('/workspace/<workspace_id>', endpoint='workspace_detail')
def workspace_detail(workspace_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    user_id = session['user_id']
    conn = _app.get_db()
    try:
        ws = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if not ws:
            return _app.page_error_response('workspace', '工作空间不存在', 404)

        role = _get_workspace_role(workspace_id, user_id)
        if role is None:
            return _app.page_error_response('workspace', '无权限访问此工作空间', 403)

        members = conn.execute(
            """SELECT wm.*, u.username FROM workspace_members wm
               LEFT JOIN users u ON wm.user_id = u.id
               WHERE wm.workspace_id = ? ORDER BY wm.joined_at""",
            (workspace_id,)).fetchall()

        files = conn.execute(
            """SELECT wf.id, wf.workspace_id, wf.file_id, wf.uploaded_by,
                      wf.visibility, wf.tags, wf.description, wf.added_at,
                      f.filename, f.size, f.project_name,
                      u.username as uploader_name
               FROM workspace_files wf
               LEFT JOIN files f ON wf.file_id = f.id
               LEFT JOIN users u ON wf.uploaded_by = u.id
               WHERE wf.workspace_id = ? ORDER BY wf.added_at DESC""",
            (workspace_id,)).fetchall()

        ws_dict = dict(ws)
        ws_dict['member_count'] = len(members)
        ws_dict['file_count'] = len(files)

        return render_template('workspace_detail.html',
                             username=session.get('username'),
                             workspace=ws_dict,
                             members=[dict(r) for r in members],
                             files=[dict(r) for r in files],
                             role=role)
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces', methods=['GET'], endpoint='api_list_workspaces')
def api_list_workspaces():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    conn = _app.get_db()
    try:
        owned = conn.execute(
            """SELECT w.*, 'owner' as role,
                      (SELECT COUNT(*) FROM workspace_members WHERE workspace_id = w.id) as member_count,
                      (SELECT COUNT(*) FROM workspace_files WHERE workspace_id = w.id) as file_count
               FROM workspaces w WHERE w.owner_id = ? ORDER BY w.updated_at DESC""",
            (user_id,)).fetchall()

        joined = conn.execute(
            """SELECT w.*, wm.role,
                      (SELECT COUNT(*) FROM workspace_members WHERE workspace_id = w.id) as member_count,
                      (SELECT COUNT(*) FROM workspace_files WHERE workspace_id = w.id) as file_count
               FROM workspaces w JOIN workspace_members wm ON w.id = wm.workspace_id
               WHERE wm.user_id = ? AND w.owner_id != ? ORDER BY w.updated_at DESC""",
            (user_id, user_id)).fetchall()

        return _app.api_response(success=True, data={
            'owned': [dict(r) for r in owned],
            'joined': [dict(r) for r in joined]
        })
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces', methods=['POST'], endpoint='api_create_workspace')
def api_create_workspace():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    icon = data.get('icon', '').strip()
    settings = data.get('settings', {})

    if not name:
        return _app.api_response(success=False, message='工作空间名称不能为空')

    ws_id = uuid.uuid4().hex
    settings_json = json.dumps(settings, ensure_ascii=False) if settings else '{}'
    user_id = session['user_id']

    conn = _app.get_db()
    try:
        conn.execute(
            """INSERT INTO workspaces (id, name, description, icon, owner_id, created_at, updated_at, settings_json)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)""",
            (ws_id, name, description, icon, user_id, settings_json))

        member_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO workspace_members (id, workspace_id, user_id, role, joined_at, permissions_json)
               VALUES (?, ?, ?, 'owner', CURRENT_TIMESTAMP, '{}')""",
            (member_id, ws_id, user_id))

        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'创建工作空间: {name}',
                        user_id=user_id, action='create_workspace',
                        target_id=ws_id, target_type='workspace', request=request)

        return _app.api_response(success=True, message='工作空间创建成功',
                               data={'id': ws_id, 'name': name})
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f'创建失败: {str(e)}')
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces/<workspace_id>', methods=['PUT'], endpoint='api_update_workspace')
def api_update_workspace(workspace_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    allowed, role = _check_permission(workspace_id, user_id, ['owner'])
    if not allowed:
        return _app.api_response(success=False, message=role, code=403)

    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    icon = data.get('icon', '').strip()
    settings = data.get('settings')

    conn = _app.get_db()
    try:
        updates = []
        params = []

        if name:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if icon is not None:
            updates.append("icon = ?")
            params.append(icon)
        if settings is not None:
            updates.append("settings_json = ?")
            params.append(json.dumps(settings, ensure_ascii=False))

        if not updates:
            return _app.api_response(success=False, message='没有需要更新的字段')

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(workspace_id)

        conn.execute(f"UPDATE workspaces SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'更新工作空间: {workspace_id}',
                        user_id=user_id, action='update_workspace',
                        target_id=workspace_id, target_type='workspace', request=request)

        return _app.api_response(success=True, message='工作空间更新成功')
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f'更新失败: {str(e)}')
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces/<workspace_id>', methods=['DELETE'], endpoint='api_delete_workspace')
def api_delete_workspace(workspace_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    allowed, role = _check_permission(workspace_id, user_id, ['owner'])
    if not allowed:
        return _app.api_response(success=False, message=role, code=403)

    conn = _app.get_db()
    try:
        ws = conn.execute("SELECT name FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        ws_name = ws['name'] if ws else workspace_id

        conn.execute("DELETE FROM workspace_files WHERE workspace_id = ?", (workspace_id,))
        conn.execute("DELETE FROM workspace_members WHERE workspace_id = ?", (workspace_id,))
        conn.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
        conn.commit()

        _app.log_message(log_type='operation', log_level='WARNING',
                        message=f'删除工作空间: {ws_name}',
                        user_id=user_id, action='delete_workspace',
                        target_id=workspace_id, target_type='workspace', request=request)

        return _app.api_response(success=True, message='工作空间已删除')
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f'删除失败: {str(e)}')
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces/<workspace_id>/members', methods=['GET'], endpoint='api_get_workspace_members')
def api_get_workspace_members(workspace_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    role = _get_workspace_role(workspace_id, user_id)
    if role is None:
        return _app.api_response(success=False, message='工作空间不存在或无权限访问', code=403)

    conn = _app.get_db()
    try:
        members = conn.execute(
            """SELECT wm.id, wm.workspace_id, wm.user_id, wm.role, wm.joined_at,
                      wm.permissions_json, u.username, u.email
               FROM workspace_members wm LEFT JOIN users u ON wm.user_id = u.id
               WHERE wm.workspace_id = ? ORDER BY
               CASE wm.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 WHEN 'editor' THEN 2 ELSE 3 END,
               wm.joined_at""",
            (workspace_id,)).fetchall()

        return _app.api_response(success=True, data={'members': [dict(r) for r in members]})
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces/<workspace_id>/members', methods=['POST'], endpoint='api_add_workspace_member')
def api_add_workspace_member(workspace_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    allowed, role = _check_permission(workspace_id, user_id, ['owner', 'admin'])
    if not allowed:
        return _app.api_response(success=False, message=role, code=403)

    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    new_role = data.get('role', 'viewer')

    if not email:
        return _app.api_response(success=False, message='邮箱不能为空')

    if new_role not in ('admin', 'editor', 'viewer'):
        return _app.api_response(success=False, message='无效的角色类型')

    conn = _app.get_db()
    try:
        target_user = conn.execute("SELECT id, username FROM users WHERE email = ?", (email,)).fetchone()
        if not target_user:
            return _app.api_response(success=False, message='未找到该邮箱对应的用户')

        existing = conn.execute(
            "SELECT id FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, target_user['id'])).fetchone()
        if existing:
            return _app.api_response(success=False, message='该用户已是工作空间成员')

        member_id = uuid.uuid4().hex
        permissions_json = json.dumps(data.get('permissions', {}), ensure_ascii=False)
        conn.execute(
            """INSERT INTO workspace_members (id, workspace_id, user_id, role, joined_at, permissions_json)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)""",
            (member_id, workspace_id, target_user['id'], new_role, permissions_json))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'添加成员 {target_user["username"]} 到工作空间，角色: {new_role}',
                        user_id=user_id, action='add_workspace_member',
                        target_id=workspace_id, target_type='workspace', request=request)

        return _app.api_response(success=True, message='成员添加成功',
                               data={'member_id': member_id, 'username': target_user['username'], 'role': new_role})
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f'添加成员失败: {str(e)}')
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces/<workspace_id>/members/<member_user_id>', methods=['PUT'], endpoint='api_update_workspace_member')
def api_update_workspace_member(workspace_id, member_user_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    allowed, role = _check_permission(workspace_id, user_id, ['owner', 'admin'])
    if not allowed:
        return _app.api_response(success=False, message=role, code=403)

    data = request.get_json(silent=True) or {}
    new_role = data.get('role', '').strip()

    if new_role not in ('admin', 'editor', 'viewer'):
        return _app.api_response(success=False, message='无效的角色类型')

    conn = _app.get_db()
    try:
        ws = conn.execute("SELECT owner_id FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if ws and ws['owner_id'] == member_user_id:
            return _app.api_response(success=False, message='无法修改工作空间所有者的角色')

        if role == 'admin' and new_role == 'admin':
            return _app.api_response(success=False, message='管理员无法设置其他管理员，仅所有者可以')

        member = conn.execute(
            "SELECT id FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, member_user_id)).fetchone()
        if not member:
            return _app.api_response(success=False, message='成员不存在', code=404)

        permissions_json = json.dumps(data.get('permissions', {}), ensure_ascii=False)
        conn.execute(
            "UPDATE workspace_members SET role = ?, permissions_json = ? WHERE workspace_id = ? AND user_id = ?",
            (new_role, permissions_json, workspace_id, member_user_id))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'更新成员角色: {member_user_id} -> {new_role}',
                        user_id=user_id, action='update_workspace_member',
                        target_id=workspace_id, target_type='workspace', request=request)

        return _app.api_response(success=True, message='成员角色更新成功')
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f'更新失败: {str(e)}')
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces/<workspace_id>/members/<member_user_id>', methods=['DELETE'], endpoint='api_remove_workspace_member')
def api_remove_workspace_member(workspace_id, member_user_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    allowed, role = _check_permission(workspace_id, user_id, ['owner', 'admin'])
    if not allowed:
        return _app.api_response(success=False, message=role, code=403)

    conn = _app.get_db()
    try:
        ws = conn.execute("SELECT owner_id FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if ws and ws['owner_id'] == member_user_id:
            return _app.api_response(success=False, message='无法移除工作空间所有者')

        result = conn.execute(
            "DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, member_user_id))
        conn.commit()

        if result.rowcount == 0:
            return _app.api_response(success=False, message='成员不存在', code=404)

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'移除工作空间成员: {member_user_id}',
                        user_id=user_id, action='remove_workspace_member',
                        target_id=workspace_id, target_type='workspace', request=request)

        return _app.api_response(success=True, message='成员已移除')
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f'移除失败: {str(e)}')
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces/<workspace_id>/files', methods=['GET'], endpoint='api_get_workspace_files')
def api_get_workspace_files(workspace_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    role = _get_workspace_role(workspace_id, user_id)
    if role is None:
        return _app.api_response(success=False, message='工作空间不存在或无权限访问', code=403)

    conn = _app.get_db()
    try:
        files = conn.execute(
            """SELECT wf.id, wf.workspace_id, wf.file_id, wf.uploaded_by,
                      wf.visibility, wf.tags, wf.description, wf.added_at,
                      f.filename, f.size, f.project_name,
                      u.username as uploader_name
               FROM workspace_files wf
               LEFT JOIN files f ON wf.file_id = f.id
               LEFT JOIN users u ON wf.uploaded_by = u.id
               WHERE wf.workspace_id = ? ORDER BY wf.added_at DESC""",
            (workspace_id,)).fetchall()

        return _app.api_response(success=True, data={'files': [dict(r) for r in files]})
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces/<workspace_id>/files', methods=['POST'], endpoint='api_add_workspace_file')
def api_add_workspace_file(workspace_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    allowed, role = _check_permission(workspace_id, user_id, ['owner', 'admin', 'editor'])
    if not allowed:
        return _app.api_response(success=False, message=role, code=403)

    data = request.get_json(silent=True) or {}
    file_id = data.get('file_id', '').strip()
    visibility = data.get('visibility', 'workspace')
    tags = data.get('tags', '')
    description = data.get('description', '').strip()

    if not file_id:
        return _app.api_response(success=False, message='文件ID不能为空')

    if visibility not in ('workspace', 'private', 'public'):
        visibility = 'workspace'

    conn = _app.get_db()
    try:
        file_record = conn.execute("SELECT id FROM files WHERE id = ?", (file_id,)).fetchone()
        if not file_record:
            return _app.api_response(success=False, message='文件不存在')

        existing = conn.execute(
            "SELECT id FROM workspace_files WHERE workspace_id = ? AND file_id = ?",
            (workspace_id, file_id)).fetchone()
        if existing:
            return _app.api_response(success=False, message='文件已在该工作空间中')

        wf_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO workspace_files (id, workspace_id, file_id, uploaded_by, visibility, tags, description, added_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (wf_id, workspace_id, file_id, user_id, visibility, tags, description))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'添加文件到工作空间: {file_id}',
                        user_id=user_id, action='add_workspace_file',
                        target_id=workspace_id, target_type='workspace', request=request)

        return _app.api_response(success=True, message='文件添加成功', data={'id': wf_id})
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f'添加文件失败: {str(e)}')
    finally:
        conn.close()


@workspace_bp.route('/api/workspaces/<workspace_id>/files/<file_record_id>', methods=['DELETE'], endpoint='api_remove_workspace_file')
def api_remove_workspace_file(workspace_id, file_record_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    user_id = session['user_id']
    allowed, role = _check_permission(workspace_id, user_id, ['owner', 'admin', 'editor'])
    if not allowed:
        return _app.api_response(success=False, message=role, code=403)

    conn = _app.get_db()
    try:
        file_record = conn.execute(
            "SELECT uploaded_by FROM workspace_files WHERE id = ? AND workspace_id = ?",
            (file_record_id, workspace_id)).fetchone()
        if not file_record:
            return _app.api_response(success=False, message='文件记录不存在', code=404)

        if role == 'editor' and file_record['uploaded_by'] != user_id:
            return _app.api_response(success=False, message='仅可移除自己上传的文件', code=403)

        conn.execute("DELETE FROM workspace_files WHERE id = ? AND workspace_id = ?",
                    (file_record_id, workspace_id))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'从工作空间移除文件: {file_record_id}',
                        user_id=user_id, action='remove_workspace_file',
                        target_id=workspace_id, target_type='workspace', request=request)

        return _app.api_response(success=True, message='文件已从工作空间移除')
    except Exception as e:
        conn.rollback()
        return _app.api_response(success=False, message=f'移除文件失败: {str(e)}')
    finally:
        conn.close()
