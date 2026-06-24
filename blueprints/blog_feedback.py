from flask import Blueprint, request, render_template, redirect, url_for, session


class _LazyAppImports:
    def __getattr__(self, name):
        from app import get_db, log_message
        _mapping = {
            'get_db': get_db,
            'log_message': log_message,
        }
        if name not in _mapping:
            raise AttributeError(f"module 'app' has no attribute '{name}'")
        return _mapping[name]


_app = _LazyAppImports()

blog_feedback_bp = Blueprint('blog_feedback', __name__)


@blog_feedback_bp.route('/blog', endpoint='blog_page')
def blog():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    conn = _app.get_db()
    try:
        posts = conn.execute("SELECT * FROM operation_logs WHERE action LIKE '%blog_post%' ORDER BY created_at DESC").fetchall()
        mapped_posts = []
        for p in posts:
            pd = dict(p)
            pd['title'] = pd.get('message', '无标题')
            pd['date'] = pd.get('created_at', '')
            pd['category'] = pd.get('action', '').replace('blog_post', '').strip() or '未分类'
            details = pd.get('details', '')
            try:
                import json as _json
                parsed = _json.loads(details)
                if isinstance(parsed, dict):
                    details = parsed.get('content', details)
            except Exception:
                pass
            pd['summary'] = (details[:200] + '...') if len(details) > 200 else details
            mapped_posts.append(pd)
        return render_template('blog_page.html', username=request.args.get('username'), posts=mapped_posts)
    finally:
        conn.close()


@blog_feedback_bp.route('/blog/<blog_id>', endpoint='blog_detail')
def blog_detail(blog_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    conn = _app.get_db()
    try:
        post = conn.execute("SELECT * FROM operation_logs WHERE id = ?", (blog_id,)).fetchone()
        if not post or 'blog_post' not in post['action']:
            return render_template('share_error.html',
                                 error='抱歉，您访问的文章不存在或已被删除。'), 404

        post_dict = dict(post)
        content = post_dict.get('details', '')
        try:
            import json as _json
            parsed = _json.loads(content)
            if isinstance(parsed, dict):
                content = parsed.get('content', content)
        except Exception:
            pass

        post_dict['title'] = post_dict.get('message', '无标题')
        post_dict['subtitle'] = ''
        post_dict['date'] = post_dict.get('created_at', '')
        post_dict['category'] = post_dict.get('action', '').replace('blog_post', '').strip() or '未分类'
        post_dict['content'] = content

        return render_template('blog_detail.html',
                             username=request.args.get('username'),
                             post=post_dict)
    finally:
        conn.close()


@blog_feedback_bp.route('/privacy', endpoint='privacy_policy')
def privacy_page():
    return render_template('privacy_policy.html')


@blog_feedback_bp.route('/terms', endpoint='service_terms')
def terms_page():
    return render_template('service_terms.html')
