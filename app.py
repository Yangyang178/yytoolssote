import os
import uuid
import json
import sqlite3
import smtplib
import random
import time
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory, jsonify, session
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# 计算文件的MD5哈希值
def calculate_file_hash(file_path):
    """计算文件的MD5哈希值"""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "db.sqlite"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

# 静态文件缓存配置
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = timedelta(days=30)  # 静态文件默认缓存30天

# 添加缓存控制头的中间件
@app.after_request
def add_cache_headers(response):
    # 为静态资源添加缓存头
    if request.path.startswith('/static/'):
        # 对于CSS、JS、图片等静态资源，设置较长的缓存时间
        if any(ext in request.path for ext in ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.json', '.woff', '.woff2', '.ttf', '.eot']):
            response.cache_control.max_age = 31536000  # 1年
            response.cache_control.public = True
            response.cache_control.immutable = True
        # 对于manifest.json和service-worker.js，设置较短的缓存时间
        elif '/static/manifest.json' in request.path or '/static/service-worker.js' in request.path:
            response.cache_control.max_age = 86400  # 1天
            response.cache_control.public = True
            response.cache_control.must_revalidate = True
    # 对于HTML页面，设置不缓存或短时间缓存
    elif request.path.endswith('.html') or '.' not in request.path:
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
    # 对于API响应，设置适当的缓存头
    elif request.path.startswith('/api/'):
        response.cache_control.max_age = 3600  # 1小时
        response.cache_control.public = True
        response.cache_control.must_revalidate = True
    return response

DKFILE_BASE = os.getenv("DKFILE_API_BASE", "http://dkfile.net/dkfile_api")
DKFILE_API_KEY = os.getenv("DKFILE_API_KEY")
DKFILE_AUTH_SCHEME = os.getenv("DKFILE_AUTH_SCHEME", "bearer")
DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 邮箱配置
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")

# 验证码配置
CODE_EXPIRATION_MINUTES = 15

# 密码复杂度正则表达式
PASSWORD_REGEX = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')

# 密码复杂度提示
PASSWORD_COMPLEXITY = "密码必须至少8个字符，包含大小写字母、数字和特殊字符"

def ensure_dirs():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

# 密码复杂度检查
def validate_password(password):
    """检查密码是否符合复杂度要求"""
    if not PASSWORD_REGEX.match(password):
        return False, PASSWORD_COMPLEXITY
    return True, "密码符合要求"



def get_db():
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn



def init_db():
    ensure_dirs()
    conn = get_db()
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        username TEXT NOT NULL,
                        password TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        role TEXT DEFAULT "user"
                    )''')
        
        # 检查并添加password字段到现有users表
        try:
            conn.execute('ALTER TABLE users ADD COLUMN password TEXT NOT NULL DEFAULT ""')
        except sqlite3.OperationalError:
            # 字段已经存在，跳过
            pass
        
        # 检查并添加role字段到现有users表
        try:
            conn.execute('ALTER TABLE users ADD COLUMN role TEXT DEFAULT "user"')
        except sqlite3.OperationalError:
            # 字段已经存在，跳过
            pass
        
        # 创建verification_codes表
        conn.execute('''CREATE TABLE IF NOT EXISTS verification_codes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        code TEXT NOT NULL,
                        purpose TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )''')
        
        # 创建files表
        conn.execute('''CREATE TABLE IF NOT EXISTS files (
                        id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        stored_name TEXT NOT NULL,
                        path TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        dkfile TEXT,
                        project_name TEXT,
                        project_desc TEXT,
                        folder_id TEXT DEFAULT NULL
                    )''')
        
        # 检查并添加folder_id字段到现有files表
        try:
            conn.execute('ALTER TABLE files ADD COLUMN folder_id TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            # 字段已经存在，跳过
            pass
        
        # 创建folders表
        conn.execute('''CREATE TABLE IF NOT EXISTS folders (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        purpose TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        parent_id TEXT DEFAULT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        FOREIGN KEY (parent_id) REFERENCES folders(id)
                    )''')
        
        # 检查并添加parent_id列（如果不存在）
        try:
            conn.execute('ALTER TABLE folders ADD COLUMN parent_id TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            # 字段已经存在，跳过
            pass
        
        # 检查并添加user_id列（如果不存在）
        try:
            conn.execute('ALTER TABLE files ADD COLUMN user_id TEXT DEFAULT "default_user"')
        except sqlite3.OperationalError:
            # 列已经存在，跳过
            pass
        
        # 创建access_logs表
        conn.execute('''CREATE TABLE IF NOT EXISTS access_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL,
                        user_id TEXT,
                        action TEXT NOT NULL,
                        ip_address TEXT,
                        user_agent TEXT,
                        access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (file_id) REFERENCES files (id),
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )''')
        
        # 创建操作日志表
        conn.execute('''CREATE TABLE IF NOT EXISTS operation_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        target_id TEXT,
                        target_type TEXT,
                        message TEXT NOT NULL,
                        details TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )''')
        
        # 检查并添加avatar字段到users表（如果不存在）
        try:
            conn.execute('ALTER TABLE users ADD COLUMN avatar TEXT')
        except sqlite3.OperationalError:
            # 字段已经存在，跳过
            pass
            
        # 创建likes表
        conn.execute('''CREATE TABLE IF NOT EXISTS likes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (file_id) REFERENCES files (id),
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        UNIQUE(file_id, user_id)
                    )''')
        
        # 创建favorites表
        conn.execute('''CREATE TABLE IF NOT EXISTS favorites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (file_id) REFERENCES files (id),
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        UNIQUE(file_id, user_id)
                    )''')
        
        # 创建文件分类表
        conn.execute('''CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        user_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        UNIQUE(name, user_id)
                    )''')
        
        # 创建文件标签表
        conn.execute('''CREATE TABLE IF NOT EXISTS tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        UNIQUE(name, user_id)
                    )''')
        
        # 创建文件分类关联表
        conn.execute('''CREATE TABLE IF NOT EXISTS file_categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL,
                        category_id INTEGER NOT NULL,
                        FOREIGN KEY (file_id) REFERENCES files (id),
                        FOREIGN KEY (category_id) REFERENCES categories (id),
                        UNIQUE(file_id, category_id)
                    )''')
        
        # 创建文件标签关联表
        conn.execute('''CREATE TABLE IF NOT EXISTS file_tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL,
                        tag_id INTEGER NOT NULL,
                        FOREIGN KEY (file_id) REFERENCES files (id),
                        FOREIGN KEY (tag_id) REFERENCES tags (id),
                        UNIQUE(file_id, tag_id)
                    )''')
        
        # 创建文件版本表
        conn.execute('''CREATE TABLE IF NOT EXISTS file_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL,
                        version_name TEXT NOT NULL,
                        version_number INTEGER NOT NULL,
                        filename TEXT NOT NULL,
                        stored_name TEXT NOT NULL,
                        path TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT NOT NULL,
                        comment TEXT,
                        FOREIGN KEY (file_id) REFERENCES files (id),
                        FOREIGN KEY (created_by) REFERENCES users (id)
                    )''')
        
        # 为files表添加created_at列
        try:
            conn.execute('ALTER TABLE files ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        except sqlite3.OperationalError:
            pass
        
        # 为files表添加preview_available列
        try:
            conn.execute('ALTER TABLE files ADD COLUMN preview_available BOOLEAN DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        # 为files表添加hash列，用于存储文件的MD5哈希值
        try:
            conn.execute('ALTER TABLE files ADD COLUMN hash TEXT')
        except sqlite3.OperationalError:
            pass
        
        # 创建AI生成内容表
        conn.execute('''CREATE TABLE IF NOT EXISTS ai_contents (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        ai_function TEXT NOT NULL,
                        prompt TEXT NOT NULL,
                        response TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )''')
        
        conn.commit()
    finally:
        conn.close()



def migrate_json_to_db():
    old_json_file = DATA_DIR / "db.json"
    if old_json_file.exists():
        try:
            # 读取并解析旧的JSON文件
            file_content = old_json_file.read_text(encoding="utf-8")
            old_data = json.loads(file_content)
            
            # 确保old_data是一个字典
            if not isinstance(old_data, dict):
                print("旧数据不是字典类型，跳过迁移")
                return
            
            # 创建默认用户
            default_user_id = "default_user"
            conn = get_db()
            try:
                # 跳过迁移，避免兼容性问题
                print("跳过JSON数据迁移")
                return
                
                # 检查files表是否有user_id列
                cursor = conn.execute("PRAGMA table_info(files)")
                columns = [row[1] for row in cursor.fetchall()]
                
                files_data = old_data.get("files", [])
                # 确保files_data是列表
                if not isinstance(files_data, list):
                    print(f"files数据不是列表类型，实际类型: {type(files_data)}")
                    files_data = []
                
                for item in files_data:
                    # 跳过非字典元素
                    if not isinstance(item, dict):
                        print(f"跳过非字典元素: {item}")
                        continue
                        
                    if "user_id" in columns:
                        # 如果有user_id列，包含它
                        conn.execute('''INSERT OR IGNORE INTO files (
                                        id, user_id, filename, stored_name, path, size, 
                                        dkfile, project_name, project_desc
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                    (item["id"], default_user_id, item["filename"], item["stored_name"], 
                                    item["path"], item["size"], json.dumps(item.get("dkfile")), 
                                    item.get("project_name"), item.get("project_desc")))
                    else:
                        # 如果没有user_id列，不包含它
                        conn.execute('''INSERT OR IGNORE INTO files (
                                        id, filename, stored_name, path, size, 
                                        dkfile, project_name, project_desc
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                                    (item["id"], item["filename"], item["stored_name"], 
                                    item["path"], item["size"], json.dumps(item.get("dkfile")), 
                                    item.get("project_name"), item.get("project_desc")))
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"迁移JSON数据失败: {e}")
            import traceback
            traceback.print_exc()



def generate_verification_code():
    return ''.join(random.choices('0123456789', k=6))



def send_verification_email(email, code, purpose):
    # 检查SMTP配置是否完整
    if not all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM]):
        print(f"SMTP配置不完整，无法发送邮件到 {email}")
        raise Exception("SMTP配置不完整，无法发送验证码邮件")
    
    subject = """yytoolssite-aipro 验证码"""
    if purpose == "register":
        body = f"""您正在注册 yytoolssite-aipro 账号，您的验证码是：{code}\n
验证码有效期为 {CODE_EXPIRATION_MINUTES} 分钟，请尽快使用。"""
    else:
        body = f"""您正在登录 yytoolssite-aipro 账号，您的验证码是：{code}\n
验证码有效期为 {CODE_EXPIRATION_MINUTES} 分钟，请尽快使用。"""
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = SMTP_FROM
    msg['To'] = email
    msg['Subject'] = subject
    
    try:
        # 尝试使用TLS连接
        print(f"正在发送验证码邮件到 {email}，用途：{purpose}，验证码：{code}")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.ehlo()  # 发送EHLO命令
        server.starttls()
        server.ehlo()  # 重新发送EHLO命令
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [email], msg.as_string())
        server.quit()
        print(f"验证码邮件发送成功到 {email}")
        return True, None
    except Exception as e:
        # 如果TLS失败，尝试SSL连接
        try:
            print(f"TLS连接失败，尝试SSL连接：{str(e)}")
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
            server.ehlo()  # 发送EHLO命令
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [email], msg.as_string())
            server.quit()
            print(f"验证码邮件发送成功到 {email}（使用SSL）")
            return True, None
        except Exception as ssl_error:
            # 两种连接方式都失败，抛出异常
            print(f"发送验证码邮件失败：{str(ssl_error)}")
            raise Exception(f"发送验证码邮件失败：{str(ssl_error)}")



def save_verification_code(email, code, purpose):
    expires_at = datetime.now() + timedelta(minutes=CODE_EXPIRATION_MINUTES)
    conn = get_db()
    try:
        conn.execute('''DELETE FROM verification_codes 
                        WHERE email = ? AND purpose = ?''', 
                    (email, purpose))
        conn.execute('''INSERT INTO verification_codes (email, code, purpose, expires_at)
                        VALUES (?, ?, ?, ?)''', 
                    (email, code, purpose, expires_at))
        conn.commit()
    finally:
        conn.close()



def verify_code(email, code, purpose):
    conn = get_db()
    try:
        row = conn.execute('''SELECT * FROM verification_codes 
                            WHERE email = ? AND code = ? AND purpose = ? 
                            AND expires_at > CURRENT_TIMESTAMP''', 
                        (email, code, purpose)).fetchone()
        if row:
            # 验证码有效，删除它
            conn.execute('''DELETE FROM verification_codes 
                            WHERE email = ? AND code = ? AND purpose = ?''', 
                        (email, code, purpose))
            conn.commit()
            return True
        return False
    finally:
        conn.close()


# 日志记录函数
def log_message(log_type='operation', log_level='INFO', message='', user_id=None, action='', target_id=None, target_type=None, details=None, request=None):
    # 记录到控制台，添加更多调试信息
    print(f"[DEBUG] 开始记录日志: log_type={log_type}, user_id={user_id}, user_id_type={type(user_id)}, action={action}")
    print(f"[{log_level}] {log_type}: {message} | User: {user_id} | Action: {action} | Target: {target_type}/{target_id} | Details: {details}")
    
    # 记录到数据库
    if log_type == 'operation':
        print(f"[DEBUG] log_type是operation")
        # 不检查user_id，即使为空也记录到数据库，以便调试
        print(f"[DEBUG] user_id值为: {user_id}, 类型: {type(user_id)}")
        conn = None
        try:
            # 确保数据库连接
            conn = get_db()
            print(f"[DEBUG] 获取数据库连接成功")
            
            # 获取本地时间
            from datetime import datetime
            local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 执行插入操作，指定created_at为本地时间
            cursor = conn.execute('''INSERT INTO operation_logs (user_id, action, target_id, target_type, message, details, created_at) 
                                   VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                               (user_id or 'unknown', action, target_id, target_type, message, details, local_time))
            conn.commit()
            print(f"[DEBUG] 日志插入数据库成功，影响行数: {cursor.rowcount}")
            
            # 立即查询刚刚插入的日志，验证是否成功
            last_log = conn.execute('SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 1').fetchone()
            if last_log:
                print(f"[DEBUG] 刚刚插入的日志: ID={last_log['id']}, UserID={last_log['user_id']}, Action={last_log['action']}, Message={last_log['message']}")
            
            # 查询该用户的所有日志
            if user_id:
                user_logs = conn.execute('SELECT * FROM operation_logs WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
                print(f"[DEBUG] 用户 {user_id} 的日志数量: {len(user_logs)}")
        except Exception as e:
            print(f"[ERROR] 记录日志到数据库失败: {str(e)}")
            import traceback
            traceback.print_exc()
            # 确保回滚
            if conn:
                try:
                    conn.rollback()
                    print(f"[DEBUG] 数据库回滚成功")
                except Exception as rollback_e:
                    print(f"[ERROR] 数据库回滚失败: {str(rollback_e)}")
        finally:
            # 确保关闭连接
            if conn:
                try:
                    conn.close()
                    print(f"[DEBUG] 关闭数据库连接成功")
                except Exception as close_e:
                    print(f"[ERROR] 关闭数据库连接失败: {str(close_e)}")
    else:
        print(f"[DEBUG] 不满足日志插入条件: log_type={log_type}, user_id={user_id}")


# 登录尝试日志
def log_login_attempt(email, success, request):
    # 简化的登录尝试记录
    print(f"[INFO] Login Attempt: Email: {email} | Success: {success} | IP: {request.remote_addr}")


# 页面错误响应
def page_error_response(redirect_url, message, code=404):
    # 简化的页面错误响应
    flash(message)
    return redirect(url_for(redirect_url))


# API响应格式化
def api_response(success=True, message='', data=None, code=200):
    # 统一的API响应格式
    response = {
        'success': success,
        'message': message
    }
    if data:
        response['data'] = data
    return jsonify(response), code

def get_all_files(user_id=None):
    conn = get_db()
    try:
        if user_id:
            rows = conn.execute('SELECT * FROM files WHERE user_id = ? AND (folder_id IS NULL OR folder_id = "") ORDER BY id DESC', (user_id,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM files WHERE folder_id IS NULL OR folder_id = "" ORDER BY id DESC').fetchall()
        
        result = []
        for row in rows:
            file_id = row["id"]
            # 获取点赞数和收藏数
            like_count = conn.execute('SELECT COUNT(*) as count FROM likes WHERE file_id = ?', (file_id,)).fetchone()['count']
            favorite_count = conn.execute('SELECT COUNT(*) as count FROM favorites WHERE file_id = ?', (file_id,)).fetchone()['count']
            
            # 获取文件分类
            categories = []
            category_rows = conn.execute('''SELECT c.* FROM categories c 
                                           JOIN file_categories fc ON c.id = fc.category_id 
                                           WHERE fc.file_id = ?''', (file_id,)).fetchall()
            for category_row in category_rows:
                categories.append({
                    "id": category_row["id"],
                    "name": category_row["name"],
                    "description": category_row["description"]
                })
            
            # 获取文件标签
            tags = []
            tag_rows = conn.execute('''SELECT t.* FROM tags t 
                                     JOIN file_tags ft ON t.id = ft.tag_id 
                                     WHERE ft.file_id = ?''', (file_id,)).fetchall()
            for tag_row in tag_rows:
                tags.append({
                    "id": tag_row["id"],
                    "name": tag_row["name"]
                })
            
            # 检查 created_at 字段是否存在并转换时区
            created_at = row["created_at"] if "created_at" in row.keys() else ""
            if created_at:
                # 将UTC时间转换为本地时间（Asia/Shanghai）
                try:
                    # 解析ISO格式的时间字符串
                    utc_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    # 转换为东八区时间
                    local_dt = utc_dt + timedelta(hours=8)
                    created_at = local_dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    # 如果解析失败，保持原格式
                    pass
            result.append({
                "id": file_id, 
                "filename": row["filename"], 
                "stored_name": row["stored_name"],
                "path": row["path"], 
                "size": row["size"], 
                "dkfile": json.loads(row["dkfile"] if row["dkfile"] else "{}"),
                "project_name": row["project_name"], 
                "project_desc": row["project_desc"],
                "like_count": like_count,
                "favorite_count": favorite_count,
                "categories": categories,
                "tags": tags,
                "created_at": created_at
            })
        return result
    finally:
        conn.close()



def get_file_by_id(file_id, user_id=None, check_owner=True):
    conn = get_db()
    try:
        if check_owner and user_id:
            row = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, user_id)).fetchone()
        else:
            row = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
        if row:
            # 获取点赞数和收藏数
            like_count = conn.execute('SELECT COUNT(*) as count FROM likes WHERE file_id = ?', (file_id,)).fetchone()['count']
            favorite_count = conn.execute('SELECT COUNT(*) as count FROM favorites WHERE file_id = ?', (file_id,)).fetchone()['count']
            
            # 获取文件分类
            categories = []
            category_rows = conn.execute('''SELECT c.* FROM categories c 
                                           JOIN file_categories fc ON c.id = fc.category_id 
                                           WHERE fc.file_id = ?''', (file_id,)).fetchall()
            for category_row in category_rows:
                categories.append({
                    "id": category_row["id"],
                    "name": category_row["name"],
                    "description": category_row["description"]
                })
            
            # 获取文件标签
            tags = []
            tag_rows = conn.execute('''SELECT t.* FROM tags t 
                                     JOIN file_tags ft ON t.id = ft.tag_id 
                                     WHERE ft.file_id = ?''', (file_id,)).fetchall()
            for tag_row in tag_rows:
                tags.append({
                    "id": tag_row["id"],
                    "name": tag_row["name"]
                })
            
            # 检查 created_at 字段是否存在并转换时区
            created_at = row["created_at"] if "created_at" in row.keys() else ""
            if created_at:
                # 将UTC时间转换为本地时间（Asia/Shanghai）
                try:
                    # 解析ISO格式的时间字符串
                    utc_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    # 转换为东八区时间
                    local_dt = utc_dt + timedelta(hours=8)
                    created_at = local_dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    # 如果解析失败，保持原格式
                    pass
            return {
                "id": row["id"], 
                "filename": row["filename"], 
                "stored_name": row["stored_name"],
                "path": row["path"], 
                "size": row["size"], 
                "dkfile": json.loads(row["dkfile"] if row["dkfile"] else "{}"),
                "project_name": row["project_name"], 
                "project_desc": row["project_desc"],
                "user_id": row["user_id"],
                "like_count": like_count,
                "favorite_count": favorite_count,
                "categories": categories,
                "tags": tags,
                "created_at": created_at
            }
        return None
    finally:
        conn.close()



def ensure_categories_exist():
    """确保系统中存在所需的分类"""
    conn = get_db()
    try:
        # 定义所需的分类
        required_categories = [
            {"name": "图片处理", "description": "图片编辑、处理相关工具"},
            {"name": "娱乐游戏", "description": "游戏、娱乐相关工具"},
            {"name": "通用工具", "description": "通用型工具"},
            {"name": "生活工具", "description": "生活相关工具"},
            {"name": "文件处理", "description": "文件编辑、转换相关工具"},
            {"name": "开发工具", "description": "编程、开发相关工具"}
        ]
        
        # 获取现有的分类
        existing_categories = conn.execute('SELECT name FROM categories WHERE user_id = ?', ('default_user',)).fetchall()
        existing_names = {row[0] for row in existing_categories}
        
        # 添加缺失的分类
        for category in required_categories:
            if category["name"] not in existing_names:
                try:
                    conn.execute('''INSERT INTO categories (name, description, user_id) 
                                VALUES (?, ?, ?)''', 
                                (category["name"], category["description"], "default_user"))
                except sqlite3.IntegrityError:
                    # 分类已存在，跳过
                    pass
        conn.commit()
    finally:
        conn.close()



def get_category_id(category_name):
    """根据分类名称获取分类ID"""
    conn = get_db()
    try:
        result = conn.execute('SELECT id FROM categories WHERE name = ? AND user_id = ?', 
                           (category_name, "default_user")).fetchone()
        return result[0] if result else None
    finally:
        conn.close()



def auto_categorize_file(file_info):
    """根据文件信息自动分类"""
    # 确保分类存在
    ensure_categories_exist()
    
    # 提取文件信息
    filename = file_info.get("filename", "").lower()
    project_name = file_info.get("project_name", "").lower()
    project_desc = file_info.get("project_desc", "").lower()
    
    # 合并所有文本信息
    all_text = f"{filename} {project_name} {project_desc}"
    
    # 优化后的分类关键词映射，增加更多娱乐游戏相关关键词
    # 调整顺序：优先匹配更具体的类别
    category_keywords = {
        "图片处理": ["图片", "图像处理", "去水印", "滤镜", "裁剪", "修图", "美颜", "相册", "照片", "图像", "美化"],
        "娱乐游戏": ["游戏", "娱乐", "休闲", "有趣", "好玩", "粒子", "流体", "模拟", "动画", 
                     "万花筒", "小游戏", "互动", "交互式", "视觉", "效果", "创意", "彩色", 
                     "绘图", "画板", "光影", "娱乐", "休闲", "趣味"],
        "生活工具": ["生活", "日常", "健康", "饮食", "出行", "天气", "日历", "记账", "工具"],
        "文件处理": ["文件", "文档", "转换", "格式", "编辑", "压缩", "解压", "pdf", "word", "excel"],
        "通用工具": ["工具", "助手", "管理", "系统", "服务", "平台", "助手", "工具集"],
        "开发工具": ["开发", "编程", "代码", "编辑器", "调试", "字体", "配色", "设计"],
        # 注意：html, css, js等技术关键词不再作为开发工具的唯一判断依据
    }
    
    # 匹配分类 - 优先匹配更具体的类别
    for category_name, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in all_text:
                return category_name
    
    # 特殊处理：如果包含技术关键词但也包含娱乐元素，优先归类为娱乐游戏
    tech_keywords = ["html", "css", "js", "javascript", "web", "网页"]
    has_tech = any(tech in all_text for tech in tech_keywords)
    
    # 检查是否有娱乐相关内容
    entertainment_keywords = ["游戏", "娱乐", "休闲", "有趣", "好玩", "互动", "动画", "视觉", "效果"]
    has_entertainment = any(ent in all_text for ent in entertainment_keywords)
    
    if has_tech and has_entertainment:
        return "娱乐游戏"
    elif has_tech:
        return "开发工具"
    
    # 默认分类
    return "通用工具"



def add_file(item):
    conn = get_db()
    try:
        # 确保所需分类存在
        ensure_categories_exist()
        
        # 检查files表的列
        cursor = conn.execute("PRAGMA table_info(files)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # 准备插入语句
        if "created_at" in columns and "hash" in columns:
            # 如果有created_at和hash列
            conn.execute('''INSERT INTO files (
                            id, user_id, filename, stored_name, path, size, 
                            dkfile, project_name, project_desc, folder_id, created_at, hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)''', 
                        (item["id"], item["user_id"], item["filename"], item["stored_name"], 
                        item["path"], item["size"], json.dumps(item.get("dkfile")), 
                        item.get("project_name"), item.get("project_desc"), item.get("folder_id"), item.get("hash")))
        elif "created_at" in columns:
            # 如果只有created_at列
            conn.execute('''INSERT INTO files (
                            id, user_id, filename, stored_name, path, size, 
                            dkfile, project_name, project_desc, folder_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                        (item["id"], item["user_id"], item["filename"], item["stored_name"], 
                        item["path"], item["size"], json.dumps(item.get("dkfile")), 
                        item.get("project_name"), item.get("project_desc"), item.get("folder_id")))
        elif "hash" in columns:
            # 如果只有hash列
            conn.execute('''INSERT INTO files (
                            id, user_id, filename, stored_name, path, size, 
                            dkfile, project_name, project_desc, folder_id, hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                        (item["id"], item["user_id"], item["filename"], item["stored_name"], 
                        item["path"], item["size"], json.dumps(item.get("dkfile")), 
                        item.get("project_name"), item.get("project_desc"), item.get("folder_id"), item.get("hash")))
        else:
            # 如果都没有
            conn.execute('''INSERT INTO files (
                            id, user_id, filename, stored_name, path, size, 
                            dkfile, project_name, project_desc, folder_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                        (item["id"], item["user_id"], item["filename"], item["stored_name"], 
                        item["path"], item["size"], json.dumps(item.get("dkfile")), 
                        item.get("project_name"), item.get("project_desc"), item.get("folder_id")))
        
        # 自动分类并添加到文件分类关联表
        category_name = auto_categorize_file(item)
        category_id = get_category_id(category_name)
        if category_id:
            conn.execute('''INSERT INTO file_categories (file_id, category_id) 
                        VALUES (?, ?)''', 
                        (item["id"], category_id))
        
        conn.commit()
    finally:
        conn.close()



def delete_file(file_id, user_id):
    conn = get_db()
    try:
        conn.execute('DELETE FROM files WHERE id = ? AND user_id = ?', (file_id, user_id))
        conn.commit()
    finally:
        conn.close()



def log_access(file_id, action, request):
    conn = get_db()
    try:
        user_id = session.get('user_id')
        ip_address = request.remote_addr
        user_agent = request.user_agent.string
        conn.execute('''INSERT INTO access_logs (file_id, user_id, action, ip_address, user_agent)
                        VALUES (?, ?, ?, ?, ?)''', 
                    (file_id, user_id, action, ip_address, user_agent))
        conn.commit()
    finally:
        conn.close()


def cleanup_old_logs():
    """清理超过一周的访问记录和操作日志"""
    conn = get_db()
    try:
        # 清理超过一周的访问记录
        conn.execute('''DELETE FROM access_logs 
                        WHERE access_time < datetime('now', '-7 days')''')
        
        # 清理超过一周的操作日志
        conn.execute('''DELETE FROM operation_logs 
                        WHERE created_at < datetime('now', '-7 days')''')
        
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if row:
            # 直接使用索引访问字段，避免字典键访问问题
            role = "user"  # 默认值
            if len(row) > 6:  # role字段在索引6位置
                role = row[6]
            return {
                "id": row[0], 
                "email": row[1], 
                "username": row[2], 
                "avatar": row[4] if len(row) > 4 and row[4] else "",
                "role": role
            }
        return None
    finally:
        conn.close()



def get_access_logs(user_id):
    conn = get_db()
    try:
        rows = conn.execute('''SELECT al.*, f.filename 
                           FROM access_logs al 
                           JOIN files f ON al.file_id = f.id 
                           WHERE f.user_id = ? 
                           ORDER BY al.access_time DESC''', 
                          (user_id,)).fetchall()
        return [{
            "id": row["id"], 
            "file_id": row["file_id"], 
            "filename": row["filename"],
            "action": row["action"], 
            "ip_address": row["ip_address"],
            "user_agent": row["user_agent"], 
            "access_time": row["access_time"]
        }
                for row in rows]
    finally:
        conn.close()



# 点赞相关函数
def toggle_like(file_id, user_id):
    """切换文件的点赞状态"""
    conn = get_db()
    try:
        # 检查是否已经点赞
        row = conn.execute('SELECT id FROM likes WHERE file_id = ? AND user_id = ?', 
                          (file_id, user_id)).fetchone()
        if row:
            # 已经点赞，取消点赞
            conn.execute('DELETE FROM likes WHERE file_id = ? AND user_id = ?', 
                        (file_id, user_id))
            liked = False
        else:
            # 未点赞，添加点赞
            conn.execute('INSERT INTO likes (file_id, user_id) VALUES (?, ?)', 
                        (file_id, user_id))
            liked = True
        conn.commit()
        
        # 获取最新点赞数
        count_row = conn.execute('SELECT COUNT(*) as count FROM likes WHERE file_id = ?', 
                               (file_id,)).fetchone()
        count = count_row['count']
        
        return liked, count
    finally:
        conn.close()



def get_like_count(file_id):
    """获取文件的点赞数量"""
    conn = get_db()
    try:
        row = conn.execute('SELECT COUNT(*) as count FROM likes WHERE file_id = ?', 
                          (file_id,)).fetchone()
        return row['count']
    finally:
        conn.close()



def is_liked(file_id, user_id):
    """检查用户是否已经点赞该文件"""
    conn = get_db()
    try:
        row = conn.execute('SELECT id FROM likes WHERE file_id = ? AND user_id = ?', 
                          (file_id, user_id)).fetchone()
        return row is not None
    finally:
        conn.close()



# 收藏相关函数
def toggle_favorite(file_id, user_id):
    """切换文件的收藏状态"""
    conn = get_db()
    try:
        # 检查是否已经收藏
        row = conn.execute('SELECT id FROM favorites WHERE file_id = ? AND user_id = ?', 
                          (file_id, user_id)).fetchone()
        if row:
            # 已经收藏，取消收藏
            conn.execute('DELETE FROM favorites WHERE file_id = ? AND user_id = ?', 
                        (file_id, user_id))
            favorited = False
        else:
            # 未收藏，添加收藏
            conn.execute('INSERT INTO favorites (file_id, user_id) VALUES (?, ?)', 
                        (file_id, user_id))
            favorited = True
        conn.commit()
        
        # 获取最新收藏数
        count_row = conn.execute('SELECT COUNT(*) as count FROM favorites WHERE file_id = ?', 
                               (file_id,)).fetchone()
        count = count_row['count']
        
        return favorited, count
    finally:
        conn.close()



def get_favorite_count(file_id):
    """获取文件的收藏数量"""
    conn = get_db()
    try:
        row = conn.execute('SELECT COUNT(*) as count FROM favorites WHERE file_id = ?', 
                          (file_id,)).fetchone()
        return row['count']
    finally:
        conn.close()



def is_favorited(file_id, user_id):
    """检查用户是否已经收藏该文件"""
    conn = get_db()
    try:
        row = conn.execute('SELECT id FROM favorites WHERE file_id = ? AND user_id = ?', 
                          (file_id, user_id)).fetchone()
        return row is not None
    finally:
        conn.close()



def get_favorite_files(user_id):
    """获取用户收藏的文件列表，只返回HTML文件且排除项目文件夹中的文件"""
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT f.* 
            FROM files f 
            JOIN favorites fav ON f.id = fav.file_id 
            WHERE fav.user_id = ? 
            AND f.filename LIKE ? 
            AND (f.folder_id IS NULL OR f.folder_id = "") 
            ORDER BY fav.created_at DESC
        ''', (user_id, '%.html')).fetchall()
        
        result = []
        for row in rows:
            file_id = row["id"]
            # 获取点赞数和收藏数
            like_count = conn.execute('SELECT COUNT(*) as count FROM likes WHERE file_id = ?', (file_id,)).fetchone()['count']
            favorite_count = conn.execute('SELECT COUNT(*) as count FROM favorites WHERE file_id = ?', (file_id,)).fetchone()['count']
            
            # 获取文件分类
            categories = []
            category_rows = conn.execute('''SELECT c.* FROM categories c 
                                           JOIN file_categories fc ON c.id = fc.category_id 
                                           WHERE fc.file_id = ?''', (file_id,)).fetchall()
            for category_row in category_rows:
                categories.append({
                    "id": category_row["id"],
                    "name": category_row["name"],
                    "description": category_row["description"]
                })
            
            # 获取文件标签
            tags = []
            tag_rows = conn.execute('''SELECT t.* FROM tags t 
                                     JOIN file_tags ft ON t.id = ft.tag_id 
                                     WHERE ft.file_id = ?''', (file_id,)).fetchall()
            for tag_row in tag_rows:
                tags.append({
                    "id": tag_row["id"],
                    "name": tag_row["name"]
                })
            
            # 检查 created_at 字段是否存在
            created_at = row["created_at"] if "created_at" in row.keys() else ""
            result.append({
                "id": file_id, 
                "filename": row["filename"], 
                "stored_name": row["stored_name"],
                "path": row["path"], 
                "size": row["size"], 
                "dkfile": json.loads(row["dkfile"] if row["dkfile"] else "{}"),
                "project_name": row["project_name"], 
                "project_desc": row["project_desc"],
                "like_count": like_count,
                "favorite_count": favorite_count,
                "categories": categories,
                "tags": tags,
                "created_at": row["created_at"] if "created_at" in row else ""
            })
        return result
    finally:
        conn.close()



def add_user(user):
    conn = get_db()
    try:
        conn.execute('''INSERT INTO users (id, email, username, password)
                        VALUES (?, ?, ?, ?)''', 
                    (user["id"], user["email"], user["username"], user["password"]))
        conn.commit()
    finally:
        conn.close()



def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function



def dkfile_headers():
    h = {"Accept": "application/json"}
    if DKFILE_API_KEY:
        if (DKFILE_AUTH_SCHEME or "").lower() == "header":
            h["X-API-KEY"] = DKFILE_API_KEY
        else:
            h["Authorization"] = f"Bearer {DKFILE_API_KEY}"
    return h

def deepseek_headers():
    h = {"Content-Type": "application/json"}
    if DEEPSEEK_API_KEY:
        h["Authorization"] = f"Bearer {DEEPSEEK_API_KEY}"
    return h

def dkfile_info():
    """获取dkfile服务信息"""
    if not DKFILE_API_KEY:
        raise Exception("DKFILE_API_KEY not configured")
    
    url = f"{DKFILE_BASE}/upload/info"
    r = requests.get(url, headers=dkfile_headers(), timeout=30)
    r.raise_for_status()
    return r.json()

def deepseek_chat(messages, model="deepseek-chat", temperature=0.5):
    # 检查是否配置了DEEPSEEK_API_KEY
    if not DEEPSEEK_API_KEY:
        raise Exception("DEEPSEEK_API_KEY not configured")
    
    url = f"{DEEPSEEK_BASE}/chat/completions"
    payload = {
        "model": model, 
        "messages": messages, 
        "stream": False,
        "temperature": float(temperature)
    }
    r = requests.post(url, headers=deepseek_headers(), json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

@app.get("/")
def index():
    # 首页只显示默认用户的文件，用户上传的文件只显示在用户中心
    files = get_all_files(user_id="default_user")
    remote_error = None
    info = None
    try:
        info = dkfile_info()
    except Exception as e:
        remote_error = str(e)
    remote_table = []
    for x in files:
        dk = x.get("dkfile") or {}
        d = dk.get("data") or {}
        if dk.get("success") and d:
            remote_table.append({
                "file_name": d.get("file_name") or x.get("filename"),
                "url": d.get("url"),
                "created_at": d.get("created_at"),
                "is_update": d.get("is_update"),
                "updated_at": d.get("updated_at"),
            })
    return render_template("index.html", files=files, remote_table=remote_table, remote_error=remote_error, dk_info=info, username=session.get('username'))



@app.get("/upload_page")
def upload_page():
    """上传发布页面"""
    return render_template("upload_page.html", username=session.get('username'))






@app.get("/ai_page")
@login_required
def ai_page():
    """AI对话页面"""
    # 获取用户保存的AI内容
    user_id = session.get('user_id')
    conn = get_db()
    saved_contents = []
    try:
        cursor = conn.cursor()
        cursor.execute('''SELECT id, ai_function, prompt, response, created_at 
                          FROM ai_contents 
                          WHERE user_id = ? 
                          ORDER BY created_at DESC''', (user_id,))
        rows = cursor.fetchall()
        saved_contents = [{
            'id': row[0],
            'ai_function': row[1],
            'prompt': row[2],
            'response': row[3],
            'created_at': row[4]
        } for row in rows]
    finally:
        conn.close()
    
    return render_template("ai_page.html", username=session.get('username'), saved_contents=saved_contents)

# 导入路由定义
from routes import *

if __name__ == "__main__":
    init_db()
    # 清理超过一周的日志记录
    cleanup_old_logs()
    app.run(debug=True, port=9876)
