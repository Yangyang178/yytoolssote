# yytoolssite-aipro

- 技术栈：`Python` + `Flask` + `HTML/CSS`
- 功能：上传文件、调用 DKFile API、展示与管理文件列表
- 主题：蓝色系精美布局

## 本地运行（Windows）

- 建议使用虚拟环境

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

- 配置 `.env`

复制 `.env.example` 为 `.env`，并填写你的密钥：

```
DKFILE_API_KEY=你的_dkfile_api_key
DKFILE_API_BASE=https://dkfile.net/api
```

- 启动服务

```
python app.py
```

- 打开浏览器访问 `http://localhost:5000/`

## 说明

- 使用 `python-dotenv` 从项目根目录的 `.env` 加载配置，避免将密钥写入代码或版本库。
- 上传后的本地文件存储在 `uploads/`，元数据保存在 `data/db.json`。
- 若 DKFile API 返回结构不同，可调整 `app.py` 中的 `dkfile_*` 方法或设置 `DKFILE_API_BASE`。
