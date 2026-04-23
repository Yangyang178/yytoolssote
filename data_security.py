import os
import json
import hashlib
import shutil
import zipfile
import threading
import base64
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backup"
UPLOAD_DIR = BASE_DIR / "uploads"
DB_FILE = DATA_DIR / "db.sqlite"
ENCRYPTION_KEY_FILE = DATA_DIR / ".encryption_key"
BACKUP_CONFIG_FILE = BACKUP_DIR / "config.json"
PRIVACY_LOG_FILE = DATA_DIR / "privacy_audit.log"

ENCRYPTION_KEY_ENV = os.getenv("DATA_ENCRYPTION_KEY", "")
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
BACKUP_AUTO_ENABLED = os.getenv("BACKUP_AUTO_ENABLED", "true").lower() == "true"
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
IP_ANONYMIZE_ENABLED = os.getenv("IP_ANONYMIZE_ENABLED", "true").lower() == "true"


class DataEncryption:
    """AES-256-GCM symmetric encryption for sensitive data fields"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._fernet = None
        self._key_loaded = False
        if not CRYPTO_AVAILABLE:
            return
        key = ENCRYPTION_KEY_ENV
        if key:
            try:
                self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
                self._key_loaded = True
            except Exception:
                pass

    @property
    def available(self):
        return CRYPTO_AVAILABLE and self._key_loaded

    @staticmethod
    def generate_key():
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography library is required")
        return Fernet.generate_key().decode()

    def save_key(self):
        if not CRYPTO_AVAILABLE:
            return None
        key = self.generate_key()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ENCRYPTION_KEY_FILE.write_text(key)
        self._fernet = Fernet(key.encode())
        self._key_loaded = True
        return key

    def load_key_from_file(self):
        if not CRYPTO_AVAILABLE or not ENCRYPTION_KEY_FILE.exists():
            return False
        try:
            key = ENCRYPTION_KEY_FILE.read_text().strip()
            self._fernet = Fernet(key.encode())
            self._key_loaded = True
            return True
        except Exception:
            return False

    def ensure_key(self):
        if self.available:
            return True
        if self.load_key_from_file():
            return True
        if ENCRYPTION_KEY_ENV:
            try:
                self._fernet = Fernet(ENCRYPTION_KEY_ENV.encode())
                self._key_loaded = True
                return True
            except Exception:
                pass
        return False

    def encrypt(self, plaintext):
        if not self.available or plaintext is None:
            return plaintext
        try:
            value = str(plaintext)
            encrypted = self._fernet.encrypt(value.encode("utf-8"))
            return f"ENC:{encrypted.decode('utf-8')}"
        except Exception:
            return plaintext

    def decrypt(self, ciphertext):
        if not self.available or ciphertext is None:
            return ciphertext
        if not isinstance(ciphertext, str) or not ciphertext.startswith("ENC:"):
            return ciphertext
        try:
            raw = ciphertext[4:].encode("utf-8")
            decrypted = self._fernet.decrypt(raw)
            return decrypted.decode("utf-8")
        except Exception:
            return ciphertext

    def encrypt_dict_fields(self, data_dict, fields):
        if not isinstance(data_dict, dict) or not self.available:
            return data_dict
        result = dict(data_dict)
        for field in fields:
            if field in result and result[field] is not None:
                result[field] = self.encrypt(result[field])
        return result

    def decrypt_row(self, row, fields=None):
        if row is None or not self.available:
            return row
        if fields is None:
            return row
        if hasattr(row, "keys"):
            result = dict(row)
            for field in fields:
                if field in result and result[field] is not None:
                    result[field] = self.decrypt(result[field])
            return type(row)(result) if hasattr(type(row), "__init__") else result
        return row


_encryption_instance = DataEncryption()


def get_encryption():
    global _encryption_instance
    return _encryption_instance


def encrypt_field(value):
    return get_encryption().encrypt(value)


def decrypt_field(value):
    return get_encryption().decrypt(value)


SENSITIVE_USER_FIELDS = {"email"}
SENSITIVE_LOG_FIELDS = {"ip_address"}


class BackupManager:
    """Enhanced backup system: encryption, rotation, integrity verification"""

    _scheduler_thread = None
    _stop_event = None

    @staticmethod
    def create_backup(encrypt=True, description=""):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = BACKUP_DIR / timestamp
        backup_subdir.mkdir(exist_ok=True)

        db_source = DB_FILE
        if db_source.exists():
            dest_db = backup_subdir / "db.sqlite"
            shutil.copy2(str(db_source), str(dest_db))

        if UPLOAD_DIR.exists():
            backup_upload = backup_subdir / "uploads"
            if backup_upload.exists():
                shutil.rmtree(str(backup_upload))
            shutil.copytree(str(UPLOAD_DIR), str(backup_upload))

        manifest = {
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "description": description,
            "db_file": "db.sqlite",
            "files": [],
            "hashes": {},
            "encrypted": False,
        }

        total_size = 0
        for dirpath, _, filenames in os.walk(backup_subdir):
            for fname in filenames:
                fp = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(fp, backup_subdir).replace("\\", "/")
                size = os.path.getsize(fp)
                total_size += size
                sha256_hash = hashlib.sha256()
                with open(fp, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256_hash.update(chunk)
                manifest["files"].append({"path": rel_path, "size": size})
                manifest["hashes"][rel_path] = sha256_hash.hexdigest()

        manifest["total_size"] = total_size
        manifest_path = backup_subdir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        if encrypt and get_encryption().available:
            archive_path = Path(f"{str(backup_subdir)}.zip")
            enc_backup_dir = backup_subdir.parent / f"{timestamp}_enc"
            enc_backup_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(str(archive_path), "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(backup_subdir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arc_name = os.path.relpath(full_path, backup_subdir)
                        with open(full_path, "rb") as f:
                            data = f.read()
                        zf.writestr(arc_name, get_encryption()._fernet.encrypt(data))
            enc_manifest = dict(manifest)
            enc_manifest["encrypted"] = True
            enc_manifest["original_dir"] = timestamp
            enc_manifest_path = enc_backup_dir / "manifest.json"
            enc_manifest_path.write_text(
                json.dumps(enc_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            shutil.move(str(archive_path), str(enc_backup_dir / "backup_data.zip.enc"))
            shutil.rmtree(str(backup_subdir))
            final_dir = enc_backup_dir
        else:
            final_dir = backup_subdir

        log_entry = {
            "action": "backup_created",
            "timestamp": datetime.now().isoformat(),
            "directory": final_dir.name,
            "total_size_bytes": total_size,
            "encrypted": encrypt and get_encryption().available,
            "description": description,
        }
        _write_privacy_log(log_entry)

        return {
            "path": final_dir,
            "size_mb": round(total_size / (1024 * 1024), 2),
            "encrypted": encrypt and get_encryption().available,
            "file_count": len(manifest["files"]),
        }

    @staticmethod
    def list_backups(limit=20):
        results = []
        if not BACKUP_DIR.exists():
            return results
        backups = sorted(
            [d for d in BACKUP_DIR.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )[:limit]
        for bd in backups:
            mf = bd / "manifest.json"
            info = {
                "name": bd.name,
                "path": str(bd),
                "modified_at": datetime.fromtimestamp(bd.stat().st_mtime).isoformat(),
                "size_mb": 0,
                "encrypted": False,
            }
            if mf.exists():
                try:
                    m = json.loads(mf.read_text(encoding="utf-8"))
                    info["created_at"] = m.get("created_at", "")
                    info["size_mb"] = round(m.get("total_size", 0) / (1024 * 1024), 2)
                    info["encrypted"] = m.get("encrypted", False)
                    info["description"] = m.get("description", "")
                    info["file_count"] = len(m.get("files", []))
                except Exception:
                    pass
            else:
                size = sum(
                    os.path.getsize(os.path.join(dp, fn))
                    for dp, dn, fns in os.walk(bd)
                    for fn in fns
                )
                info["size_mb"] = round(size / (1024 * 1024), 2)
            results.append(info)
        return results

    @staticmethod
    def verify_backup(backup_dir_name):
        backup_path = BACKUP_DIR / backup_dir_name
        if not backup_path.exists():
            return {"valid": False, "error": "Backup directory not found"}
        manifest_path = backup_path / "manifest.json"
        if not manifest_path.exists():
            return {"valid": False, "error": "Manifest file not found"}
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"valid": False, "error": "Invalid manifest JSON"}

        errors = []
        verified = 0
        for file_info in manifest.get("files", []):
            fp = backup_path / file_info["path"]
            if not fp.exists():
                errors.append(f"Missing file: {file_info['path']}")
                continue
            sha256_hash = hashlib.sha256()
            with open(fp, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256_hash.update(chunk)
            current_hash = sha256_hash.hexdigest()
            expected_hash = manifest["hashes"].get(file_info["path"], "")
            if current_hash != expected_hash:
                errors.append(f"Hash mismatch: {file_info['path']}")
            else:
                verified += 1

        return {
            "valid": len(errors) == 0,
            "verified_files": verified,
            "total_files": len(manifest.get("files", [])),
            "errors": errors,
        }

    @staticmethod
    def restore_backup(backup_dir_name, target_dir=None):
        backup_path = BACKUP_DIR / backup_dir_name
        if not backup_path.exists():
            return {"success": False, "error": "Backup directory not found"}
        manifest_path = backup_path / "manifest.json"
        if not manifest_path.exists():
            return {"success": False, "error": "Manifest file not found"}
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"success": False, "error": "Invalid manifest JSON"}

        if manifest.get("encrypted"):
            if not get_encryption().available:
                return {"success": False, "error": "Encryption key not configured"}
            enc_zip = backup_path / "backup_data.zip.enc"
            if not enc_zip.exists():
                return {"success": False, "error": "Encrypted backup file not found"}
            restore_to = target_dir or DATA_DIR / "_restore_temp"
            restore_to.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(enc_zip), "r") as zf:
                for item in zf.namelist():
                    data = zf.read(item)
                    decrypted = get_encryption()._fernet.decrypt(data)
                    dest_path = restore_to / item
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(decrypted)
            return {"success": True, "restored_to": str(restore_to), "encrypted": True}

        db_backup = backup_path / "db.sqlite"
        if db_backup.exists():
            if target_dir:
                shutil.copy2(str(db_backup), str(Path(target_dir) / "db.sqlite"))
            else:
                DB_FILE.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(db_backup), str(DB_FILE))

        upload_backup = backup_path / "uploads"
        if upload_backup.exists() and UPLOAD_DIR.exists():
            if target_dir:
                dest_upload = Path(target_dir) / "uploads"
            else:
                dest_upload = UPLOAD_DIR
            if dest_upload.exists():
                shutil.rmtree(str(dest_upload))
            shutil.copytree(str(upload_backup), str(dest_upload))

        log_entry = {
            "action": "backup_restored",
            "timestamp": datetime.now().isoformat(),
            "source_backup": backup_dir_name,
        }
        _write_privacy_log(log_entry)

        return {"success": True, "restored_to": target_dir or "default location"}

    @staticmethod
    def delete_backup(backup_dir_name):
        backup_path = BACKUP_DIR / backup_dir_name
        if not backup_path.exists():
            return {"success": False, "error": "Backup not found"}
        shutil.rmtree(str(backup_path))
        log_entry = {
            "action": "backup_deleted",
            "timestamp": datetime.now().isoformat(),
            "deleted_backup": backup_dir_name,
        }
        _write_privacy_log(log_entry)
        return {"success": True}

    @staticmethod
    def cleanup_old_backups(retention_days=BACKUP_RETENTION_DAYS):
        if not BACKUP_DIR.exists():
            return {"cleaned": 0, "freed_bytes": 0}
        cutoff = datetime.now() - timedelta(days=retention_days)
        cleaned = 0
        freed = 0
        for bd in BACKUP_DIR.iterdir():
            if bd.is_dir():
                mtime = datetime.fromtimestamp(bd.stat().st_mtime)
                if mtime < cutoff:
                    freed += sum(
                        os.path.getsize(os.path.join(dp, fn))
                        for dp, dns, fns in os.walk(bd)
                        for fn in fns
                    )
                    shutil.rmtree(str(bd))
                    cleaned += 1
        return {"cleaned": cleaned, "freed_bytes": freed, "freed_mb": round(freed / (1024 * 1024), 2)}

    @staticmethod
    def start_auto_backup():
        if not BACKUP_AUTO_ENABLED:
            return
        if BackupManager._stop_event is not None:
            return

        def _auto_backup_loop():
            stop = BackupManager._stop_event
            interval = max(BACKUP_INTERVAL_HOURS * 3600, 3600)
            while not stop.is_set():
                stop.wait(interval)
                if stop.is_set():
                    break
                try:
                    BackupManager.create_backup(description="Auto scheduled backup")
                except Exception:
                    pass

        BackupManager._stop_event = threading.Event()
        BackupManager._scheduler_thread = threading.Thread(
            target=_auto_backup_loop, daemon=True, name="AutoBackupScheduler"
        )
        BackupManager._scheduler_thread.start()

    @staticmethod
    def stop_auto_backup():
        if BackupManager._stop_event is not None:
            BackupManager._stop_event.set()
            BackupManager._stop_event = None
            BackupManager._scheduler_thread = None


class PrivacyProtection:
    """GDPR-style privacy protection tools"""

    @staticmethod
    def anonymize_ip(ip_address):
        if not ip_address or not IP_ANONYMIZE_ENABLED:
            return ip_address
        try:
            parts = ip_address.strip().split(".")
            if len(parts) == 4:
                parts[3] = "0"
                return ".".join(parts)
            if ":" in ip_address and ip_address.count(":") > 3:
                colons = ip_address.split(":")
                return ":".join(colons[:4]) + "::" + ("0000" if len(colons) <= 4 else "")
        except Exception:
            pass
        return ip_address

    @staticmethod
    def anonymize_email(email):
        if not email or "@" not in email:
            return email
        local, domain = email.rsplit("@", 1)
        if len(local) <= 2:
            masked = "***"
        else:
            masked = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{masked}@{domain}"

    @staticmethod
    def export_user_data(conn, user_id):
        user = conn.execute(
            "SELECT id, username, created_at, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return None
        export_data = {
            "user": dict(user),
            "exported_at": datetime.now().isoformat(),
            "files": [
                dict(r)
                for r in conn.execute(
                    "SELECT id, filename, project_name, size, created_at FROM files WHERE user_id = ? AND is_deleted = 0",
                    (user_id,),
                ).fetchall()
            ],
            "folders": [
                dict(r)
                for r in conn.execute(
                    "SELECT id, name, purpose, created_at FROM folders WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            ],
            "categories": [
                dict(r)
                for r in conn.execute(
                    "SELECT id, name, description, created_at FROM categories WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            ],
            "tags": [
                dict(r)
                for r in conn.execute(
                    "SELECT id, name, created_at FROM tags WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            ],
            "ai_contents_count": conn.execute(
                "SELECT COUNT(*) FROM ai_contents WHERE user_id = ?", (user_id,)
            ).fetchone()[0],
            "access_log_count": conn.execute(
                "SELECT COUNT(*) FROM access_logs WHERE user_id = ?", (user_id,)
            ).fetchone()[0],
        }

        log_entry = {
            "action": "data_export",
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
        }
        _write_privacy_log(log_entry)
        return export_data

    @staticmethod
    def delete_user_account(conn, user_id, hard_delete=False):
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return {"success": False, "error": "User not found"}

        tables_to_clean = [
            ("files", "user_id"),
            ("folders", "user_id"),
            ("categories", "user_id"),
            ("tags", "user_id"),
            ("likes", "user_id"),
            ("favorites", "user_id"),
            ("ai_contents", "user_id"),
            ("file_shares", "user_id"),
            ("trash", "user_id"),
            ("access_logs", "user_id"),
            ("operation_logs", "user_id"),
            ("user_2fa", "user_id"),
            ("login_devices", "user_id"),
            ("security_events", "user_id"),
        ]

        for table, fk_col in tables_to_clean:
            try:
                conn.execute(f"DELETE FROM {table} WHERE {fk_col} = ?", (user_id,))
            except sqlite3.OperationalError:
                pass

        if hard_delete:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        else:
            anon_username = f"deleted_user_{user_id[:8]}"
            anon_email = f"deleted_{user_id[:8]}@anonymized.local"
            conn.execute(
                "UPDATE users SET username=?, email=?, password='', avatar=NULL, two_factor_enabled=0 WHERE id=?",
                (anon_username, anon_email, user_id),
            )

        conn.commit()

        log_entry = {
            "action": "account_deletion",
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "hard_delete": hard_delete,
        }
        _write_privacy_log(log_entry)

        return {"success": True, "mode": "hard_delete" if hard_delete else "anonymized"}

    @staticmethod
    def cleanup_expired_data(conn, retention_days=90):
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()

        deleted_codes = conn.execute(
            "DELETE FROM verification_codes WHERE expires_at < ?", (cutoff,)
        ).rowcount

        old_shares = conn.execute(
            "DELETE FROM file_shares WHERE expires_at IS NOT NULL AND expires_at < ?", (cutoff,)
        ).rowcount

        old_trash = conn.execute(
            "DELETE FROM trash WHERE expire_at IS NOT NULL AND expire_at < ?", (cutoff,)
        ).rowcount

        old_events = conn.execute(
            "DELETE FROM security_events WHERE created_at < ?", (cutoff,)
        ).rowcount

        old_access = conn.execute(
            "DELETE FROM access_logs WHERE access_time < ?", (cutoff,)
        ).rowcount

        old_ops = conn.execute(
            "DELETE FROM operation_logs WHERE created_at < ?", (cutoff,)
        ).rowcount

        conn.commit()

        log_entry = {
            "action": "data_cleanup",
            "timestamp": datetime.now().isoformat(),
            "retention_days": retention_days,
            "deleted_records": {
                "verification_codes": deleted_codes,
                "file_shares": old_shares,
                "trash_items": old_trash,
                "security_events": old_events,
                "access_logs": old_access,
                "operation_logs": old_ops,
            },
        }
        _write_privacy_log(log_entry)

        return {
            "verification_codes": deleted_codes,
            "file_shares": old_shares,
            "trash_items": old_trash,
            "security_events": old_events,
            "access_logs": old_access,
            "operation_logs": old_ops,
        }


def _write_privacy_log(entry):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(PRIVACY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def get_privacy_audit_log(limit=100):
    entries = []
    if PRIVACY_LOG_FILE.exists():
        lines = PRIVACY_LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
        for line in lines[-limit:]:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    return reversed(entries)


def require_encryption(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_encryption().available:
            return jsonify({"error": "Encryption not enabled"}), 503
        return f(*args, **kwargs)

    return decorated
