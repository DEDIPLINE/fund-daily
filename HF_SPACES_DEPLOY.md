# fund-daily Hugging Face Spaces 部署指南

## 概述

本指南将帮助你将 fund-daily 项目部署到 Hugging Face Spaces，实现：
- ✅ 完全免费（不需要信用卡）
- ✅ 2核 vCPU + 16GB 内存
- ✅ SQLite 数据持久化（通过 Storage Bucket）
- ✅ 自动定时数据更新
- ✅ 全球可访问

## 前置条件

1. **Hugging Face 账号**：仅需邮箱注册，不需要信用卡
2. **GitHub 账号**：用于代码托管和自动部署
3. **Git 基础知识**：用于推送代码

## 部署步骤

### 第一步：注册 Hugging Face

1. 访问 [huggingface.co](https://huggingface.co)
2. 点击右上角 "Sign Up"
3. 使用邮箱注册（不需要信用卡）
4. 验证邮箱并登录

### 第二步：创建 Storage Bucket

Storage Bucket 用于持久化 SQLite 数据，防止 Space 重启后数据丢失。

1. 登录 Hugging Face
2. 访问 [huggingface.co/spaces/buckets](https://huggingface.co/spaces/buckets)
3. 点击 "Create new bucket"
4. 填写配置：
   - **Name**: `/fund-daily-storage`（或你喜欢的名字）
   - **Visibility**: Private（推荐）
5. 点击 "Create" 完成创建
6. **记录 Bucket ID**（格式：`<用户名>/fund-daily-storage`）

### 第三步：创建 Hugging Face Space

1. 登录 Hugging Face
2. 点击右上角头像 → "New Space"
3. 填写配置：
   - **Space Name**: `fund-daily`（或你喜欢的名字）
   - **License**: MIT
   - **Space SDK**: **Docker**（重要！不要选 Gradio 或 Streamlit）
   - **Docker Template**: Blank（空白模板）
   - **Space Hardware**: Free（免费）
4. 点击 "Create Space"
5. **记录你的 Space URL**（格式：`https://<用户名>-fund-daily.hf.space`）

### 第四步：配置 Space 环境变量

1. 进入你的 Space → Settings 标签页
2. 在 "Variables and secrets" 部分添加以下环境变量：

   | Variable Name | Value | 说明 |
   |--------------|-------|------|
   | `HF_TOKEN` | `hf_xxxxxxxx` | Hugging Face API Token |
   | `HF_BUCKET_ID` | `<用户名>/fund-daily-storage` | Storage Bucket ID |
   | `DATA_DIR` | `/data` | 数据存储目录（Storage Bucket 挂载点） |

3. **获取 HF_TOKEN**：
   - 访问 [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
   - 点击 "New token"
   - 名称：`fund-daily`
   - 类型：Read & Write
   - 点击 "Generate token"
   - **复制并保存 token**（只会显示一次）

### 第五步：挂载 Storage Bucket 到 Space

1. 进入你的 Space → Settings 标签页
2. 找到 "Storage Buckets" 部分
3. 点击 "Add bucket"
4. 选择你创建的 Bucket（`/fund-daily-storage`）
5. 点击 "Save"

### 第六步：准备代码并推送

#### 6.1 克隆项目（如果还没有）

```bash
git clone https://github.com/<你的用户名>/fund-daily.git
cd fund-daily
```

#### 6.2 确保文件完整

项目根目录应包含以下关键文件：
```
fund-daily/
├── Dockerfile              # HF Spaces 部署配置
├── requirements.txt        # Python 依赖
├── app.py                  # Flask 后端
├── index.html              # 仪表盘 SPA
├── main.py                 # CLI 入口
├── portfolio.json          # 持仓配置
├── src/
│   ├── db.py               # SQLite 数据层
│   ├── storage_sync.py     # Storage Bucket 同步模块
│   └── ...                 # 其他模块
└── .github/
    └── workflows/
        └── keep-alive.yml  # GitHub Actions 保活
```

#### 6.3 创建 .env 文件（本地测试用，不要提交到 Git）

```bash
# .env（本地测试用）
HF_TOKEN=hf_xxxxxxxx
HF_BUCKET_ID=<用户名>/fund-daily-storage
DATA_DIR=/data
```

#### 6.4 提交代码到 GitHub

```bash
git add .
git commit -m "feat: 准备 HF Spaces 部署"
git push origin main
```

#### 6.5 连接到 Hugging Face Space

**方法 A：从 GitHub 自动部署（推荐）**

1. 进入你的 Space → Settings 标签页
2. 找到 "Git repository" 部分
3. 输入你的 GitHub 仓库 URL
4. 点击 "Link Git Repository"
5. 之后每次 push 到 main 分支，Space 会自动重新部署

**方法 B：直接推送到 HF Space**

```bash
# 添加 HF Space 作为 remote
git remote add space https://huggingface.co/spaces/<用户名>/fund-daily

# 推送代码
git push space main
```

### 第七步：配置 GitHub Actions 保活（可选但推荐）

GitHub Actions 可以每 15 分钟 ping 一次你的 Space，防止 48 小时无访问后休眠。

1. 进入你的 GitHub 仓库 → Settings → Secrets and variables → Actions
2. 点击 "New repository secret"
3. 添加：
   - **Name**: `HF_SPACE_URL`
   - **Secret**: `https://<用户名>-fund-daily.hf.space`
4. 保存

这样 GitHub Actions 就会自动每 15 分钟 ping 一次你的 Space，保持其活跃。

### 第八步：验证部署

1. 等待 Space 构建完成（通常 5-10 分钟）
2. 访问你的 Space URL：`https://<用户名>-fund-daily.hf.space`
3. 检查以下功能：
   - ✅ 仪表盘页面能正常加载
   - ✅ 数据从 API 正常获取
   - ✅ `/api/status` 返回正常状态

## 常见问题

### Q1: Space 构建失败

**可能原因**：
- Dockerfile 语法错误
- 依赖安装失败
- 端口配置错误

**解决方法**：
1. 进入 Space → Logs 标签页查看构建日志
2. 常见问题：
   - 确保 `EXPOSE 7860`（HF Spaces 标准端口）
   - 确保 `requirements.txt` 包含所有依赖
   - 检查 Python 版本兼容性

### Q2: 数据不持久化

**可能原因**：
- Storage Bucket 未正确挂载
- 环境变量未设置
- 同步模块未正确初始化

**解决方法**：
1. 检查 Settings → Variables and secrets 中的环境变量
2. 检查 Settings → Storage Buckets 中的 Bucket 挂载状态
3. 查看 Space 日志中的同步信息

### Q3: Space 休眠

**可能原因**：
- 48 小时无访问
- GitHub Actions 未配置或失败

**解决方法**：
1. 手动访问一次 Space URL 即可唤醒
2. 检查 GitHub Actions 是否正常运行
3. 确认 `HF_SPACE_URL` secret 已正确设置

### Q4: 冷启动慢（30-60 秒）

**这是正常现象**。HF Spaces 免费层在无访问 48 小时后会休眠，首次访问需要冷启动。

**优化方案**：
1. 配置 GitHub Actions 保活（推荐）
2. 接受冷启动延迟（个人工具可接受）

### Q5: 如何更新代码？

**如果使用 GitHub 自动部署**：
1. 修改代码并 push 到 GitHub
2. Space 会自动重新部署

**如果直接推送到 HF Space**：
```bash
git push space main
```

## 数据备份与恢复

### 自动备份

项目会自动将数据同步到 Storage Bucket：
- 启动时：从 Bucket 下载数据
- 运行时：每 2 分钟同步一次
- 退出时：上传数据到 Bucket

### 手动备份

如果需要手动备份数据：

```python
from huggingface_hub import HfApi

api = HfApi(token="hf_xxxxxxxx")

# 上传整个 data 目录
api.upload_folder(
    folder_path="./data",
    repo_id="<用户名>/fund-daily-storage",
    repo_type="dataset"
)
```

### 恢复数据

```python
from huggingface_hub import HfApi

api = HfApi(token="hf_xxxxxxxx")

# 下载整个 data 目录
api.snapshot_download(
    repo_id="<用户名>/fund-daily-storage",
    repo_type="dataset",
    local_dir="./data"
)
```

## 成本说明

- **Hugging Face Spaces 免费层**：完全免费，不需要信用卡
- **Storage Bucket 免费层**：100GB 免费空间
- **GitHub Actions**：每月 2000 分钟免费（足够每 15 分钟 ping 一次）

## 安全注意事项

1. **不要提交 `.env` 文件到 Git**
2. **不要在代码中硬编码 `HF_TOKEN`**
3. **使用 GitHub Secrets 存储敏感信息**
4. **设置 Storage Bucket 为 Private**

## 技术支持

如果遇到问题，可以：
1. 查看 Space 日志（Logs 标签页）
2. 查看 GitHub Actions 日志
3. 在 Hugging Face 社区提问
4. 参考 [Hugging Face Spaces 文档](https://huggingface.co/docs/hub/en/spaces-overview)

## 下一步

部署成功后，你可以：
1. 绑定自定义域名（需要 HF Pro）
2. 添加认证保护（使用 HF Tokens）
3. 配置监控告警
4. 优化性能（升级硬件）

---

**部署完成后，你就有了一个完全免费、24/7 运行的基金助手！** 🚀