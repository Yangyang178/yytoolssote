import os
import uuid
import json
import sqlite3
import smtplib
import random
import time
import re
import hashlib
import threading
import functools
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory, jsonify, session, g, make_response
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# ==================== 缓存系统实现 ====================

class CacheBackend:
    """缓存后端抽象基类"""
    def get(self, key):
        raise NotImplementedError

    def set(self, key, value, timeout=None):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

    def exists(self, key):
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError


class MemoryCache(CacheBackend):
    """内存缓存实现（线程安全）"""

    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self._stats = {'hits': 0, 'misses': 0}

    def get(self, key):
        with self._lock:
            if key in self._cache:
                item = self._cache[key]
                if item['expires'] is None or time.time() < item['expires']:
                    self._stats['hits'] += 1
                    return item['value']
                else:
                    del self._cache[key]
            self._stats['misses'] += 1
            return None

    def set(self, key, value, timeout=None):
        with self._lock:
            expires = time.time() + timeout if timeout else None
            self._cache[key] = {
                'value': value,
                'expires': expires,
                'created_at': time.time()
            }

    def delete(self, key):
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def exists(self, key):
        with self._lock:
            if key in self._cache:
                item = self._cache[key]
                if item['expires'] is None or time.time() < item['expires']:
                    return True
                else:
                    del self._cache[key]
            return False

    def clear(self):
        with self._lock:
            self._cache.clear()

    def get_stats(self):
        total = self._stats['hits'] + self._stats['misses']
        return {
            **self._stats,
            'hit_rate': round(self._stats['hits'] / max(total, 1) * 100, 2),
            'size': len(self._cache)
        }


class RedisCache(CacheBackend):
    """Redis缓存实现（如果可用）"""

    def __init__(self, host='localhost', port=6379, db=0, password=None):
        try:
            import redis
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # 测试连接
            self.client.ping()
            self._available = True
            print("[缓存] Redis连接成功")
        except Exception as e:
            self._available = False
            print(f"[缓存] Redis不可用: {e}")

    def _serialize(self, value):
        """序列化值"""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    def _deserialize(self, value):
        """反序列化值"""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def get(self, key):
        if not self._available:
            return None
        try:
            value = self.client.get(key)
            return self._deserialize(value)
        except Exception as e:
            print(f"[Redis] GET错误: {e}")
            return None

    def set(self, key, value, timeout=None):
        if not self._available:
            return False
        try:
            serialized = self._serialize(value)
            return self.client.setex(key, timeout or 3600, serialized)
        except Exception as e:
            print(f"[Redis] SET错误: {e}")
            return False

    def delete(self, key):
        if not self._available:
            return False
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            print(f"[Redis] DELETE错误: {e}")
            return False

    def exists(self, key):
        if not self._available:
            return False
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            print(f"[Redis] EXISTS错误: {e}")
            return False

    def clear(self):
        if not self._available:
            return False
        try:
            return self.client.flushdb()
        except Exception as e:
            print(f"[Redis] FLUSH错误: {e}")
            return False


class UnifiedCache:
    """统一缓存管理器（自动选择后端）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化缓存系统"""
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")

        # 尝试使用Redis
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_db = int(os.getenv('REDIS_DB', 0))
        redis_pass = os.getenv('REDIS_PASSWORD')

        self.redis_cache = RedisCache(redis_host, redis_port, redis_db, redis_pass)

        if self.redis_cache._available:
            self.backend = self.redis_cache
            self.cache_type = "redis"
            print("[缓存系统] 使用 Redis 后端")
        else:
            self.backend = MemoryCache()
            self.cache_type = "memory"
            print("[缓存系统] 使用 内存 后端")

        # 缓存配置
        self.config = {
            'default_timeout': 3600,      # 默认1小时
            'user_data_timeout': 1800,     # 用户数据30分钟
            'file_list_timeout': 300,      # 文件列表5分钟
            'api_response_timeout': 60,     # API响应1分钟
            'static_resource_timeout': 86400,  # 静态资源24小时
            'preview_timeout': 3600,       # 文件预览1小时
            'hot_data_timeout': 600,        # 热点数据10分钟
        }

        print(f"[缓存系统] 初始化完成 (类型: {self.cache_type})")

    def get(self, key):
        """获取缓存"""
        return self.backend.get(key)

    def set(self, key, value, timeout=None):
        """设置缓存"""
        timeout = timeout or self.config['default_timeout']
        return self.backend.set(key, value, timeout)

    def delete(self, key):
        """删除缓存"""
        return self.backend.delete(key)

    def exists(self, key):
        """检查缓存是否存在"""
        return self.backend.exists(key)

    def clear(self):
        """清空所有缓存"""
        return self.backend.clear()

    def get_or_set(self, key, factory, timeout=None):
        """
        获取缓存，如果不存在则调用factory函数生成并缓存

        参数:
            key: 缓存键
            factory: 缓存未命中时的回调函数
            timeout: 过期时间（秒）
        """
        value = self.get(key)
        if value is not None:
            return value

        value = factory()
        if value is not None:
            self.set(key, value, timeout)

        return value

    def invalidate_pattern(self, pattern):
        """批量删除匹配模式的缓存（仅内存缓存支持）"""
        if self.cache_type == "memory":
            keys_to_delete = [k for k in list(self.backend._cache.keys()) if pattern in k]
            for key in keys_to_delete:
                self.delete(key)
            return len(keys_to_delete)
        elif self.cache_type == "redis" and self.redis_cache._available:
            try:
                import redis
                cursor = '0'
                deleted = 0
                while True:
                    cursor, keys = self.redis_cache.client.scan(cursor=cursor, match=pattern, count=100)
                    if keys:
                        deleted += self.redis_cache.client.delete(*keys)
                    if cursor == '0':
                        break
                return deleted
            except Exception as e:
                print(f"[缓存] 批量删除错误: {e}")
                return 0
        return 0

    def get_stats(self):
        """获取缓存统计信息"""
        stats = {
            'type': self.cache_type,
            'config': self.config.copy(),
        }

        if self.cache_type == "memory":
            stats.update(self.backend.get_stats())
        elif self.cache_type == "redis":
            stats['available'] = self.redis_cache._available

        return stats


# 全局缓存实例
cache_manager = None


def init_cache():
    """初始化全局缓存实例"""
    global cache_manager
    cache_manager = UnifiedCache()
    return cache_manager


def get_cache():
    """获取缓存实例（延迟初始化）"""
    global cache_manager
    if cache_manager is None:
        init_cache()
    return cache_manager


# ==================== API响应缓存装饰器 ====================

def cached_api(timeout=None, key_prefix='api'):
    """
    API响应缓存装饰器

    使用方法:
        @cached_api(timeout=60)
        def my_api():
            return expensive_operation()

    参数:
        timeout: 缓存过期时间（秒）
        key_prefix: 缓存键前缀
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键（基于函数名+参数+请求路径）
            cache_key = f"{key_prefix}:{func.__name__}:{request.path}"

            # 添加查询参数到键中
            if request.args:
                sorted_args = sorted(request.args.items())
                args_hash = hashlib.md5(str(sorted_args).encode()).hexdigest()[:12]
                cache_key += f":{args_hash}"

            # 检查是否是POST/PUT/DELETE请求（不缓存写操作）
            if request.method not in ['GET', 'HEAD']:
                result = func(*args, **kwargs)
                # 写操作后清除相关缓存
                cache = get_cache()
                cache.invalidate_pattern(f"{key_prefix}:*")
                return result

            # 尝试从缓存获取
            cache = get_cache()
            cached_result = cache.get(cache_key)

            if cached_result is not None:
                # 添加缓存头标识
                if isinstance(cached_result, dict):
                    cached_result['_cached'] = True
                    cached_result['_cache_time'] = datetime.now().isoformat()
                return cached_result

            # 执行原始函数
            result = func(*args, **kwargs)

            # 只缓存成功的JSON响应
            if result and isinstance(result, dict):
                cache.set(cache_key, result, timeout or cache.config['api_response_timeout'])

            return result

        return wrapper
    return decorator


# ==================== 页面渲染缓存装饰器 ====================

def cached_page(timeout=300, vary_by_user=False):
    """
    页面渲染缓存装饰器

    使用方法:
        @cached_page(timeout=300)
        def my_page():
            return render_template('page.html')
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # 生成缓存键
            cache_key = f"page:{request.endpoint}"
            if vary_by_user and 'user_id' in session:
                cache_key += f":user_{session['user_id']}"
            if request.args:
                args_str = '&'.join(f"{k}={v}" for k, v in sorted(request.args.items()))
                cache_key += f"?{args_str}"

            # 检查缓存
            cached_html = cache.get(cache_key)
            if cached_html is not None:
                response = make_response(cached_html)
                response.headers['X-Cache'] = 'HIT'
                return response

            # 渲染页面
            html_content = func(*args, **kwargs)

            # 缓存HTML内容
            if html_content:
                cache.set(cache_key, html_content, timeout)
                response = make_response(html_content)
                response.headers['X-Cache'] = 'MISS'
                return response

            return html_content

        return wrapper
    return decorator


# ==================== 文件预览缓存系统 ====================

class FilePreviewCache:
    """文件预览缓存管理器"""

    def __init__(self, cache_instance=None):
        self.cache = cache_instance or get_cache()
        self.preview_dir = Path(__file__).parent / "data" / "previews"
        self.preview_dir.mkdir(parents=True, exist_ok=True)

    def get_preview_path(self, file_id, file_ext):
        """获取预览文件的存储路径"""
        preview_filename = f"preview_{file_id}{file_ext}"
        return self.preview_dir / preview_filename

    def has_preview(self, file_id, file_ext):
        """检查预览是否存在（在缓存或磁盘）"""
        cache_key = f"preview:exists:{file_id}"

        # 先查内存缓存
        cached_exists = self.cache.get(cache_key)
        if cached_exists is not None:
            return cached_exists

        # 再查磁盘
        preview_path = self.get_preview_path(file_id, file_ext)
        exists = preview_path.exists()

        # 缓存结果（10分钟）
        self.cache.set(cache_key, exists, 600)

        return exists

    def save_preview(self, file_id, file_ext, content, content_type='text/plain'):
        """
        保存预览内容到缓存和磁盘

        参数:
            file_id: 原始文件ID
            file_ext: 预览文件扩展名
            content: 预览内容（文本或base64编码的图片）
            content_type: 内容类型
        """
        preview_path = self.get_preview_path(file_id, file_ext)

        # 保存到磁盘
        mode = 'wb' if content_type.startswith('image/') else 'w'
        encoding = None if content_type.startswith('image/') else 'utf-8'

        with open(preview_path, mode, encoding=encoding) as f:
            f.write(content)

        # 更新缓存
        cache_key = f"preview:content:{file_id}"
        self.cache.set(cache_key, {
            'content': content[:10000],  # 只缓存前10KB用于快速访问
            'content_type': content_type,
            'path': str(preview_path),
            'created_at': datetime.now().isoformat()
        }, timeout=self.cache.config['preview_timeout'])

        exists_key = f"preview:exists:{file_id}"
        self.cache.set(exists_key, True, 600)

        return str(preview_path)

    def get_preview(self, file_id, file_ext):
        """获取预览内容"""
        cache_key = f"preview:content:{file_id}"

        # 先查缓存
        cached_preview = self.cache.get(cache_key)
        if cached_preview:
            return cached_preview

        # 再查磁盘
        preview_path = self.get_preview_path(file_id, file_ext)
        if preview_path.exists():
            try:
                with open(preview_path, 'r', encoding='utf-8') as f:
                    content = f.read(10000)  # 读取前10KB

                preview_data = {
                    'content': content,
                    'content_type': 'text/plain',
                    'path': str(preview_path),
                    'created_at': datetime.fromtimestamp(preview_path.stat().st_mtime).isoformat()
                }
                self.cache.set(cache_key, preview_data, self.cache.config['preview_timeout'])
                return preview_data
            except Exception as e:
                print(f"[预览缓存] 读取失败: {e}")

        return None

    def delete_preview(self, file_id, ext=None):
        """删除指定文件的预览"""
        # 清除缓存
        self.cache.delete(f"preview:content:{file_id}")
        self.cache.delete(f"preview:exists:{file_id}")

        # 删除磁盘文件
        if ext:
            preview_path = self.get_preview_path(file_id, ext)
            if preview_path.exists():
                preview_path.unlink()
        else:
            # 删除该文件的所有预览
            for preview_file in self.preview_dir.glob(f"preview_{file_id}.*"):
                preview_file.unlink()

    def clear_old_previews(self, days=7):
        """清理超过指定天数的预览文件"""
        cutoff_time = time.time() - (days * 86400)
        deleted_count = 0

        for preview_file in self.preview_dir.iterdir():
            if preview_file.is_file() and preview_file.stat().st_mtime < cutoff_time:
                preview_file.unlink()
                deleted_count += 1

        if deleted_count > 0:
            print(f"[预览缓存] 已清理 {deleted_count} 个过期预览文件")

        return deleted_count


# 全局预览缓存实例
preview_cache = None


def init_preview_cache():
    """初始化文件预览缓存"""
    global preview_cache
    preview_cache = FilePreviewCache(get_cache())
    return preview_cache


# ==================== CDN静态资源配置 ====================

def configure_cdn(app, cdn_url=None, static_version=None):
    """
    配置CDN加速静态资源

    参数:
        app: Flask应用实例
        cdn_url: CDN基础URL（如 https://cdn.example.com）
        static_version: 静态资源版本号（用于缓存破坏）
    """
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")

    # 从环境变量读取CDN配置
    cdn_base = cdn_url or os.getenv('CDN_URL', '')
    version = static_version or os.getenv('STATIC_VERSION', 'v1')

    app.config['CDN_URL'] = cdn_base
    app.config['STATIC_VERSION'] = version
    app.config['USE_CDN'] = bool(cdn_base)

    if cdn_base:
        print(f"[CDN] 已启用: {cdn_base} (版本: {version})")
    else:
        print("[CDN] 未配置，使用本地静态资源")


def url_for_static(filename):
    """
    生成带版本号的静态资源URL（支持CDN）

    使用方法:
        在模板中: {{ url_for_static('css/style.css') }}
    """
    from flask import url_for

    # 获取版本号
    version = current_app.config.get('STATIC_VERSION', 'v1')

    # 如果配置了CDN，使用CDN URL
    cdn_url = current_app.config.get('CDN_URL', '')

    if cdn_url:
        # 返回CDN URL（带版本号参数）
        return f"{cdn_url.rstrip('/')}/static/{filename}?v={version}"
    else:
        # 返回本地URL（Flask会自动处理）
        return url_for('static', filename=filename, v=version)


# ==================== 热点数据自动缓存 ====================

class HotDataCache:
    """热点数据缓存管理器"""

    def __init__(self, cache_instance=None):
        self.cache = cache_instance or get_cache()
        self.access_counts = {}  # 访问计数
        self.lock = threading.Lock()

    def record_access(self, data_type, data_id):
        """记录数据访问（用于识别热点）"""
        key = f"{data_type}:{data_id}"

        with self.lock:
            if key not in self.access_counts:
                self.access_counts[key] = {
                    'count': 0,
                    'last_access': time.time()
                }

            self.access_counts[key]['count'] += 1
            self.access_counts[key]['last_access'] = time.time()

            # 如果访问次数达到阈值，自动延长缓存时间
            count = self.access_counts[key]['count']
            if count >= 10 and count % 10 == 0:  # 每10次访问检查一次
                cache_key = f"hot:{key}"
                if self.cache.exists(cache_key):
                    # 延长缓存时间到1小时
                    existing = self.cache.get(cache_key)
                    if existing:
                        self.cache.set(cache_key, existing, 3600)

    def get_hot_data(self, data_type, data_id, factory=None):
        """获取热点数据（优先从缓存）"""
        cache_key = f"hot:{data_type}:{data_id}"

        # 记录访问
        self.record_access(data_type, data_id)

        # 尝试从缓存获取
        data = self.cache.get(cache_key)
        if data is not None:
            return data

        # 缓存未命中，调用工厂函数
        if factory:
            data = factory()
            if data is not None:
                # 根据访问频率设置不同的缓存时间
                access_key = f"{data_type}:{data_id}"
                access_info = self.access_counts.get(access_key, {})
                count = access_info.get('count', 0)

                if count >= 50:
                    timeout = 1800  # 高频访问：30分钟
                elif count >= 20:
                    timeout = 900   # 中频：15分钟
                else:
                    timeout = 300   # 低频：5分钟

                self.cache.set(cache_key, data, timeout)

            return data

        return None

    def invalidate_hot_data(self, data_type, data_id=None):
        """使热点数据失效"""
        if data_id:
            cache_key = f"hot:{data_type}:{data_id}"
            self.cache.delete(cache_key)
        else:
            # 使该类型所有热点数据失效
            self.cache.invalidate_pattern(f"hot:{data_type}:*")

    def get_top_hot_data(self, limit=10):
        """获取最热门的数据（按访问量排序）"""
        with self.lock:
            sorted_data = sorted(
                self.access_counts.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )[:limit]

            return [
                {
                    'key': key,
                    'type': key.split(':')[0],
                    'id': key.split(':')[1],
                    **info
                }
                for key, info in sorted_data
            ]

    def clear_access_stats(self):
        """清空访问统计"""
        with self.lock:
            self.access_counts.clear()


# 全局热点数据缓存实例
hot_data_cache = None


def init_hot_data_cache():
    """初始化热点数据缓存"""
    global hot_data_cache
    hot_data_cache = HotDataCache(get_cache())
    return hot_data_cache


# ==================== 文件存储优化系统 ====================

class StorageBackend:
    """存储后端抽象基类"""
    
    def upload_file(self, file_obj, file_path, **kwargs):
        raise NotImplementedError
    
    def download_file(self, file_path):
        raise NotImplementedError
    
    def delete_file(self, file_path):
        raise NotImplementedError
    
    def file_exists(self, file_path):
        raise NotImplementedError
    
    def get_file_url(self, file_path):
        raise NotImplementedError
    
    def get_file_info(self, file_path):
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """本地文件系统存储"""
    
    def __init__(self, base_path=None):
        self.base_path = Path(base_path) if base_path else UPLOAD_DIR
        self.base_path.mkdir(parents=True, exist_ok=True)
        print(f"[本地存储] 初始化完成: {self.base_path}")
    
    def _get_full_path(self, file_path):
        """获取完整路径"""
        if isinstance(file_path, str):
            file_path = Path(file_path)
        
        # 如果是相对路径，拼接基础路径
        if not file_path.is_absolute():
            full_path = self.base_path / file_path
        else:
            full_path = file_path
        
        return full_path
    
    def upload_file(self, file_obj, file_path, **kwargs):
        """
        上传文件到本地存储
        
        参数:
            file_obj: 文件对象（FileStorage或文件路径）
            file_path: 存储路径（相对或绝对）
            **kwargs: 额外参数
                - create_dirs: 是否自动创建目录（默认True）
        """
        full_path = self._get_full_path(file_path)
        
        # 自动创建目录
        if kwargs.get('create_dirs', True):
            full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        if hasattr(file_obj, 'save'):
            # Flask FileStorage对象
            file_obj.save(str(full_path))
        elif hasattr(file_obj, 'read'):
            # 文件对象
            with open(full_path, 'wb') as f:
                f.write(file_obj.read())
        elif isinstance(file_obj, (str, Path)):
            # 文件路径（复制）
            import shutil
            shutil.copy2(str(file_obj), str(full_path))
        else:
            raise ValueError(f"不支持的文件对象类型: {type(file_obj)}")
        
        return {
            'success': True,
            'path': str(full_path),
            'size': full_path.stat().st_size,
            'url': f'/uploads/{full_path.relative_to(UPLOAD_DIR)}' if UPLOAD_DIR in full_path.parents else f'/static/uploads/{file_path}'
        }
    
    def download_file(self, file_path):
        """下载/读取文件"""
        full_path = self._get_full_path(file_path)
        
        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        return open(full_path, 'rb')
    
    def delete_file(self, file_path):
        """删除文件"""
        full_path = self._get_full_path(file_path)
        
        if full_path.exists():
            full_path.unlink()
            return {'success': True}
        
        return {'success': False, 'error': '文件不存在'}
    
    def file_exists(self, file_path):
        """检查文件是否存在"""
        full_path = self._get_full_path(file_path)
        return full_path.exists()
    
    def get_file_url(self, file_path):
        """获取文件访问URL"""
        full_path = self._get_full_path(file_path)
        
        try:
            relative_path = full_path.relative_to(UPLOAD_DIR)
            return url_for('static', filename=f'uploads/{relative_path}')
        except ValueError:
            return f'/static/uploads/{file_path}'
    
    def get_file_info(self, file_path):
        """获取文件信息"""
        full_path = self._get_full_path(file_path)
        
        if not full_path.exists():
            return None
        
        stat = full_path.stat()
        return {
            'name': full_path.name,
            'path': str(full_path),
            'size': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'extension': full_path.suffix.lower()
        }


class OSSStorage(StorageBackend):
    """阿里云OSS/S3兼容对象存储"""
    
    def __init__(self, access_key_id=None, access_key_secret=None,
                 endpoint=None, bucket_name=None):
        """
        初始化OSS存储
        
        参数:
            access_key_id: Access Key ID
            access_key_secret: Access Key Secret
            endpoint: OSS端点（如 https://oss-cn-hangzhou.aliyuncs.com）
            bucket_name: 存储桶名称
        """
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")
        
        self.access_key_id = access_key_id or os.getenv('OSS_ACCESS_KEY_ID')
        self.access_key_secret = access_key_secret or os.getenv('OSS_ACCESS_KEY_SECRET')
        self.endpoint = endpoint or os.getenv('OSS_ENDPOINT')
        self.bucket_name = bucket_name or os.getenv('OSS_BUCKET_NAME')
        self.client = None
        self._available = False
        
        # 尝试初始化OSS客户端
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化OSS客户端"""
        try:
            import oss2
            
            if not all([self.access_key_id, self.access_key_secret, 
                       self.endpoint, self.bucket_name]):
                print("[OSS] 配置不完整，将使用本地存储作为回退")
                return
            
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.client = oss2.Bucket(auth, self.endpoint, self.bucket_name)
            
            # 测试连接
            self.client.get_bucket_info()
            self._available = True
            print(f"[OSS] 连接成功: {self.bucket_name}")
            
        except ImportError:
            print("[OSS] oss2库未安装，请运行: pip install oss2")
        except Exception as e:
            print(f"[OSS] 连接失败: {e}")
    
    def upload_file(self, file_obj, object_key, **kwargs):
        """
        上传文件到OSS
        
        参数:
            file_obj: 文件对象
            object_key: 对象键（如 uploads/2024/01/file.txt）
            **kwargs: 
                - content_type: MIME类型
                - headers: 自定义头
        """
        if not self._available:
            raise RuntimeError("OSS未配置或连接失败")
        
        # 读取文件内容
        if hasattr(file_obj, 'read'):
            data = file_obj.read()
        elif isinstance(file_obj, (str, Path)):
            with open(str(file_obj), 'rb') as f:
                data = f.read()
        else:
            raise ValueError(f"不支持的文件对象类型")
        
        # 上传选项
        headers = kwargs.get('headers', {})
        if kwargs.get('content_type'):
            headers['Content-Type'] = kwargs['content_type']
        
        # 执行上传
        result = self.client.put_object(object_key, data, headers=headers)
        
        return {
            'success': True,
            'key': object_key,
            'url': f"https://{self.bucket_name}.{self.endpoint.replace('https://', '').replace('http://', '')}/{object_key}",
            'etag': result.etag,
            'size': len(data)
        }
    
    def download_file(self, object_key):
        """从OSS下载文件"""
        if not self._available:
            raise RuntimeError("OSS未配置或连接失败")
        
        result = self.client.get_object(object_key)
        return result
    
    def delete_file(self, object_key):
        """删除OSS对象"""
        if not self._available:
            raise RuntimeError("OSS未配置或连接失败")
        
        try:
            self.client.delete_object(object_key)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def file_exists(self, object_key):
        """检查对象是否存在"""
        if not self._available:
            return False
        
        try:
            self.client.head_object(object_key)
            return True
        except:
            return False
    
    def get_file_url(self, object_key, expires=3600):
        """生成带签名的临时URL"""
        if not self._available:
            return None
        
        return self.client.sign_url('GET', object_key, expires)
    
    def get_file_info(self, object_key):
        """获取对象元数据"""
        if not self._available:
            return None
        
        try:
            meta = self.client.head_object(object_key)
            return {
                'key': object_key,
                'size': meta.content_length,
                'content_type': meta.content_type,
                'last_modified': meta.last_modified,
                'etag': meta.etag
            }
        except:
            return None


class UnifiedStorageManager:
    """统一存储管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化存储系统"""
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")
        
        storage_type = os.getenv('STORAGE_TYPE', 'local').lower()
        
        # 尝试使用OSS
        if storage_type == 'oss' or storage_type == 's3':
            self.oss_storage = OSSStorage()
            if self.oss_storage._available:
                self.primary = self.oss_storage
                self.fallback = LocalStorage()
                self.storage_type = "oss"
                print(f"[存储系统] 使用 OSS 主存储 + 本地回退")
            else:
                self.primary = LocalStorage()
                self.fallback = None
                self.storage_type = "local"
                print(f"[存储系统] OSS不可用，回退到本地存储")
        else:
            self.primary = LocalStorage()
            self.fallback = None
            self.storage_type = "local"
            print(f"[存储系统] 使用本地存储")
        
        # 分片上传临时目录
        self.chunk_temp_dir = DATA_DIR / "chunks"
        self.chunk_temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 断点续传记录
        self.upload_sessions = {}
        self.sessions_lock = threading.Lock()
        
        print(f"[存储系统] 初始化完成 (主存储: {self.storage_type})")
    
    def upload(self, file_obj, file_path, use_oss=False, **kwargs):
        """
        统一上传接口
        
        参数:
            file_obj: 文件对象
            file_path: 存储路径
            use_oss: 强制使用OSS（如果可用）
            **kwargs: 传递给后端的额外参数
        """
        try:
            # 如果强制使用OSS且可用
            if use_oss and self.storage_type == 'oss':
                return self.primary.upload_file(file_obj, file_path, **kwargs)
            
            # 使用主存储
            result = self.primary.upload_file(file_obj, file_path, **kwargs)
            result['storage'] = self.storage_type
            return result
            
        except Exception as e:
            print(f"[存储] 主存储上传失败: {e}")
            
            # 回退到备用存储
            if self.fallback:
                print(f"[存储] 回退到备用存储...")
                result = self.fallback.upload_file(file_obj, file_path, **kwargs)
                result['storage'] = 'local_fallback'
                result['fallback_reason'] = str(e)
                return result
            
            raise
    
    def download(self, file_path):
        """统一下载接口"""
        return self.primary.download_file(file_path)
    
    def delete(self, file_path):
        """统一删除接口"""
        return self.primary.delete_file(file_path)
    
    def exists(self, file_path):
        """检查文件是否存在"""
        return self.primary.file_exists(file_path)
    
    def get_url(self, file_path):
        """获取文件URL"""
        return self.primary.get_file_url(file_path)
    
    def get_info(self, file_path):
        """获取文件信息"""
        return self.primary.get_file_info(file_path)


# 全局存储管理器实例
storage_manager = None


def init_storage():
    """初始化全局存储管理器"""
    global storage_manager
    storage_manager = UnifiedStorageManager()
    return storage_manager


def get_storage():
    """获取存储实例（延迟初始化）"""
    global storage_manager
    if storage_manager is None:
        init_storage()
    return storage_manager


# ==================== 图片处理系统 ====================

class ImageProcessor:
    """图片压缩与格式转换处理器"""
    
    SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    OUTPUT_QUALITY = 85  # 默认压缩质量
    MAX_DIMENSION = 1920  # 最大边长限制
    
    @classmethod
    def is_image(cls, filename):
        """判断是否为图片文件"""
        ext = Path(filename).suffix.lower()
        return ext in cls.SUPPORTED_FORMATS
    
    @classmethod
    def process_image(cls, input_path, output_path=None, **options):
        """
        处理图片（压缩+格式转换+缩放）
        
        参数:
            input_path: 输入图片路径
            output_path: 输出路径（None则覆盖原文件）
            **options:
                - quality: 压缩质量 (1-100)，默认85
                - format: 输出格式 ('JPEG', 'PNG', 'WEBP')
                - max_width: 最大宽度
                - max_height: 最大高度
                - thumbnail: 是否生成缩略图
                - thumbnail_size: 缩略图尺寸 (width, height)
        
        返回:
            dict: 处理结果信息
        """
        try:
            from PIL import Image
        except ImportError:
            print("[图片处理] PIL/Pillow未安装，跳过处理")
            return {'success': False, 'error': 'Pillow未安装'}
        
        input_path = Path(input_path)
        if not input_path.exists():
            return {'success': False, 'error': '输入文件不存在'}
        
        # 打开图片
        img = Image.open(input_path)
        original_format = img.format
        original_size = input_path.stat().st_size
        
        # 处理选项
        quality = options.get('quality', cls.OUTPUT_QUALITY)
        output_format = options.get('format', original_format or 'JPEG')
        max_width = options.get('max_width', cls.MAX_DIMENSION)
        max_height = options.get('max_height', cls.MAX_DIMENSION)
        
        # 转换为RGB模式（JPEG不支持透明度）
        if output_format.upper() in ['JPEG', 'JPG']:
            if img.mode in ['RGBA', 'P']:
                img = img.convert('RGB')
        
        # 计算新尺寸（保持宽高比）
        width, height = img.size
        if width > max_width or height > max_height:
            ratio = min(max_width / width, max_height / height)
            new_size = (int(width * ratio), int(height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # 确定输出路径
        if output_path is None:
            output_path = input_path
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存处理后的图片
        save_options = {}
        if output_format.upper() in ['JPEG', 'JPG']:
            save_options['quality'] = quality
            save_options['optimize'] = True
        elif output_format.upper() == 'PNG':
            save_options['optimize'] = True
        elif output_format.upper() == 'WEBP':
            save_options['quality'] = quality
        
        img.save(str(output_path), format=output_format, **save_options)
        
        output_size = output_path.stat().st_size
        compression_ratio = (1 - output_size / original_size) * 100 if original_size > 0 else 0
        
        result = {
            'success': True,
            'input_path': str(input_path),
            'output_path': str(output_path),
            'original_size': original_size,
            'output_size': output_size,
            'compression_ratio': round(compression_ratio, 2),
            'original_dimensions': (width, height),
            'new_dimensions': img.size,
            'format': output_format
        }
        
        # 生成缩略图（可选）
        if options.get('thumbnail', False):
            thumb_size = options.get('thumbnail_size', (200, 200))
            thumbnail = img.copy()
            thumbnail.thumbnail(thumb_size, Image.LANCZOS)
            
            thumb_path = output_path.with_suffix(f'.thumb{output_path.suffix}')
            thumbnail.save(str(thumb_path), format=output_format, **save_options)
            result['thumbnail_path'] = str(thumb_path)
            result['thumbnail_size'] = thumb_path.stat().st_size
        
        print(f"[图片处理] 完成: {input_path.name} "
              f"({original_size//1024}KB → {output_size//1024}KB, "
              f"压缩率: {compression_ratio:.1f}%)")
        
        return result
    
    @classmethod
    def generate_thumbnail(cls, image_path, size=(200, 200), output_dir=None):
        """
        生成缩略图
        
        参数:
            image_path: 原图路径
            size: 缩略图尺寸 (width, height)
            output_dir: 输出目录（默认与原图同目录）
        
        返回:
            dict: 包含缩略图路径的信息
        """
        image_path = Path(image_path)
        
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            thumb_path = output_dir / f"{image_path.stem}_thumb{image_path.suffix}"
        else:
            thumb_path = image_path.with_suffix(f'.thumb{image_path.suffix}')
        
        result = cls.process_image(
            image_path,
            output_path=thumb_path,
            thumbnail=True,
            thumbnail_size=size
        )
        
        return result


# ==================== 分片上传管理器 ====================

class ChunkUploadManager:
    """分片上传管理器"""

    CHUNK_SIZE = 5 * 1024 * 1024  # 默认分片大小：5MB

    def __init__(self):
        self.TEMP_DIR = DATA_DIR / "chunks"
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self.sessions = {}  # 上传会话
        self.lock = threading.Lock()
        print(f"[分片上传] 初始化完成，分片大小: {self.CHUNK_SIZE // 1024 // 1024}MB")
    
    def create_session(self, file_id, filename, total_size, chunk_count, file_hash=None):
        """
        创建分片上传会话
        
        参数:
            file_id: 文件唯一标识
            filename: 原始文件名
            total_size: 文件总大小（字节）
            chunk_count: 总分片数
            file_hash: 文件MD5（用于完整性校验）
        """
        session = {
            'id': file_id,
            'filename': filename,
            'total_size': total_size,
            'chunk_count': chunk_count,
            'file_hash': file_hash,
            'uploaded_chunks': [],
            'created_at': datetime.now().isoformat(),
            'status': 'uploading',
            'temp_dir': self.TEMP_DIR / file_id
        }
        
        # 创建临时目录
        session['temp_dir'].mkdir(parents=True, exist_ok=True)
        
        with self.lock:
            self.sessions[file_id] = session
        
        print(f"[分片上传] 创建会话: {file_id}, 文件: {filename}, "
              f"大小: {total_size // 1024 // 1024}MB, 分片数: {chunk_count}")
        
        return session
    
    def upload_chunk(self, file_id, chunk_index, chunk_data):
        """
        上传单个分片
        
        参数:
            file_id: 会话ID
            chunk_index: 分片索引（从0开始）
            chunk_data: 分片数据（bytes）
        """
        with self.lock:
            session = self.sessions.get(file_id)
        
        if not session:
            return {'success': False, 'error': '会话不存在'}
        
        if session['status'] != 'uploading':
            return {'success': False, 'error': f'会话状态异常: {session["status"]}'}
        
        # 保存分片到临时目录
        chunk_path = session['temp_dir'] / f"chunk_{chunk_index}"
        with open(chunk_path, 'wb') as f:
            f.write(chunk_data)
        
        chunk_size = len(chunk_data)
        
        with self.lock:
            if chunk_index not in session['uploaded_chunks']:
                session['uploaded_chunks'].append(chunk_index)
        
        progress = len(session['uploaded_chunks']) / session['chunk_count'] * 100
        
        print(f"[分片上传] {file_id}: 分片 {chunk_index + 1}/{session['chunk_count']} "
              f"({progress:.1f}%)")
        
        return {
            'success': True,
            'chunk_index': chunk_index,
            'chunk_size': chunk_size,
            'uploaded_count': len(session['uploaded_chunks']),
            'total_chunks': session['chunk_count'],
            'progress': round(progress, 2)
        }
    
    def get_upload_progress(self, file_id):
        """获取上传进度"""
        with self.lock:
            session = self.sessions.get(file_id)
        
        if not session:
            return {'success': False, 'error': '会话不存在'}
        
        uploaded = len(session['uploaded_chunks'])
        total = session['chunk_count']
        
        return {
            'success': True,
            'file_id': file_id,
            'filename': session['filename'],
            'uploaded_chunks': uploaded,
            'total_chunks': total,
            'progress': round(uploaded / total * 100, 2) if total > 0 else 0,
            'status': session['status'],
            'created_at': session['created_at']
        }
    
    def merge_chunks(self, file_id, target_path=None):
        """
        合并所有分片
        
        参数:
            file_id: 会话ID
            target_path: 目标保存路径（None则使用默认路径）
        
        返回:
            dict: 合并结果
        """
        with self.lock:
            session = self.sessions.get(file_id)
        
        if not session:
            return {'success': False, 'error': '会话不存在'}
        
        # 检查是否所有分片都已上传
        missing = set(range(session['chunk_count'])) - set(session['uploaded_chunks'])
        if missing:
            return {
                'success': False,
                'error': f'缺少分片: {sorted(missing)}',
                'missing_chunks': sorted(missing)
            }
        
        # 确定目标路径
        if target_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = re.sub(r'[^\w\-_.]', '_', session['filename'])
            target_path = UPLOAD_DIR / timestamp / safe_filename
        else:
            target_path = Path(target_path)
        
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 按顺序合并分片
        print(f"[分片合并] 开始合并: {file_id}")
        merged_size = 0
        
        with open(target_path, 'wb') as outfile:
            for i in range(session['chunk_count']):
                chunk_path = session['temp_dir'] / f"chunk_{i}"
                
                if not chunk_path.exists():
                    return {
                        'success': False,
                        'error': f'分片文件丢失: chunk_{i}',
                        'chunk_index': i
                    }
                
                with open(chunk_path, 'rb') as infile:
                    data = infile.read()
                    outfile.write(data)
                    merged_size += len(data)
        
        # 校验文件大小
        expected_size = session['total_size']
        if abs(merged_size - expected_size) > 1024:  # 允许1KB误差
            print(f"[分片合并] 警告: 大小不匹配 (期望: {expected_size}, 实际: {merged_size})")
        
        # 可选：校验MD5
        if session.get('file_hash'):
            actual_hash = calculate_file_hash(target_path)
            if actual_hash != session['file_hash']:
                target_path.unlink()  # 删除损坏的文件
                return {
                    'success': False,
                    'error': '文件完整性校验失败（MD5不匹配）',
                    'expected_hash': session['file_hash'],
                    'actual_hash': actual_hash
                }
        
        # 更新会话状态
        with self.lock:
            session['status'] = 'completed'
            session['merged_path'] = str(target_path)
            session['merged_at'] = datetime.now().isoformat()
        
        # 清理临时分片文件（异步）
        self._cleanup_session_files(file_id)
        
        print(f"[分片合并] 完成: {target_path.name} ({merged_size // 1024 // 1024}MB)")
        
        return {
            'success': True,
            'file_id': file_id,
            'path': str(target_path),
            'size': merged_size,
            'filename': session['filename']
        }
    
    def cancel_upload(self, file_id):
        """取消上传并清理资源"""
        with self.lock:
            session = self.sessions.pop(file_id, None)
        
        if not session:
            return {'success': False, 'error': '会话不存在'}
        
        # 更新状态
        session['status'] = 'cancelled'
        
        # 清理临时文件
        self._cleanup_session_files(file_id)
        
        print(f"[分片上传] 已取消: {file_id}")
        
        return {'success': True, 'message': '上传已取消'}
    
    def resume_upload(self, file_id):
        """
        断点续传：获取已上传的分片列表
        
        用于客户端恢复中断的上传
        """
        with self.lock:
            session = self.sessions.get(file_id)
        
        if not session:
            return {'success': False, 'error': '会话不存在'}
        
        if session['status'] == 'completed':
            return {'success': False, 'error': '上传已完成', 'merged_path': session.get('merged_path')}
        
        return {
            'success': True,
            'file_id': file_id,
            'filename': session['filename'],
            'total_size': session['total_size'],
            'chunk_count': session['chunk_count'],
            'uploaded_chunks': sorted(session['uploaded_chunks']),
            'missing_chunks': sorted(
                set(range(session['chunk_count'])) - set(session['uploaded_chunks'])
            ),
            'status': session['status'],
            'can_resume': session['status'] == 'uploading'
        }
    
    def _cleanup_session_files(self, file_id):
        """清理会话的临时文件"""
        temp_dir = self.TEMP_DIR / file_id
        
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"[清理] 已删除临时目录: {temp_dir}")
    
    def cleanup_expired_sessions(self, hours=24):
        """清理过期的上传会话"""
        expired = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            for file_id, session in self.sessions.items():
                created_at = datetime.fromisoformat(session['created_at'])
                if created_at < cutoff_time and session['status'] != 'uploading':
                    expired.append(file_id)
        
        for file_id in expired:
            self.cancel_upload(file_id)
        
        if expired:
            print(f"[分片上传] 清理了 {len(expired)} 个过期会话")
        
        return len(expired)


# 全局分片上传管理器
chunk_manager = None


def init_chunk_manager():
    """初始化分片上传管理器"""
    global chunk_manager
    chunk_manager = ChunkUploadManager()
    return chunk_manager


def get_chunk_manager():
    """获取分片上传管理器"""
    global chunk_manager
    if chunk_manager is None:
        init_chunk_manager()
    return chunk_manager


# 计算文件的MD5哈希值
def calculate_file_hash(file_path):
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_file_category(filename):
    """根据文件扩展名自动识别文件分类"""
    ext = os.path.splitext(filename)[1].lower()
    
    category_mapping = {
        '图片处理': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico', '.tiff', '.psd', '.ai', '.eps'],
        '文件处理': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.odt', '.ods', '.odp'],
        '娱乐游戏': ['.html', '.htm', '.swf', '.fla', '.unity3d', '.unity'],
        '开发工具': ['.py', '.js', '.java', '.c', '.cpp', '.h', '.php', '.rb', '.go', '.rs', '.ts', '.jsx', '.vue', '.css', '.scss', '.less', '.json', '.xml', '.yaml', '.yml', '.sql', '.sh', '.bat', '.ps1'],
        '通用工具': ['.zip', '.rar', '.7z', '.tar', '.gz', '.exe', '.msi', '.dmg', '.apk', '.ipa', '.deb', '.rpm'],
        '生活工具': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.3gp', '.m4v']
    }
    
    for category, extensions in category_mapping.items():
        if ext in extensions:
            return category
    
    return '通用工具'

def get_or_create_category(conn, category_name, user_id):
    """获取或创建分类"""
    category = conn.execute('SELECT id FROM categories WHERE name = ? AND user_id = ?', (category_name, user_id)).fetchone()
    if category:
        return category['id']
    
    cursor = conn.cursor()
    cursor.execute('INSERT INTO categories (name, user_id) VALUES (?, ?)', (category_name, user_id))
    conn.commit()
    return cursor.lastrowid

def assign_category_to_file(conn, file_id, category_name, user_id):
    """为文件分配分类"""
    category_id = get_or_create_category(conn, category_name, user_id)
    conn.execute('INSERT OR IGNORE INTO file_categories (file_id, category_id) VALUES (?, ?)', (file_id, category_id))
    conn.commit()

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "db.sqlite"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

# 静态文件缓存配置
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = timedelta(days=30)  # 静态文件默认缓存30天

# 注册CDN辅助函数到模板上下文
@app.context_processor
def inject_cdn_helpers():
    """向模板注入CDN辅助函数"""
    return {
        'url_for_static': url_for_static,
        'cdn_enabled': app.config.get('USE_CDN', False),
        'cdn_url': app.config.get('CDN_URL', ''),
        'static_version': app.config.get('STATIC_VERSION', 'v1'),
    }

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



# ==================== 数据库查询性能监控 ====================

class QueryMonitor:
    """数据库查询性能监控器"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.slow_queries = []
                    cls._instance.query_count = 0
                    cls._instance.total_time = 0.0
                    cls._instance.slow_threshold = 0.5  # 慢查询阈值（秒）
        return cls._instance

    def log_query(self, sql, params, duration):
        """记录查询"""
        self.query_count += 1
        self.total_time += duration

        if duration > self.slow_threshold:
            query_info = {
                'timestamp': datetime.now().isoformat(),
                'sql': sql[:200],  # 截断过长的SQL
                'params': str(params)[:100] if params else None,
                'duration': round(duration, 4),
                'traceback': ''
            }
            import traceback
            query_info['traceback'] = ''.join(traceback.format_stack()[-5:-1])
            self.slow_queries.append(query_info)

            # 只保留最近100条慢查询
            if len(self.slow_queries) > 100:
                self.slow_queries = self.slow_queries[-100:]

            print(f"[慢查询警告] 耗时 {duration:.3f}s: {sql[:80]}...")

    def get_stats(self):
        """获取统计信息"""
        return {
            'total_queries': self.query_count,
            'total_time': round(self.total_time, 4),
            'avg_time': round(self.total_time / max(self.query_count, 1), 4),
            'slow_query_count': len(self.slow_queries),
            'recent_slow_queries': self.slow_queries[-10:]  # 最近10条慢查询
        }

    def reset_stats(self):
        """重置统计"""
        self.slow_queries = []
        self.query_count = 0
        self.total_time = 0.0


class MonitoredConnection(sqlite3.Connection):
    """带监控的数据库连接"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor = QueryMonitor()

    def execute(self, sql, parameters=None):
        start_time = time.time()
        try:
            if parameters:
                cursor = super().execute(sql, parameters)
            else:
                cursor = super().execute(sql)

            duration = time.time() - start_time
            self.monitor.log_query(sql, parameters, duration)

            return cursor
        except Exception as e:
            duration = time.time() - start_time
            print(f"[查询错误] 耗时 {duration:.3f}s: {sql[:80]}...")
            raise


def get_db():
    """获取数据库连接（带性能监控）"""
    if 'db' not in g:
        g.db = sqlite3.connect(
            str(DB_FILE),
            factory=MonitoredConnection,
            timeout=30,  # 30秒超时
            check_same_thread=False  # 允许跨线程使用
        )
        g.db.row_factory = sqlite3.Row

        # 启用WAL模式提升并发性能
        g.db.execute('PRAGMA journal_mode=WAL')

        # 设置缓存大小（负值表示KB）
        g.db.execute('PRAGMA cache_size=-10000')  # 10MB缓存

        # 设置临时存储为内存
        g.db.execute('PRAGMA temp_store=MEMORY')

    return g.db


@app.teardown_appcontext
def close_db(exception):
    """请求结束后关闭数据库连接"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


# 全局监控器实例（用于API访问）
query_monitor = QueryMonitor()


# ==================== 数据库连接池 ====================

class DatabaseConnectionPool:
    """SQLite数据库连接池（线程安全）"""

    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._local = threading.local()
        self._lock = threading.Lock()
        self._connections = []
        self._created_count = 0
        print(f"[连接池] 初始化完成，池大小: {pool_size}")

    def get_connection(self):
        """从池中获取连接"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            with self._lock:
                if len(self._connections) > 0:
                    conn = self._connections.pop()
                    try:
                        conn.execute('SELECT 1')  # 测试连接是否有效
                        self._local.connection = conn
                        return conn
                    except:
                        pass

            # 创建新连接
            conn = sqlite3.connect(
                str(self.db_path),
                factory=MonitoredConnection,
                timeout=30,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            self._optimize_connection(conn)
            self._local.connection = conn
            self._created_count += 1

        return self._local.connection

    def _optimize_connection(self, conn):
        """优化连接配置"""
        # WAL模式 - 提升并发读写性能
        conn.execute('PRAGMA journal_mode=WAL')

        # 外键约束检查
        conn.execute('PRAGMA foreign_keys=ON')

        # 同步模式：NORMAL（平衡性能和安全）
        conn.execute('PRAGMA synchronous=NORMAL')

        # 缓存大小：10MB
        conn.execute('PRAGMA cache_size=-10000')

        # 临时表使用内存
        conn.execute('PRAGMA temp_store=MEMORY')

        # 忙等待超时：5秒
        conn.execute('PRAGMA busy_timeout=5000')

        # MMAP大小：20MB（加速大查询）
        try:
            conn.execute('PRAGMA mmap_size=20971520')
        except:
            pass

    def return_connection(self, conn):
        """归还连接到池中"""
        if hasattr(self._local, 'connection'):
            self._local.connection = None

        with self._lock:
            if len(self._connections) < self.pool_size:
                self._connections.append(conn)
            else:
                conn.close()

    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except:
                    pass
            self._connections.clear()

        self._local.connection = None
        print("[连接池] 所有连接已关闭")

    def get_stats(self):
        """获取连接池统计信息"""
        return {
            'pool_size': self.pool_size,
            'available_connections': len(self._connections),
            'total_created': self._created_count,
            'db_path': str(self.db_path)
        }


# 全局连接池实例
db_pool = None


def init_db_pool():
    """初始化数据库连接池"""
    global db_pool
    ensure_dirs()
    db_pool = DatabaseConnectionPool(DB_FILE, pool_size=10)
    print(f"[数据库] 连接池已就绪")
    return db_pool



def init_db():
    ensure_dirs()
    # 初始化时使用直接连接（不使用Flask g对象）
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
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
        
        # 检查并添加view_count字段到现有files表
        try:
            conn.execute('ALTER TABLE files ADD COLUMN view_count INTEGER DEFAULT 0')
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
        
        # 创建文件分享链接表
        conn.execute('''CREATE TABLE IF NOT EXISTS file_shares (
                        id TEXT PRIMARY KEY,
                        file_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        share_code TEXT NOT NULL UNIQUE,
                        expires_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        access_count INTEGER DEFAULT 0,
                        FOREIGN KEY (file_id) REFERENCES files (id),
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )''')
        
        # 为files表添加is_deleted字段
        try:
            conn.execute('ALTER TABLE files ADD COLUMN is_deleted INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute('ALTER TABLE files ADD COLUMN deleted_at TIMESTAMP')
        except sqlite3.OperationalError:
            pass
        
        # 创建回收站表
        conn.execute('''CREATE TABLE IF NOT EXISTS trash (
                        id TEXT PRIMARY KEY,
                        file_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        stored_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER,
                        file_type TEXT,
                        folder_id TEXT,
                        original_folder_name TEXT,
                        deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expire_at TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )''')

        conn.commit()

    except Exception as e:
        print(f"[数据库] 初始化错误: {e}")
        conn.rollback()
        raise

    # ==================== 数据库优化 - 索引创建 ====================
    try:
        create_database_indexes(conn)
    except Exception as e:
        print(f"[数据库] 索引创建警告: {e}")

    conn.close()


def create_database_indexes(conn):
    """创建数据库索引以优化查询性能"""
    print("[数据库] 正在优化索引...")

    indexes = [
        # users表索引
        ("idx_users_email", "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"),
        ("idx_users_username", "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"),

        # files表索引（高频查询字段）
        ("idx_files_user_id", "CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id)"),
        ("idx_files_folder_id", "CREATE INDEX IF NOT EXISTS idx_files_folder_id ON files(folder_id)"),
        ("idx_files_filename", "CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename)"),
        ("idx_files_is_deleted", "CREATE INDEX IF NOT EXISTS idx_files_is_deleted ON files(is_deleted)"),
        ("idx_files_created_at", "CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at)"),
        ("idx_files_user_folder", "CREATE INDEX IF NOT EXISTS idx_files_user_folder ON files(user_id, folder_id)"),

        # folders表索引
        ("idx_folders_user_id", "CREATE INDEX IF NOT EXISTS folders_user_id ON folders(user_id)"),
        ("idx_folders_parent_id", "CREATE INDEX IF NOT EXISTS folders_parent_id ON folders(parent_id)"),

        # access_logs表索引
        ("idx_access_logs_file_id", "CREATE INDEX IF NOT EXISTS idx_access_logs_file_id ON access_logs(file_id)"),
        ("idx_access_logs_user_id", "CREATE INDEX IF NOT EXISTS idx_access_logs_user_id ON access_logs(user_id)"),
        ("idx_access_logs_time", "CREATE INDEX IF NOT EXISTS idx_access_logs_time ON access_logs(access_time)"),

        # operation_logs表索引
        ("idx_op_logs_user_id", "CREATE INDEX IF NOT EXISTS idx_op_logs_user_id ON operation_logs(user_id)"),
        ("idx_op_logs_action", "CREATE INDEX IF NOT EXISTS idx_op_logs_action ON operation_logs(action)"),
        ("idx_op_logs_time", "CREATE INDEX IF NOT EXISTS idx_op_logs_time ON operation_logs(created_at)"),

        # likes表索引
        ("idx_likes_file_user", "CREATE INDEX IF NOT EXISTS idx_likes_file_user ON likes(file_id, user_id)"),
        ("idx_likes_user_id", "CREATE INDEX IF NOT EXISTS idx_likes_user_id ON likes(user_id)"),

        # favorites表索引
        ("idx_fav_file_user", "CREATE INDEX IF NOT EXISTS idx_fav_file_user ON favorites(file_id, user_id)"),
        ("idx_fav_user_id", "CREATE INDEX IF NOT EXISTS idx_fav_user_id ON favorites(user_id)"),

        # tags表索引
        ("idx_tags_name_user", "CREATE INDEX IF NOT EXISTS idx_tags_name_user ON tags(name, user_id)"),
        ("idx_tags_user_id", "CREATE INDEX IF NOT EXISTS idx_tags_user_id ON tags(user_id)"),

        # file_tags关联表索引
        ("idx_file_tags_file_id", "CREATE INDEX IF NOT EXISTS idx_file_tags_file_id ON file_tags(file_id)"),
        ("idx_file_tags_tag_id", "CREATE INDEX IF NOT EXISTS idx_file_tags_tag_id ON file_tags(tag_id)"),

        # file_categories关联表索引
        ("idx_fc_file_id", "CREATE INDEX IF NOT EXISTS idx_fc_file_id ON file_categories(file_id)"),
        ("idx_fc_category_id", "CREATE INDEX IF NOT EXISTS idx_fc_category_id ON file_categories(category_id)"),

        # ai_contents表索引
        ("idx_ai_contents_user", "CREATE INDEX IF NOT EXISTS idx_ai_contents_user ON ai_contents(user_id)"),
        ("idx_ai_contents_function", "CREATE INDEX IF NOT EXISTS idx_ai_contents_function ON ai_contents(ai_function)"),
        ("idx_ai_contents_created", "CREATE INDEX IF NOT EXISTS idx_ai_contents_created ON ai_contents(created_at)"),

        # file_shares表索引
        ("idx_shares_share_code", "CREATE INDEX IF NOT EXISTS idx_shares_share_code ON file_shares(share_code)"),
        ("idx_shares_user_id", "CREATE INDEX IF NOT EXISTS idx_shares_user_id ON file_shares(user_id)"),

        # trash表索引
        ("idx_trash_user_id", "CREATE INDEX IF NOT EXISTS idx_trash_user_id ON trash(user_id)"),
        ("idx_trash_expire", "CREATE INDEX IF NOT EXISTS idx_trash_expire ON trash(expire_at)"),

        # file_versions表索引
        ("idx_versions_file_id", "CREATE INDEX IF NOT EXISTS idx_versions_file_id ON file_versions(file_id)"),
    ]

    created_count = 0
    for index_name, sql in indexes:
        try:
            conn.execute(sql)
            created_count += 1
        except Exception as e:
            print(f"[数据库] 索引 {index_name} 创建失败: {e}")

    conn.commit()
    print(f"[数据库] 索引优化完成！已创建/更新 {created_count} 个索引")



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
            view_count = row["view_count"] if "view_count" in row.keys() else 0
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
                "view_count": view_count,
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


def get_user_storage_usage(user_id):
    """获取用户存储空间使用情况"""
    conn = get_db()
    try:
        # 计算用户所有文件的总大小（包括文件夹中的文件）
        result = conn.execute('''
            SELECT COALESCE(SUM(size), 0) as total_size
            FROM files 
            WHERE user_id = ?
        ''', (user_id,)).fetchone()
        
        total_size = result['total_size'] if result else 0
        
        # 定义总空间限制（1GB）
        MAX_STORAGE = 1 * 1024 * 1024 * 1024  # 1GB in bytes
        
        return {
            'total_size': total_size,
            'max_storage': MAX_STORAGE,
            'used_percentage': (total_size / MAX_STORAGE * 100) if MAX_STORAGE > 0 else 0,
            'is_over_limit': total_size >= MAX_STORAGE
        }
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


def cleanup_expired_trash():
    """清理回收站中过期的文件（超过30天）"""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    try:
        expired_items = conn.execute('''
            SELECT * FROM trash
            WHERE expire_at < datetime('now')
        ''').fetchall()

        deleted_count = 0
        for item in expired_items:
            if os.path.exists(item['file_path']):
                try:
                    os.unlink(item['file_path'])
                except Exception as e:
                    print(f"删除文件失败: {item['file_path']}, 错误: {str(e)}")

            conn.execute('DELETE FROM files WHERE id = ?', (item['file_id'],))
            conn.execute('DELETE FROM trash WHERE id = ?', (item['id'],))
            deleted_count += 1

        conn.commit()
        if deleted_count > 0:
            print(f"已清理 {deleted_count} 个过期回收站文件")
    except Exception as e:
        print(f"清理回收站失败: {str(e)}")
        conn.rollback()
    finally:
        conn.close()


# ==================== 数据归档机制 ====================

def archive_old_logs(days_to_keep=90):
    """
    归档旧日志数据到归档表

    参数:
        days_to_keep: 保留最近N天的日志，默认90天
    """
    print(f"[数据归档] 开始清理 {days_to_keep} 天前的日志数据...")
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    total_archived = 0

    try:
        # 创建归档表（如果不存在）
        conn.execute('''CREATE TABLE IF NOT EXISTS access_logs_archive (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT,
                        user_id TEXT,
                        action TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        access_time TIMESTAMP,
                        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')

        conn.execute('''CREATE TABLE IF NOT EXISTS operation_logs_archive (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        action TEXT,
                        target_id TEXT,
                        target_type TEXT,
                        message TEXT,
                        details TEXT,
                        created_at TIMESTAMP,
                        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')

        # 归档旧的访问日志
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d %H:%M:%S')
        
        old_access_logs = conn.execute('''
            SELECT * FROM access_logs 
            WHERE access_time < ?
        ''', (cutoff_date,)).fetchall()

        for log in old_access_logs:
            conn.execute('''
                INSERT INTO access_logs_archive 
                (file_id, user_id, action, ip_address, user_agent, access_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (log['file_id'], log['user_id'], log['action'],
                  log['ip_address'], log['user_agent'], log['access_time']))
            total_archived += 1

        # 删除已归档的访问日志
        if old_access_logs:
            conn.execute('DELETE FROM access_logs WHERE access_time < ?', (cutoff_date,))
            print(f"  - 访问日志：归档 {len(old_access_logs)} 条")

        # 归档旧的操作日志
        old_op_logs = conn.execute('''
            SELECT * FROM operation_logs 
            WHERE created_at < ?
        ''', (cutoff_date,)).fetchall()

        for log in old_op_logs:
            conn.execute('''
                INSERT INTO operation_logs_archive
                (user_id, action, target_id, target_type, message, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (log['user_id'], log['action'], log['target_id'],
                  log['target_type'], log['message'], log['details'], log['created_at']))
            total_archived += 1

        # 删除已归档的操作日志
        if old_op_logs:
            conn.execute('DELETE FROM operation_logs WHERE created_at < ?', (cutoff_date,))
            print(f"  - 操作日志：归档 {len(old_op_logs)} 条")

        # 清理过期的验证码（超过24小时）
        conn.execute('''
            DELETE FROM verification_codes 
            WHERE expires_at < datetime('now')
        ''')

        # 清理过期的分享链接
        conn.execute('''
            DELETE FROM file_shares 
            WHERE expires_at IS NOT NULL AND expires_at < datetime('now')
        ''')

        conn.commit()
        print(f"[数据归档] 完成！共归档 {total_archived} 条记录")

        return {
            'success': True,
            'archived_count': total_archived,
            'access_logs': len(old_access_logs) if 'old_access_logs' in dir() else 0,
            'operation_logs': len(old_op_logs) if 'old_op_logs' in dir() else 0
        }

    except Exception as e:
        print(f"[数据归档] 错误: {e}")
        conn.rollback()
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        conn.close()


def cleanup_archive_tables(max_age_days=365):
    """
    清理归档表中超过指定时间的数据

    参数:
        max_age_days: 归档数据最大保留天数，默认1年
    """
    print(f"[归档清理] 清理超过 {max_age_days} 天的归档数据...")
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row

    try:
        cutoff_date = (datetime.now() - timedelta(days=max_age_days)).strftime('%Y-%m-%d %H:%M:%S')

        deleted_access = conn.execute('''
            DELETE FROM access_logs_archive WHERE access_time < ?
        ''', (cutoff_date,)).rowcount

        deleted_ops = conn.execute('''
            DELETE FROM operation_logs_archive WHERE created_at < ?
        ''', (cutoff_date,)).rowcount

        conn.commit()
        total_deleted = deleted_access + deleted_ops

        if total_deleted > 0:
            print(f"[归档清理] 已删除 {total_deleted} 条过期归档数据")
            print(f"  - 访问日志归档：{deleted_access} 条")
            print(f"  - 操作日志归档：{deleted_ops} 条")

        return {
            'success': True,
            'deleted_access_logs': deleted_access,
            'deleted_operation_logs': deleted_ops,
            'total_deleted': total_deleted
        }

    except Exception as e:
        print(f"[归档清理] 错误: {e}")
        conn.rollback()
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        conn.close()


def get_database_stats():
    """获取数据库统计信息"""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    stats = {}

    try:
        # 获取各表的行数
        tables = ['users', 'files', 'folders', 'access_logs', 'operation_logs',
                  'likes', 'favorites', 'tags', 'categories', 'ai_contents',
                  'trash', 'file_shares', 'file_versions',
                  'access_logs_archive', 'operation_logs_archive']

        table_stats = {}
        for table in tables:
            try:
                count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                table_stats[table] = count
            except Exception as e:
                table_stats[table] = f"错误: {e}"

        stats['tables'] = table_stats

        # 数据库文件大小
        db_size = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
        stats['db_size_bytes'] = db_size
        stats['db_size_mb'] = round(db_size / (1024 * 1024), 2)

        # 索引信息
        indexes = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        stats['index_count'] = len(indexes)

        # 查询监控统计
        stats['query_monitor'] = query_monitor.get_stats()

        # 连接池状态
        if db_pool:
            stats['connection_pool'] = db_pool.get_stats()

        return stats

    except Exception as e:
        print(f"[数据库统计] 错误: {e}")
        return {'error': str(e)}
    finally:
        conn.close()


def optimize_database():
    """执行数据库优化操作"""
    print("[数据库优化] 开始执行VACUUM和ANALYZE...")
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row

    try:
        # VACUUM - 重建数据库文件，释放空间
        start_time = time.time()
        conn.execute('VACUUM')
        vacuum_time = time.time() - start_time
        print(f"  VACUUM完成，耗时: {vacuum_time:.2f}s")

        # ANALYZE - 更新统计信息以优化查询计划
        start_time = time.time()
        conn.execute('ANALYZE')
        analyze_time = time.time() - start_time
        print(f"  ANALYZE完成，耗时: {analyze_time:.2f}s")

        conn.commit()

        # 获取优化后的数据库大小
        db_size = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0

        return {
            'success': True,
            'vacuum_time': round(vacuum_time, 2),
            'analyze_time': round(analyze_time, 2),
            'db_size_mb': round(db_size / (1024 * 1024), 2),
            'message': '数据库优化完成'
        }

    except Exception as e:
        print(f"[数据库优化] 错误: {e}")
        return {
            'success': False,
            'error': str(e)
        }
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
    return render_template("index.html", files=files, remote_table=remote_table, remote_error=remote_error, dk_info=info, username=session.get('username'), role=session.get('role'))



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


def main():
    """主函数 - 启动服务器"""
    # 导入路由定义
    import routes  # noqa: F401

    # 修复Windows控制台编码问题
    import sys
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    try:
        print("\n" + "=" * 60)
        print("[启动] 正在初始化...")
        print("=" * 60 + "\n")

        # 初始化数据库（不依赖Flask上下文）
        print("[数据库] 初始化中...")
        init_db()
        print("  [OK] 数据库就绪")

        # 初始化连接池（不依赖Flask上下文）
        print("[连接池] 初始化中...")
        init_db_pool()
        print("  [OK] 连接池就绪")

        # 初始化缓存系统
        print("[缓存] 初始化中...")
        init_cache()
        init_preview_cache()
        init_hot_data_cache()

        # 配置CDN（如果环境变量中有配置）
        with app.app_context():
            configure_cdn(app)

        cache_stats = get_cache().get_stats()
        print(f"  [OK] 缓存就绪 (类型: {cache_stats['type']})")

        # 清理过期预览文件
        if preview_cache:
            preview_cache.clear_old_previews(days=7)

        # 清理过期数据（使用应用上下文）
        print("[清理] 清理过期数据...")
        with app.app_context():
            cleanup_old_logs()
            cleanup_expired_trash()

            # 执行定期归档（可选，默认保留90天）
            try:
                archive_result = archive_old_logs(days_to_keep=90)
                if archive_result.get('success'):
                    print(f"  [OK] 日志归档完成: {archive_result.get('archived_count', 0)} 条")
            except Exception as e:
                print(f"  [WARN] 日志归档跳过: {e}")

        print("  [OK] 清理完成\n")

        # 显示启动信息
        print("=" * 60)
        print("[就绪] 服务器准备就绪！")
        print("=" * 60)
        print(f"  [本地] http://127.0.0.1:9876")

        # 获取局域网IP
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            print(f"  [局域网] http://{local_ip}:9876")
        except Exception:
            pass

        # 显示数据库优化状态
        print("-" * 60)
        print("[数据库优化]")
        with app.app_context():
            stats = get_database_stats()
        if 'db_size_mb' in stats:
            print(f"  数据库大小: {stats['db_size_mb']} MB")
        if 'index_count' in stats:
            print(f"  索引数量: {stats['index_count']}")
        if db_pool:
            pool_stats = db_pool.get_stats()
            print(f"  连接池: {pool_stats['available_connections']}/{pool_stats['pool_size']} 可用")
        print("-" * 60)
        print("  按 Ctrl+C 停止服务器")
        print("=" * 60 + "\n")

        # 启动Flask应用（禁用reloader以支持SSE流式传输）
        app.run(debug=True, host='0.0.0.0', port=9876, use_reloader=False)
        
    except KeyboardInterrupt:
        print("\n\n[停止] 服务器已正常停止")
    except ImportError as e:
        print(f"\n[错误] 缺少依赖: {e}")
        print("请运行: pip install flask")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
