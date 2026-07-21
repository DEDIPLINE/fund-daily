# AI 基金助手

面向中国场外基金定投小白的本地 AI 理财参谋工具。通过 akshare + 腾讯自选股 MCP 自动抓取行情/新闻/舆情/诊断数据，生成可视化 HTML 报告，辅助定投决策。

> ⚠️ 本工具仅做信息聚合与可视化，**不构成任何投资建议**。基金有风险，投资须谨慎。

## 功能

| 模块 | 说明 |
|------|------|
| 📊 **每日收盘日报** | 持仓市值、净值涨跌、盘中估值、红绿灯信号、迷你走势图 |
| 📰 **消息面参考卡** | 个股新闻、市场热点、宏观经济日历、微博情绪、雪球热度 |
| 🩺 **持仓诊断** | 集中度(HHI)、假分散检测、波动率、最大回撤、夏普比率、基准对比 |
| 🚦 **信号总览** | 估值红绿灯(过热/中性/低估)、止盈阶梯触发、异动预警 |
| 🖥️ **仪表盘** | SPA 单页应用，侧边栏切换 4 个视图，深色主题，ECharts 图表 |

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/fund-daily.git
cd fund-daily
```

### 2. 创建虚拟环境并安装依赖

```bash
# 需要 Python 3.11+（推荐 3.11.9，3.13 可能装不了 akshare）
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 配置持仓

复制示例配置并填入你的基金信息：

```bash
cp config.example.json portfolio.json
```

编辑 `portfolio.json`，填入：
- `holdings`：你的基金代码、名称、类型、分类、持仓金额
- `theme_map`：每只基金关联的龙头股票代码和行业关键词
- `signals`：信号阈值（可保持默认）
- `diagnostics`：诊断阈值（可保持默认）

**示例持仓**：
```json
{
  "code": "014194",
  "name": "汇添富中证芯片产业指数增强C",
  "type": "股票型-行业指增",
  "category": "半导体/芯片",
  "amount": 986.63
}
```

### 4. 运行

```bash
# 生成每日收盘日报
python main.py daily

# 生成消息面参考卡
python main.py news

# 生成持仓诊断报告（月报）
python main.py diag

# 生成周报
python main.py diag --period weekly

# 一键生成全部报告
python main.py all

# 打开仪表盘
# 直接用浏览器打开 index.html
```

## 项目结构

```
fund-daily/
├── index.html                  # 仪表盘主页面（SPA，4视图切换）
├── portfolio.json              # 持仓配置（你的基金信息）
├── config.example.json         # 配置模板（脱敏）
├── requirements.txt            # Python 依赖
├── main.py                     # 统一入口脚本
├── LICENSE                     # MIT 协议
│
├── src/                        # Python 模块
│   ├── phase1_daily_report.py  # 每日收盘日报
│   ├── signals.py              # 买卖信号引擎
│   ├── diagnostics.py          # 持仓诊断引擎
│   ├── phase4_diagnostic_report.py  # 周/月诊断报告
│   ├── news_signal.py          # 消息面参考卡
│   ├── ask.py                  # 对话查询接口
│   └── export_json.py          # 仪表盘数据导出
│
├── tests/                      # 单元测试
│   ├── test_signals.py
│   └── test_diagnostics.py
│
└── data/                       # 数据目录（git 忽略）
    ├── history/                # 基金净值缓存
    └── reports/                # 生成的 HTML 报告
```

## 数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| 基金净值 | akshare | 官方净值（每日收盘后更新） |
| 盘中估值 | akshare | 交易时段实时预估 |
| 个股新闻 | akshare / 腾讯自选股 MCP | 按关联股票拉取 |
| 宏观经济 | akshare | 经济日历事件 |
| 微博情绪 | akshare | 讨论热度系数 |
| 雪球热度 | akshare | 关注度排行 |
| 基金公告 | akshare | 季报/年报公告 |

## 信号说明

### 红绿灯（估值）
- 🔴 **过热（红灯）**：净值处于近 1 年高位（≥80% 分位）
- 🟡 **中性（黄灯）**：净值处于中间区间
- 🟢 **低估（绿灯）**：净值处于近 1 年低位（≤20% 分位）

### 止盈阶梯
- 近 1 年涨幅触达 15%/20%/25% 时提示
- 无真实成本时用"近 1 年涨幅"代理（方案 B 口径）

### 异动预警
- 单日跌幅 > 3%
- 连续下跌 ≥ 3 日

## 诊断指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| HHI | 集中度指数，越大越集中 | > 0.15 偏高 |
| 前三大占比 | 前 3 只基金市值占比 | > 60% 偏高 |
| 风险桶 | 同类资产占比 | > 40% 偏高 |
| 相关性 | 两两基金收益率相关系数 | > 0.70 假分散 |
| 夏普比率 | 风险调整后收益 | > 1.0 良好 |
| 最大回撤 | 历史最大亏损幅度 | — |

## 测试

```bash
python -m pytest tests/ -v
```

## 配置说明

### signals 配置

```json
{
  "valuation_window": 252,        // 估值百分位窗口（交易日）
  "valuation_high": 80,           // 红灯阈值（百分位）
  "valuation_low": 20,            // 绿灯阈值（百分位）
  "take_profit_baseline": "2025-01-01",  // 止盈基准日
  "take_profit_tiers": [15, 20, 25],     // 止盈档位（%）
  "anomaly_drop_pct": 3.0,        // 异动跌幅阈值（%）
  "anomaly_consecutive_down": 3    // 异动连跌天数
}
```

### diagnostics 配置

```json
{
  "rf": 0.015,                    // 无风险利率（年化）
  "single_limit": 25.0,           // 单只占比阈值（%）
  "bucket_limit": 40.0,           // 风险桶占比阈值（%）
  "hhi_limit": 0.15,              // HHI 阈值
  "corr_limit": 0.70,             // 相关性阈值
  "benchmark": ["000300", "000012"]  // 基准指数代码
}
```

## 技术栈

- **后端**：Python 3.11 + pandas + akshare
- **前端**：Tailwind CSS + Alpine.js + ECharts
- **数据源**：akshare（行情/净值/新闻）+ 腾讯自选股 MCP（新闻/板块）
- **测试**：pytest

## 常见问题

### Q: 为什么用 Python 3.11 而不是 3.13？
A: akshare 的依赖 `tqdm` 在 Python 3.13 上没有对应发行版，会导致安装失败。推荐使用 Python 3.11.9。

### Q: 盘中估值准吗？
A: 盘中估值是平台按持仓实时估算的**预估值**，收盘后常与官方净值有偏差（波动大时 0.5%-1%+），仅作参考。

### Q: QDII 基金净值为什么滞后？
A: QDII 基金（如纳斯达克 100）投资海外市场，净值通常滞后 1-2 个交易日。报告中会标注"滞后"。

### Q: 如何添加新的基金？
A: 编辑 `portfolio.json`，在 `holdings` 数组中添加新基金，并在 `theme_map` 中配置关联股票和关键词。

## 路线图

- [x] v0.1.0 - MVP 版本（日报/消息面/诊断/信号）
- [ ] v0.2.0 - 数据自动化（一键生成 + 定时任务）
- [ ] v0.3.0 - 功能增强（真实成本 + 情绪分析）
- [ ] v1.0.0 - 生态完善（插件系统 + 社区贡献）

## 许可证

[MIT License](LICENSE)
