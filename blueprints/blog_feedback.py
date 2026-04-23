from flask import Blueprint, request, render_template, redirect, url_for
from app import (get_db, log_message)

blog_feedback_bp = Blueprint('blog_feedback', __name__)


@blog_feedback_bp.route('/blog', endpoint='blog')
def blog():
    conn = get_db()
    try:
        posts = conn.execute("SELECT * FROM operation_logs WHERE action LIKE '%blog_post%' ORDER BY created_at DESC").fetchall()
        return render_template('blog.html', username=request.args.get('username'), posts=[dict(p) for p in posts])
    finally:
        conn.close()


@blog_feedback_bp.route('/blog/<blog_id>', endpoint='blog_detail')
def blog_detail(blog_id):
    conn = get_db()
    try:
        post = conn.execute("SELECT * FROM operation_logs WHERE id = ?", (blog_id,)).fetchone()
        if not post or 'blog_post' not in post['action']:
            return render_template('page_error.html',
                                 error_title='文章不存在',
                                 error_message='抱歉，您访问的文章不存在或已被删除。',
                                 back_url='blog',
                                 back_text='返回博客列表')

        content = post.get('details', '')
        try:
            import json as _json
            parsed = _json.loads(content)
            if isinstance(parsed, dict):
                content = parsed.get('content', content)
        except Exception:
            pass

        return render_template('blog_detail.html',
                             username=request.args.get('username'),
                             post=dict(post), content=content)
    finally:
        conn.close()


@blog_feedback_bp.route('/privacy', endpoint='privacy_page')
def privacy_page():
    return render_template('privacy_policy.html')


@blog_feedback_bp.route('/terms', endpoint='terms_page')
def terms_page():
    return render_template('terms_of_service.html')
