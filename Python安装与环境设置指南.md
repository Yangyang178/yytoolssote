# Python安装与环境设置指南

## 问题分析

经过诊断，发现系统中没有安装Python或Python未添加到系统路径，这是导致Flask应用无法启动的根本原因。

## 解决方案

### 步骤1：安装Python

**下载Python安装包**

# 访问Python官方网站：<https://www.python.org/downloads/windows/>

下载最新版本的Python（推荐Python 3.10+）

- 选择适合你系统的版本（通常是64位）
- **安装Python**
  - 运行下载的安装包
  - **重要**：勾选「Add Python to PATH」选项
  - 点击「Install Now」完成安装
- **验证Python安装**
  - 打开命令提示符（Win+R → 输入cmd → 回车）
  - 输入 `python --version`，应该显示Python版本信息
  - 输入 `pip --version`，应该显示pip版本信息

### 步骤2：设置项目环境

1. **创建虚拟环境**
   - 打开命令提示符，进入项目目录：
     ```
     cd D:\Trae\接口文件
     ```
   - 创建虚拟环境：
     ```
     python -m venv venv
     ```
2. **激活虚拟环境**
   - Windows命令提示符：
     ```
     venv\Scripts\activate
     ```
   - Windows PowerShell：
     ```
     .\venv\Scripts\Activate.ps1
     ```
3. **安装依赖**
   - 安装项目所需的依赖：
     ```
     pip install -r requirements.txt
     ```

### 步骤3：启动应用

1. **运行启动脚本**
   - 双击运行 `一键启动.bat` 文件
   - 或在命令提示符中运行：
     ```
     venv\Scripts\python.exe app.py
     ```
2. **验证网站访问**
   - 打开浏览器，访问：<http://localhost:9876>
   - 应该能看到网站首页

## 常见问题解决

### 问题1：Python命令无法识别

- **原因**：Python未添加到系统PATH
- **解决**：重新安装Python并勾选「Add Python to PATH」选项

### 问题2：虚拟环境创建失败

- **原因**：Python版本不兼容或权限不足
- **解决**：使用管理员权限运行命令提示符

### 问题3：依赖安装失败

- **原因**：网络问题或pip版本过低
- **解决**：更新pip：`python -m pip install --upgrade pip`

### 问题4：网站无法访问

- **原因**：端口被占用或Flask应用启动失败
- **解决**：检查端口占用并重启应用

## 技术支持

如果按照上述步骤操作后仍无法解决问题，请提供以下信息：

1. Python版本
2. 安装过程中的错误信息
3. 启动脚本的输出日志

我们将为你提供进一步的技术支持。
