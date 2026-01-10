# 日志系统使用说明

## 1. 概述

本项目实现了一个完善的日志系统，包括：
- 操作日志记录
- 错误日志分类
- 登录异常监控

## 2. 日志表结构

### 2.1 logs 表

| 字段名 | 类型 | 描述 |
|--------|------|------|
| id | INTEGER | 主键，自增 |
| log_type | TEXT | 日志类型：operation, error, security |
| log_level | TEXT | 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL |
| user_id | TEXT | 用户ID |
| action | TEXT | 操作类型 |
| target_id | TEXT | 目标ID |
| target_type | TEXT | 目标类型 |
| message | TEXT | 日志消息 |
| ip_address | TEXT | IP地址 |
| user_agent | TEXT | 用户代理 |
| details | TEXT | 详细信息 |
| created_at | TIMESTAMP | 创建时间 |

### 2.2 login_attempts 表

| 字段名 | 类型 | 描述 |
|--------|------|------|
| id | INTEGER | 主键，自增 |
| email | TEXT | 登录邮箱 |
| success | INTEGER | 登录是否成功 (1: 成功, 0: 失败) |
| ip_address | TEXT | IP地址 |
| user_agent | TEXT | 用户代理 |
| attempt_time | TIMESTAMP | 尝试时间 |

## 3. 日志函数使用

### 3.1 记录日志

```python
from app import log_message

# 记录操作日志
log_message(
    log_type='operation',
    log_level='INFO',
    message='用户上传了文件',
    request=request,
    user_id=session.get('user_id'),
    action='upload',
    target_id=file_id,
    target_type='file',
    details=f'文件名: {filename}'
)

# 记录错误日志
log_message(
    log_type='error',
    log_level='ERROR',
    message='文件上传失败',
    request=request,
    user_id=session.get('user_id'),
    action='upload',
    target_type='file',
    details=str(error)
)

# 记录安全日志
log_message(
    log_type='security',
    log_level='WARNING',
    message='登录失败次数过多',
    request=request,
    details=f'邮箱: {email}, IP: {ip_address}'
)
```

### 3.2 记录登录尝试

```python
from app import log_login_attempt

# 登录成功
log_login_attempt(
    email=email,
    success=1,
    request=request
)

# 登录失败
log_login_attempt(
    email=email,
    success=0,
    request=request
)
```

## 4. 登录异常监控

### 4.1 功能说明

登录异常监控会自动检查：
- 同一邮箱在10分钟内失败5次
- 同一IP在10分钟内失败10次

当检测到异常时，会自动记录安全日志。

### 4.2 使用方法

在登录相关的路由中调用`log_login_attempt`函数，系统会自动进行异常检查：

```python
@app.post('/login')
def login():
    # 登录逻辑
    if login_success:
        log_login_attempt(email, 1, request)
        # 登录成功处理
    else:
        log_login_attempt(email, 0, request)
        # 登录失败处理
```

## 5. 错误日志分类

### 5.1 功能说明

系统会自动将错误分为：
- 应用错误 (AppError)
- 未捕获的异常

### 5.2 日志级别

| 错误类型 | 日志级别 |
|----------|----------|
| AppError | ERROR |
| 未捕获的异常 | CRITICAL |

## 6. 使用示例

### 6.1 文件上传路由

```python
@app.post('/upload')
def upload():
    try:
        # 文件上传逻辑
        # ...
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='文件上传成功',
            request=request,
            user_id=session.get('user_id'),
            action='upload',
            target_id=file_id,
            target_type='file',
            details=f'文件名: {filename}'
        )
        
        return redirect(url_for('index'))
    except Exception as e:
        # 记录错误日志
        log_message(
            log_type='error',
            log_level='ERROR',
            message='文件上传失败',
            request=request,
            user_id=session.get('user_id'),
            action='upload',
            target_type='file',
            details=str(e)
        )
        flash(f'上传失败: {str(e)}')
        return redirect(url_for('upload_page'))
```

### 6.2 登录路由

```python
@app.post('/login')
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    # 验证用户名和密码
    user = get_user_by_email(email)
    if user and check_password_hash(user['password'], password):
        # 登录成功
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['username'] = user['username']
        
        # 记录登录成功日志
        log_login_attempt(email, 1, request)
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='INFO',
            message='用户登录成功',
            request=request,
            user_id=user['id'],
            action='login'
        )
        
        return redirect(url_for('index'))
    else:
        # 登录失败
        log_login_attempt(email, 0, request)
        
        # 记录操作日志
        log_message(
            log_type='operation',
            log_level='WARNING',
            message='用户登录失败',
            request=request,
            action='login',
            details=f'邮箱: {email}'
        )
        
        flash('登录失败，请检查邮箱和密码')
        return redirect(url_for('login'))
```

## 7. 日志查询

### 7.1 查询所有日志

```python
def get_all_logs():
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM logs ORDER BY created_at DESC').fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
```

### 7.2 查询特定类型的日志

```python
def get_logs_by_type(log_type):
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM logs WHERE log_type = ? ORDER BY created_at DESC', (log_type,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
```

### 7.3 查询登录尝试

```python
def get_login_attempts(email=None, ip_address=None, limit=100):
    conn = get_db()
    try:
        if email and ip_address:
            query = 'SELECT * FROM login_attempts WHERE email = ? AND ip_address = ? ORDER BY attempt_time DESC LIMIT ?'
            params = (email, ip_address, limit)
        elif email:
            query = 'SELECT * FROM login_attempts WHERE email = ? ORDER BY attempt_time DESC LIMIT ?'
            params = (email, limit)
        elif ip_address:
            query = 'SELECT * FROM login_attempts WHERE ip_address = ? ORDER BY attempt_time DESC LIMIT ?'
            params = (ip_address, limit)
        else:
            query = 'SELECT * FROM login_attempts ORDER BY attempt_time DESC LIMIT ?'
            params = (limit,)
        
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
```

## 8. 注意事项

1. 确保在所有路由中使用日志系统
2. 合理设置日志级别，避免过多的日志
3. 记录足够的详细信息，便于问题排查
4. 定期清理过期日志，避免数据库过大
5. 在开发环境中可以使用更高的日志级别，生产环境中使用较低的日志级别
