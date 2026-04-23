from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from app import (app, get_db, log_message, api_response, login_required)
import data_security
import json
import uuid
import pyotp
import qrcode
import io
import base64

security_bp = Blueprint('security', __name__)


@security_bp.get('/security/status', endpoint='security_status')
def security_status():
    enc = data_security.get_encryption()
    return jsonify({
        "encryption_enabled": enc.available,
        "encryption_configured": enc._key_loaded,
        "ip_anonymize": data_security.IP_ANONYMIZE_ENABLED,
        "backup_auto": data_security.BACKUP_AUTO_ENABLED,
        "backup_retention_days": data_security.BACKUP_RETENTION_DAYS,
    })


@security_bp.post('/api/security/encryption/generate-key', endpoint='api_generate_encryption_key')
@data_security.require_encryption
def api_generate_encryption_key():
    if data_security.get_encryption().available:
        return jsonify({"error": "Encryption already configured"}), 400
    key = data_security.get_encryption().save_key()
    log_message(log_type='security', log_level='INFO',
               message='数据加密密钥已生成', action='generate_encryption_key', request=request)
    return jsonify({"success": True, "message": "Encryption key generated and saved",
                   "key_preview": key[:10] + "..." if key else None})


@security_bp.post('/api/security/encryption/encrypt-field', endpoint='api_encrypt_field')
@data_security.require_encryption
def api_encrypt_field():
    data = request.get_json(silent=True) or {}
    value = data.get("value", "")
    encrypted = data_security.encrypt_field(value)
    return jsonify({"encrypted": encrypted})


@security_bp.post('/api/security/encryption/decrypt-field', endpoint='api_decrypt_field')
@data_security.require_encryption
def api_decrypt_field():
    data = request.get_json(silent=True) or {}
    value = data.get("value", "")
    decrypted = data_security.decrypt_field(value)
    return jsonify({"decrypted": decrypted})


@security_bp.post('/api/security/encrypt-user-emails', endpoint='api_encrypt_user_emails')
@data_security.require_encryption
def api_encrypt_user_emails():
    conn = get_db()
    users = conn.execute("SELECT id, email FROM users").fetchall()
    count = 0
    for user in users:
        if user["email"] and not str(user["email"]).startswith("ENC:"):
            encrypted = data_security.encrypt_field(user["email"])
            conn.execute("UPDATE users SET email = ? WHERE id = ?", (encrypted, user["id"]))
            count += 1
    conn.commit()
    log_message(log_type='security', log_level='INFO',
               message=f'批量加密用户邮箱: {count} 条',
               action='batch_encrypt_emails', request=request)
    return jsonify({"success": True, "encrypted_count": count})


@security_bp.post('/api/security/decrypt-user-emails', endpoint='api_decrypt_user_emails')
@data_security.require_encryption
def api_decrypt_user_emails():
    conn = get_db()
    users = conn.execute("SELECT id, email FROM users").fetchall()
    count = 0
    for user in users:
        if user["email"] and str(user["email"]).startswith("ENC:"):
            decrypted = data_security.decrypt_field(user["email"])
            conn.execute("UPDATE users SET email = ? WHERE id = ?", (decrypted, user["id"]))
            count += 1
    conn.commit()
    return jsonify({"success": True, "decrypted_count": count})


@security_bp.post('/api/backup/create', endpoint='api_create_backup')
def api_create_backup():
    data = request.get_json(silent=True) or {}
    encrypt = data.get("encrypt", True)
    description = data.get("description", "")
    result = data_security.BackupManager.create_backup(encrypt=encrypt, description=description)
    log_message(log_type='operation', log_level='INFO',
               message=f'创建备份: {result["path"].name}',
               action='create_backup', request=request)
    return jsonify(result)


@security_bp.get('/api/backup/list', endpoint='api_list_backups')
def api_list_backups():
    limit = request.args.get("limit", 20, type=int)
    backups = data_security.BackupManager.list_backups(limit=limit)
    return jsonify(backups)


@security_bp.get('/api/backup/verify/<backup_name>', endpoint='api_verify_backup')
def api_verify_backup(backup_name):
    result = data_security.BackupManager.verify_backup(backup_name)
    return jsonify(result)


@security_bp.post('/api/backup/restore/<backup_name>', endpoint='api_restore_backup')
def api_restore_backup(backup_name):
    result = data_security.BackupManager.restore_backup(backup_name)
    log_message(log_type='operation', log_level='INFO',
               message=f'恢复备份: {backup_name}, 结果: {result.get("success")}',
               action='restore_backup', request=request)
    return jsonify(result)


@security_bp.delete('/api/backup/<backup_name>', endpoint='api_delete_backup')
def api_delete_backup(backup_name):
    result = data_security.BackupManager.delete_backup(backup_name)
    return jsonify(result)


@security_bp.post('/api/backup/cleanup', endpoint='api_cleanup_backups')
def api_cleanup_backups():
    days = request.args.get("days", data_security.BACKUP_RETENTION_DAYS, type=int)
    result = data_security.BackupManager.cleanup_old_backups(retention_days=days)
    log_message(log_type='operation', log_level='INFO',
               message=f'清理过期备份: 删除 {result["cleaned"]} 个, 释放 {result["freed_mb"]} MB',
               action='cleanup_backups', request=request)
    return jsonify(result)


@security_bp.get('/api/privacy/export', endpoint='api_export_user_data')
@login_required
def api_export_user_data():
    user_id = session.get("user_id")
    conn = get_db()
    export_data = data_security.PrivacyProtection.export_user_data(conn, user_id)
    if not export_data:
        return jsonify({"error": "User not found"}), 404
    response = make_response(json.dumps(export_data, indent=2, ensure_ascii=False))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = f'attachment; filename=user_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    return response


@security_bp.post('/api/privacy/delete-account', endpoint='api_delete_account')
@login_required
def api_delete_account():
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    hard_delete = data.get("hard_delete", False)

    password = data.get("password", "")
    if not hard_delete and not password:
        return jsonify({"error": "Password required for account deletion"}), 400

    if password:
        from werkzeug.security import check_password_hash
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not check_password_hash(user["password"], password):
            return jsonify({"error": "Invalid password"}), 403

    conn = get_db()
    result = data_security.PrivacyProtection.delete_user_account(conn, user_id, hard_delete=hard_delete)
    session.clear()

    log_message(log_type='security', log_level='WARNING',
               message=f'账户删除: user_id={user_id}, mode={"硬删除" if hard_delete else "匿名化"}',
               action='delete_account', user_id=user_id, request=request)
    return jsonify(result)


@security_bp.post('/api/privacy/anonymize-ip', endpoint='api_anonymize_ip')
def api_anonymize_ip():
    ip_address = (request.get_json(silent=True) or {}).get("ip", "")
    anonymized = data_security.PrivacyProtection.anonymize_ip(ip_address)
    return jsonify({"original": ip_address, "anonymized": anonymized})


@security_bp.post('/api/privacy/cleanup-expired', endpoint='api_cleanup_expired_data')
def api_cleanup_expired_data():
    days = request.args.get("days", 90, type=int)
    conn = get_db()
    result = data_security.PrivacyProtection.cleanup_expired_data(conn, retention_days=days)
    total_deleted = sum(result.values())
    log_message(log_type='operation', log_level='INFO',
               message=f'清理过期数据: 共删除 {total_deleted} 条记录',
               action='cleanup_expired_data', request=request)
    return jsonify({"success": True, "deleted": result, "total_deleted": total_deleted})


@security_bp.get('/api/privacy/audit-log', endpoint='api_privacy_audit_log')
def api_privacy_audit_log():
    limit = request.args.get("limit", 100, type=int)
    entries = list(data_security.get_privacy_audit_log(limit=limit))
    return jsonify(entries)


@security_bp.route('/api/security/password-strength', methods=['POST'], endpoint='check_password_strength')
def check_password_strength():
    data = request.get_json(silent=True) or {}
    password = data.get('password', '')

    if not password:
        return api_response(success=False, message='密码不能为空')

    score = 0
    suggestions = []

    if len(password) >= 8:
        score += 1
    else:
        suggestions.append('密码长度至少需要8个字符')

    if re.search(r'[a-z]', password):
        score += 1
    else:
        suggestions.append('包含小写字母')

    if re.search(r'[A-Z]', password):
        score += 1
    else:
        suggestions.append('包含大写字母')

    if re.search(r'\d', password):
        score += 1
    else:
        suggestions.append('包含数字')

    if re.search(r'[^a-zA-Z\d]', password):
        score += 1
    else:
        suggestions.append('包含特殊字符')

    if len(password) >= 12:
        score += 1

    if len(password) >= 16:
        score += 1

    common_passwords = ['123456', 'password', '12345678', 'qwerty', 'abc123', '111111']
    if password.lower() in common_passwords:
        score = 0
        suggestions = ['此密码过于常见，请使用更复杂的密码']

    strength_levels = {
        0: ('非常弱', '#dc3545'),
        1-2: ('弱', '#fd7e14'),
        3-4: ('中等', '#ffc107'),
        5-6: ('强', '#28a745'),
        7-8: ('非常强', '#17a2b8')
    }

    level_text, color = next(
        (v for k, v in strength_levels.items() if score <= k),
        ('非常强', '#17a2b8')
    )

    return api_response(success=True, data={
        'score': score,
        'max_score': 8,
        'level': level_text,
        'color': color,
        'suggestions': suggestions
    })


@security_bp.route('/api/security/2fa/setup', methods=['POST'], endpoint='setup_2fa')
def setup_2fa():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    secret = pyotp.random_base32()
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=session['email'],
        issuer_name="YYToolsSote"
    )

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM user_2fa WHERE user_id = ?",
                              (session['user_id'],)).fetchone()
        if existing:
            conn.execute("UPDATE user_2fa SET secret = ?, verified = 0 WHERE user_id = ?",
                        (secret, session['user_id']))
        else:
            conn.execute("INSERT INTO user_2fa (id, user_id, secret, verified) VALUES (?, ?, ?, 0)",
                        (str(uuid.uuid4()), session['user_id'], secret))
        conn.commit()

        log_message(log_type='security', log_level='INFO',
                   message='用户设置两步验证', user_id=session['user_id'],
                   action='setup_2fa', request=request)

        return api_response(success=True, data={
            'secret': secret,
            'qr_code': f'data:image/png;base64,{qr_code_base64}'
        })
    finally:
        conn.close()


@security_bp.route('/api/security/2fa/verify', methods=['POST'], endpoint='verify_2fa')
def verify_2fa():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    code = request.form.get('code') or (request.get_json(silent=True) or {}).get('code', '')

    if not code:
        return api_response(success=False, message='请输入验证码')

    conn = get_db()
    try:
        two_fa = conn.execute("SELECT * FROM user_2fa WHERE user_id = ? AND verified = 0",
                             (session['user_id'],)).fetchone()
        if not two_fa:
            return api_response(success=False, message='未找到待验证的2FA设置')

        totp = pyotp.TOTP(two_fa['secret'])
        if not totp.verify(code, valid_window=1):
            return api_response(success=False, message='验证码无效')

        conn.execute("UPDATE user_2fa SET verified = 1 WHERE id = ?", (two_fa['id'],))
        conn.execute("UPDATE users SET two_factor_enabled = 1 WHERE id = ?", (session['user_id'],))
        conn.commit()

        log_message(log_type='security', log_level='INFO',
                   message='用户完成两步验证设置', user_id=session['user_id'],
                   action='verify_2fa', request=request)

        return api_response(success=True, message='两步验证已启用')
    finally:
        conn.close()


@security_bp.route('/api/security/2fa/disable', methods=['POST'], endpoint='disable_2fa')
def disable_2fa():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    password = (request.get_json(silent=True) or {}).get('password', '')
    if not password:
        return api_response(success=False, message='请输入密码确认')

    conn = get_db()
    try:
        user = conn.execute("SELECT password FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        if not check_password_hash(user['password'], password):
            return api_response(success=False, message='密码不正确')

        conn.execute("DELETE FROM user_2fa WHERE user_id = ?", (session['user_id'],))
        conn.execute("UPDATE users SET two_factor_enabled = 0 WHERE id = ?", (session['user_id'],))
        conn.commit()

        log_message(log_type='security', log_level='WARNING',
                   message='用户禁用两步验证', user_id=session['user_id'],
                   action='disable_2fa', request=request)

        return api_response(success=True, message='两步验证已禁用')
    finally:
        conn.close()


@security_bp.route('/api/security/events', methods=['GET'], endpoint='get_security_events')
def get_security_events():
    if 'user_id' not in session and session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    limit = request.args.get('limit', 50, type=int)
    event_type = request.args.get('type', '')

    conn = get_db()
    try:
        where_clauses = []
        params = []
        if event_type:
            where_clauses.append('event_type = ?')
            params.append(event_type)

        where_sql = 'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''
        rows = conn.execute(f'SELECT * FROM security_events {where_sql} ORDER BY created_at DESC LIMIT ?',
                           params + [limit]).fetchall()

        events = []
        for r in rows:
            details = {}
            try:
                details = json.loads(r['details_json']) if r['details_json'] else {}
            except:
                pass
            events.append({
                'id': r['id'],
                'event_type': r['event_type'],
                'severity': r['severity'],
                'ip_address': r['ip_address'],
                'user_agent': r['user_agent'],
                'details': details,
                'created_at': r['created_at']
            })

        return api_response(success=True, data={'events': events})
    finally:
        conn.close()


@security_bp.route('/api/login-devices', methods=['GET'], endpoint='get_login_devices')
def get_login_devices():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    conn = get_db()
    try:
        devices = conn.execute(
            "SELECT * FROM login_devices WHERE user_id = ? ORDER BY last_login DESC",
            (session['user_id'],)).fetchall()

        device_list = []
        for d in devices:
            info = {}
            try:
                info = json.loads(d['device_info']) if d['device_info'] else {}
            except:
                pass
            device_list.append({
                'id': d['id'],
                'device_name': d['device_name'],
                'is_trusted': bool(d['is_trusted']),
                'last_login': d['last_login'],
                'device_info': info
            })

        return api_response(success=True, data={'devices': device_list})
    finally:
        conn.close()


@security_bp.route('/api/login-devices/<device_id>/trust', methods=['POST'], endpoint='trust_device')
def trust_device(device_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    conn = get_db()
    try:
        device = conn.execute(
            "SELECT * FROM login_devices WHERE id = ? AND user_id = ?",
            (device_id, session['user_id'])).fetchone()
        if not device:
            return api_response(success=False, message='设备不存在', code=404)

        conn.execute("UPDATE login_devices SET is_trusted = 1 WHERE id = ?", (device_id,))
        conn.commit()

        return api_response(success=True, message='设备已标记为信任')
    finally:
        conn.close()


@security_bp.route('/api/login-devices/<device_id>/remove', methods=['DELETE'], endpoint='remove_device')
def remove_device(device_id):
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    conn = get_db()
    try:
        result = conn.execute(
            "DELETE FROM login_devices WHERE id = ? AND user_id = ?",
            (device_id, session['user_id']))
        conn.commit()

        if result.rowcount == 0:
            return api_response(success=False, message='设备不存在或已被删除')

        log_message(log_type='security', log_level='INFO',
                   message=f'用户移除登录设备: {device_id}',
                   user_id=session['user_id'], action='remove_device',
                   target_id=device_id, target_type='login_device', request=request)

        return api_response(success=True, message='设备已移除')
    finally:
        conn.close()
