from flask import Blueprint, request, render_template, redirect, url_for, jsonify, session, send_from_directory
import os, json, sqlite3, shutil, base64, uuid, re
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
comments_bp = Blueprint('comments', __name__)


def _build_reactions(reaction_rows):
    reactions = {}
    for r in reaction_rows:
        emoji = r['emoji']
        if emoji not in reactions:
            reactions[emoji] = {'emoji': emoji, 'count': 0, 'users': []}
        reactions[emoji]['count'] += 1
        reactions[emoji]['users'].append({'user_id': r['user_id'], 'username': r['username']})
    return list(reactions.values())


def _handle_mentions(content, comment_id, author_id, conn):
    mentions = re.findall(r'@(\w+)', content)
    if not mentions:
        return
    seen = set()
    for username in mentions:
        if username in seen:
            continue
        seen.add(username)
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not user or user['id'] == author_id:
            continue
        notif_id = uuid.uuid4().hex
        truncated = content[:100]
        conn.execute(
            """INSERT INTO notifications (id, user_id, type, category, title, content,
               icon, action_url, action_text, source_type, source_id, is_read, created_at, expires_at)
               VALUES (?, ?, 'comment_mention', 'info', '在评论中提到了你', ?, '', '', '查看详情',
                       'comment', ?, 0, CURRENT_TIMESTAMP, '')""",
            (notif_id, user['id'], truncated, comment_id)
        )
    conn.commit()


@comments_bp.route('/api/files/<file_id>/comments', methods=['GET'], endpoint='api_list_comments')
def api_list_comments(file_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sort = request.args.get('sort', 'newest')

    if sort not in ('newest', 'oldest', 'unresolved'):
        sort = 'newest'

    offset = (page - 1) * per_page

    conn = _app.get_db()
    try:
        file_row = conn.execute("SELECT id FROM files WHERE id = ?", (file_id,)).fetchone()
        if not file_row:
            return _app.api_response(success=False, message='文件不存在', code=404)

        if sort == 'oldest':
            order_sql = "c.created_at ASC"
        elif sort == 'unresolved':
            order_sql = "c.is_resolved ASC, c.created_at DESC"
        else:
            order_sql = "c.created_at DESC"

        total = conn.execute(
            "SELECT COUNT(*) FROM file_comments WHERE file_id = ? AND parent_id IS NULL",
            (file_id,)
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT c.*, u.username FROM file_comments c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.file_id = ? AND c.parent_id IS NULL
                ORDER BY {order_sql} LIMIT ? OFFSET ?""",
            (file_id, per_page, offset)
        ).fetchall()

        comments = []
        for row in rows:
            comment = dict(row)
            comment['supports_markdown'] = True
            comment['replies'] = []

            reply_rows = conn.execute(
                """SELECT c.*, u.username FROM file_comments c
                   LEFT JOIN users u ON c.user_id = u.id
                   WHERE c.parent_id = ? ORDER BY c.created_at ASC""",
                (comment['id'],)
            ).fetchall()

            for reply in reply_rows:
                reply_dict = dict(reply)
                reply_dict['supports_markdown'] = True
                reaction_rows = conn.execute(
                    """SELECT cr.emoji, cr.user_id, u.username FROM comment_reactions cr
                       LEFT JOIN users u ON cr.user_id = u.id
                       WHERE cr.comment_id = ?""",
                    (reply_dict['id'],)
                ).fetchall()
                reply_dict['reactions'] = _build_reactions(reaction_rows)
                comment['replies'].append(reply_dict)

            reaction_rows = conn.execute(
                """SELECT cr.emoji, cr.user_id, u.username FROM comment_reactions cr
                   LEFT JOIN users u ON cr.user_id = u.id
                   WHERE cr.comment_id = ?""",
                (comment['id'],)
            ).fetchall()
            comment['reactions'] = _build_reactions(reaction_rows)
            comments.append(comment)

        return _app.api_response(success=True, data={
            'comments': comments,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    finally:
        conn.close()


@comments_bp.route('/api/files/<file_id>/comments', methods=['POST'], endpoint='api_create_comment')
def api_create_comment(file_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    parent_id = data.get('parent_id')

    if not content:
        return _app.api_response(success=False, message='评论内容不能为空')

    conn = _app.get_db()
    try:
        file_row = conn.execute("SELECT id FROM files WHERE id = ?", (file_id,)).fetchone()
        if not file_row:
            return _app.api_response(success=False, message='文件不存在', code=404)

        if parent_id:
            parent = conn.execute(
                "SELECT id, parent_id FROM file_comments WHERE id = ? AND file_id = ?",
                (parent_id, file_id)
            ).fetchone()
            if not parent:
                return _app.api_response(success=False, message='父评论不存在', code=404)
            if parent['parent_id']:
                return _app.api_response(success=False, message='不支持超过两层的嵌套回复')

        comment_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO file_comments (id, file_id, user_id, content, parent_id, is_resolved, created_at)
               VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)""",
            (comment_id, file_id, session['user_id'], content, parent_id)
        )
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'添加评论: {content[:50]}',
                        user_id=session['user_id'], action='create_comment',
                        target_id=comment_id, target_type='comment', request=request)

        _handle_mentions(content, comment_id, session['user_id'], conn)

        comment_row = conn.execute(
            """SELECT c.*, u.username FROM file_comments c
               LEFT JOIN users u ON c.user_id = u.id
               WHERE c.id = ?""",
            (comment_id,)
        ).fetchone()

        result = dict(comment_row)
        result['supports_markdown'] = True
        result['replies'] = []
        result['reactions'] = []

        return _app.api_response(success=True, data={'comment': result}, message='评论添加成功')
    finally:
        conn.close()


@comments_bp.route('/api/comments/<comment_id>', methods=['PUT'], endpoint='api_update_comment')
def api_update_comment(comment_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()

    if not content:
        return _app.api_response(success=False, message='评论内容不能为空')

    conn = _app.get_db()
    try:
        comment = conn.execute(
            "SELECT * FROM file_comments WHERE id = ?", (comment_id,)
        ).fetchone()

        if not comment:
            return _app.api_response(success=False, message='评论不存在', code=404)

        if comment['user_id'] != session['user_id']:
            return _app.api_response(success=False, message='无权修改此评论', code=403)

        conn.execute(
            "UPDATE file_comments SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (content, comment_id)
        )
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'更新评论: {content[:50]}',
                        user_id=session['user_id'], action='update_comment',
                        target_id=comment_id, target_type='comment', request=request)

        comment_row = conn.execute(
            """SELECT c.*, u.username FROM file_comments c
               LEFT JOIN users u ON c.user_id = u.id
               WHERE c.id = ?""",
            (comment_id,)
        ).fetchone()

        result = dict(comment_row)
        result['supports_markdown'] = True

        return _app.api_response(success=True, data={'comment': result}, message='评论更新成功')
    finally:
        conn.close()


@comments_bp.route('/api/comments/<comment_id>', methods=['DELETE'], endpoint='api_delete_comment')
def api_delete_comment(comment_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    conn = _app.get_db()
    try:
        comment = conn.execute(
            "SELECT * FROM file_comments WHERE id = ?", (comment_id,)
        ).fetchone()

        if not comment:
            return _app.api_response(success=False, message='评论不存在', code=404)

        is_author = comment['user_id'] == session['user_id']
        is_admin = session.get('role') in ('admin', 'developer')

        if not is_author and not is_admin:
            return _app.api_response(success=False, message='无权删除此评论', code=403)

        conn.execute("DELETE FROM comment_reactions WHERE comment_id = ?", (comment_id,))
        reply_rows = conn.execute(
            "SELECT id FROM file_comments WHERE parent_id = ?", (comment_id,)
        ).fetchall()
        for reply in reply_rows:
            conn.execute("DELETE FROM comment_reactions WHERE comment_id = ?", (reply['id'],))
        conn.execute("DELETE FROM file_comments WHERE parent_id = ?", (comment_id,))
        conn.execute("DELETE FROM file_comments WHERE id = ?", (comment_id,))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'删除评论: {comment_id}',
                        user_id=session['user_id'], action='delete_comment',
                        target_id=comment_id, target_type='comment', request=request)

        return _app.api_response(success=True, message='评论已删除')
    finally:
        conn.close()


@comments_bp.route('/api/comments/<comment_id>/resolve', methods=['PUT'], endpoint='api_toggle_resolve')
def api_toggle_resolve(comment_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    conn = _app.get_db()
    try:
        comment = conn.execute(
            "SELECT * FROM file_comments WHERE id = ?", (comment_id,)
        ).fetchone()

        if not comment:
            return _app.api_response(success=False, message='评论不存在', code=404)

        is_author = comment['user_id'] == session['user_id']
        is_admin = session.get('role') in ('admin', 'developer')

        if not is_author and not is_admin:
            return _app.api_response(success=False, message='无权操作此评论', code=403)

        new_status = 0 if comment['is_resolved'] else 1
        conn.execute(
            "UPDATE file_comments SET is_resolved = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_status, comment_id)
        )
        conn.commit()

        status_text = '已解决' if new_status else '未解决'
        _app.log_message(log_type='operation', log_level='INFO',
                        message=f'评论状态变更: {status_text}',
                        user_id=session['user_id'], action='toggle_resolve',
                        target_id=comment_id, target_type='comment', request=request)

        return _app.api_response(success=True, data={'is_resolved': new_status},
                                message=f'评论已标记为{status_text}')
    finally:
        conn.close()


@comments_bp.route('/api/comments/<comment_id>/react', methods=['POST'], endpoint='api_react_comment')
def api_react_comment(comment_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='未登录', code=401)

    data = request.get_json(silent=True) or {}
    emoji = (data.get('emoji') or '').strip()

    if not emoji:
        return _app.api_response(success=False, message='表情不能为空')

    conn = _app.get_db()
    try:
        comment = conn.execute(
            "SELECT id FROM file_comments WHERE id = ?", (comment_id,)
        ).fetchone()

        if not comment:
            return _app.api_response(success=False, message='评论不存在', code=404)

        existing = conn.execute(
            "SELECT id FROM comment_reactions WHERE comment_id = ? AND user_id = ? AND emoji = ?",
            (comment_id, session['user_id'], emoji)
        ).fetchone()

        if existing:
            conn.execute("DELETE FROM comment_reactions WHERE id = ?", (existing['id'],))
        else:
            reaction_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO comment_reactions (id, comment_id, user_id, emoji, created_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (reaction_id, comment_id, session['user_id'], emoji)
            )

        conn.commit()

        reaction_rows = conn.execute(
            """SELECT cr.emoji, cr.user_id, u.username FROM comment_reactions cr
               LEFT JOIN users u ON cr.user_id = u.id
               WHERE cr.comment_id = ?""",
            (comment_id,)
        ).fetchall()
        reactions = _build_reactions(reaction_rows)

        return _app.api_response(success=True, data={'reactions': reactions})
    finally:
        conn.close()
