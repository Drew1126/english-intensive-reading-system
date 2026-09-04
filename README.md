# 英语精读系统

一个面向中文学习者的 AI 英语精读工具，支持外刊与考研英语真题阅读、句子选择、单词与短语聚焦、上下文追问、句子结构分析和文章翻译。

## 主要功能

- 上传并解析 PDF 英语文章
- 管理考研英语真题文章
- 点击单词、连续选择短语或双击选择整句
- 基于选中内容进行流式 AI 问答
- 句中释义、句子结构和相似词辨析快捷提问
- 停止回答、重新生成、复制回答和回答耗时显示
- 左右阅读区域拖动调整，移动端使用底部问答抽屉
- 阅读打卡、头像和历史文章
- 管理员与普通用户分级权限
- 管理员账号管理，包括添加普通账号、修改密码和删除账号

## 账号和权限

系统包含两种角色：

| 角色 | 权限 |
| --- | --- |
| 管理员 | 浏览和问答；上传、修改、删除文章；上传、删除真题；管理账号 |
| 普通用户 | 浏览文章、使用问答、翻译、打卡和个人头像 |

`root` 是唯一管理员，其他账号固定为普通用户，不能被提升为管理员。

首次运行会自动创建预设的管理员账号和游客账号。请使用项目部署时约定的初始凭据登录，并在首次登录后通过“账号管理”立即修改默认密码。

权限同时由前端和后端控制。普通用户即使直接调用管理接口，也会收到 `403` 响应。

## 环境要求

- Python 3.9 或更高版本
- 可用的兼容 OpenAI 接口的语言模型服务
- Windows、Linux 或 macOS

## 快速开始

1. 创建并启用虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux 或 macOS：

```bash
source .venv/bin/activate
```

2. 安装依赖：

```bash
pip install -r backend/requirements.txt
```

3. 创建环境配置：

```bash
cp backend/.env.example backend/.env
```

在 `backend/.env` 中配置模型接口：

```env
LLM_API_KEY=填写你的接口密钥
```

不要把真实的 API 密钥提交到 Git 仓库。

4. 启动服务：

```bash
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

然后访问 [http://127.0.0.1:8000/](http://127.0.0.1:8000/)。

Windows 也可以运行 `start_backend.bat`，Linux 可以运行 `start.sh`。

## 项目结构

```text
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置与数据目录
│   ├── routers/                # 文章、问答、翻译、鉴权和真题接口
│   ├── services/               # 鉴权、文章处理、翻译和 AI 问答逻辑
│   ├── storage/                # JSON 文件读写
│   ├── schemas/                # 数据模型
│   └── data/                   # 文章、账号、会话和运行数据
├── frontend/
│   ├── index.html              # 页面结构
│   ├── css/                    # 界面样式
│   └── js/                     # 阅读、问答、鉴权和账号管理交互
├── start_backend.bat           # Windows 启动脚本
└── start.sh                    # Linux 启动脚本
```

## 数据和安全

- 密码使用 PBKDF2-SHA256 加盐哈希存储，不保存明文密码。
- 登录令牌保存在运行时会话文件中。
- 文章、账号资料和打卡数据使用 JSON 文件持久化。
- 生产环境应限制 `backend/data/` 的文件访问权限并定期备份。
- 默认密码必须在部署后立即修改。
- `backend/.env`、运行日志和会话文件不应提交到公共仓库。

## 部署

项目可通过 Uvicorn 独立运行，也可由 Nginx 或其他反向代理挂载到 `/english` 路径。反向代理需要保留流式响应能力，否则 AI 回答可能无法实时显示。

Linux systemd 示例操作：

```bash
sudo systemctl status english-reader
sudo systemctl restart english-reader
sudo journalctl -u english-reader -f
```

## 验证

提交或部署前建议至少执行：

```bash
python -m py_compile backend/services/auth_service.py backend/routers/auth.py backend/routers/article.py backend/routers/zhenti.py
```

并验证：

- 管理员可以进入账号管理并维护文章。
- 普通用户看不到上传、编辑和删除入口。
- 普通用户直接请求管理接口时返回 `403`。
- 问答流可以正常停止、重试和复制。
- 桌面拖动分栏与移动端问答抽屉工作正常。
