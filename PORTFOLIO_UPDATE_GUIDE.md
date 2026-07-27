# 持仓配置修改指南

## 📋 概述

本文档说明如何手动修改持仓配置文件 `portfolio.json` 并更新网站数据。

## 🔍 当前架构说明

### 文件结构
```
fund-daily/
├── .github/workflows/
│   ├── update-data.yml      # 数据更新工作流（已禁用）
│   └── deploy-pages.yml     # 网站部署工作流
├── portfolio.json           # 持仓配置文件（本地维护）
├── data/dashboard.json      # 生成的数据文件（部署到GitHub）
└── index.html               # 前端页面
```

### 数据流程
1. **配置阶段**：用户编辑 `portfolio.json` 文件
2. **更新阶段**：运行 `python main.py export` 生成新的 `dashboard.json`
3. **部署阶段**：推送代码到GitHub，自动部署到GitHub Pages
4. **查看阶段**：用户访问网站查看更新后的数据

## ✏️ 修改持仓配置

### 方法一：直接编辑 portfolio.json

#### 1. 备份当前配置
```bash
# 在项目目录下
cp portfolio.json portfolio.json.backup
```

#### 2. 编辑 portfolio.json
使用任何文本编辑器打开 `portfolio.json` 文件，修改以下部分：

**持仓信息示例：**
```json
{
  "holdings": [
    {
      "code": "014194",
      "name": "汇添富中证芯片产业指数增强C",
      "type": "股票型-行业指增",
      "category": "半导体/芯片",
      "amount": 986.63
    }
  ]
}
```

**修改持仓金额：**
```json
{
  "code": "014194",
  "name": "汇添富中证芯片产业指数增强C",
  "type": "股票型-行业指增",
  "category": "半导体/芯片",
  "amount": 1000.00  // 修改持仓金额
}
```

**添加新基金：**
```json
{
  "code": "新基金代码",
  "name": "新基金名称",
  "type": "基金类型",
  "category": "基金类别",
  "amount": 持仓金额
}
```

**删除基金：**
直接删除对应的JSON对象即可。

#### 3. 保存并验证
```bash
# 验证JSON格式
python -c "import json; json.load(open('portfolio.json', encoding='utf-8')); print('✅ JSON格式正确')"
```

### 方法二：使用在线JSON编辑器

1. 打开 [JSON编辑器在线](https://jsoneditoronline.org/)
2. 复制 `portfolio.json` 的内容
3. 在编辑器中修改
4. 复制修改后的内容
5. 粘贴回 `portfolio.json` 文件

## 🔄 更新网站数据

### 本地更新（推荐）

#### 1. 运行数据更新脚本
```bash
# 在项目根目录下
python main.py export
```

这将执行以下操作：
- 读取最新的 `portfolio.json` 配置
- 从akshare获取基金净值数据
- 生成新的 `data/dashboard.json` 文件

#### 2. 验证更新结果
```bash
# 查看生成时间
python -c "import json; d=json.load(open('data/dashboard.json')); print(f'生成时间: {d[\"generatedAt\"]}')"

# 查看持仓数量
python -c "import json; d=json.load(open('data/dashboard.json')); print(f'持仓数量: {len(d[\"holdings\"])}')"
```

### 推送到GitHub

#### 1. 添加更改
```bash
# 添加修改的文件
git add portfolio.json data/dashboard.json

# 查看更改
git status
```

#### 2. 提交更改
```bash
git commit -m "更新持仓配置 - $(date +'%Y-%m-%d %H:%M')"
```

#### 3. 推送到GitHub
```bash
git push origin main
```

#### 4. 等待自动部署
- GitHub Actions会自动检测到代码变更
- 约1-2分钟后网站会自动更新

## 🛠️ 常见问题解决

### 问题1：JSON格式错误
**症状**：运行 `python main.py export` 时报错

**解决方法**：
```bash
# 检查JSON语法
python -m json.tool portfolio.json
```

### 问题2：基金代码不存在
**症状**：数据更新时某些基金显示为"无数据"

**解决方法**：
1. 检查基金代码是否正确（6位数字）
2. 确认基金是否为场外开放式基金
3. 使用akshare验证基金代码：
```python
import akshare as ak
# 测试基金代码是否存在
try:
    df = ak.fund_open_fund_info_em(symbol="014194", indicator="单位净值走势")
    print(f"✅ 基金代码 014194 有效")
except Exception as e:
    print(f"❌ 基金代码 014194 无效: {e}")
```

### 问题3：GitHub Actions更新失败
**症状**：网站数据未更新

**解决方法**：
1. 检查GitHub Actions状态
2. 手动触发部署工作流
3. 查看Actions日志排查问题

## 📝 持仓配置说明

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | ✅ | 基金代码（6位数字） |
| name | string | ✅ | 基金全称 |
| type | string | ✅ | 基金类型（如：股票型-行业指增） |
| category | string | ✅ | 基金类别（如：半导体/芯片） |
| amount | number | ✅ | 持仓金额（元） |

### 基金类型分类

- **股票型-行业指增**：行业指数增强基金
- **混合型-偏股**：偏股混合型基金
- **黄金**：黄金ETF联接基金
- **QDII-股票**：投资海外股票的QDII基金
- **债券型-中长债**：中长期纯债基金

### 基金类别分类

- **半导体/芯片**：半导体、芯片相关
- **碳中和/制造**：新能源、制造业
- **黄金**：黄金、贵金属
- **新能源/汽车**：新能源汽车产业链
- **纳斯达克/QDII**：海外科技股
- **科技/数字经济**：数字经济、AI
- **机器人/高端制造**：机器人、高端制造
- **电网/电力设备**：电网设备、电力
- **债券/避险**：债券、避险资产
- **资源/周期**：有色金属、资源股

## 🔧 高级配置

### 修改信号参数

在 `portfolio.json` 的 `signals` 部分可以调整信号参数：

```json
{
  "signals": {
    "valuation_window": 252,        // 估值窗口（交易日）
    "valuation_high": 80,           // 高估阈值
    "valuation_low": 20,            // 低估阈值
    "take_profit_baseline": "2025-07-20",  // 止盈基准日期
    "take_profit_tiers": [15, 20, 25],     // 止盈档位（%）
    "anomaly_drop_pct": 3.0,        // 异常下跌阈值（%）
    "anomaly_consecutive_down": 3   // 连续下跌天数阈值
  }
}
```

### 修改主题映射

`theme_map` 部分定义了每只基金关联的股票和关键词：

```json
{
  "theme_map": {
    "014194": {
      "stocks": ["688981", "688256"],
      "stock_names": ["中芯国际", "寒武纪"],
      "keywords": ["芯片", "半导体", "IC", "晶圆"],
      "note": "芯片指增→半导体龙头"
    }
  }
}
```

## 📞 技术支持

如果遇到问题，请：

1. 查看本指南的常见问题部分
2. 检查项目的 `GITHUB_PAGES_DEPLOY.md` 文档
3. 查看 `DEPLOYMENT_EXPERIENCE_SKILL.md` 了解部署经验
4. 在GitHub Issues中提问

## 📅 更新日志

- **2026-07-27**：创建本指南，说明手动配置持仓数据的方法
- **2026-07-26**：更新工作流配置，暂时禁用自动更新任务