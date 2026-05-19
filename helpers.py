import sqlite3
import functools
import json
from datetime import datetime
from flask import request, session, jsonify, current_app, g
import threading
from pathlib import Path

# ==================== 数据库连接 ====================

_db_path = None
_db_lock = threading.Lock()

def set_db_path(path):
    global _db_path
    _db_path = path

def get_db():
    global _db_path
    if 'db' not in g:
        if _db_path is None:
            base_dir = Path(__file__).parent
            data_dir = base_dir / "data"
            data_dir.mkdir(exist_ok=True)
            _db_path = str(data_dir / "db.sqlite")
        g.db = sqlite3.connect(_db_path)
        g.db.row_factory = sqlite3.Row
    return g.db


# ==================== 日志系统 ====================

def log_message(log_type='operation', log_level='INFO', message='', user_id=None,
                action='', request=None, request_obj=None, extra_data=None, target_id=None, target_type=None, details=None):
    try:
        conn = get_db()
        uid = user_id or (session.get('user_id') if session else None)
        req = request_obj or request
        ip = req.remote_addr if req else ''
        ua = req.user_agent.string if req else ''

        extra_json = json.dumps(extra_data) if extra_data else '{}'
        details_json = json.dumps(details) if details else None

        conn.execute('''INSERT INTO logs
            (log_type, log_level, message, user_id, ip_address, user_agent, action, extra_data, target_id, target_type, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
            (log_type, log_level, message[:500] if message else '', uid, ip, ua, action, extra_json,
             target_id, target_type, details_json))
        conn.commit()
    except Exception as e:
        print(f"[日志错误] {e}")


# ==================== API 响应工具 ====================

def api_response(success=True, message='', data=None, code=200):
    response_data = {
        'success': success,
        'message': message,
        'data': data
    }
    response = jsonify(response_data)
    response.status_code = code
    return response


# ==================== 登录验证装饰器 ====================

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            from flask import redirect, url_for
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== 分页错误响应 ====================

def page_error_response(template='error', message='页面不存在', code=404):
    from flask import render_template
    return render_template(f'{template}.html', error=message, code=code), code


# ==================== 获取所有文件 ====================

def get_all_files(user_id=None):
    conn = get_db()
    try:
        if user_id:
            rows = conn.execute("""SELECT * FROM files WHERE (user_id = ? OR user_id = 'default_user') AND is_deleted = 0
                                  ORDER BY created_at DESC""", (user_id,)).fetchall()
        else:
            rows = conn.execute("""SELECT * FROM files WHERE is_deleted = 0
                                  ORDER BY created_at DESC""").fetchall()

        print(f"[INFO] get_all_files: 查询到 {len(rows)} 个文件")

        import json
        files = []
        for row in rows:
            try:
                f = dict(row)
                f['categories'] = get_file_categories(conn, f['id'])
                f['tags'] = get_file_tags(conn, f['id'])

                dkfile_raw = f.get('dkfile')
                if isinstance(dkfile_raw, str) and dkfile_raw:
                    try:
                        f['dkfile'] = json.loads(dkfile_raw)
                    except (json.JSONDecodeError, TypeError):
                        f['dkfile'] = {}
                elif not dkfile_raw:
                    f['dkfile'] = {}

                f['stored_name'] = f.get('stored_name') or ''
                f['filename'] = f.get('filename') or '未命名文件'

                files.append(f)
            except Exception as e:
                print(f"[警告] 处理文件 {row.get('id', 'unknown')} 时出错: {e}")
                continue

        return files
    except Exception as e:
        print(f"[错误] get_all_files 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        pass


# ==================== 文件操作辅助函数 ====================

def get_file_by_id(file_id):
    """根据ID获取文件信息"""
    conn = get_db()
    row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if row:
        f = dict(row)
        f['categories'] = get_file_categories(conn, f['id'])
        f['tags'] = get_file_tags(conn, f['id'])
        return f
    return None


def get_file_categories(conn, file_id):
    """获取文件的分类"""
    rows = conn.execute('''SELECT c.* FROM categories c
                           JOIN file_categories fc ON c.id = fc.category_id
                           WHERE fc.file_id = ?''', (file_id,)).fetchall()
    return [dict(r) for r in rows]


def get_file_tags(conn, file_id):
    """获取文件的标签"""
    rows = conn.execute('''SELECT t.* FROM tags t
                           JOIN file_tags ft ON t.id = ft.tag_id
                           WHERE ft.file_id = ?''', (file_id,)).fetchall()
    return [dict(r) for r in rows]


def get_like_count(file_id):
    """获取文件点赞数"""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) as cnt FROM likes WHERE file_id = ?", (file_id,)).fetchone()['cnt']
    return count


def get_favorite_count(file_id):
    """获取文件收藏数"""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) as cnt FROM favorites WHERE file_id = ?", (file_id,)).fetchone()['cnt']
    return count


def is_liked(file_id, user_id):
    """检查用户是否已点赞"""
    if not user_id:
        return False
    conn = get_db()
    existing = conn.execute("SELECT id FROM likes WHERE user_id = ? AND file_id = ?",
                          (user_id, file_id)).fetchone()
    return existing is not None


def is_favorited(file_id, user_id):
    """检查用户是否已收藏"""
    if not user_id:
        return False
    conn = get_db()
    existing = conn.execute("SELECT id FROM favorites WHERE user_id = ? AND file_id = ?",
                          (user_id, file_id)).fetchone()
    return existing is not None


def assign_category_to_file(conn, file_id, category_name, user_id):
    """为文件分配分类（自动创建或使用已有分类）"""
    category = conn.execute("SELECT * FROM categories WHERE name = ?", (category_name,)).fetchone()
    if not category:
        cat_id = str(__import__('uuid').uuid4())
        conn.execute("INSERT INTO categories (id, name) VALUES (?, ?)", (cat_id, category_name))
        category_id = cat_id
    else:
        category_id = category['id']

    existing = conn.execute("SELECT * FROM file_categories WHERE file_id = ? AND category_id = ?",
                          (file_id, category_id)).fetchone()
    if not existing:
        fc_id = str(__import__('uuid').uuid4())
        conn.execute("INSERT INTO file_categories (id, file_id, category_id) VALUES (?, ?, ?)",
                    (fc_id, file_id, category_id))


def notify_security_event(user_id, title, message, category='warning'):
    """发送安全通知事件到通知中心"""
    try:
        from blueprints.notification import create_notification
        create_notification(
            user_id=user_id,
            notif_type='security',
            title=title,
            content=message,
            category=category
        )
    except Exception as e:
        print(f"[通知错误] 安全事件通知失败: {e}")


def get_access_logs(user_id):
    """获取用户的访问日志"""
    conn = get_db()
    logs = conn.execute("""SELECT * FROM logs WHERE user_id = ?
                          ORDER BY created_at DESC LIMIT 100""", (user_id,)).fetchall()
    result = []
    for log in logs:
        item = dict(log)
        item['access_time'] = item.get('created_at', '')
        result.append(item)
    return result
