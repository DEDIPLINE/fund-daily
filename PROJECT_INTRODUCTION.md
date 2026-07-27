# AI 基金助手 - 项目介绍文档

> 本文档供其他 AI 或开发者参考，包含项目架构、部署步骤、开发指南。

## 一、项目概述

### 1.1 项目定位
面向中国场外基金定投小白的本地 AI 理财参谋工具。通过 akshare + 腾讯自选股 MCP 自动抓取行情/新闻/舆情/诊断数据，生成可视化 HTML 报告，辅助定投决策。

### 1.2 技术栈
- **前端**：Tailwind CSS + 原生 JavaScript + ECharts
- **后端**：Python 3.11 + akshare + 腾讯自选股 MCP
- **部署**：GitHub Pages + GitHub Actions
- **数据**：JSON 文件作为数据交换格式

### 1.3 核心功能
| 模块 | 说明 |
|------|------|
| 📊 **每日收盘日报** | 持仓市值、净值涨跌、盘中估值、红绿灯信号、迷你走势图 |
| 📰 **消息面参考卡** | 个股新闻、市场热点、宏观经济日历、微博情绪、雪球热度 |
| 🩺 **持仓诊断** | 集中度(HHI)、假分散检测、波动率、最大回撤、夏普比率、基准对比 |
| 🚦 **信号总览** | 估值红绿灯(过热/中性/低估)、止盈阶梯触发、异动预警 |
| 🖥️ **仪表盘** | SPA 单页应用，侧边栏切换 4 个视图，深色主题，ECharts 图表 |

## 二、项目架构

### 2.1 架构模式
**静态前端 + 动态数据更新模式**
- 前端：纯静态 HTML/CSS/JavaScript，无服务器依赖
- 后端：Python 脚本定期生成 JSON 数据文件
- 部署：GitHub Pages 托管静态文件

### 2.2 目录结构
```
fund-daily/
├── index.html                  # 仪表盘主页面（SPA，4视图切换）
├── portfolio.json              # 持仓配置（代码/金额/信号阈值/诊断阈值/theme_map/news配置）
├── README.md                   # 项目说明
├── ARCHITECTURE.md             # 架构与待办
│
├── src/                        # Python 脚本
│   ├── phase0_connectivity.py  # Phase0: 数据层连通性验证
│   ├── phase1_daily_report.py  # Phase1+1.5: 每日收盘日报（净值+盘中估值+信号）
│   ├── signals.py              # Phase2: 买卖信号引擎（红绿灯/止盈/异动）
│   ├── diagnostics.py          # Phase4: 持仓诊断引擎（HHI/相关性/波动/回撤/夏普）
│   ├── phase4_diagnostic_report.py  # Phase4: 周/月体检报告 HTML
│   ├── phase4_probe.py         # Phase4: 诊断探针（只读可行性验证）
│   ├── ask.py                  # M4: 对话陪伴接地层（关键词→诊断事实）
│   └── news_signal.py          # M5: 消息面参考卡（新闻/舆情/宏观/热点）
│
├── data/
│   ├── dashboard.json          # 主数据文件（前端读取）
│   ├── history/                # 基金净值增量缓存（每只 .csv）
│   └── reports/                # 生成的 HTML 报告
│
├── .github/workflows/          # GitHub Actions
│   ├── deploy-pages.yml        # 部署工作流
│   ├── update-data.yml         # 数据更新工作流
│   └── keep-alive.yml          # 保活工作流
│
└── requirements.txt            # Python 依赖
```

### 2.3 数据流设计
1. **数据抓取**：Python 脚本通过 akshare/MCP 获取数据
2. **数据处理**：处理数据并生成仪表盘 JSON
3. **数据存储**：保存到 `data/dashboard.json`
4. **前端加载**：前端页面加载并显示数据
5. **自动更新**：GitHub Actions 定时运行数据抓取脚本

## 三、部署步骤

### 3.1 前置条件
1. **GitHub 账号**：用于代码托管和自动部署
2. **Git 基础知识**：用于推送代码
3. **项目已推送到 GitHub**：确保项目已在 GitHub 上

### 3.2 部署流程

#### 第一步：推送代码到 GitHub
```bash
cd /path/to/project
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/project-name.git
git push -u origin main
```

#### 第二步：启用 GitHub Pages
1. 登录 GitHub，进入项目仓库
2. 点击 **Settings** → **Pages**
3. 在 **Source** 部分，选择 **GitHub Actions**
4. 保存设置

#### 第三步：配置 GitHub Actions 权限
1. 进入项目仓库的 **Settings** → **Actions** → **General**
2. 在 **Workflow permissions** 部分，选择 **Read and write permissions**
3. 保存设置

#### 第四步：创建部署工作流
创建 `.github/workflows/deploy-pages.yml`：
```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [ main ]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        
      - name: Setup Pages
        uses: actions/configure-pages@v4
        
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: .
          exclude: |
            .git
            .github
            *.py
            src/
            tests/
            __pycache__/
            .pytest_cache/
            *.md
            LICENSE
            
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

#### 第五步：手动触发首次部署
1. 进入项目仓库的 **Actions** 标签页
2. 在左侧选择 **Deploy to GitHub Pages** 工作流
3. 点击 **Run workflow**，选择 `main` 分支
4. 等待部署完成

### 3.3 自动数据更新配置

#### 创建数据更新工作流
创建 `.github/workflows/update-data.yml`：
```yaml
name: Update Data

on:
  schedule:
    # 每个交易日北京时间 11:30 更新数据（盘中估值）
    - cron: '30 3 * * 1-5'  # UTC 03:30 = 北京时间 11:30
    # 每个交易日北京时间 16:00 更新数据（收盘后全量）
    - cron: '0 8 * * 1-5'   # UTC 08:00 = 北京时间 16:00
  workflow_dispatch:

jobs:
  update-data:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
      
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        
    - name: Update dashboard data
      run: |
        python main.py export
        
    - name: Commit and push changes
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add data/dashboard.json
        git diff --staged --quiet || git commit -m "Update dashboard data $(date +'%Y-%m-%d')"
        git push
```

## 四、前端开发指南

### 4.1 双模式数据加载
前端支持两种数据加载模式：

```javascript
async function loadData() {
  try {
    // 优先从 API 获取（后端模式）
    const resp = await fetch('/api/dashboard');
    if (resp.ok) return await resp.json();
  } catch (e) {}
  
  try {
    // 回退到静态 JSON（离线模式）
    const resp2 = await fetch('data/dashboard.json');
    if (resp2.ok) return await resp2.json();
  } catch (e2) {}
  
  return null;
}
```

### 4.2 响应式设计
使用 Tailwind CSS 实现响应式布局：
- **移动端**：`w-full md:w-64`（侧边栏在移动端全宽）
- **主内容区**：`flex-1 p-4 md:p-6`（移动端减小内边距）
- **视口配置**：`width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no`

### 4.3 日志系统
```javascript
const Logger = {
  logs: [],
  
  addLog: function(level, message, data = null) {
    const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    const log = { timestamp, level, message, data };
    this.logs.push(log);
    console.log(`[${timestamp}] [${level.toUpperCase()}] ${message}`, data || '');
  },
  
  info: function(message, data) { this.addLog('info', message, data); },
  warn: function(message, data) { this.addLog('warn', message, data); },
  error: function(message, data) { this.addLog('error', message, data); }
};
```

## 五、维护指南

### 5.1 日常维护
1. **监控数据更新**：检查 GitHub Actions 运行状态
2. **检查部署状态**：确保网站正常访问
3. **查看日志**：浏览器控制台查看错误信息

### 5.2 故障排查
1. **页面空白**：检查 `data/dashboard.json` 是否存在且有效
2. **数据不更新**：检查 GitHub Actions 运行日志
3. **部署失败**：检查 `deploy-pages.yml` 配置

### 5.3 性能优化
1. **CDN 加速**：使用 CDN 加载外部库
2. **缓存策略**：合理的浏览器缓存设置
3. **懒加载**：按需加载图表和组件

## 六、安全注意事项

### 6.1 敏感数据保护
- **配置文件**：`portfolio.json` 不上传到 GitHub
- **数据库文件**：`fund_daily.db` 不上传到 GitHub
- **个人持仓**：不上传到 GitHub

### 6.2 访问控制
- **GitHub Pages**：公开访问
- **API 保护**：不暴露后端 API
- **数据脱敏**：示例配置文件脱敏

## 七、扩展指南

### 7.1 添加新视图
1. 在 `appState.navItems` 中添加新视图
2. 创建 `renderNewView(container)` 函数
3. 在 `renderCurrentView()` 中添加 case

### 7.2 添加新数据源
1. 在 Python 脚本中添加数据抓取逻辑
2. 在 `data/dashboard.json` 中添加新字段
3. 在前端 JavaScript 中处理新数据

### 7.3 添加新图表
1. 引入 ECharts 库
2. 创建图表容器 `<div id="chart-new"></div>`
3. 使用 ECharts API 初始化图表

## 八、常见问题

### Q1: 为什么选择 GitHub Pages？
**A**: 完全免费、全球 CDN、自动部署、易于维护。

### Q2: 如何修改更新时间？
**A**: 编辑 `.github/workflows/update-data.yml` 中的 cron 表达式。

### Q3: 如何添加新的数据字段？
**A**: 1. 在 Python 脚本中添加数据抓取；2. 在 JSON 文件中添加字段；3. 在前端 JavaScript 中处理。

### Q4: 如何自定义主题？
**A**: 修改 `tailwind.config` 中的颜色配置。

## 九、相关文档

- `ARCHITECTURE.md` - 项目架构与待办
- `GITHUB_PAGES_DEPLOY.md` - 部署指南
- `README.md` - 项目说明

---

**文档版本**：v1.0  
**最后更新**：2026-07-27  
**维护者**：WorkBuddy AI 助手