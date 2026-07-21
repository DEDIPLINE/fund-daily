# AI 基金助手 — 项目架构与待办

## 一、项目概述

本地 AI 基金日报助手，面向场外基金（支付宝定投）小白用户。通过 akshare + 腾讯自选股 MCP 自动抓取行情/新闻/舆情/诊断数据，生成可视化 HTML 报告。

- **用户画像**：金融小白，~4500 元持仓，12 只场外基金（半导体/黄金/新能源/纳指等）
- **定位**：参谋型信息助手（非自动交易），不构成投资建议
- **技术栈**：Python 3.11 + akshare + 腾讯自选股 MCP | 前端 Tailwind + Alpine.js + ECharts

## 二、目录结构

```
fund-daily/
├── index.html                  # 仪表盘主页面（SPA，4视图切换）
├── portfolio.json              # 持仓配置（代码/金额/信号阈值/诊断阈值/theme_map/news配置）
├── README.md                   # 项目说明
├── ARCHITECTURE.md             # 本文件：架构与待办
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
│   ├── history/                # 基金净值增量缓存（每只 .csv）
│   └── reports/                # 生成的 HTML 报告
│       ├── report_YYYYMMDD.html    # 每日日报
│       ├── diag_YYYYMMDD.html      # 周/月诊断
│       └── news_YYYYMMDD.html      # 消息面参考卡
│
├── Phase0_连通性报告.md         # 开发文档（可移除）
├── Phase4_持仓诊断与对话陪伴_规划.md  # 开发文档（可移除）
├── M5_消息面操作建议_方案.md     # 开发文档（可移除）
└── 盘中估值_调研与方案.md       # 开发文档（可移除）
```

## 三、功能完成度

### 已完成 ✅

| 场景 | 模块 | 状态 | 说明 |
|------|------|------|------|
| M1 每日行情跟踪 | phase1_daily_report.py | ✅ | 官方净值+盘中估值+红涨绿跌+迷你走势图 |
| M2 持仓诊断 | diagnostics.py + phase4_diagnostic_report.py | ✅ | HHI/相关性/波动/回撤/夏普/基准对比/再平衡建议 |
| M3 买卖信号 | signals.py | ✅ | 估值红绿灯+止盈阶梯+异动预警 |
| M4 对话陪伴 | ask.py + WorkBuddy 当伴侣 | ✅ | CLI 关键词→诊断事实，或直接问 WorkBuddy |
| M5 消息面 | news_signal.py | ✅ | 个股新闻+宏观日历+研报+微博情绪+雪球热度+基金公告 |
| 前端仪表盘 | index.html | ✅ | SPA 4视图切换，ECharts 图表，深色主题 |

### 未完成 ❌

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | **Python→前端数据注入** | 当前仪表盘数据是硬编码，需让 Python 脚本自动生成 JSON 数据文件，前端读取 |
| P0 | **requirements.txt** | 缺依赖清单，别人 clone 后无法安装 |
| P0 | **.gitignore** | 缺 git 忽略文件（data/history/、data/reports/、__pycache__/ 等） |
| P1 | **config.example.json** | portfolio.json 包含个人持仓，需要一个 example 模板供别人参考 |
| P1 | **统一入口脚本** | 缺 `python main.py --all` 一键跑全部功能的入口 |
| P1 | **MCP 新闻集成到 news_signal.py** | 当前 news_signal.py 用 akshare 拉新闻，应切换到腾讯自选股 MCP（质量更好） |
| P1 | **测试** | 缺单元测试（signals/diagnostics 核心逻辑） |
| P2 | Phase 3 定时推送 | 用户暂缓，可选做 |
| P2 | 真实成本接入 | 方案A：用户提供每只累计投入成本，止盈切真实收益率口径 |
| P2 | 深色/浅色主题切换 | 仪表盘目前只有深色 |
| P2 | 移动端适配优化 | 仪表盘在手机上的体验 |
| P3 | README 完善 | 缺安装步骤、使用说明、截图、贡献指南 |
| P3 | LICENSE | 缺开源协议 |
| P3 | CI/CD | GitHub Actions 自动测试 |

## 四、GitHub 开源打包待办（按顺序）

### 第一步：基础规范（必须）
1. `requirements.txt` — `akshare>=1.18.66` 等
2. `.gitignore` — 忽略 `data/history/`、`data/reports/`、`__pycache__/`、`.venv/` 等
3. `config.example.json` — 从 portfolio.json 脱敏，保留结构，持仓金额清零
4. `LICENSE` — MIT 或 Apache 2.0

### 第二步：代码质量（推荐）
5. 统一入口 `main.py` — `python main.py daily|news|diag|all`
6. Python→前端数据注入 — `python export_json.py` 生成 `data/dashboard.json`，前端 `index.html` 读取
7. MCP 新闻源切换 — `news_signal.py` 支持 akshare 和腾讯自选股 MCP 双源
8. 核心逻辑单测 — `tests/test_signals.py`、`tests/test_diagnostics.py`

### 第三步：文档与体验（锦上添花）
9. `README.md` 重写 — 安装步骤、使用说明、功能截图、配置说明
10. 仪表盘深色/浅色切换
11. 移动端响应式优化
12. GitHub Actions CI

## 五、关键运行命令

```bash
# 激活环境
C:\Users\DEDIPLINE\.workbuddy\binaries\python\envs\fund-daily-py311\Scripts\activate

# 每日日报（M1）
python src/phase1_daily_report.py

# 消息面参考卡（M5）
python src/news_signal.py

# 周报（M2）
python src/phase4_diagnostic_report.py --period weekly

# 月报（M2）
python src/phase4_diagnostic_report.py --period monthly

# 对话查询（M4）
python src/ask.py 分散
python src/ask.py 回撤

# 仪表盘（前端）
# 直接浏览器打开 index.html
```

## 六、技术决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 数据源 | akshare（主）+ 腾讯自选股 MCP（新闻/板块） | akshare 免费全量覆盖；MCP 新闻质量更好 |
| 信号引擎 | 纯 pandas 规则，不引入量化框架 | 基金净值场景不需要 Qlib/Backtrader/TA-Lib |
| 止盈口径 | 方案B（近1年涨幅代理） | 用户未提供真实成本 |
| 前端方案 | 纯静态 HTML + Tailwind CDN + Alpine.js | 零构建，与 Python 生成静态 HTML 兼容 |
| 诊断理论 | Markowitz MPT / HHI / MDD / Sharpe | 标准金融理论，零售级实现 |
| venv 路径 | managed 区 `fund-daily-py311` | D盘沙箱拦截可执行文件复制 |
| Python 版本 | 系统 Python 3.11.9 | managed 3.13 装不了 akshare（tqdm 无发行版） |
