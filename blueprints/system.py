from flask import Blueprint, request, render_template, redirect, url_for, jsonify, session, send_from_directory
from app import (app, get_db, get_all_files, log_message,
                page_error_response, api_response)
import os
import json
import sqlite3

system_bp = Blueprint('system', __name__)


@system_bp.route('/', endpoint='index')
def index():
    try:
        files = get_all_files()
        remote_table = []
        remote_error = None

        try:
            from app import get_remote_file_list
            remote_table, remote_error = get_remote_file_list()
        except Exception as e:
            remote_error = str(e)

        dk_info = None
        try:
            from app import get_dkfile_info
            dk_info = get_dkfile_info()
        except Exception:
            pass

        return render_template(
            'index.html',
            files=files,
            remote_table=remote_table,
            remote_error=remote_error,
            dk_info=dk_info,
            username=session.get('username'),
            role=session.get('role'),
        )
    except Exception as e:
        log_message(log_type='error', log_level='ERROR',
                   message=f'首页加载失败: {str(e)}',
                   action='index_load_failed', request=request)
        return page_error_response('index', f'页面加载错误: {str(e)}', 500)


@system_bp.route('/api/db/stats', methods=['GET'], endpoint='api_db_stats')
def api_db_stats():
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    from app import get_database_stats
    stats = get_database_stats()

    conn = get_db()
    try:
        tables = {}
        for table in ['users', 'files', 'folders', 'categories', 'tags', 'ai_contents',
                      'likes', 'favorites', 'file_shares', 'trash']:
            try:
                count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                tables[table] = count
            except Exception:
                pass

        stats['tables'] = tables
        return api_response(success=True, data=stats)
    finally:
        conn.close()


@system_bp.route('/api/db/optimize', methods=['POST'], endpoint='api_db_optimize')
def api_db_optimize():
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    try:
        from app import optimize_database
        result = optimize_database()

        log_message(log_type='operation', log_level='INFO',
                   message='管理员执行数据库优化',
                   user_id=session['user_id'], action='db_optimize', request=request)

        return api_response(success=True, data=result, message='数据库优化完成')
    except Exception as e:
        return api_response(success=False, message=f'优化失败: {str(e)}')


@system_bp.route('/api/db/archive', methods=['POST'], endpoint='api_db_archive')
def api_db_archive():
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    days_to_keep = request.args.get('days', 90, type=int)

    try:
        from app import archive_old_logs
        result = archive_old_logs(days_to_keep=days_to_keep)

        log_message(log_type='operation', log_level='INFO',
                   message=f'管理员执行日志归档 (保留{days_to_keep}天)',
                   user_id=session['user_id'], action='db_archive', request=request)

        return api_response(success=True, data=result, message='归档完成')
    except Exception as e:
        return api_response(success=False, message=f'归档失败: {str(e)}')


@system_bp.route('/api/cache/stats', methods=['GET'], endpoint='api_cache_stats')
def api_cache_stats():
    cache = get_cache()
    stats = cache.get_stats()

    preview_cache = get_preview_cache()
    preview_stats = preview_cache.get_stats() if preview_cache else None

    hot_cache = get_hot_data_cache()
    hot_stats = hot_cache.get_stats() if hot_cache else None

    return api_response(success=True, data={
        'main_cache': stats,
        'preview_cache': preview_stats,
        'hot_data_cache': hot_stats
    })


@system_bp.route('/api/cache/clear', methods=['POST'], endpoint='api_cache_clear')
def api_cache_clear():
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    cache_type = (request.get_json(silent=True) or {}).get('type', 'all')

    cleared = {}

    if cache_type in ('all', 'main'):
        cache = get_cache()
        cleared['main'] = cache.clear()

    if cache_type in ('all', 'preview'):
        preview_cache = get_preview_cache()
        if preview_cache:
            cleared['preview'] = preview_cache.clear()

    if cache_type in ('all', 'hot'):
        hot_cache = get_hot_data_cache()
        if hot_cache:
            cleared['hot'] = hot_cache.clear()

    log_message(log_type='operation', log_level='INFO',
               message=f'管理员清除缓存: {cache_type}, 结果: {cleared}',
               user_id=session['user_id'], action='clear_cache', request=request)

    return api_response(success=True, data=cleared, message='缓存已清除')


@system_bp.route('/api/storage/info', methods=['GET'], endpoint='api_storage_info')
def api_storage_info():
    storage_config = {
        'type': app.config.get('STORAGE_TYPE', 'local'),
        'oss_endpoint': app.config.get('OSS_ENDPOINT', ''),
        'oss_bucket': app.config.get('OSS_BUCKET', ''),
        'upload_folder': app.config.get('UPLOAD_FOLDER', ''),
    }

    upload_dir = Path(app.config.get('UPLOAD_FOLDER', 'uploads'))
    total_size = 0
    file_count = 0
    if upload_dir.exists():
        for f in upload_dir.rglob('*'):
            if f.is_file():
                total_size += f.stat().st_size
                file_count += 1

    disk_usage = shutil.disk_usage(upload_dir) if upload_dir.exists() else None

    from app import get_user_storage_usage
    my_usage = get_user_storage_usage(session.get('user_id')) if 'user_id' in session else None

    return api_response(success=True, data={
        'config': storage_config,
        'total_files': file_count,
        'total_size_bytes': total_size,
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'disk_free_gb': round(disk_usage.free / (1024 ** 3), 2) if disk_usage else None,
        'disk_total_gb': round(disk_usage.total / (1024 ** 3), 2) if disk_usage else None,
        'my_usage': my_usage,
    })


@system_bp.route('/api/storage/test-oss', methods=['POST'], endpoint='api_test_oss_connection')
def api_test_oss_connection():
    if 'user_id' not in session or session.get('role') != 'admin':
        return api_response(success=False, message='权限不足', code=403)

    try:
        import oss2
        auth = oss2.Auth(app.config.get('OSS_ACCESS_KEY_ID'), app.config.get('OSS_ACCESS_KEY_SECRET'))
        bucket = oss2.Bucket(auth, app.config.get('OSS_ENDPOINT'), app.config.get('OSS_BUCKET'))
        bucket.get_bucket_info()

        log_message(log_type='operation', log_level='INFO',
                   message='管理员测试OSS连接成功',
                   user_id=session['user_id'], action='test_oss', request=request)

        return api_response(success=True, message='OSS连接测试成功')
    except Exception as e:
        return api_response(success=False, message=f'连接失败: {str(e)}')


@system_bp.route('/api/image/resize', methods=['POST'], endpoint='api_image_resize')
def api_image_resize():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    if 'image' not in request.files:
        return api_response(success=False, message='未上传图片')

    image_file = request.files['image']
    width = request.form.get('width', type=int)
    height = request.form.get('height', type=int)
    quality = request.form.get('quality', 85, type=int)

    if not all([width, height]):
        return api_response(success=False, message='请提供宽度和高度参数')

    try:
        from PIL import Image
        import io

        img = Image.open(image_file.stream)
        original_format = img.format or 'JPEG'

        resized_img = img.resize((width, height), Image.LANCZOS)

        buffer = io.BytesIO()
        if original_format.upper() in ('PNG', 'GIF', 'WEBP'):
            resized_img.save(buffer, format=original_format, quality=quality)
        else:
            resized_img.save(buffer, format='JPEG', quality=quality)

        buffer.seek(0)
        result_base64 = base64.b64encode(buffer.getvalue()).decode()

        log_message(log_type='operation', log_level='INFO',
                   message=f'图片缩放处理: {width}x{height}',
                   user_id=session['user_id'], action='image_resize', request=request)

        return api_response(success=True, data={
            'resized_image': f'data:image/{original_format.lower()};base64,{result_base64}',
            'original_size': img.size,
            'new_size': (width, height),
            'format': original_format
        })
    except ImportError:
        return api_response(success=False, message='需要安装 Pillow 库: pip install Pillow')
    except Exception as e:
        return api_response(success=False, message=f'图片处理失败: {str(e)}')


@system_bp.route('/api/image/convert', methods=['POST'], endpoint='api_image_convert')
def api_image_convert():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    if 'image' not in request.files:
        return api_response(success=False, message='未上传图片')

    image_file = request.files['image']
    target_format = request.form.get('format', 'PNG').upper()
    quality = request.form.get('quality', 85, type=int)

    valid_formats = ['JPEG', 'PNG', 'WEBP', 'GIF']
    if target_format not in valid_formats:
        return api_response(success=False, message=f'不支持的目标格式，支持: {", ".join(valid_formats)}')

    try:
        from PIL import Image
        import io

        img = Image.open(image_file.stream)

        if target_format == 'JPEG' and img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        buffer = io.BytesIO()
        save_kwargs = {'format': target_format}
        if target_format == 'JPEG':
            save_kwargs['quality'] = quality
        elif target_format == 'WEBP':
            save_kwargs['quality'] = quality

        img.save(buffer, **save_kwargs)
        buffer.seek(0)
        result_base64 = base64.b64encode(buffer.getvalue()).decode()

        mime_type = f'image/{target_format.lower()}'

        log_message(log_type='operation', log_level='INFO',
                   message=f'图片格式转换: -> {target_format}',
                   user_id=session['user_id'], action='image_convert', request=request)

        return api_response(success=True, data={
            'converted_image': f'data:{mime_type};base64,{result_base64}',
            'original_format': img.format,
            'target_format': target_format,
            'size': img.size
        })
    except ImportError:
        return api_response(success=False, message='需要安装 Pillow 库: pip install Pillow')
    except Exception as e:
        return api_response(success=False, message=f'格式转换失败: {str(e)}')


@system_bp.route('/api/storage/upload', methods=['POST'], endpoint='api_storage_upload')
def api_storage_upload():
    if 'user_id' not in session:
        return api_response(success=False, message='请先登录', code=401)

    if 'file' not in request.files:
        return api_response(success=False, message='未上传文件')

    uploaded_file = request.files['file']

    if uploaded_file.filename == '':
        return api_response(success=False, message='文件名为空')

    try:
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(uploaded_file.filename)[1]
        stored_name = f"{file_id}{ext}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
        uploaded_file.save(file_path)
        file_size = os.path.getsize(file_path)

        dkfile_info = "{}"
        try:
            from app import upload_to_dkfile
            dkfile_info = upload_to_dkfile(uploaded_file, stored_name, file_path)
        except Exception:
            pass

        conn = get_db()
        try:
            conn.execute("""INSERT INTO files (id, user_id, filename, stored_name, path, size, dkfile,
                           project_name, project_desc, folder_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, '', '', NULL, CURRENT_TIMESTAMP)""",
                        (file_id, session['user_id'], uploaded_file.filename, stored_name,
                         file_path, file_size, dkfile_info))
            conn.commit()

            log_message(log_type='operation', log_level='INFO',
                       message=f'API上传文件: {uploaded_file.filename}',
                       user_id=session['user_id'], action='api_upload',
                       target_id=file_id, target_type='file', request=request)

            return api_response(success=True, data={
                'id': file_id,
                'filename': uploaded_file.filename,
                'stored_name': stored_name,
                'size': file_size,
                'url': url_for('uploads_serve', filename=stored_name, _external=True),
                'dkfile_info': dkfile_info if isinstance(dkfile_info, dict) else json.loads(dkfile_info)
            })
        finally:
            conn.close()
    except Exception as e:
        return api_response(success=False, message=f'上传失败: {str(e)}')


@system_bp.route('/api/health', endpoint='health_check')
def health_check():
    health_status = {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

    db_ok = True
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
    except Exception as e:
        db_ok = False
        health_status['database'] = {'status': 'error', 'message': str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

    if db_ok:
        health_status['database'] = {'status': 'ok'}

    upload_dir = Path(app.config.get('UPLOAD_FOLDER', 'uploads'))
    fs_ok = upload_dir.exists()
    health_status['filesystem'] = {
        'status': 'ok' if fs_ok else 'error',
        'path': str(upload_dir),
        'writable': os.access(str(upload_dir), os.W_OK) if fs_ok else False
    }

    overall = 'healthy' if (db_ok and fs_ok) else 'degraded'
    health_status['status'] = overall
    status_code = 200 if overall == 'healthy' else 503

    return jsonify(health_status), status_code


@system_bp.route('/favicon.ico', endpoint='favicon')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')
