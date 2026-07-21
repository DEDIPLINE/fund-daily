# -*- coding: utf-8 -*-
"""
方案B · Phase 2 —— 信号引擎（纯规则，pandas 实现，无外部框架依赖）

输入：每只基金的净值历史缓存（data/history/{code}.csv，列：净值日期/单位净值/日增长率）
输出：结构化信号 dict，包含三类信号：
  1) 估值红绿灯  —— 当前净值在自身历史(默认近1年)中的百分位
  2) 止盈阶梯    —— 自基准日(方案B默认近1年)以来的累计涨幅，触 15/20/25% 档
  3) 异动预警    —— 单日跌幅 >3% 或 连续下跌 >=3 日

所有信号均为“提示”，非投资建议，最后由解读层(WorkBuddy)翻成白话。

注意（方案B口径）：
  用户未提供真实成本，止盈用“自基准日涨幅”近似。基准日默认取近1年(2025-07-20)，
  因为用持仓快照日(2026-07-20)做基准会得到 ~0% 而无意义；近1年涨幅是衡量“涨势”的合理代理。
  若用户日后提供成本，可切换为真实收益率口径（方案A）。
"""

import pandas as pd

# 默认值（与 portfolio.json 的 signals 配置块保持一致；缺省时回退到此）
DEFAULT_CFG = {
    "valuation_window": 252,      # 百分位窗口（交易日，约1年）
    "valuation_high": 80,         # 百分位 >= 此值 → 红(过热)
    "valuation_low": 20,          # 百分位 <= 此值 → 绿(低估)
    "take_profit_baseline": "2025-07-20",  # 方案B止盈基准日（近1年）
    "take_profit_tiers": [15, 20, 25],      # 止盈阶梯(%)
    "anomaly_drop_pct": 3.0,      # 单日跌幅阈值(%)
    "anomaly_consecutive_down": 3,          # 连续下跌天数阈值
}

LIGHT_COLOR = {"red": "#d40000", "yellow": "#c47f00", "green": "#008000", "unknown": "#888888"}
LIGHT_LABEL = {"red": "过热", "yellow": "中性", "green": "低估", "unknown": "数据不足"}


def valuation_percentile(nav, window=252):
    """最新净值在最近 window 个观测值中的百分位(0-100)。None 表示数据不足。"""
    recent = nav.tail(window)
    if recent.empty or len(recent) < 5:
        return None
    latest = recent.iloc[-1]
    # 严格小于最新值的观测占比（最新值本身不计入“低于”）
    below = (recent < latest).mean() * 100.0
    return round(below, 1)


def valuation_light(pct, high=80, low=20):
    if pct is None:
        return "unknown"
    if pct >= high:
        return "red"
    if pct <= low:
        return "green"
    return "yellow"


def trailing_return(nav, dates, baseline_date):
    """自 baseline_date（含）以来净值累计涨幅(%)。无数据返回 None。"""
    if nav is None or nav.empty:
        return None
    d = dates.astype(str)
    mask = d >= str(baseline_date)
    if mask.any():
        idx = mask.idxmax()  # 首个 >= 基准日的索引
    else:
        idx = nav.index[0]   # 否则取最早
    base = nav.loc[idx]
    latest = nav.iloc[-1]
    if base in (0, None) or pd.isna(base):
        return None
    return round((latest / base - 1.0) * 100.0, 2)


def take_profit_tier(gain, tiers):
    """返回已触发的最高档位（0 表示未触发）。"""
    if gain is None:
        return 0
    triggered = [t for t in tiers if gain >= t]
    return max(triggered) if triggered else 0


def anomaly_signal(growth, drop_pct=3.0, consecutive=3):
    """异动预警：单日跌幅 > drop_pct 或 连续下跌 >= consecutive 日。"""
    g = pd.to_numeric(growth, errors="coerce").dropna()
    if g.empty:
        return {"single_drop": False, "consecutive_down": 0, "triggered": False, "latest_growth": None}
    latest = float(g.iloc[-1])
    single = latest <= -abs(drop_pct)
    cnt = 0
    for v in reversed(g.tolist()):
        if v < 0:
            cnt += 1
        else:
            break
    triggered = bool(single) or (cnt >= consecutive)
    return {"single_drop": single, "consecutive_down": cnt, "triggered": triggered, "latest_growth": latest}


def compute_signals(cache, cfg=None, fund_type="", category=""):
    """对单只基金的净值缓存计算全部信号。cache 为 DataFrame(净值日期/单位净值/日增长率)。
    fund_type/category 用于债券等低波动品种的特例处理。"""
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    df = cache.copy()
    df["净值日期"] = df["净值日期"].astype(str)
    df["单位净值"] = pd.to_numeric(df["单位净值"], errors="coerce")
    df["日增长率"] = pd.to_numeric(df["日增长率"], errors="coerce")
    df = df.sort_values("净值日期").reset_index(drop=True)
    nav = df["单位净值"]

    pct_rank = valuation_percentile(nav, cfg["valuation_window"])
    light = valuation_light(pct_rank, cfg["valuation_high"], cfg["valuation_low"])

    # 债券/避险类：净值波动极小，靠近历史高位是常态，百分位“过热/低估”无买卖含义，
    # 统一视为中性，避免误导小白误判“该卖”。
    is_bond = ("债券" in (fund_type or "")) or ("债券" in (category or "")) or ((category or "") in ("债券/避险",))
    if is_bond and light in ("red", "green"):
        light = "yellow"
    gain = trailing_return(nav, df["净值日期"], cfg["take_profit_baseline"])
    tier = take_profit_tier(gain, cfg["take_profit_tiers"])
    anom = anomaly_signal(df["日增长率"], cfg["anomaly_drop_pct"], cfg["anomaly_consecutive_down"])

    return {
        "pct_rank": pct_rank,
        "light": light,
        "gain_since_base": gain,
        "baseline": cfg["take_profit_baseline"],
        "take_profit_tier": tier,
        "tiers": cfg["take_profit_tiers"],
        "anomaly": anom,
    }


def signal_summary(rows):
    """根据全部基金信号生成“白话小结”文本（纯模板，确定性）。返回 str。"""
    red = [r for r in rows if r.get("sig", {}).get("light") == "red"]
    green = [r for r in rows if r.get("sig", {}).get("light") == "green"]
    tp = [r for r in rows if (r.get("sig", {}).get("take_profit_tier") or 0) > 0]
    an = [r for r in rows if r.get("sig", {}).get("anomaly", {}).get("triggered")]

    lines = []
    if not (red or green or tp or an):
        return "今日无红灯 / 止盈 / 异动信号，持仓整体平稳，按既定周定投计划执行即可。"

    if red:
        names = "、".join(f"{r['name'][:6]}…（近1年{r['sig']['pct_rank']:.0f}%分位）" for r in red)
        lines.append(f"[过热] {names} 当前净值处于近1年高位，涨多后注意别追高，可考虑暂停加仓或分批止盈。")
    if green:
        names = "、".join(f"{r['name'][:6]}…" for r in green)
        lines.append(f"[低估] {names} 处于近1年低位，若看好长期逻辑，定投可正常甚至适度加码。")
    if tp:
        items = "、".join(f"{r['name'][:6]}…（近1年{r['sig']['gain_since_base']:+.1f}%，触第{r['sig']['take_profit_tier']}档）" for r in tp)
        lines.append(f"[止盈] {items} 已达止盈阶梯，若前期盈利丰厚可考虑部分止盈落袋。")
    if an:
        items = "、".join(f"{r['name'][:6]}…（{'单日'+format(r['sig']['anomaly']['latest_growth'],'.2f')+'%' if r['sig']['anomaly']['single_drop'] else '连跌'+str(r['sig']['anomaly']['consecutive_down'])+'日'}）" for r in an)
        lines.append(f"[异动] {items} 出现异常下跌，关注是否系统性回撤，勿恐慌性杀跌。")
    lines.append("以上为数据信号提示，非买卖指令；具体操作请结合自身定投计划与风险承受力。")
    return "\n".join(lines)
