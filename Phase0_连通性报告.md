# Phase 0 — 数据层连通性验证报告

- **测试时间**：2026-07-21 14:58
- **系统**：Windows；解释器为系统 Python 3.11.9（managed 3.13 因 akshare 依赖冲突不可用，已按 fallback 规则切换）
- **venv 路径**：`C:\Users\DEDIPLINE\.workbuddy\binaries\python\envs\fund-daily-py311`
- **已安装**：akshare 1.18.66 / easyquotation 0.7.7 / yfinance 1.5.1（含 pandas 3.0.3 / numpy 2.4.6 等依赖）
- **运行命令**：`fund-daily-py311\Scripts\python.exe src\phase0_connectivity.py`

## 一、结论速览

| 数据源 | 能否取数 | 耗时 | 字段完整性 | 备注 |
|---|---|---|---|---|
| akshare | ✅ | 24.6s（全市场 1552 只 ETF） | 完整：代码/名称/最新价/涨跌幅/成交额 | **主数据源**，权威（东方财富） |
| easyquotation | ✅ | 0.07s | 现价+昨收齐全；涨跌幅需由 `(now-昨收)/昨收` 计算 | 极速备用源，与 akshare 数据一致 |
| yfinance | ⚠️ | 14.9s | 0 行（雅虎 `YFRateLimitError` 限流） | 沙箱 IP 被限流，暂不可用 |

**可用数据源：3/3 库均能 import 并运行；实际有效数据 = akshare + easyquotation。**

## 二、实测数据快照（代表性标的，双源交叉验证）

| 代码 | 名称 | akshare 最新价 | akshare 涨跌幅 | easyquotation 现价 | easyquotation 涨跌幅(计算) |
|---|---|---|---|---|---|
| 512480 | 半导体ETF国联安 | 1.144 | +10.00% | 1.144 | +10.00% |
| 518880 | 黄金ETF华安 | 8.466 | +1.78% | 8.466 | +1.78% |
| 515030 | 新能源车ETF华夏 | 1.579 | +4.09% | 1.579 | +4.09% |
| 513100 | 纳指ETF国泰 | 2.130 | +1.62% | 2.130 | +1.62% |
| 159941 | 纳指ETF广发 | 1.587 | +2.32% | 1.587 | +2.32% |

→ easyquotation 计算的涨跌幅与 akshare **完全吻合**，双源一致性通过。

## 三、关键发现 / 踩坑

1. **Python 版本坑**：managed 环境 3.13.14 安装 akshare 报 `ResolutionImpossible`（依赖回溯要求一个 3.13 上无对应发行版的 `tqdm`）。已 fallback 到系统 Python 3.11.9（akshare 生态在 3.11 最稳）解决。
2. **D 盘 venv 坑**：沙箱内 D 盘无法落盘 venv（`python -m venv` 静默返回 0 但不生成文件）。venv 必须建在 managed 区 `C:\Users\DEDIPLINE\.workbuddy\binaries\python\envs\`。
3. **easyquotation 无涨跌幅字段**：sina 源返回 `now`(现价)/`close`(=昨收)/五档买卖等，无直接涨跌幅，需自行计算。
4. **yfinance 限流**：雅虎返回 `YFRateLimitError: Too Many Requests`。但纳指 ETF（513100/159941）已被 akshare 覆盖，**不影响你的持仓数据获取**。

## 四、对方案 B 的调整建议

- **数据层精简**：主源 `akshare` + 快速备用 `easyquotation`；`yfinance` 暂弃。
  - 若后续确需美股指数 / QQQ，可加代理，或改用 akshare 的 `stock_us_spot_em` 等美股接口。
- **性能优化（Phase 1）**：akshare 全市场拉取约 24s 偏慢；改为仅按 `portfolio.json` 的目标代码拉取 + 日间缓存。
- **涨跌幅口径**：以 akshare 为准；easyquotation 用于收盘瞬间快速校验。

## 五、下一步（Phase 1：基础每日收盘日报）

1. 用户发来持仓截图 → 读图识别真实基金代码 → 固化 `portfolio.json`（成本/定投额/止盈线）。
2. 实现 `fetch_data.py`：仅拉目标标的 + 缓存；`indicators.py` 算估值/止盈/异动；`report.py` 生成 HTML 日报（红涨绿跌）。
3. 接入 WorkBuddy 定时推送（每个交易日收盘后）。
