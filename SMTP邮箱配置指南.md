# SMTP邮箱服务配置指南

## 问题说明

您遇到的问题是：**验证码显示已发送，但邮箱没有收到**。

**根本原因**：SMTP邮箱服务未配置或配置不完整。

## 解决方案

### 方案一：配置SMTP邮箱服务（推荐）

#### 步骤1：获取邮箱授权码

**QQ邮箱配置**：
1. 登录QQ邮箱网页版
2. 点击「设置」→「账户」
3. 找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」
4. 开启「POP3/SMTP服务」或「IMAP/SMTP服务」
5. 点击「生成授权码」，按提示发送短信
6. 记录生成的**授权码**（不是QQ密码）

**163网易邮箱配置**：
1. 登录163邮箱网页版
2. 点击「设置」→「POP3/SMTP/IMAP」
3. 开启「IMAP/SMTP服务」
4. 点击「客户端授权密码」，按提示发送短信
5. 记录生成的**授权密码**

**Gmail配置**：
1. 登录Google账户
2. 开启「两步验证」
3. 生成「应用专用密码」
4. 记录生成的**应用专用密码**

#### 步骤2：编辑配置文件

打开项目目录下的 `.env` 文件，填写以下配置：

```env
# 邮件配置
SMTP_HOST=smtp.qq.com              # QQ邮箱
SMTP_PORT=587                      # 端口号
SMTP_USERNAME=your_email@qq.com    # 你的邮箱地址
SMTP_PASSWORD=xxxxxxxxxxxx         # 授权码（不是邮箱密码）
SMTP_FROM=your_email@qq.com        # 发件人邮箱（同上）
```

**常用邮箱SMTP配置**：

| 邮箱服务商 | SMTP_HOST | SMTP_PORT | 说明 |
|-----------|-----------|-----------|------|
| QQ邮箱 | smtp.qq.com | 587 | 使用授权码 |
| 163邮箱 | smtp.163.com | 465 | 使用授权密码 |
| Gmail | smtp.gmail.com | 587 | 使用应用专用密码 |
| Outlook | smtp.office365.com | 587 | 使用邮箱密码 |
| 阿里企业邮箱 | smtp.qiye.aliyun.com | 465 | 使用邮箱密码 |

#### 步骤3：重启网站

修改配置后，需要重启网站才能生效：
1. 停止当前运行的网站（按Ctrl+C）
2. 重新运行 `一键启动.bat` 或 `python app.py`

#### 步骤4：测试验证码发送

1. 访问网站登录页面
2. 输入邮箱地址
3. 点击「发送验证码」
4. 检查邮箱收件箱（包括垃圾邮件文件夹）

### 方案二：使用密码登录（临时方案）

如果暂时无法配置SMTP服务，可以使用密码登录方式：

1. 在登录页面选择「密码登录」
2. 输入邮箱和密码进行登录

**注意**：如果还没有账号，需要先注册。注册时需要验证码，因此必须配置SMTP服务。

## 常见问题

### Q1: 提示"SMTP配置不完整"
**A**: 检查 `.env` 文件中的SMTP配置是否完整填写，特别注意：
- SMTP_HOST 不能为空
- SMTP_USERNAME 不能为空
- SMTP_PASSWORD 不能为空
- SMTP_FROM 不能为空

### Q2: 提示"发送验证码失败"
**A**: 可能的原因：
1. 授权码错误（请重新生成）
2. 邮箱地址错误
3. SMTP服务器地址错误
4. 网络连接问题

### Q3: 验证码发送成功但收不到邮件
**A**: 检查以下位置：
1. 邮箱的垃圾邮件文件夹
2. 邮箱是否设置了过滤规则
3. 邮箱是否已满

### Q4: 如何测试SMTP配置是否正确
**A**: 可以使用以下Python代码测试：

```python
import smtplib
from email.mime.text import MIMEText

# 配置信息
SMTP_HOST = 'smtp.qq.com'
SMTP_PORT = 587
SMTP_USERNAME = 'your_email@qq.com'
SMTP_PASSWORD = 'your_auth_code'
SMTP_FROM = 'your_email@qq.com'

# 创建邮件
msg = MIMEText('这是一封测试邮件', 'plain', 'utf-8')
msg['From'] = SMTP_FROM
msg['To'] = 'test@example.com'
msg['Subject'] = '测试邮件'

# 发送邮件
try:
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
    server.starttls()
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    server.sendmail(SMTP_FROM, ['test@example.com'], msg.as_string())
    server.quit()
    print('邮件发送成功！')
except Exception as e:
    print(f'邮件发送失败: {e}')
```

## 技术支持

如果按照上述步骤操作后仍无法解决问题，请提供以下信息：
1. 使用的邮箱服务商（QQ/163/Gmail等）
2. 错误提示信息
3. `.env` 文件中的SMTP配置（隐藏密码）

我们将为你提供进一步的技术支持。