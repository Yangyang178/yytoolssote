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
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        # 检查并添加password字段到现有users表
        try:
            conn.execute('ALTER TABLE users ADD COLUMN password TEXT NOT NULL DEFAULT ""')
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
                        project_desc TEXT
                    )''')
        
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
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        user_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
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
    # 确保我们尝试发送邮件，不考虑开发模式
    if not all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM]):
        # SMTP配置不完整，抛出异常
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
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.ehlo()  # 发送EHLO命令
        server.starttls()
        server.ehlo()  # 重新发送EHLO命令
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [email], msg.as_string())
        server.quit()
        return True, None
    except Exception as e:
        # 如果TLS失败，尝试SSL连接
        try:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
            server.ehlo()  # 发送EHLO命令
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [email], msg.as_string())
            server.quit()
            return True, None
        except Exception as ssl_error:
            # 两种连接方式都失败，抛出异常
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

def get_all_files(user_id=None):
    conn = get_db()
    try:
        if user_id:
            rows = conn.execute('SELECT * FROM files WHERE user_id = ? ORDER BY id DESC', (user_id,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM files ORDER BY id DESC').fetchall()
        
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
                "created_at": row["created_at"] if "created_at" in row.keys() else ""
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
            
            # 检查 created_at 字段是否存在
            created_at = row["created_at"] if "created_at" in row.keys() else ""
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


def add_file(item):
    conn = get_db()
    try:
        # 检查files表的列
        cursor = conn.execute("PRAGMA table_info(files)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # 准备插入语句
        if "created_at" in columns and "hash" in columns:
            # 如果有created_at和hash列
            conn.execute('''INSERT INTO files (
                            id, user_id, filename, stored_name, path, size, 
                            dkfile, project_name, project_desc, created_at, hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)''', 
                        (item["id"], item["user_id"], item["filename"], item["stored_name"], 
                        item["path"], item["size"], json.dumps(item.get("dkfile")), 
                        item.get("project_name"), item.get("project_desc"), item.get("hash")))
        elif "created_at" in columns:
            # 如果只有created_at列
            conn.execute('''INSERT INTO files (
                            id, user_id, filename, stored_name, path, size, 
                            dkfile, project_name, project_desc, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                        (item["id"], item["user_id"], item["filename"], item["stored_name"], 
                        item["path"], item["size"], json.dumps(item.get("dkfile")), 
                        item.get("project_name"), item.get("project_desc")))
        elif "hash" in columns:
            # 如果只有hash列
            conn.execute('''INSERT INTO files (
                            id, user_id, filename, stored_name, path, size, 
                            dkfile, project_name, project_desc, hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                        (item["id"], item["user_id"], item["filename"], item["stored_name"], 
                        item["path"], item["size"], json.dumps(item.get("dkfile")), 
                        item.get("project_name"), item.get("project_desc"), item.get("hash")))
        else:
            # 如果都没有
            conn.execute('''INSERT INTO files (
                            id, user_id, filename, stored_name, path, size, 
                            dkfile, project_name, project_desc
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                        (item["id"], item["user_id"], item["filename"], item["stored_name"], 
                        item["path"], item["size"], json.dumps(item.get("dkfile")), 
                        item.get("project_name"), item.get("project_desc")))
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


def get_user_by_email(email):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if row:
            return {"id": row["id"], "email": row["email"], "username": row["username"], "avatar": row["avatar"] if "avatar" in row and row["avatar"] else ""}
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
    """获取用户收藏的文件列表"""
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT f.* 
            FROM files f 
            JOIN favorites fav ON f.id = fav.file_id 
            WHERE fav.user_id = ? 
            ORDER BY fav.created_at DESC
        ''', (user_id,)).fetchall()
        
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
            return redirect(url_for('login', next=request.url))
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

def deepseek_chat(messages, model="deepseek-chat"):
    # 检查是否配置了DEEPSEEK_API_KEY
    if not DEEPSEEK_API_KEY:
        raise Exception("DEEPSEEK_API_KEY not configured")
    
    url = f"{DEEPSEEK_BASE}/chat/completions"
    payload = {"model": model, "messages": messages, "stream": False}
    r = requests.post(url, headers=deepseek_headers(), json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def dkfile_upload(filepath, filename, project_name=None, description=None):
    url = f"{DKFILE_BASE}/upload"
    with open(filepath, "rb") as f:
        files = {"file": (filename, f)}
        data = {}
        if project_name:
            data["project_name"] = project_name
        if description:
            data["description"] = description
        r = requests.post(url, headers=dkfile_headers(), files=files, data=data, timeout=60)
    r.raise_for_status()
    return r.json()

def dkfile_info():
    url = f"{DKFILE_BASE}/upload/info"
    r = requests.get(url, headers=dkfile_headers(), timeout=30)
    r.raise_for_status()
    return r.json()

def dkfile_delete(file_id):
    url = f"{DKFILE_BASE}/files/{file_id}"
    r = requests.delete(url, headers=dkfile_headers(), timeout=30)
    r.raise_for_status()
    return r.json() if r.text else {"status": "ok"}

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


@app.get("/blog_page")
def blog_page():
    """博客页面"""
    return render_template("blog_page.html", username=session.get('username'))


@app.get("/ai_page")
def ai_page():
    """AI对话页面"""
    return render_template("ai_page.html", username=session.get('username'))

@app.post("/upload")
@login_required
def upload():
    files = request.files.getlist("file")
    if not files or len(files) == 0:
        flash("请选择文件")
        return redirect(url_for("upload_page"))
    
    # 先检查项目名称和项目描述是否填写
    project_name = request.form.get("project_name")
    project_desc = request.form.get("project_desc")
    if not project_name or not project_desc:
        flash("项目名称和项目描述不能为空")
        return redirect(url_for("upload_page"))
    
    # 服务器端文件验证
    # 允许的文件类型
    ALLOWED_MIME_PREFIXES = ['image/', 'application/', 'text/', 'video/', 'audio/']
    ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 
                         'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'json', 'xml',
                         'txt', 'csv', 'html', 'css', 'js', 'ts', 'py', 'java', 'c', 'cpp', 'php',
                         'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm',
                         'mp3', 'wav', 'ogg', 'wma', 'aac']
    MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
    
    uploaded_count = 0
    for f in files:
        if not f or f.filename == "":
            continue
        
        # 验证文件类型
        file_mimetype = f.mimetype
        file_extension = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
        is_allowed_type = any(file_mimetype.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES) or \
                         file_extension in ALLOWED_EXTENSIONS
        
        if not is_allowed_type:
            flash(f"不支持的文件类型：{f.filename}，请上传图片、文档、视频或音频文件")
            continue
        
        # 验证文件大小
        if f.content_length > MAX_FILE_SIZE:
            flash(f"文件大小超过限制：{f.filename}，单个文件不超过200MB")
            continue
        
        filename = f.filename
        local_id = uuid.uuid4().hex
        local_name = f"{local_id}__{filename}"
        dest = UPLOAD_DIR / local_name
        f.save(dest)
        
        # 计算文件哈希值
        file_hash = calculate_file_hash(dest)
        
        # 检查当前用户是否已经上传过相同的文件
        conn = get_db()
        try:
            # 先检查files表是否有hash列
            cursor = conn.execute("PRAGMA table_info(files)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if "hash" in columns:
                # 如果有hash列，使用hash检测重复
                existing_file = conn.execute('SELECT id FROM files WHERE user_id = ? AND hash = ?', 
                                          (session['user_id'], file_hash)).fetchone()
                if existing_file:
                    # 文件已存在，删除刚保存的临时文件并跳过上传
                    os.remove(dest)
                    flash(f"文件 '{filename}' 已存在，无需重复上传")
                    continue
            else:
                # 如果没有hash列，使用文件名和大小检测重复
                existing_file = conn.execute('SELECT id FROM files WHERE user_id = ? AND filename = ? AND size = ?', 
                                          (session['user_id'], filename, dest.stat().st_size)).fetchone()
                if existing_file:
                    # 文件已存在，删除刚保存的临时文件并跳过上传
                    os.remove(dest)
                    flash(f"文件 '{filename}' 已存在，无需重复上传")
                    continue
        finally:
            conn.close()
        
        dk_resp = None
        try:
            dk_resp = dkfile_upload(dest, filename, project_name=project_name, description=project_desc)
        except Exception as e:
            dk_resp = {"error": str(e)}
        item = {
            "id": local_id,
            "user_id": session['user_id'],
            "filename": filename,
            "stored_name": local_name,
            "path": str(dest),
            "size": dest.stat().st_size,
            "dkfile": dk_resp,
            "project_name": project_name,
            "project_desc": project_desc,
            "hash": file_hash  # 添加文件哈希值
        }
        add_file(item)
        uploaded_count += 1
    
    flash(f"成功上传 {uploaded_count} 个文件")
    return redirect(url_for("index"))

@app.get("/files/<file_id>")
@login_required
def file_detail(file_id):
    found = get_file_by_id(file_id, check_owner=False)
    if not found:
        return render_template("detail.html", not_found=True, item=None)
    # 记录访问日志
    log_access(file_id, 'view', request)
    return render_template("detail.html", not_found=False, item=found)

@app.post("/files/<file_id>/delete")
@login_required
def file_delete(file_id):
    item = get_file_by_id(file_id, session['user_id'])
    if not item:
        return redirect(url_for("index"))
    try:
        p = Path(item["path"])
        if p.exists():
            p.unlink()
    except Exception:
        pass
    try:
        dk = item.get("dkfile") or {}
        did = dk.get("id") or dk.get("file_id") or dk.get("data", {}).get("id")
        if did:
            dkfile_delete(did)
    except Exception:
        pass
    delete_file(file_id, session['user_id'])
    return redirect(url_for("index"))


@app.post("/file_replace")
@login_required
def file_replace():
    """替换文件"""
    file_id = request.form.get("file_id")
    if not file_id:
        flash("缺少文件ID")
        return redirect(url_for("user_center"))
    
    # 获取要替换的文件信息
    item = get_file_by_id(file_id, session['user_id'])
    if not item:
        flash("文件不存在或无权限访问")
        return redirect(url_for("user_center"))
    
    # 获取新文件
    new_file = request.files.get("file")
    if not new_file or new_file.filename == "":
        flash("请选择要上传的文件")
        return redirect(url_for("user_center"))
    
    try:
        # 保存新文件，覆盖旧文件
        local_name = item["stored_name"]
        dest = UPLOAD_DIR / local_name
        new_file.save(dest)
        
        # 计算新文件哈希值
        file_hash = calculate_file_hash(dest)
        
        # 检查当前用户是否已经上传过相同的文件
        conn = get_db()
        try:
            # 更新文件大小和哈希值
            conn.execute('''UPDATE files SET size = ?, hash = ? WHERE id = ?''',
                        (dest.stat().st_size, file_hash, file_id))
            conn.commit()
        finally:
            conn.close()
        
        # 更新远程文件（如果有）
        try:
            dk = item.get("dkfile") or {}
            did = dk.get("id") or dk.get("file_id") or dk.get("data", {}).get("id")
            if did:
                # 重新上传文件到远程存储
                project_name = item.get("project_name")
                project_desc = item.get("project_desc")
                dk_resp = dkfile_upload(dest, item["filename"], project_name=project_name, description=project_desc)
                
                # 更新数据库中的远程文件信息
                conn = get_db()
                try:
                    conn.execute('''UPDATE files SET dkfile = ? WHERE id = ?''',
                                (json.dumps(dk_resp), file_id))
                    conn.commit()
                finally:
                    conn.close()
        except Exception as remote_error:
            # 远程文件更新失败，不影响本地文件替换
            flash(f"本地文件替换成功，但远程文件更新失败: {str(remote_error)}")
        else:
            flash("文件替换成功")
        
        # 重定向到用户中心页面
        return redirect(url_for("user_center"))
    except Exception as e:
        # 处理错误
        flash(f"文件替换失败: {str(e)}")
        return redirect(url_for("user_center"))


@app.post("/api/files/batch-delete")
@login_required
def api_batch_delete():
    """批量删除文件"""
    file_ids = request.json.get("file_ids")
    if not file_ids or not isinstance(file_ids, list):
        return jsonify({"success": False, "message": "请提供要删除的文件ID列表"}), 400
    
    conn = get_db()
    try:
        deleted_count = 0
        for file_id in file_ids:
            # 获取文件信息
            item = get_file_by_id(file_id, session['user_id'])
            if not item:
                continue
            
            # 删除本地文件
            try:
                p = Path(item["path"])
                if p.exists():
                    p.unlink()
            except Exception:
                pass
            
            # 删除远程文件
            try:
                dk = item.get("dkfile") or {}
                did = dk.get("id") or dk.get("file_id") or dk.get("data", {}).get("id")
                if did:
                    dkfile_delete(did)
            except Exception:
                pass
            
            # 删除文件记录
            conn.execute('DELETE FROM files WHERE id = ? AND user_id = ?', (file_id, session['user_id']))
            deleted_count += 1
        
        conn.commit()
        return jsonify({"success": True, "message": f"成功删除 {deleted_count} 个文件", "deleted_count": deleted_count})
    finally:
        conn.close()





@app.post("/api/files/batch-download")
@login_required
def api_batch_download_files():
    """批量下载文件"""
    try:
        import zipfile
        import io
        
        file_ids = request.json.get('file_ids', [])
        if not isinstance(file_ids, list) or not file_ids:
            return jsonify({'success': False, 'message': '请提供有效的文件ID列表'}), 400
        
        conn = get_db()
        files_to_download = []
        
        try:
            # 验证文件是否存在且属于当前用户
            for file_id in file_ids:
                item = get_file_by_id(file_id, session['user_id'])
                if item:
                    files_to_download.append(item)
            
            if not files_to_download:
                return jsonify({'success': False, 'message': '没有可下载的文件'}), 404
            
            # 创建内存中的ZIP文件
            memory_file = io.BytesIO()
            with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_item in files_to_download:
                    file_path = file_item["path"]
                    filename = file_item["filename"]
                    zipf.write(file_path, filename)
            
            # 重置文件指针到开头
            memory_file.seek(0)
            
            conn.close()
            
            # 返回ZIP文件
            from flask import send_file
            return send_file(
                memory_file,
                mimetype='application/zip',
                as_attachment=True,
                download_name='files.zip'
            )
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': f'批量下载失败: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'请求处理失败: {str(e)}'}), 400
def batch_delete_files():
    """批量删除文件"""
    file_ids = request.json.get("file_ids")
    if not file_ids or not isinstance(file_ids, list):
        return jsonify({"success": False, "message": "请提供要删除的文件ID列表"}), 400
    
    deleted_count = 0
    conn = get_db()
    try:
        for file_id in file_ids:
            # 验证文件属于当前用户
            item = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, session['user_id'])).fetchone()
            if not item:
                continue
            
            # 删除本地文件
            try:
                p = Path(item["path"])
                if p.exists():
                    p.unlink()
            except Exception:
                pass
            
            # 删除远程文件
            try:
                dk = json.loads(item["dkfile"] if item["dkfile"] else "{}")
                did = dk.get("id") or dk.get("file_id") or dk.get("data", {}).get("id")
                if did:
                    dkfile_delete(did)
            except Exception:
                pass
            
            # 删除文件记录
            conn.execute('DELETE FROM files WHERE id = ? AND user_id = ?', (file_id, session['user_id']))
            deleted_count += 1
        
        conn.commit()
        return jsonify({"success": True, "message": f"成功删除 {deleted_count} 个文件"})
    finally:
        conn.close()

import zipfile
import io

@app.get("/download/<stored_name>")
@login_required
def download_local(stored_name):
    # 查找文件ID
    conn = get_db()
    try:
        row = conn.execute('SELECT id FROM files WHERE stored_name = ?', (stored_name,)).fetchone()
        if row:
            # 记录访问日志
            log_access(row['id'], 'download', request)
    finally:
        conn.close()
    return send_from_directory(app.config["UPLOAD_FOLDER"], stored_name, as_attachment=True)





@app.get("/open/<stored_name>")
@login_required
def open_local(stored_name):
    # 查找文件ID和信息
    conn = get_db()
    try:
        row = conn.execute('SELECT id, filename, stored_name, path FROM files WHERE stored_name = ?', (stored_name,)).fetchone()
        if row:
            # 记录访问日志
            log_access(row['id'], 'open', request)
            
            # 直接使用数据库中存储的完整路径
            file_path = row['path']
            
            # 首先检查文件是否存在
            if not os.path.exists(file_path):
                return "File not found", 404
            
            # 获取文件扩展名
            filename = row['filename']
            ext = ''
            if '.' in filename:
                ext = filename.rsplit('.', 1)[-1].lower()
            
            # 直接检测文件内容，确保正确识别HTML文件
            with open(file_path, 'rb') as f:
                first_bytes = f.read(100)
            
            # 强制检查HTML文件，不管扩展名是什么
            if first_bytes.startswith(b'<!DOCTYPE html') or first_bytes.startswith(b'<html'):
                ext = 'html'
            
            # 直接返回HTML文件，设置正确的MIME类型
            if ext in ['html', 'htm']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
            
            # 根据扩展名返回正确的MIME类型
            mime_types = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'bmp': 'image/bmp',
                'svg': 'image/svg+xml',
                'webp': 'image/webp',
                'txt': 'text/plain',
                'md': 'text/plain',
                'css': 'text/css',
                'js': 'application/javascript',
                'ts': 'text/typescript',
                'py': 'text/plain',
                'java': 'text/plain',
                'c': 'text/plain',
                'cpp': 'text/plain',
                'json': 'application/json',
                'xml': 'application/xml',
                'yaml': 'text/yaml',
                'yml': 'text/yaml',
                'pdf': 'application/pdf'
            }
            
            # 获取对应的MIME类型
            mimetype = mime_types.get(ext, None)
            
            if mimetype:
                # 如果能确定MIME类型，直接返回
                return send_from_directory(app.config["UPLOAD_FOLDER"], stored_name, as_attachment=False, mimetype=mimetype)
            else:
                # 对于无法确定类型的文件，作为附件下载
                return send_from_directory(app.config["UPLOAD_FOLDER"], stored_name, as_attachment=True)
    finally:
        conn.close()
    # 如果文件不存在，返回404
    return "File not found", 404

@app.get("/api/files")
@login_required
def api_files():
    files = get_all_files(session['user_id'])
    return jsonify({"files": files})


# 分类相关API
@app.get("/dkfile/status")
@login_required
def dk_status():
    try:
        info = dkfile_info()
        return jsonify({"ok": True, "info": info})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

@app.post("/ai")
@login_required
def ai():
    prompt = request.form.get("prompt")
    ai_error = None
    ai_output = None
    try:
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt or ""}]
        res = deepseek_chat(messages)
        ai_output = (res.get("choices") or [{}])[0].get("message", {}).get("content")
    except Exception as e:
        ai_error = str(e)
    # AI页面也只显示默认用户的文件，用户上传的文件只显示在用户中心
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
    return render_template("index.html", files=files, remote_table=remote_table, remote_error=remote_error, dk_info=info, ai_output=ai_output, ai_error=ai_error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    # 优先从表单中获取login_method，其次从URL参数中获取
    login_method = request.form.get('login_method', request.args.get('login_method', 'password'))
    
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        
        if login_method == 'password':
            # 密码注册流程
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if not password:
                return render_template('auth.html', mode='register', page_title='注册', error='请输入密码', login_method=login_method)
            
            # 检查密码复杂度
            is_valid, msg = validate_password(password)
            if not is_valid:
                return render_template('auth.html', mode='register', page_title='注册', error=msg, login_method=login_method)
            
            if password != confirm_password:
                return render_template('auth.html', mode='register', page_title='注册', error='两次输入的密码不一致', login_method=login_method)
            
            if get_user_by_email(email):
                return render_template('auth.html', mode='register', page_title='注册', error='该邮箱已被注册', login_method=login_method)
            
            # 直接注册，不发送验证码
            user_id = uuid.uuid4().hex
            hashed_password = generate_password_hash(password)
            add_user({
                'id': user_id, 
                'email': email, 
                'username': username,
                'password': hashed_password
            })
            
            session['user_id'] = user_id
            session['email'] = email
            session['username'] = username
            
            return redirect(url_for('index'))
        else:
            # 验证码注册流程（原流程）
            if get_user_by_email(email):
                return render_template('auth.html', mode='register', page_title='注册', error='该邮箱已被注册', login_method=login_method)
            
            try:
                code = generate_verification_code()
                success, message = send_verification_email(email, code, 'register')
                save_verification_code(email, code, 'register')
                return redirect(url_for('register', step='verify', email=email, debug_code=message if not success else None, login_method=login_method))
            except Exception as e:
                return render_template('auth.html', mode='register', page_title='注册', error=f'发送验证码失败：{str(e)}', login_method=login_method)
    
    return render_template('auth.html', mode='register', page_title='注册', login_method=login_method)


@app.route('/verify_register', methods=['POST'])
def verify_register():
    email = request.form['email']
    code = request.form['code']
    username = request.form.get('username', '')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    login_method = request.form.get('login_method', 'code')
    
    if not verify_code(email, code, 'register'):
        return render_template('auth.html', mode='register', page_title='注册', error='验证码无效或已过期', step='verify', login_method=login_method)
    
    if get_user_by_email(email):
        return render_template('auth.html', mode='register', page_title='注册', error='该邮箱已被注册', step='verify', login_method=login_method)
    
    user_id = uuid.uuid4().hex
    hashed_password = generate_password_hash(password) if password else ''
    
    add_user({
        'id': user_id, 
        'email': email, 
        'username': username,
        'password': hashed_password
    })
    
    session['user_id'] = user_id
    session['email'] = email
    session['username'] = username
    
    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    # 优先从表单中获取login_method，其次从URL参数中获取
    login_method = request.form.get('login_method', request.args.get('login_method', 'password'))
    step = request.args.get('step', 'enter')
    
    if request.method == 'POST':
        email = request.form['email']
        
        # 获取密码字段
        password = request.form.get('password')
        
        # 智能判断登录方式：如果有密码字段，执行密码登录；否则执行验证码登录
        if login_method == 'password' and password:
            # 密码登录流程
            user = get_user_by_email(email)
            if not user:
                return render_template('auth.html', mode='login', page_title='登录', error='该邮箱未注册', login_method=login_method)
            
            # 验证密码
            conn = get_db()
            try:
                row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                if not row:
                    return render_template('auth.html', mode='login', page_title='登录', error='该邮箱未注册', login_method=login_method)
                
                if not check_password_hash(row['password'], password):
                    return render_template('auth.html', mode='login', page_title='登录', error='密码错误', login_method=login_method)
                
                # 登录成功
                session['user_id'] = row['id']
                session['email'] = row['email']
                session['username'] = row['username']
                
                return redirect(url_for('index'))
            finally:
                conn.close()
        else:
            # 验证码登录流程
            user = get_user_by_email(email)
            if not user:
                return render_template('auth.html', mode='login', page_title='登录', error='该邮箱未注册', login_method=login_method)
            
            try:
                code = generate_verification_code()
                success, message = send_verification_email(email, code, 'login')
                save_verification_code(email, code, 'login')
                return redirect(url_for('login', step='verify', email=email, debug_code=message if not success else None, login_method='code'))
            except Exception as e:
                return render_template('auth.html', mode='login', page_title='登录', error=f'发送验证码失败：{str(e)}', login_method=login_method)
    
    return render_template('auth.html', mode='login', page_title='登录', login_method=login_method, step=step)


@app.route('/verify_login', methods=['POST'])
def verify_login():
    email = request.form['email']
    code = request.form['code']
    login_method = request.form.get('login_method', 'code')
    
    if not verify_code(email, code, 'login'):
        return render_template('auth.html', mode='login', page_title='登录', error='验证码无效或已过期', step='verify', login_method=login_method)
    
    user = get_user_by_email(email)
    if not user:
        return render_template('auth.html', mode='login', page_title='登录', error='该邮箱未注册', step='verify', login_method=login_method)
    
    session['user_id'] = user['id']
    session['email'] = user['email']
    session['username'] = user['username']
    
    return redirect(url_for('index'))


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """忘记密码页面"""
    if request.method == 'POST':
        email = request.form['email']
        user = get_user_by_email(email)
        
        if not user:
            return render_template('auth.html', mode='forgot_password', page_title='忘记密码', error='该邮箱未注册')
        
        try:
            # 发送重置密码验证码
            code = generate_verification_code()
            save_verification_code(email, code, 'reset_password')
            
            # 发送邮件
            msg = MIMEText(f"您正在重置 yytoolssite-aipro 账号密码，您的验证码是：{code}\n\n验证码有效期为 {CODE_EXPIRATION_MINUTES} 分钟，请尽快使用。", 'plain', 'utf-8')
            msg['From'] = SMTP_FROM
            msg['To'] = email
            msg['Subject'] = "yytoolssite-aipro 密码重置验证码"
            
            server = smtplib.SMTP(SMTP_HOST, 587, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [email], msg.as_string())
            server.quit()
            
            return redirect(url_for('reset_password', email=email))
        except Exception:
            return render_template('auth.html', mode='forgot_password', page_title='忘记密码', error='发送验证码失败，请稍后重试')
    
    return render_template('auth.html', mode='forgot_password', page_title='忘记密码')


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """重置密码页面"""
    email = request.args.get('email')
    
    if not email:
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        code = request.form['code']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # 验证验证码
        if not verify_code(email, code, 'reset_password'):
            return render_template('auth.html', mode='reset_password', page_title='重置密码', error='验证码无效或已过期', email=email)
        
        # 验证密码一致性
        if new_password != confirm_password:
            return render_template('auth.html', mode='reset_password', page_title='重置密码', error='两次输入的密码不一致', email=email)
        
        # 检查密码复杂度
        is_valid, msg = validate_password(new_password)
        if not is_valid:
            return render_template('auth.html', mode='reset_password', page_title='重置密码', error=msg, email=email)
        
        # 更新密码
        conn = get_db()
        try:
            hashed_password = generate_password_hash(new_password)
            conn.execute('UPDATE users SET password = ? WHERE email = ?', 
                        (hashed_password, email))
            conn.commit()
        finally:
            conn.close()
        
        return redirect(url_for('login', message='密码重置成功，请登录'))


@app.route('/user-center')
def user_center():
    if 'user_id' in session:
        # 用户中心只显示当前用户的文件列表
        files = get_all_files(session['user_id'])
        # 获取用户收藏的文件列表
        favorite_files = get_favorite_files(session['user_id'])
        access_logs = get_access_logs(session['user_id'])
        
        # 从数据库获取用户信息，包括头像
        conn = get_db()
        try:
            row = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
            if row:
                user = {
                    'id': row['id'],
                    'email': row['email'],
                    'username': row['username'],
                    'avatar': row['avatar'] if 'avatar' in row else None
                }
            else:
                user = {
                    'email': session.get('email'),
                    'username': session.get('username')
                }
        finally:
            conn.close()
    else:
        files = []
        favorite_files = []
        access_logs = []
        user = None
    return render_template('user_center.html', user=user, files=files, favorite_files=favorite_files, access_logs=access_logs)


@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    init_db()
    user_id = session['user_id']
    username = request.form.get('username')
    avatar = request.files.get('avatar')
    
    conn = get_db()
    try:
        if username:
            # 更新用户名
            conn.execute('UPDATE users SET username = ? WHERE id = ?', (username, user_id))
            # 更新session中的用户名
            session['username'] = username
        
        if avatar and avatar.filename:
            # 保存头像文件
            avatar_id = uuid.uuid4().hex
            avatar_ext = avatar.filename.rsplit('.', 1)[1].lower() if '.' in avatar.filename else 'png'
            avatar_name = f"{avatar_id}.{avatar_ext}"
            avatar_path = os.path.join('static', 'avatars')
            
            # 确保目录存在
            if not os.path.exists(avatar_path):
                os.makedirs(avatar_path)
            
            # 保存文件
            avatar.save(os.path.join(avatar_path, avatar_name))
            
            # 更新数据库中的头像路径
            conn.execute('UPDATE users SET avatar = ? WHERE id = ?', (avatar_name, user_id))
        
        conn.commit()
    finally:
        conn.close()
    
    return redirect(url_for('user_center'))


@app.route('/account-settings')
@login_required
def account_settings():
    """账户设置页面"""
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if row:
            user = {
                'id': row['id'],
                'email': row['email'],
                'username': row['username'],
                'avatar': row['avatar'] if 'avatar' in row else None
            }
        else:
            user = {
                'email': session.get('email'),
                'username': session.get('username')
            }
    finally:
        conn.close()
    return render_template('account_settings.html', user=user)


@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码"""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # 验证密码一致性
    if new_password != confirm_password:
        return render_template('account_settings.html', error='两次输入的密码不一致', user={'email': session.get('email'), 'username': session.get('username')})
    
    # 检查新密码复杂度
    is_valid, msg = validate_password(new_password)
    if not is_valid:
        return render_template('account_settings.html', error=msg, user={'email': session.get('email'), 'username': session.get('username')})
    
    # 验证当前密码是否正确
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not row:
            return render_template('account_settings.html', error='用户不存在', user={'email': session.get('email'), 'username': session.get('username')})
        
        if not check_password_hash(row['password'], current_password):
            return render_template('account_settings.html', error='当前密码错误', user={'email': session.get('email'), 'username': session.get('username')})
        
        # 更新密码
        hashed_password = generate_password_hash(new_password)
        conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, session['user_id']))
        conn.commit()
        return render_template('account_settings.html', success='密码修改成功', user={'email': session.get('email'), 'username': session.get('username')})
    finally:
        conn.close()


@app.route('/send-email-code', methods=['POST'])
@login_required
def send_email_code():
    """发送邮箱验证码"""
    new_email = request.json.get('new_email')
    
    if not new_email:
        return jsonify({'success': False, 'message': '请输入邮箱地址'}), 400
    
    # 验证邮箱是否已被使用
    conn = get_db()
    try:
        existing_user = conn.execute('SELECT * FROM users WHERE email = ? AND id != ?', 
                                   (new_email, session['user_id'])).fetchone()
        if existing_user:
            return jsonify({'success': False, 'message': '该邮箱已被使用'}), 400
    finally:
        conn.close()
    
    try:
        code = generate_verification_code()
        success, message = send_verification_email(new_email, code, 'change_email')
        save_verification_code(new_email, code, 'change_email')
        
        if success:
            return jsonify({'success': True, 'message': '验证码已发送'})
        else:
            return jsonify({'success': True, 'message': '验证码已发送（调试模式：' + message + '）'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'发送验证码失败：{str(e)}'}), 500


@app.route('/change-email', methods=['POST'])
@login_required
def change_email():
    """修改邮箱"""
    new_email = request.form.get('new_email')
    code = request.form.get('code')
    
    # 验证验证码
    if not code:
        return render_template('account_settings.html', error='请输入验证码', user={'email': session.get('email'), 'username': session.get('username')})
    
    if not verify_code(new_email, code, 'change_email'):
        return render_template('account_settings.html', error='验证码无效或已过期', user={'email': session.get('email'), 'username': session.get('username')})
    
    # 验证邮箱是否已被使用
    conn = get_db()
    try:
        existing_user = conn.execute('SELECT * FROM users WHERE email = ? AND id != ?', 
                                   (new_email, session['user_id'])).fetchone()
        if existing_user:
            return render_template('account_settings.html', error='该邮箱已被使用', user={'email': session.get('email'), 'username': session.get('username')})
        
        # 更新邮箱
        conn.execute('UPDATE users SET email = ? WHERE id = ?', 
                   (new_email, session['user_id']))
        conn.commit()
    finally:
        conn.close()
    
    # 更新session中的邮箱
    session['email'] = new_email
    return render_template('account_settings.html', success='邮箱修改成功', user={'email': new_email, 'username': session.get('username')})


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')


@app.route('/service-terms')
def service_terms():
    return render_template('service_terms.html')


@app.get('/api/categories')
@login_required
def api_get_categories():
    """获取用户的所有分类"""
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM categories WHERE user_id = ? ORDER BY name', (session['user_id'],)).fetchall()
        return jsonify({
            'success': True,
            'categories': [{
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'created_at': row['created_at']
            } for row in rows]
        })
    finally:
        conn.close()

@app.post('/api/categories')
@login_required
def api_create_category():
    """创建新分类"""
    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    
    if not name:
        return jsonify({'success': False, 'message': '分类名称不能为空'}), 400
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO categories (name, description, user_id) VALUES (?, ?, ?)',
                    (name, description, session['user_id']))
        conn.commit()
        return jsonify({'success': True, 'message': '分类创建成功'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '分类名称已存在'}), 400
    finally:
        conn.close()

@app.put('/api/categories/<int:category_id>')
@login_required
def api_update_category(category_id):
    """更新分类"""
    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    
    if not name:
        return jsonify({'success': False, 'message': '分类名称不能为空'}), 400
    
    conn = get_db()
    try:
        result = conn.execute('UPDATE categories SET name = ?, description = ? WHERE id = ? AND user_id = ?',
                            (name, description, category_id, session['user_id']))
        if result.rowcount == 0:
            return jsonify({'success': False, 'message': '分类不存在或无权限'}), 404
        conn.commit()
        return jsonify({'success': True, 'message': '分类更新成功'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '分类名称已存在'}), 400
    finally:
        conn.close()

@app.delete('/api/categories/<int:category_id>')
@login_required
def api_delete_category(category_id):
    """删除分类"""
    conn = get_db()
    try:
        # 先删除分类关联
        conn.execute('DELETE FROM file_categories WHERE category_id = ?', (category_id,))
        # 再删除分类
        result = conn.execute('DELETE FROM categories WHERE id = ? AND user_id = ?',
                            (category_id, session['user_id']))
        if result.rowcount == 0:
            return jsonify({'success': False, 'message': '分类不存在或无权限'}), 404
        conn.commit()
        return jsonify({'success': True, 'message': '分类删除成功'})
    finally:
        conn.close()

@app.post('/api/files/<file_id>/categories')
@login_required
def api_add_file_category(file_id):
    """为文件添加分类"""
    data = request.json
    category_id = data.get('category_id')
    
    if not category_id:
        return jsonify({'success': False, 'message': '分类ID不能为空'}), 400
    
    conn = get_db()
    try:
        # 检查文件是否存在且属于当前用户
        file = conn.execute('SELECT id FROM files WHERE id = ? AND user_id = ?',
                          (file_id, session['user_id'])).fetchone()
        if not file:
            return jsonify({'success': False, 'message': '文件不存在或无权限'}), 404
        
        # 检查分类是否存在且属于当前用户
        category = conn.execute('SELECT id FROM categories WHERE id = ? AND user_id = ?',
                              (category_id, session['user_id'])).fetchone()
        if not category:
            return jsonify({'success': False, 'message': '分类不存在或无权限'}), 404
        
        # 添加分类关联
        conn.execute('INSERT OR IGNORE INTO file_categories (file_id, category_id) VALUES (?, ?)',
                    (file_id, category_id))
        conn.commit()
        return jsonify({'success': True, 'message': '分类添加成功'})
    finally:
        conn.close()

@app.delete('/api/files/<file_id>/categories/<int:category_id>')
@login_required
def api_remove_file_category(file_id, category_id):
    """从文件中删除分类"""
    conn = get_db()
    try:
        # 检查文件是否存在且属于当前用户
        file = conn.execute('SELECT id FROM files WHERE id = ? AND user_id = ?',
                          (file_id, session['user_id'])).fetchone()
        if not file:
            return jsonify({'success': False, 'message': '文件不存在或无权限'}), 404
        
        # 删除分类关联
        conn.execute('DELETE FROM file_categories WHERE file_id = ? AND category_id = ?',
                    (file_id, category_id))
        conn.commit()
        return jsonify({'success': True, 'message': '分类删除成功'})
    finally:
        conn.close()


# 标签管理 API
@app.get('/api/tags')
@login_required
def api_get_tags():
    """获取用户的所有标签"""
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM tags WHERE user_id = ? ORDER BY name', (session['user_id'],)).fetchall()
        return jsonify({
            'success': True,
            'tags': [{
                'id': row['id'],
                'name': row['name'],
                'created_at': row['created_at']
            } for row in rows]
        })
    finally:
        conn.close()

@app.post('/api/tags')
@login_required
def api_create_tag():
    """创建新标签"""
    data = request.json
    name = data.get('name')
    
    if not name:
        return jsonify({'success': False, 'message': '标签名称不能为空'}), 400
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO tags (name, user_id) VALUES (?, ?)',
                    (name, session['user_id']))
        conn.commit()
        return jsonify({'success': True, 'message': '标签创建成功'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '标签名称已存在'}), 400
    finally:
        conn.close()

@app.put('/api/tags/<int:tag_id>')
@login_required
def api_update_tag(tag_id):
    """更新标签"""
    data = request.json
    name = data.get('name')
    
    if not name:
        return jsonify({'success': False, 'message': '标签名称不能为空'}), 400
    
    conn = get_db()
    try:
        result = conn.execute('UPDATE tags SET name = ? WHERE id = ? AND user_id = ?',
                            (name, tag_id, session['user_id']))
        if result.rowcount == 0:
            return jsonify({'success': False, 'message': '标签不存在或无权限'}), 404
        conn.commit()
        return jsonify({'success': True, 'message': '标签更新成功'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '标签名称已存在'}), 400
    finally:
        conn.close()

@app.delete('/api/tags/<int:tag_id>')
@login_required
def api_delete_tag(tag_id):
    """删除标签"""
    conn = get_db()
    try:
        # 先删除标签关联
        conn.execute('DELETE FROM file_tags WHERE tag_id = ?', (tag_id,))
        # 再删除标签
        result = conn.execute('DELETE FROM tags WHERE id = ? AND user_id = ?',
                            (tag_id, session['user_id']))
        if result.rowcount == 0:
            return jsonify({'success': False, 'message': '标签不存在或无权限'}), 404
        conn.commit()
        return jsonify({'success': True, 'message': '标签删除成功'})
    finally:
        conn.close()

@app.post('/api/files/<file_id>/tags')
@login_required
def api_add_file_tag(file_id):
    """为文件添加标签"""
    data = request.json
    tag_id = data.get('tag_id')
    
    if not tag_id:
        return jsonify({'success': False, 'message': '标签ID不能为空'}), 400
    
    conn = get_db()
    try:
        # 检查文件是否存在且属于当前用户
        file = conn.execute('SELECT id FROM files WHERE id = ? AND user_id = ?',
                          (file_id, session['user_id'])).fetchone()
        if not file:
            return jsonify({'success': False, 'message': '文件不存在或无权限'}), 404
        
        # 检查标签是否存在且属于当前用户
        tag = conn.execute('SELECT id FROM tags WHERE id = ? AND user_id = ?',
                              (tag_id, session['user_id'])).fetchone()
        if not tag:
            return jsonify({'success': False, 'message': '标签不存在或无权限'}), 404
        
        # 添加标签关联
        conn.execute('INSERT OR IGNORE INTO file_tags (file_id, tag_id) VALUES (?, ?)',
                    (file_id, tag_id))
        conn.commit()
        return jsonify({'success': True, 'message': '标签添加成功'})
    finally:
        conn.close()

@app.delete('/api/files/<file_id>/tags/<int:tag_id>')
@login_required
def api_remove_file_tag(file_id, tag_id):
    """从文件中删除标签"""
    conn = get_db()
    try:
        # 检查文件是否存在且属于当前用户
        file = conn.execute('SELECT id FROM files WHERE id = ? AND user_id = ?',
                          (file_id, session['user_id'])).fetchone()
        if not file:
            return jsonify({'success': False, 'message': '文件不存在或无权限'}), 404
        
        # 删除标签关联
        conn.execute('DELETE FROM file_tags WHERE file_id = ? AND tag_id = ?',
                    (file_id, tag_id))
        conn.commit()
        return jsonify({'success': True, 'message': '标签删除成功'})
    finally:
        conn.close()


# API路由：获取文件的点赞和收藏状态
@app.get('/api/files/<file_id>/interactions')
def api_get_interactions(file_id):
    """获取文件的点赞和收藏状态"""
    try:
        conn = get_db()
        # 获取点赞数和收藏数
        like_count = conn.execute('SELECT COUNT(*) as count FROM likes WHERE file_id = ?', (file_id,)).fetchone()['count']
        favorite_count = conn.execute('SELECT COUNT(*) as count FROM favorites WHERE file_id = ?', (file_id,)).fetchone()['count']
        
        # 检查当前用户是否已点赞和收藏
        user_id = session.get('user_id')
        is_liked = False
        is_favorited = False
        
        if user_id:
            # 只有登录用户才检查点赞和收藏状态
            liked_result = conn.execute('SELECT id FROM likes WHERE file_id = ? AND user_id = ?', (file_id, user_id)).fetchone()
            favorited_result = conn.execute('SELECT id FROM favorites WHERE file_id = ? AND user_id = ?', (file_id, user_id)).fetchone()
            is_liked = bool(liked_result)
            is_favorited = bool(favorited_result)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'like_count': like_count,
            'favorite_count': favorite_count,
            'is_liked': is_liked,
            'is_favorited': is_favorited
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.post('/api/files/<file_id>/like')
@login_required
def api_toggle_like(file_id):
    """切换文件点赞状态"""
    try:
        user_id = session['user_id']
        conn = get_db()
        
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
        conn.close()
        
        return jsonify({'success': True, 'liked': liked, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.post('/api/files/<file_id>/favorite')
@login_required
def api_toggle_favorite(file_id):
    """切换文件收藏状态"""
    try:
        user_id = session['user_id']
        conn = get_db()
        
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
        conn.close()
        
        return jsonify({'success': True, 'favorited': favorited, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 文件版本控制API



@app.get('/api/files/<file_id>/versions')
@login_required
def get_file_versions(file_id):
    """获取文件的所有版本"""
    conn = get_db()
    try:
        rows = conn.execute('''SELECT * FROM file_versions WHERE file_id = ? ORDER BY version_number DESC''', 
                          (file_id,)).fetchall()
        versions = [dict(row) for row in rows]
        return jsonify({'success': True, 'versions': versions})
    finally:
        conn.close()


@app.get('/api/files/<file_id>/versions/<int:version_id>')
@login_required
def get_file_version(file_id, version_id):
    """获取特定版本的文件"""
    conn = get_db()
    try:
        version = conn.execute('''SELECT * FROM file_versions WHERE id = ? AND file_id = ?''', 
                              (version_id, file_id)).fetchone()
        if not version:
            return jsonify({'success': False, 'message': '版本不存在'}), 404
        return jsonify({'success': True, 'version': dict(version)})
    finally:
        conn.close()


@app.post('/api/files/<file_id>/versions/<int:version_id>/restore')
@login_required
def restore_file_version(file_id, version_id):
    """恢复文件到指定版本"""
    conn = get_db()
    try:
        # 验证版本存在且属于当前用户
        version = conn.execute('''SELECT * FROM file_versions 
                               WHERE id = ? AND file_id = ?''', 
                             (version_id, file_id)).fetchone()
        
        file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, session['user_id'])).fetchone()
        
        if not version or not file:
            return jsonify({'success': False, 'message': '版本不存在或无权限操作'}), 404
        
        # 更新主文件为指定版本
        conn.execute('''UPDATE files SET filename = ?, stored_name = ?, path = ?, size = ? 
                        WHERE id = ?''', 
                    (version['filename'], version['stored_name'], version['path'], version['size'], file_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': '文件已恢复到指定版本'})
    finally:
        conn.close()


@app.delete('/api/files/<file_id>/versions/<int:version_id>')
@login_required
def delete_file_version(file_id, version_id):
    """删除文件版本"""
    conn = get_db()
    try:
        # 获取版本信息
        version = conn.execute('''SELECT * FROM file_versions 
                               WHERE id = ? AND file_id = ?''', 
                             (version_id, file_id)).fetchone()
        
        # 验证文件属于当前用户
        file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, session['user_id'])).fetchone()
        
        if not version or not file:
            return jsonify({'success': False, 'message': '版本不存在或无权限操作'}), 404
        
        # 删除版本记录
        conn.execute('DELETE FROM file_versions WHERE id = ?', (version_id,))
        
        # 删除版本文件
        if Path(version['path']).exists():
            Path(version['path']).unlink()
        
        conn.commit()
        return jsonify({'success': True, 'message': '文件版本已删除'})
    finally:
        conn.close()


@app.before_request
def force_https():
    # 在生产环境中强制使用HTTPS
    # Vercel已经自动处理HTTPS，所以这个中间件可能导致问题，暂时注释掉
    pass


@app.after_request
def add_security_headers(response):
    # 添加缓存控制头
    if request.path.endswith('.css') or request.path.endswith('.js'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    # 添加内容安全策略（CSP）头
    # 对于打开的文件和文件详情页面，允许内联脚本和样式，以便HTML文件中的功能可以正常使用
    if request.path.startswith('/open/') or request.path.startswith('/files/'):
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://beian.miit.gov.cn; font-src 'self' data:; connect-src 'self'; frame-src 'none'"
    else:
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://beian.miit.gov.cn; font-src 'self' data:; connect-src 'self'; frame-src 'none'"
    
    # 添加X-XSS-Protection头
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # 添加X-Frame-Options头
    response.headers['X-Frame-Options'] = 'DENY'
    
    # 添加X-Content-Type-Options头
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    return response


# 应用启动时执行一次数据库初始化
with app.app_context():
    init_db()
    migrate_json_to_db()


if __name__ == "__main__":
    app.secret_key = os.getenv("SECRET_KEY", "dev")
    # 根据环境变量决定是否开启DEBUG模式，生产环境默认为False
    app.debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "9876")))
