from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
from app import (app, get_db, get_all_files, log_message,
                page_error_response, api_response)
import os
import uuid
import json

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/ai', methods=['GET', 'POST'], endpoint='ai')
def ai():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    if request.method == 'POST':
        message = request.form.get('message')
        model = request.form.get('model', 'deepseek-chat')

        if not message.strip():
            flash('请输入消息')
            return redirect(url_for('ai'))

        try:
            from app import call_deepseek_api
            response_text = call_deepseek_api(message, model=model)

            conn = get_db()
            try:
                content_id = str(uuid.uuid4())
                conn.execute('''INSERT INTO ai_contents (id, user_id, content_type, title,
                               content, metadata_json, created_at)
                               VALUES (?, ?, 'chat', 'AI对话', ?, ?, CURRENT_TIMESTAMP)''',
                           (content_id, session['user_id'],
                            json.dumps({"user_message": message, "response": response_text},
                                     ensure_ascii=False),
                            json.dumps({"model": model}, ensure_ascii=False)))
                conn.commit()

                log_message(log_type='operation', log_level='INFO',
                           message=f'AI对话完成 (模型: {model})',
                           user_id=session['user_id'], action='ai_chat',
                           target_id=content_id, target_type='ai_content', request=request)

                return render_template('ai_page.html',
                                     username=session.get('username'),
                                     user_message=message,
                                     response=response_text,
                                     content_id=content_id)
            finally:
                conn.close()

        except Exception as e:
            flash(f'AI服务调用失败: {str(e)}')
            return redirect(url_for('ai'))

    return render_template('ai_page.html', username=session.get('username'))


@ai_bp.route('/ai_page', endpoint='ai_page')
def ai_page():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    return render_template('ai_page.html', username=session.get('username'))


@ai_bp.route('/save-ai-content', methods=['POST'], endpoint='save_ai_content')
def save_ai_content():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    content = request.form.get('content')
    content_type = request.form.get('content_type', 'chat')
    title = request.form.get('title', '')

    if not content:
        flash('内容不能为空')
        return redirect(url_for('ai_page'))

    conn = get_db()
    try:
        content_id = str(uuid.uuid4())
        conn.execute('''INSERT INTO ai_contents (id, user_id, content_type, title, content, created_at)
                       VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                   (content_id, session['user_id'], content_type, title, content))
        conn.commit()

        log_message(log_type='operation', log_level='INFO',
                   message=f'保存AI内容: {title or content[:20]}',
                   user_id=session['user_id'], action='save_ai_content',
                   target_id=content_id, target_type='ai_content', request=request)

        flash('AI内容保存成功!')
        return redirect(url_for('ai_page'))
    except Exception as e:
        conn.rollback()
        flash(f'保存失败: {str(e)}')
        return redirect(url_for('ai_page'))
    finally:
        conn.close()


@ai_bp.route('/delete-ai-content/<content_id>', methods=['POST'], endpoint='delete_ai_content')
def delete_ai_content(content_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    conn = get_db()
    try:
        ai_content = conn.execute("SELECT * FROM ai_contents WHERE id = ? AND user_id = ?",
                                 (content_id, session['user_id'])).fetchone()
        if not ai_content:
            flash('内容不存在或无权限删除')
            return redirect(url_for('ai_page'))

        conn.execute("DELETE FROM ai_contents WHERE id = ? AND user_id = ?",
                    (content_id, session['user_id']))
        conn.commit()

        log_message(log_type='operation', log_level='WARNING',
                   message=f"删除AI内容: {ai_content['title']}",
                   user_id=session['user_id'], action='delete_ai_content',
                   target_id=content_id, target_type='ai_content', request=request)

        flash('AI内容已删除')
        return redirect(url_for('ai_page'))
    except Exception as e:
        conn.rollback()
        flash(f'删除失败: {str(e)}')
        return redirect(url_for('ai_page'))
    finally:
        conn.close()


@ai_bp.route('/api/ai/chat', methods=['POST'], endpoint='api_ai_chat')
def api_ai_chat():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    message = data.get('message', '')
    model = data.get('model', 'deepseek-chat')
    stream = data.get('stream', False)

    if not message.strip():
        return api_response(success=False, message='消息不能为空')

    if stream:
        from app import generate_streaming_response
        return generate_streaming_response(message, model=model)

    try:
        from app import call_deepseek_api
        response_text = call_deepseek_api(message, model=model)

        conn = get_db()
        try:
            content_id = str(uuid.uuid4())
            conn.execute("""INSERT INTO ai_contents (id, user_id, content_type, title, content,
                           metadata_json, created_at) VALUES (?, ?, 'chat', 'AI对话', ?, ?, CURRENT_TIMESTAMP)""",
                        (content_id, session['user_id'],
                         json.dumps({"user_message": message, "response": response_text},
                                  ensure_ascii=False),
                         json.dumps({"model": model}, ensure_ascii=False)))
            conn.commit()

            log_message(log_type='operation', log_level='INFO',
                       message=f'API AI对话完成 (模型: {model})',
                       user_id=session['user_id'], action='api_ai_chat',
                       target_id=content_id, target_type='ai_content', request=request)

            return api_response(success=True, data={
                'response': response_text,
                'content_id': content_id
            })
        finally:
            conn.close()
    except Exception as e:
        return api_response(success=False, message=f'AI调用失败: {str(e)}')


@ai_bp.route('/api/ai/conversations', methods=['GET'], endpoint='api_ai_conversations')
def api_ai_conversations():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM ai_contents WHERE user_id = ? AND content_type = 'chat'
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (session['user_id'], limit, offset)).fetchall()

        conversations = []
        for row in rows:
            meta = {}
            try:
                meta = json.loads(row['metadata_json']) if row['metadata_json'] else {}
            except:
                pass
            conversations.append({
                'id': row['id'],
                'created_at': row['created_at'],
                'model': meta.get('model', 'unknown'),
                'preview': row['content'][:200] if row['content'] else ''
            })

        total = conn.execute(
            "SELECT COUNT(*) FROM ai_contents WHERE user_id = ? AND content_type = 'chat'",
            (session['user_id'],)).fetchone()[0]

        return api_response(success=True, data={
            'conversations': conversations,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    finally:
        conn.close()


@ai_bp.route('/api/ai/export', methods=['GET'], endpoint='api_ai_export')
def api_ai_export():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    format_type = request.args.get('format', 'json').lower()
    if format_type not in ('json', 'txt'):
        return api_response(success=False, message='不支持的导出格式')

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM ai_contents WHERE user_id = ?
               ORDER BY created_at DESC""", (session['user_id'],)).fetchall()

        if format_type == 'json':
            export_data = [dict(r) for r in rows]
            response = make_response(json.dumps(export_data, indent=2, ensure_ascii=False))
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename="ai_conversations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
        elif format_type == 'txt':
            lines = []
            for r in rows:
                lines.append(f"[{r['created_at']}] 模型: {r.get('metadata_json', '')}")
                lines.append(f"{r['content']}")
                lines.append("-" * 60)
            response = make_response('\n'.join(lines))
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="ai_conversations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt"'

        log_message(log_type='operation', log_level='INFO',
                   message=f'导出AI对话记录 (格式: {format_type})',
                   user_id=session['user_id'], action='export_ai_data', request=request)

        return response
    finally:
        conn.close()


@ai_bp.route('/api/ai/delete/<content_id>', methods=['DELETE'], endpoint='api_delete_ai_content')
def api_delete_ai_content(content_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    conn = get_db()
    try:
        result = conn.execute("DELETE FROM ai_contents WHERE id = ? AND user_id = ?",
                             (content_id, session['user_id']))
        conn.commit()

        if result.rowcount == 0:
            return api_response(success=False, message='内容不存在或无权限', code=404)

        log_message(log_type='operation', log_level='WARNING',
                   message=f'API删除AI内容: {content_id}',
                   user_id=session['user_id'], action='api_delete_ai_content',
                   target_id=content_id, target_type='ai_content', request=request)

        return api_response(success=True, message='删除成功')
    finally:
        conn.close()
