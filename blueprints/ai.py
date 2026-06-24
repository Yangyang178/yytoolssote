from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session, make_response
import os
import uuid
import json
from datetime import datetime, timezone, timedelta


_bj_tz = timezone(timedelta(hours=8))

def _bj_now():
    return datetime.now(_bj_tz).strftime('%Y-%m-%d %H:%M:%S') + '+08:00'

class _LazyAppImports:

    def __getattr__(self, name):
        if name == 'app':
            from app import app as _app
            return _app
        from app import (
            get_db, get_all_files, log_message,
            page_error_response, api_response,
            deepseek_chat,
        )
        locals_dict = locals()
        if name in locals_dict:
            return locals_dict[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


_app = _LazyAppImports()

ai_bp = Blueprint('ai', __name__)


def _get_saved_contents(user_id):
    conn = _app.get_db()
    try:
        rows = conn.execute(
            '''SELECT id, ai_function, prompt, response, created_at
               FROM ai_contents WHERE user_id = ?
               ORDER BY created_at DESC''', (user_id,)).fetchall()
        return [{
            'id': row['id'],
            'ai_function': row['ai_function'],
            'prompt': row['prompt'],
            'response': row['response'],
            'created_at': row['created_at']
        } for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


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
            result = _app.deepseek_chat([{"role": "user", "content": message}], model=model)
            response_text = result.get('choices', [{}])[0].get('message', {}).get('content', str(result))

            conn = _app.get_db()
            try:
                content_id = str(uuid.uuid4())
                conn.execute(
                    '''INSERT INTO ai_contents (id, user_id, ai_function, prompt, response, created_at)
                       VALUES (?, ?, 'chat', ?, ?, ?)''',
                    (content_id, session['user_id'], message, response_text, _bj_now()))
                conn.commit()

                _app.log_message(log_type='operation', log_level='INFO',
                           message=f'AI对话完成 (模型: {model})',
                           user_id=session['user_id'], action='ai_chat',
                           target_id=content_id, target_type='ai_content', request=request)

                saved_contents = _get_saved_contents(session['user_id'])
                return render_template('ai_page.html',
                                     username=session.get('username'),
                                     user_message=message,
                                     response=response_text,
                                     content_id=content_id,
                                     saved_contents=saved_contents)
            finally:
                conn.close()

        except Exception as e:
            flash(f'AI服务调用失败: {str(e)}')
            return redirect(url_for('ai'))

    saved_contents = _get_saved_contents(session['user_id'])
    return render_template('ai_page.html', username=session.get('username'),
                          saved_contents=saved_contents)


@ai_bp.route('/ai_page', endpoint='ai_page')
def ai_page():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    saved_contents = _get_saved_contents(session['user_id'])
    return render_template('ai_page.html', username=session.get('username'),
                          saved_contents=saved_contents)


@ai_bp.route('/save-ai-content', methods=['POST'], endpoint='save_ai_content')
def save_ai_content():
    if 'user_id' not in session:
        return redirect(url_for('auth'))

    ai_function = request.form.get('ai_function', 'chat')
    prompt = request.form.get('prompt', '')
    response_text = request.form.get('response', '')

    if not prompt or not response_text:
        flash('内容不能为空')
        return redirect(url_for('ai_page'))

    conn = _app.get_db()
    try:
        content_id = str(uuid.uuid4())
        conn.execute(
            '''INSERT INTO ai_contents (id, user_id, ai_function, prompt, response, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (content_id, session['user_id'], ai_function, prompt, response_text, _bj_now()))
        conn.commit()

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'保存AI内容: {prompt[:20]}',
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

    conn = _app.get_db()
    try:
        ai_content = conn.execute("SELECT * FROM ai_contents WHERE id = ? AND user_id = ?",
                                 (content_id, session['user_id'])).fetchone()
        if not ai_content:
            flash('内容不存在或无权限删除')
            return redirect(url_for('ai_page'))

        conn.execute("DELETE FROM ai_contents WHERE id = ? AND user_id = ?",
                    (content_id, session['user_id']))
        conn.commit()

        _app.log_message(log_type='operation', log_level='WARNING',
                   message=f"删除AI内容: {ai_content['prompt'][:30]}",
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
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    message = data.get('message', '')
    model = data.get('model', 'deepseek-chat')
    stream = data.get('stream', False)

    if not message.strip():
        return _app.api_response(success=False, message='消息不能为空')

    if stream:
        try:
            result = _app.deepseek_chat([{"role": "user", "content": message}], model=model)
            response_text = result.get('choices', [{}])[0].get('message', {}).get('content', str(result))
            return _app.api_response(success=True, data={'response': response_text})
        except Exception as e:
            return _app.api_response(success=False, message=f'AI调用失败: {str(e)}')

    try:
        result = _app.deepseek_chat([{"role": "user", "content": message}], model=model)
        response_text = result.get('choices', [{}])[0].get('message', {}).get('content', str(result))

        conn = _app.get_db()
        try:
            content_id = str(uuid.uuid4())
            conn.execute(
                '''INSERT INTO ai_contents (id, user_id, ai_function, prompt, response, created_at)
                   VALUES (?, ?, 'chat', ?, ?, ?)''',
                (content_id, session['user_id'], message, response_text, _bj_now()))
            conn.commit()

            _app.log_message(log_type='operation', log_level='INFO',
                       message=f'API AI对话完成 (模型: {model})',
                       user_id=session['user_id'], action='api_ai_chat',
                       target_id=content_id, target_type='ai_content', request=request)

            return _app.api_response(success=True, data={
                'response': response_text,
                'content_id': content_id
            })
        finally:
            conn.close()
    except Exception as e:
        return _app.api_response(success=False, message=f'AI调用失败: {str(e)}')


@ai_bp.route('/api/ai/conversations', methods=['GET'], endpoint='api_ai_conversations')
def api_ai_conversations():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    conn = _app.get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM ai_contents WHERE user_id = ? AND ai_function = 'chat'
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (session['user_id'], limit, offset)).fetchall()

        conversations = []
        for row in rows:
            conversations.append({
                'id': row['id'],
                'created_at': row['created_at'],
                'model': 'deepseek-chat',
                'preview': row['prompt'][:200] if row['prompt'] else '',
                'title': row['prompt'][:50] if row['prompt'] else '对话',
                'message_count': 1
            })

        total = conn.execute(
            "SELECT COUNT(*) FROM ai_contents WHERE user_id = ? AND ai_function = 'chat'",
            (session['user_id'],)).fetchone()[0]

        return _app.api_response(success=True, data={
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
        return _app.api_response(success=False, message='请先登录', code=401)

    format_type = request.args.get('format', 'json').lower()
    if format_type not in ('json', 'txt'):
        return _app.api_response(success=False, message='不支持的导出格式')

    conn = _app.get_db()
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
                rd = dict(r)
                lines.append(f"[{rd['created_at']}] 功能: {rd.get('ai_function', '')}")
                lines.append(f"问题: {rd.get('prompt', '')}")
                lines.append(f"回答: {rd.get('response', '')}")
                lines.append("-" * 60)
            response = make_response('\n'.join(lines))
            response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename="ai_conversations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt"'

        _app.log_message(log_type='operation', log_level='INFO',
                   message=f'导出AI对话记录 (格式: {format_type})',
                   user_id=session['user_id'], action='export_ai_data', request=request)

        return response
    finally:
        conn.close()


@ai_bp.route('/api/ai/delete/<content_id>', methods=['DELETE'], endpoint='api_delete_ai_content')
def api_delete_ai_content(content_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        result = conn.execute("DELETE FROM ai_contents WHERE id = ? AND user_id = ?",
                             (content_id, session['user_id']))
        conn.commit()

        if result.rowcount == 0:
            return _app.api_response(success=False, message='内容不存在或无权限', code=404)

        _app.log_message(log_type='operation', log_level='WARNING',
                   message=f'API删除AI内容: {content_id}',
                   user_id=session['user_id'], action='api_delete_ai_content',
                   target_id=content_id, target_type='ai_content', request=request)

        return _app.api_response(success=True, message='删除成功')
    finally:
        conn.close()


@ai_bp.route('/api/ai/chat/multi-turn', methods=['POST'], endpoint='api_ai_chat_multi_turn')
def api_ai_chat_multi_turn():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    messages = data.get('messages', [])
    model = data.get('model', 'deepseek-chat')
    system_prompt = data.get('system_prompt', '')

    if not messages:
        return _app.api_response(success=False, message='消息不能为空')

    try:
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            if msg.get('role') in ('user', 'assistant', 'system'):
                api_messages.append({"role": msg['role'], "content": msg['content']})

        result = _app.deepseek_chat(api_messages, model=model)
        response_text = result.get('choices', [{}])[0].get('message', {}).get('content', str(result))

        conn = _app.get_db()
        try:
            content_id = str(uuid.uuid4())
            conversation_json = json.dumps(messages[-3:], ensure_ascii=False)
            conn.execute(
                '''INSERT INTO ai_contents (id, user_id, ai_function, prompt, response, created_at)
                   VALUES (?, ?, 'multi_turn', ?, ?, ?)''',
                (content_id, session['user_id'],
                 conversation_json, response_text, _bj_now()))
            conn.commit()
        finally:
            conn.close()

        return _app.api_response(success=True, data={
            'response': response_text,
            'content_id': content_id
        })
    except Exception as e:
        return _app.api_response(success=False, message=f'AI调用失败: {str(e)}')


@ai_bp.route('/api/ai/templates', methods=['GET'], endpoint='api_ai_templates')
def api_ai_templates():
    templates = [
        {'id': 'code_review', 'name': '代码审查', 'icon': '🔍',
         'system_prompt': '你是一位资深代码审查专家，请分析代码质量、安全漏洞和优化建议。',
         'placeholder': '粘贴你的代码，我来帮你审查...'},
        {'id': 'doc_writer', 'name': '文档写作', 'icon': '📝',
         'system_prompt': '你是一位技术文档专家，请帮助撰写清晰、专业的技术文档。',
         'placeholder': '描述你要写文档的功能或项目...'},
        {'id': 'translator', 'name': '翻译助手', 'icon': '🌐',
         'system_prompt': '你是一位专业翻译，请准确翻译并保持原文风格。如未指定语言，默认中英互译。',
         'placeholder': '输入需要翻译的内容...'},
        {'id': 'data_analyst', 'name': '数据分析', 'icon': '📊',
         'system_prompt': '你是一位数据分析专家，请帮助分析数据、生成洞察和建议可视化方案。',
         'placeholder': '描述你的数据或粘贴CSV数据...'},
        {'id': 'debug_helper', 'name': '调试助手', 'icon': '🐛',
         'system_prompt': '你是一位调试专家，请帮助分析错误原因并提供修复方案。',
         'placeholder': '粘贴错误信息和相关代码...'},
        {'id': 'general', 'name': '通用对话', 'icon': '💬',
         'system_prompt': '',
         'placeholder': '输入你的问题...'},
    ]
    return _app.api_response(success=True, data={'templates': templates})


@ai_bp.route('/api/ai/analyze-file/<file_id>', methods=['POST'], endpoint='api_ai_analyze_file')
def api_ai_analyze_file(file_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        file = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if not file:
            return _app.api_response(success=False, message='文件不存在', code=404)

        fd = dict(file)
        analysis_type = request.get_json(silent=True) or {}.get('type', 'summary')

        prompt_map = {
            'summary': f'请对以下文件进行简要摘要分析：\n文件名：{fd["filename"]}\n大小：{fd["size"]}字节\n项目：{fd.get("project_name", "无")}\n描述：{fd.get("project_desc", "无")}',
            'tags': f'请为以下文件推荐3-5个标签（只输出标签，逗号分隔）：\n文件名：{fd["filename"]}\n项目：{fd.get("project_name", "无")}\n描述：{fd.get("project_desc", "无")}',
            'security': f'请分析以下文件的安全风险：\n文件名：{fd["filename"]}\n类型：{fd["filename"].split(".")[-1] if "." in fd["filename"] else "未知"}',
        }

        prompt = prompt_map.get(analysis_type, prompt_map['summary'])

        try:
            result = _app.deepseek_chat([{"role": "user", "content": prompt}])
            response_text = result.get('choices', [{}])[0].get('message', {}).get('content', str(result))
        except Exception as e:
            return _app.api_response(success=False, message=f'AI分析失败: {str(e)}')

        content_id = str(uuid.uuid4())
        conn.execute(
            '''INSERT INTO ai_contents (id, user_id, ai_function, prompt, response, created_at)
               VALUES (?, ?, 'file_analysis', ?, ?, ?)''',
            (content_id, session['user_id'], prompt, response_text, _bj_now()))
        conn.commit()

        return _app.api_response(success=True, data={
            'analysis': response_text,
            'content_id': content_id,
            'file_id': file_id
        })
    finally:
        conn.close()


@ai_bp.route('/api/ai/chat/stream', methods=['POST'], endpoint='api_ai_chat_stream')
def api_ai_chat_stream():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    data = request.get_json(silent=True) or {}
    message = data.get('message', '')
    model = data.get('model', 'deepseek-chat')

    if not message.strip():
        return _app.api_response(success=False, message='消息不能为空')

    try:
        result = _app.deepseek_chat([{"role": "user", "content": message}], model=model)
        response_text = result.get('choices', [{}])[0].get('message', {}).get('content', str(result))

        conn = _app.get_db()
        try:
            content_id = str(uuid.uuid4())
            conn.execute(
                '''INSERT INTO ai_contents (id, user_id, ai_function, prompt, response, created_at)
                   VALUES (?, ?, 'chat', ?, ?, ?)''',
                (content_id, session['user_id'], message, response_text, _bj_now()))
            conn.commit()
        finally:
            conn.close()

        return _app.api_response(success=True, data={
            'response': response_text,
            'content_id': content_id
        })
    except Exception as e:
        return _app.api_response(success=False, message=f'AI调用失败: {str(e)}')


@ai_bp.route('/api/ai/conversation/<conv_id>', methods=['GET'], endpoint='api_ai_conversation')
def api_ai_conversation(conv_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        row = conn.execute("SELECT * FROM ai_contents WHERE id = ? AND user_id = ?",
                          (conv_id, session['user_id'])).fetchone()
        if not row:
            return _app.api_response(success=False, message='对话不存在', code=404)

        messages = [
            {'role': 'user', 'content': row['prompt'] or ''},
            {'role': 'assistant', 'content': row['response'] or ''}
        ]

        return _app.api_response(success=True, data={
            'id': row['id'],
            'messages': messages,
            'created_at': row['created_at']
        })
    finally:
        conn.close()


@ai_bp.route('/api/ai/conversations/clear', methods=['POST'], endpoint='api_ai_conversations_clear')
def api_ai_conversations_clear():
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        result = conn.execute("DELETE FROM ai_contents WHERE user_id = ? AND ai_function = 'chat'",
                             (session['user_id'],))
        conn.commit()
        return _app.api_response(success=True, message=f'已清除 {result.rowcount} 条对话记录')
    finally:
        conn.close()


@ai_bp.route('/api/ai-content/<content_id>', methods=['GET'], endpoint='api_get_ai_content')
def api_get_ai_content(content_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        row = conn.execute("SELECT * FROM ai_contents WHERE id = ? AND user_id = ?",
                          (content_id, session['user_id'])).fetchone()
        if not row:
            return _app.api_response(success=False, message='内容不存在', code=404)
        return _app.api_response(success=True, data=dict(row))
    finally:
        conn.close()


@ai_bp.route('/api/ai-content/<content_id>', methods=['DELETE'], endpoint='api_delete_ai_content_alt')
def api_delete_ai_content_alt(content_id):
    if 'user_id' not in session:
        return _app.api_response(success=False, message='请先登录', code=401)

    conn = _app.get_db()
    try:
        result = conn.execute("DELETE FROM ai_contents WHERE id = ? AND user_id = ?",
                             (content_id, session['user_id']))
        conn.commit()
        if result.rowcount == 0:
            return _app.api_response(success=False, message='内容不存在或无权限', code=404)
        return _app.api_response(success=True, message='删除成功')
    finally:
        conn.close()
