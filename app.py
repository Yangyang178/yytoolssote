import os
import uuid
import json
from pathlib import Path
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory, jsonify
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "db.json"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

DKFILE_BASE = os.getenv("DKFILE_API_BASE", "http://dkfile.net/dkfile_api")
DKFILE_API_KEY = os.getenv("DKFILE_API_KEY")
DKFILE_AUTH_SCHEME = os.getenv("DKFILE_AUTH_SCHEME", "bearer")
DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

def ensure_dirs():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_FILE.exists():
        DB_FILE.write_text(json.dumps({"files": []}, ensure_ascii=False), encoding="utf-8")

def load_db():
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"files": []}

def save_db(data):
    DB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

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
    ensure_dirs()
    db = load_db()
    remote_error = None
    info = None
    try:
        info = dkfile_info()
    except Exception as e:
        remote_error = str(e)
    remote_table = []
    for x in db.get("files", []):
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
    return render_template("index.html", files=db["files"], remote_table=remote_table, remote_error=remote_error, dk_info=info)

@app.post("/upload")
def upload():
    ensure_dirs()
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
    db = load_db()
    project_name = request.form.get("project_name")
    project_desc = request.form.get("project_desc")
    item = {
        "id": local_id,
        "filename": filename,
        "stored_name": local_name,
        "path": str(dest),
        "size": dest.stat().st_size,
        "dkfile": dk_resp,
        "project_name": project_name,
        "project_desc": project_desc,
    }
    db["files"].insert(0, item)
    save_db(db)
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
def file_detail(file_id):
    db = load_db()
    found = next((x for x in db["files"] if x["id"] == file_id), None)
    if not found:
        return render_template("detail.html", not_found=True, item=None)
    return render_template("detail.html", not_found=False, item=found)

@app.post("/files/<file_id>/delete")
def file_delete(file_id):
    db = load_db()
    idx = next((i for i, x in enumerate(db["files"]) if x["id"] == file_id), None)
    if idx is None:
        return redirect(url_for("index"))
    item = db["files"][idx]
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
    del db["files"][idx]
    save_db(db)
    return redirect(url_for("index"))

@app.get("/download/<stored_name>")
def download_local(stored_name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], stored_name, as_attachment=True)

@app.get("/api/files")
def api_files():
    return jsonify(load_db())

@app.get("/dkfile/status")
def dk_status():
    try:
        info = dkfile_info()
        return jsonify({"ok": True, "info": info})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

@app.post("/ai")
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
    db = load_db()
    remote_error = None
    info = None
    try:
        info = dkfile_info()
    except Exception as e:
        remote_error = str(e)
    remote_table = []
    for x in db.get("files", []):
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
    return render_template("index.html", files=db["files"], remote_table=remote_table, remote_error=remote_error, dk_info=info, ai_output=ai_output, ai_error=ai_error)

if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "9876")))
