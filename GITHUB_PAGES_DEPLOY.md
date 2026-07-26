# fund-daily GitHub Pages 部署指南

## 概述

本指南将帮助你将 fund-daily 项目部署到 GitHub Pages，实现：
- ✅ 完全免费（不需要信用卡）
- ✅ 全球 CDN 加速
- ✅ 自动每日数据更新（通过 GitHub Actions）
- ✅ 自动部署

## 前置条件

1. **GitHub 账号**：用于代码托管和自动部署
2. **Git 基础知识**：用于推送代码
3. **项目已推送到 GitHub**：确保 fund-daily 项目已在 GitHub 上

## 部署步骤

### 第一步：推送代码到 GitHub

如果项目还未推送到 GitHub：

```bash
cd /d/Agent-wyf/fund-daily
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/fund-daily.git
git push -u origin main
```

### 第二步：启用 GitHub Pages

1. 登录 GitHub，进入项目仓库
2. 点击 **Settings** → **Pages**
3. 在 **Source** 部分，选择 **GitHub Actions**
4. 保存设置

### 第三步：配置 GitHub Actions 权限

1. 进入项目仓库的 **Settings** → **Actions** → **General**
2. 在 **Workflow permissions** 部分，选择 **Read and write permissions**
3. 保存设置

### 第四步：手动触发首次部署

1. 进入项目仓库的 **Actions** 标签页
2. 在左侧选择 **Deploy to GitHub Pages** 工作流
3. 点击 **Run workflow**，选择 `main` 分支
4. 等待部署完成

### 第五步：验证部署

1. 部署完成后，在 **Settings** → **Pages** 中可以看到网站 URL
2. 访问 `https://your-username.github.io/fund-daily/`
3. 应该能看到 AI 基金助手仪表盘

## 自动更新机制

### 数据更新工作流
- **触发时间**：每个交易日两次更新
  - 北京时间 11:30（盘中估值更新）
  - 北京时间 16:00（收盘后全量更新）
- **执行内容**：运行 `python main.py export` 更新 `data/dashboard.json`
- **自动提交**：更新后的数据自动提交到仓库

### 部署工作流
- **触发条件**：当 `main` 分支有新提交时自动触发
- **部署内容**：`index.html`、`data/`、`README.md`、`LICENSE`
- **部署时间**：通常在 1-2 分钟内完成

## 手动更新数据

如果需要手动更新数据：

1. 进入项目仓库的 **Actions** 标签页
2. 在左侧选择 **Update Fund Data** 工作流
3. 点击 **Run workflow**
4. 等待工作流完成

## 常见问题

### Q: 为什么数据没有自动更新？
A: 检查以下几点：
1. 确保 GitHub Actions 已启用
2. 检查工作流是否有错误（在 Actions 标签页查看）
3. 确保项目有推送权限

### Q: 如何修改更新时间？
A: 编辑 `.github/workflows/update-data.yml` 文件中的 cron 表达式：
```yaml
schedule:
  # 每个交易日北京时间 11:30 更新数据（盘中估值）
  - cron: '30 3 * * 1-5'  # UTC 03:30 = 北京时间 11:30
  # 每个交易日北京时间 16:00 更新数据（收盘后全量）
  - cron: '0 8 * * 1-5'   # UTC 08:00 = 北京时间 16:00
```

### Q: 如何添加自定义域名？
A: 
1. 在项目根目录创建 `CNAME` 文件，内容为你的域名
2. 在域名 DNS 设置中添加 CNAME 记录指向 `your-username.github.io`
3. 在 GitHub Pages 设置中填写自定义域名

### Q: 数据目录中的其他文件会更新吗？
A: 只有 `data/dashboard.json` 会被自动更新。其他文件（如 `fund_daily.db`）不会上传到 GitHub Pages。

## 本地测试

在部署前，可以在本地测试：

```bash
cd /d/Agent-wyf/fund-daily

# 安装依赖
pip install -r requirements.txt

# 更新数据
python main.py export

# 启动本地服务器
python -m http.server 8000

# 访问 http://localhost:8000
```

## 下一步

1. **监控工作流**：检查 GitHub Actions 是否正常运行
2. **设置通知**：配置 GitHub 通知，了解工作流状态
3. **优化性能**：如果更新时间过长，可以考虑优化脚本
4. **添加功能**：考虑添加历史数据对比、趋势分析等功能

## 注意事项

1. **免费额度**：GitHub Actions 每月有 2000 分钟免费额度，足够个人使用
2. **数据隐私**：`portfolio.json` 包含你的持仓信息，确保仓库为私有
3. **更新频率**：默认每日更新一次，避免过于频繁触发
4. **错误处理**：工作流失败时会发送邮件通知

---

**部署完成后，你的 AI 基金助手将每天自动更新数据，全球可访问！**
