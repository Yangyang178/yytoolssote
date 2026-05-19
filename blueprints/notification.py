from flask import Blueprint, request, render_template, redirect, url_for, jsonify, session
from helpers import (get_db, log_message, api_response, login_required)
import json
import uuid
from datetime import datetime

notification_bp = Blueprint('notification', __name__)

NOTIFICATION_TYPES = ['system', 'file_share', 'security', 'ai', 'collaboration', 'backup']
NOTIFICATION_CATEGORIES = ['info', 'success', 'warning', 'error', 'critical']

NOTIFICATION_ICONS = {
    'system': {'icon': '⚙️', 'bg': '#e0e7ff', 'color': '#4F46E5'},
    'file_share': {'icon': '📁', 'bg': '#d1fae5', 'color': '#059669'},
    'security': {'icon': '🔒', 'bg': '#fee2e2', 'color': '#dc2626'},
    'ai': {'icon': '🤖', 'bg': '#ede9fe', 'color': '#7c3aed'},
    'collaboration': {'icon': '👥', 'bg': '#fce7f3', 'color': '#db2777'},
    'backup': {'icon': '💾', 'bg': '#fff7ed', 'color': '#ea580c'},
}

DEFAULT_POLL_INTERVAL = 30


def _get_user_id():
    return session.get('user_id')


def _is_admin():
    return session.get('role') in ('admin', 'developer')


def create_notification(user_id, notif_type, category, title, content='',
                        icon='', action_url='', action_text='查看详情',
                        source_type='', source_id='', expires_at=None):
    if not user_id:
        return None
    if notif_type not in NOTIFICATION_TYPES:
        notif_type = 'system'
    if category not in NOTIFICATION_CATEGORIES:
        category = 'info'

    conn = get_db()
    try:
        notif_id = str(uuid.uuid4())
        expires_str = expires_at.isoformat() if isinstance(expires_at, datetime) else (expires_at or '')
        conn.execute('''INSERT INTO notifications 
            (id, user_id, type, category, title, content, icon, action_url, action_text,
             source_type, source_id, is_read, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP, ?)''',
                    (notif_id, user_id, notif_type, category, title, content, icon,
                     action_url, action_text, source_type, source_id, expires_str))
        conn.commit()
        return notif_id
    except Exception as e:
        log_message(log_type='error', log_level='ERROR',
                   message=f'创建通知失败: {e}', action='create_notification')
        return None
    finally:
        conn.close()


def notify_user(user_id, notif_type, title, content='', **kwargs):
    return create_notification(
        user_id=user_id, notif_type=notif_type,
        category=kwargs.get('category', 'info'),
        title=title, content=content,
        icon=kwargs.get('icon', ''),
        action_url=kwargs.get('action_url', ''),
        action_text=kwargs.get('action_text', '查看详情'),
        source_type=kwargs.get('source_type', ''),
        source_id=kwargs.get('source_id', ''),
        expires_at=kwargs.get('expires_at'),
    )


def notify_file_shared(target_user_id, sharer_name, filename, share_url, share_id=''):
    icon_info = NOTIFICATION_ICONS.get('file_share', {})
    return create_notification(
        user_id=target_user_id, notif_type='file_share',
        category='info',
        title=f'{sharer_name} 分享了文件给你',
        content=f'文件: {filename}',
        icon=json.dumps(icon_info, ensure_ascii=False),
        action_url=share_url or '',
        action_text='查看分享',
        source_type='share',
        source_id=share_id,
    )


def notify_share_viewed(owner_user_id, viewer_name, filename, share_id=''):
    icon_info = NOTIFICATION_ICONS.get('file_share', {})
    return create_notification(
        user_id=owner_user_id, notif_type='file_share',
        category='info',
        title=f'有人查看了你的分享链接',
        content=f'{viewer_name} 查看了你分享的文件「{filename}」',
        icon=json.dumps(icon_info, ensure_ascii=False),
        action_url=url_for('share_file') if share_id else '',
        source_type='share_view',
        source_id=share_id,
    )


def notify_security_event(user_id, event_title, event_desc='',
                           category='warning', source_id=''):
    icon_info = NOTIFICATION_ICONS.get('security', {})
    return create_notification(
        user_id=user_id, notif_type='security',
        category=category,
        title=event_title,
        content=event_desc,
        icon=json.dumps(icon_info, ensure_ascii=False),
        action_url=url_for('account_settings') if 'account' in event_title.lower() else '',
        action_text='查看详情',
        source_type='security_event',
        source_id=source_id,
    )


def notify_system(user_id, title, content='', category='info',
                  action_url='', source_type='system'):
    icon_info = NOTIFICATION_ICONS.get('system', {})
    return create_notification(
        user_id=user_id, notif_type='system',
        category=category,
        title=title,
        content=content,
        icon=json.dumps(icon_info, ensure_ascii=False),
        action_url=action_url,
        source_type=source_type,
    )


def notify_admin(notif_type, title, content='', category='info', **kwargs):
    conn = get_db()
    try:
        admins = conn.execute("SELECT id FROM users WHERE role IN ('admin', 'developer')").fetchall()
        for admin in admins:
            create_notification(
                user_id=admin['id'], notif_type=notif_type,
                category=category, title=title, content=content,
                icon=kwargs.get('icon', ''),
                action_url=kwargs.get('action_url', ''),
                action_text=kwargs.get('action_text', '查看详情'),
                source_type=kwargs.get('source_type', 'admin_notify'),
                source_id=kwargs.get('source_id', ''),
                expires_at=kwargs.get('expires_at'),
            )
    finally:
        conn.close()


def get_unread_count(user_id=None):
    uid = user_id or _get_user_id()
    if not uid:
        return 0
    conn = get_db()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (uid,)
        ).fetchone()[0]
        return count
    finally:
        conn.close()


def _build_notif_dict(row):
    n = dict(row)
    icon_data = {}
    if n.get('icon'):
        try:
            icon_data = json.loads(n['icon']) if isinstance(n['icon'], str) else {}
        except Exception:
            pass
    if not icon_data:
        default_icon = NOTIFICATION_ICONS.get(n.get('type', 'system'), {})
        icon_data = default_icon
    n['icon_data'] = icon_data
    n['time_ago'] = _time_ago(n.get('created_at', ''))
    return n


def _time_ago(dt_str):
    if not dt_str:
        return ''
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00').replace('+00:00', ''))
        now = datetime.now()
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return '刚刚'
        elif seconds < 3600:
            return f'{seconds // 60}分钟前'
        elif seconds < 86400:
            return f'{seconds // 3600}小时前'
        elif seconds < 604800:
            return f'{seconds // 86400}天前'
        else:
            return dt.strftime('%Y-%m-%d')
    except Exception:
        return dt_str[:16] if dt_str else ''


@notification_bp.route('/notifications', endpoint='notification_center')
@login_required
def notification_center():
    user_id = _get_user_id()
    is_admin = _is_admin()

    notif_type = request.args.get('type', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    conn = get_db()
    try:
        where_clauses = []
        params = [user_id]

        if is_admin and notif_type == 'all_users':
            where_clauses.append("n.user_id != ?")
            params.append(user_id)
        else:
            where_clauses.append("n.user_id = ?")

        if notif_type and notif_type != 'all':
            where_clauses.append("n.type = ?")
            params.append(notif_type)

        where_sql = ' AND '.join(where_clauses)

        total = conn.execute(f"SELECT COUNT(*) FROM notifications n WHERE {where_sql}",
                           tuple(params)).fetchone()[0]

        rows = conn.execute(
            f"""SELECT n.* FROM notifications n WHERE {where_sql}
               ORDER BY n.created_at DESC LIMIT ? OFFSET ?""",
            tuple(params + [per_page, offset])).fetchall()

        notifications = [_build_notif_dict(r) for r in rows]

        unread_count = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,)
        ).fetchone()[0]

        type_counts = {}
        type_rows = conn.execute(
            """SELECT type, COUNT(*) as cnt, SUM(CASE WHEN is_read=0 THEN 1 ELSE 0 END) as unread
               FROM notifications WHERE user_id = ?
               GROUP BY type""", (user_id,)).fetchall()
        for tr in type_rows:
            type_counts[tr['type']] = {'total': tr['cnt'], 'unread': tr['unread']}

        return render_template('notifications.html',
                             username=session.get('username'),
                             is_admin=is_admin,
                             notifications=notifications,
                             unread_count=unread_count,
                             type_counts=type_counts,
                             current_type=notif_type,
                             pagination={
                                 'page': page, 'per_page': per_page,
                                 'total': total,
                                 'total_pages': (total + per_page - 1) // per_page
                             },
                             notif_types=NOTIFICATION_TYPES,
                             notif_icons=NOTIFICATION_ICONS)
    finally:
        conn.close()


@notification_bp.get('/api/notifications/unread')
def api_get_unread_count():
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    count = get_unread_count()
    recent = []
    if count > 0:
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT * FROM notifications WHERE user_id = ? AND is_read = 0
                   ORDER BY created_at DESC LIMIT 5""",
                (session['user_id'],)).fetchall()
            recent = [_build_notif_dict(r) for r in rows]
        finally:
            conn.close()

    return api_response(success=True, data={'count': count, 'recent': recent})


@notification_bp.get('/api/notifications')
def api_get_notifications():
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    user_id = _get_user_id()
    is_admin = _is_admin()
    limit = request.args.get('limit', 10, type=int)
    notif_type = request.args.get('type', '')

    conn = get_db()
    try:
        params = [user_id]
        where_sql = "n.user_id = ?"

        if is_admin and notif_type == 'admin_all':
            where_sql = "1=1"
            params = []

        if notif_type and notif_type not in ('all', 'admin_all'):
            where_sql += " AND n.type = ?"
            params.append(notif_type)

        rows = conn.execute(
            f"""SELECT n.* FROM notifications n WHERE {where_sql}
               ORDER BY n.created_at DESC LIMIT ?""",
            tuple(params + [limit])).fetchall()

        notifications = [_build_notif_dict(r) for r in rows]
        unread = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,)).fetchone()[0]

        return api_response(success=True, data={
            'notifications': notifications,
            'unread_count': unread,
            'is_admin': is_admin
        })
    finally:
        conn.close()


@notification_bp.put('/api/notifications/<notif_id>/read')
def api_mark_read(notif_id):
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    conn = get_db()
    try:
        result = conn.execute(
            """UPDATE notifications SET is_read = 1, read_at = CURRENT_TIMESTAMP
               WHERE id = ? AND user_id = ? AND is_read = 0""",
            (notif_id, session['user_id']))
        conn.commit()
        return api_response(success=True,
                          data={'updated': result.rowcount > 0},
                          message='已标记为已读')
    finally:
        conn.close()


@notification_bp.put('/api/notifications/read-all')
def api_mark_all_read():
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    user_id = _get_user_id()
    notif_type = request.args.get('type')

    conn = get_db()
    try:
        if notif_type and notif_type != 'all':
            result = conn.execute(
                """UPDATE notifications SET is_read = 1, read_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND type = ? AND is_read = 0""",
                (user_id, notif_type))
        else:
            result = conn.execute(
                """UPDATE notifications SET is_read = 1, read_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND is_read = 0""",
                (user_id,))
        conn.commit()

        log_message(log_type='operation', log_level='INFO',
                   message=f'用户标记全部通知已读 (类型: {notif_type or "全部"})',
                   user_id=user_id, action='mark_all_read', request=request)

        return api_response(success=True,
                          data={'updated': result.rowcount},
                          message=f'已标记 {result.rowcount} 条为已读')
    finally:
        conn.close()


@notification_bp.delete('/api/notifications/<notif_id>')
def api_delete_notification(notif_id):
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    conn = get_db()
    try:
        result = conn.execute(
            "DELETE FROM notifications WHERE id = ? AND user_id = ?",
            (notif_id, session['user_id']))
        conn.commit()

        if result.rowcount == 0:
            return api_response(success=False, message='通知不存在或无权限', code=404)

        return api_response(success=True, message='通知已删除')
    finally:
        conn.close()


@notification_bp.delete('/api/notifications/clear')
def api_clear_notifications():
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    user_id = _get_user_id()
    notif_type = request.args.get('type')
    is_admin = _is_admin()

    conn = get_db()
    try:
        if is_admin and notif_type == 'admin_all':
            result = conn.execute("DELETE FROM notifications")
        elif notif_type and notif_type != 'all':
            result = conn.execute(
                "DELETE FROM notifications WHERE user_id = ? AND type = ?",
                (user_id, notif_type))
        else:
            result = conn.execute(
                "DELETE FROM notifications WHERE user_id = ?", (user_id,))
        conn.commit()

        log_message(log_type='operation', log_level='INFO',
                   message=f'清空通知 (类型: {notif_type or "全部"}, 删除{result.rowcount}条)',
                   user_id=user_id, action='clear_notifications', request=request)

        return api_response(success=True,
                          data={'deleted': result.rowcount},
                          message=f'已删除 {result.rowcount} 条通知')
    finally:
        conn.close()


@notification_bp.get('/api/notifications/settings')
def api_get_notification_settings():
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    settings = {
        'poll_interval': DEFAULT_POLL_INTERVAL,
        'enabled_types': list(NOTIFICATION_TYPES),
        'email_enabled': False,
        'sound_enabled': True,
        'auto_mark_read': True,
    }

    return api_response(success=True, data=settings)


@notification_bp.put('/api/notifications/settings')
def api_update_notification_settings():
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    data = request.get_json(silent=True) or {}

    poll_interval = data.get('poll_interval', DEFAULT_POLL_INTERVAL)
    if not isinstance(poll_interval, int) or poll_interval < 10:
        poll_interval = DEFAULT_POLL_INTERVAL

    enabled_types = data.get('enabled_types', [])
    if not isinstance(enabled_types, list):
        enabled_types = list(NOTIFICATION_TYPES)

    sound_enabled = data.get('sound_enabled', True)
    auto_mark_read = data.get('auto_mark_read', True)

    settings_json = json.dumps({
        'poll_interval': poll_interval,
        'enabled_types': enabled_types,
        'sound_enabled': sound_enabled,
        'auto_mark_read': auto_mark_read,
    }, ensure_ascii=False)

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM notification_settings WHERE user_id = ?",
            (session['user_id'],)).fetchone()
        if existing:
            conn.execute(
                "UPDATE notification_settings SET settings_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (settings_json, existing['id']))
        else:
            conn.execute("""INSERT INTO notification_settings (id, user_id, settings_json, created_at)
                           VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
                        (str(uuid.uuid4()), session['user_id'], settings_json))
        conn.commit()

        return api_response(success=True, message='设置已保存')
    finally:
        conn.close()


NOTIFICATION_PRIORITIES = {
    'critical': {'level': 4, 'label': '紧急', 'color': '#dc2626', 'icon': '🔴'},
    'important': {'level': 3, 'label': '重要', 'color': '#f59e0b', 'icon': '🟡'},
    'normal': {'level': 2, 'label': '一般', 'color': '#3b82f6', 'icon': '🔵'},
    'low': {'level': 1, 'label': '低优', 'color': '#94a3b8', 'icon': '⚪'},
}


@notification_bp.route('/api/notifications/priorities', methods=['GET'], endpoint='api_notification_priorities')
def api_notification_priorities():
    return api_response(success=True, data={'priorities': NOTIFICATION_PRIORITIES})


@notification_bp.route('/api/notifications/by-priority', methods=['GET'], endpoint='api_notifications_by_priority')
def api_notifications_by_priority():
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    priority = request.args.get('priority', 'all')
    conn = get_db()
    try:
        query = '''SELECT n.* FROM notifications n WHERE n.user_id = ?'''
        params = [session['user_id']]

        if priority != 'all' and priority in NOTIFICATION_PRIORITIES:
            if priority == 'critical':
                query += " AND n.category IN ('critical', 'error')"
            elif priority == 'important':
                query += " AND n.category IN ('warning')"
            elif priority == 'normal':
                query += " AND n.category IN ('info', 'success')"
            elif priority == 'low':
                query += " AND n.type IN ('ai', 'backup') AND n.category NOT IN ('critical', 'error', 'warning')"

        query += ' ORDER BY n.created_at DESC LIMIT 50'
        rows = conn.execute(query, params).fetchall()
        notifications = [dict(r) for r in rows]
        return api_response(success=True, data={'notifications': notifications})
    finally:
        conn.close()


@notification_bp.route('/api/notifications/push/subscribe', methods=['POST'], endpoint='api_push_subscribe')
def api_push_subscribe():
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    data = request.get_json(silent=True) or {}
    subscription = data.get('subscription')

    if not subscription:
        return api_response(success=False, message='订阅信息无效')

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM notification_settings WHERE user_id = ?",
            (session['user_id'],)).fetchone()

        if existing:
            current = json.loads(existing['settings_json'] if existing['settings_json'] else '{}')
            current['push_subscription'] = subscription
            conn.execute(
                "UPDATE notification_settings SET settings_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(current, ensure_ascii=False), existing['id']))
        else:
            settings = json.dumps({'push_subscription': subscription}, ensure_ascii=False)
            conn.execute("""INSERT INTO notification_settings (id, user_id, settings_json, created_at)
                           VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
                        (str(uuid.uuid4()), session['user_id'], settings))
        conn.commit()
        return api_response(success=True, message='推送通知已启用')
    finally:
        conn.close()


@notification_bp.route('/api/notifications/push/unsubscribe', methods=['POST'], endpoint='api_push_unsubscribe')
def api_push_unsubscribe():
    if 'user_id' not in session:
        return api_response(success=False, message='未登录', code=401)

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id, settings_json FROM notification_settings WHERE user_id = ?",
            (session['user_id'],)).fetchone()
        if existing and existing['settings_json']:
            current = json.loads(existing['settings_json'])
            current.pop('push_subscription', None)
            conn.execute(
                "UPDATE notification_settings SET settings_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(current, ensure_ascii=False), existing['id']))
            conn.commit()
        return api_response(success=True, message='推送通知已关闭')
    finally:
        conn.close()
