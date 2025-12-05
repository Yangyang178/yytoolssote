import os
import uuid
import json
import sqlite3
import smtplib
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory, jsonify, session
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from dotenv import load_dotenv

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

def ensure_dirs():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


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
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS verification_codes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        code TEXT NOT NULL,
                        purpose TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS files (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        stored_name TEXT NOT NULL,
                        path TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        dkfile TEXT,
                        project_name TEXT,
                        project_desc TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )''')
        conn.commit()
    finally:
        conn.close()


def migrate_json_to_db():
    old_json_file = DATA_DIR / "db.json"
    if old_json_file.exists():
        try:
            old_data = json.loads(old_json_file.read_text(encoding="utf-8"))
            conn = get_db()
            try:
                # 创建默认用户
                default_user_id = "default_user"
                conn.execute('''INSERT OR IGNORE INTO users (id, email, username)
                                VALUES (?, ?, ?)''', 
                            (default_user_id, "default@example.com", "默认用户"))
                
                for item in old_data.get("files", []):
                    conn.execute('''INSERT OR IGNORE INTO files (
                                    id, user_id, filename, stored_name, path, size, 
                                    dkfile, project_name, project_desc
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                (item["id"], default_user_id, item["filename"], item["stored_name"], 
                                 item["path"], item["size"], json.dumps(item.get("dkfile")), 
                                 item.get("project_name"), item.get("project_desc")))
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"迁移JSON数据失败: {e}")


def generate_verification_code():
    return ''.join(random.choices('0123456789', k=6))


def send_verification_email(email, code, purpose):
    if not all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM]):
        raise Exception("邮箱配置不完整")
    
    subject = """yytoolssite-aipro 验证码"""
    if purpose == "register":
        body = f"""您正在注册 yytoolssite-aipro 账号，您的验证码是：{code}\n
验证码有效期为 {CODE_EXPIRATION_MINUTES} 分钟，请尽快使用。"""
    else:
        body = f"""您正在登录 yytoolssite-aipro 账号，您的验证码是：{code}\n
验证码有效期为 {CODE_EXPIRATION_MINUTES} 分钟，请尽快使用。"""
    
    msg = MIMEMultipart()
    msg['From'] = SMTP_FROM
    msg['To'] = email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)


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
        return [{"id": row["id"], "filename": row["filename"], "stored_name": row["stored_name"],
                "path": row["path"], "size": row["size"], "dkfile": json.loads(row["dkfile"] if row["dkfile"] else "null"),
                "project_name": row["project_name"], "project_desc": row["project_desc"]}
                for row in rows]
    finally:
        conn.close()


def get_file_by_id(file_id, user_id):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?', (file_id, user_id)).fetchone()
        if row:
            return {"id": row["id"], "filename": row["filename"], "stored_name": row["stored_name"],
                    "path": row["path"], "size": row["size"], "dkfile": json.loads(row["dkfile"] if row["dkfile"] else "null"),
                    "project_name": row["project_name"], "project_desc": row["project_desc"]}
        return None
    finally:
        conn.close()


def add_file(item):
    conn = get_db()
    try:
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


def get_user_by_email(email):
    conn = get_db()
    try:
        row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if row:
            return {"id": row["id"], "email": row["email"], "username": row["username"]}
        return None
    finally:
        conn.close()


def add_user(user):
    conn = get_db()
    try:
        conn.execute('''INSERT INTO users (id, email, username)
                        VALUES (?, ?, ?)''', 
                    (user["id"], user["email"], user["username"]))
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
    init_db()
    migrate_json_to_db()
    files = get_all_files(session.get('user_id'))
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

@app.post("/upload")
@login_required
def upload():
    init_db()
    f = request.files.get("file")
    if not f or f.filename == "":
        flash("请选择文件")
        return redirect(url_for("index"))
    filename = f.filename
    local_id = uuid.uuid4().hex
    local_name = f"{local_id}__{filename}"
    dest = UPLOAD_DIR / local_name
    f.save(dest)
    dk_resp = None
    try:
        dk_resp = dkfile_upload(dest, filename, project_name=request.form.get("project_name"), description=request.form.get("project_desc"))
    except Exception as e:
        dk_resp = {"error": str(e)}
    project_name = request.form.get("project_name")
    project_desc = request.form.get("project_desc")
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
    }
    add_file(item)
    try:
        if isinstance(dk_resp, dict) and dk_resp.get("success"):
            url = (dk_resp.get("data") or {}).get("url")
            flash(f"已上传到 DKFile：{url or '成功'}")
        else:
            msg = dk_resp.get("message") if isinstance(dk_resp, dict) else None
            flash(f"DKFile 上传失败：{msg or '未知错误'}")
    except Exception:
        pass
    return redirect(url_for("index"))

@app.get("/files/<file_id>")
@login_required
def file_detail(file_id):
    init_db()
    found = get_file_by_id(file_id, session['user_id'])
    if not found:
        return render_template("detail.html", not_found=True, item=None)
    return render_template("detail.html", not_found=False, item=found)

@app.post("/files/<file_id>/delete")
@login_required
def file_delete(file_id):
    init_db()
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

@app.get("/download/<stored_name>")
@login_required
def download_local(stored_name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], stored_name, as_attachment=True)

@app.get("/api/files")
@login_required
def api_files():
    init_db()
    files = get_all_files(session['user_id'])
    return jsonify({"files": files})

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
    init_db()
    migrate_json_to_db()
    files = get_all_files(session['user_id'])
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
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        
        if get_user_by_email(email):
            return render_template('auth.html', mode='register', page_title='注册', error='该邮箱已被注册')
        
        try:
            code = generate_verification_code()
            send_verification_email(email, code, 'register')
            save_verification_code(email, code, 'register')
            return redirect(url_for('register', step='verify', email=email))
        except Exception as e:
            return render_template('auth.html', mode='register', page_title='注册', error=f'发送验证码失败：{str(e)}')
    
    return render_template('auth.html', mode='register', page_title='注册')


@app.route('/verify_register', methods=['POST'])
def verify_register():
    email = request.form['email']
    code = request.form['code']
    username = request.form.get('username', '')
    
    if not verify_code(email, code, 'register'):
        return render_template('auth.html', mode='register', page_title='注册', error='验证码无效或已过期', step='verify')
    
    if get_user_by_email(email):
        return render_template('auth.html', mode='register', page_title='注册', error='该邮箱已被注册')
    
    user_id = uuid.uuid4().hex
    add_user({'id': user_id, 'email': email, 'username': username})
    
    session['user_id'] = user_id
    session['email'] = email
    session['username'] = username
    
    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form['email']
        
        user = get_user_by_email(email)
        if not user:
            return render_template('auth.html', mode='login', page_title='登录', error='该邮箱未注册')
        
        try:
            code = generate_verification_code()
            send_verification_email(email, code, 'login')
            save_verification_code(email, code, 'login')
            return redirect(url_for('login', step='verify', email=email))
        except Exception as e:
            return render_template('auth.html', mode='login', page_title='登录', error=f'发送验证码失败：{str(e)}')
    
    return render_template('auth.html', mode='login', page_title='登录')


@app.route('/verify_login', methods=['POST'])
def verify_login():
    email = request.form['email']
    code = request.form['code']
    
    if not verify_code(email, code, 'login'):
        return render_template('auth.html', mode='login', page_title='登录', error='验证码无效或已过期', step='verify')
    
    user = get_user_by_email(email)
    if not user:
        return render_template('auth.html', mode='login', page_title='登录', error='该邮箱未注册')
    
    session['user_id'] = user['id']
    session['email'] = user['email']
    session['username'] = user['username']
    
    return redirect(url_for('index'))


@app.route('/user-center')
def user_center():
    init_db()
    if 'user_id' in session:
        files = get_all_files(session['user_id'])
        user = {
            'email': session.get('email'),
            'username': session.get('username')
        }
    else:
        files = []
        user = None
    return render_template('user_center.html', user=user, files=files)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.after_request
def add_cache_control(response):
    if request.path.endswith('.css') or request.path.endswith('.js'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


if __name__ == "__main__":
    app.secret_key = os.getenv("SECRET_KEY", "dev")
    app.debug = True
    init_db()
    migrate_json_to_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "9876")))
