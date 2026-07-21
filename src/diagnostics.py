# -*- coding: utf-8 -*-
"""
方案B · Phase 4 —— 持仓诊断引擎（M2，纯 pandas/numpy 实现，无外部框架依赖）

理论根基（均为标准金融工程工具箱，非自创）：
  - 相关性矩阵      : 现代投资组合理论 MPT (Markowitz, 1952)
  - 年化波动率      : std(日收益) × √252（年交易日），MPT 风险度量
  - 最大回撤 MDD    : 峰-谷最深跌幅，风控通用指标
  - 夏普比率 Sharpe : (年化收益 − 无风险利率) / 年化波动 (Sharpe, 1966)
  - HHI 集中度      : 产业组织经济学（反垄断 DOJ 标准）借用到组合 Σ权重²
  - 风险桶聚合      : 定性归类（由 category/type 关键词映射），仅用于“是否假分散”判定

全部指标向后看（历史估计），非预测。相关/波动在极端行情下会失效（相关性趋同于 1）。

注意：
  - 组合风险用【持仓金额加权】（真实仓位），非等权。
  - 无真实成本时，收益/回撤用金额加权净值日增长率近似（非资金加权真实收益）。
  - 基准对比默认取 沪深300 与 中债综合(近似用中证综合债)，网络不可达时自动跳过该区块。
"""

import os
import json
import datetime
import numpy as np
import pandas as pd
import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = os.path.join(ROOT, "portfolio.json")
HISTORY_DIR = os.path.join(ROOT, "data", "history")

SQRT252 = 252 ** 0.5

# 默认配置（可被 portfolio.json 的 diagnostics 块覆盖）
DEFAULT_CFG = {
    "rf": 0.015,                 # 无风险利率（年化），约中国10年期国债
    "single_limit": 25.0,        # 单只权重上限(%)，触发提示
    "bucket_limit": 40.0,        # 单一风险桶权重上限(%)，触发提示
    "hhi_limit": 0.15,           # HHI 上限（>0.15 视为偏高集中）
    "corr_limit": 0.70,          # 相关性上限（>0.7 视为高同质/假分散）
    "benchmark": ["000300", "000012"],  # 沪深300 / 上证国债指数(防御基准)
    "benchmark_names": {"000300": "沪深300", "000012": "上证国债指数"},
}

# 风险桶关键词映射（分类用语 → 风险桶）
RISK_BUCKET_RULES = [
    ("债券", "债券/避险"),
    ("黄金", "商品/避险"),
    ("QDII", "海外权益"),
    ("纳指", "海外权益"),
]


def classify_risk_bucket(category, fund_type, name):
    """把一只基金归类到风险桶。优先关键词匹配，兜底归为 A股成长/周期。"""
    text = f"{category} {fund_type} {name}"
    for kw, bucket in RISK_BUCKET_RULES:
        if kw in text:
            return bucket
    return "A股成长/周期"


def load_portfolio():
    with open(PORTFOLIO, encoding="utf-8") as f:
        return json.load(f)


def load_returns_matrix(holdings):
    """读各基金净值缓存，构造对齐的日收益率矩阵。
    返回 (returns_df, weights_series, aligned_info)
      returns_df: index=净值日期, columns=code, values=日收益率(小数)
      weights_series: code -> 金额权重(小数)
    """
    series = {}
    amounts = {}
    for h in holdings:
        code = h["code"]
        amounts[code] = float(h.get("amount", 0.0))
        path = os.path.join(HISTORY_DIR, f"{code}.csv")
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        df["净值日期"] = df["净值日期"].astype(str).str[:10]
        df["日增长率"] = pd.to_numeric(df["日增长率"], errors="coerce")
        ret = (df["日增长率"] / 100.0).rename(code)
        ret.index = df["净值日期"]
        series[code] = ret.dropna()

    if not series:
        return pd.DataFrame(), pd.Series(dtype=float), {}
    returns_df = pd.concat(series.values(), axis=1, join="inner")
    returns_df.columns = list(series.keys())
    returns_df = returns_df.sort_index()

    total = sum(amounts.values()) or 1.0
    weights = pd.Series({c: amounts[c] / total for c in returns_df.columns})
    # 仅保留矩阵内有的 code
    weights = weights[returns_df.columns]
    return returns_df, weights, {"total_amount": total}


def concentration_metrics(weights, holdings):
    """集中度：单只权重、分类权重、HHI。"""
    # 单只
    items = []
    for code, w in weights.items():
        h = next((x for x in holdings if x["code"] == code), {})
        items.append({
            "code": code, "name": h.get("name", code),
            "category": h.get("category", ""),
            "weight": round(w * 100, 2),
            "amount": round(float(h.get("amount", 0.0)), 2),
        })
    items.sort(key=lambda x: x["weight"], reverse=True)

    # 分类聚合
    cat = {}
    for h in holdings:
        code = h["code"]
        if code not in weights.index:
            continue
        c = cat.setdefault(h.get("category", "其他"), 0.0)
        cat[h.get("category", "其他")] = c + weights[code] * 100
    cat = {k: round(v, 2) for k, v in sorted(cat.items(), key=lambda kv: kv[1], reverse=True)}

    hhi = float((weights ** 2).sum())
    # 前三大权重之和
    top3 = round(float(weights.sort_values(ascending=False).head(3).sum() * 100), 2)
    return {"single": items, "by_category": cat, "hhi": round(hhi, 4),
            "top3_weight": top3, "n_funds": len(weights)}


def risk_bucket_metrics(weights, holdings):
    """风险桶聚合（定性归类）。"""
    buckets = {}
    for h in holdings:
        code = h["code"]
        if code not in weights.index:
            continue
        b = classify_risk_bucket(h.get("category", ""), h.get("type", ""), h.get("name", ""))
        buckets[b] = buckets.get(b, 0.0) + weights[code] * 100
    return {k: round(v, 2) for k, v in sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)}


def correlation_analysis(returns_df, corr_limit=0.70):
    """相关性矩阵 + 高相关对（假分散检测）。"""
    if returns_df.shape[1] < 2:
        return {"matrix": {}, "high_pairs": [], "avg_corr": None}
    corr = returns_df.corr()
    codes = list(corr.columns)
    high_pairs = []
    vals = []
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            c = corr.iloc[i, j]
            if pd.notna(c):
                vals.append(c)
                if c >= corr_limit:
                    high_pairs.append({
                        "a": codes[i], "b": codes[j], "corr": round(float(c), 3),
                    })
    high_pairs.sort(key=lambda x: x["corr"], reverse=True)
    avg = float(np.mean(vals)) if vals else None
    # 矩阵转 dict（保留2位）
    matrix = {a: {b: (None if pd.isna(corr.loc[a, b]) else round(float(corr.loc[a, b]), 3))
                  for b in codes} for a in codes}
    return {"matrix": matrix, "high_pairs": high_pairs,
            "avg_corr": round(avg, 3) if avg is not None else None,
            "n_pairs": len(vals)}


def risk_metrics(returns_df, weights, rf=0.015):
    """组合加权波动率/收益/夏普/最大回撤。"""
    if returns_df.empty or weights.empty:
        return {}
    w = weights.reindex(returns_df.columns).fillna(0.0).values
    port_ret = returns_df.dot(w)
    mean_ann = float(port_ret.mean() * 252)
    vol = float(port_ret.std() * SQRT252)
    sharpe = float((mean_ann - rf) / vol) if vol > 0 else None
    cum = (1 + port_ret).cumprod()
    mdd = float(((cum - cum.cummax()) / cum.cummax()).min())
    # 区间累计收益
    cum_ret = float(cum.iloc[-1] - 1.0)
    n_days = len(port_ret)
    return {
        "mean_annual": round(mean_ann * 100, 2),
        "vol_annual": round(vol * 100, 2),
        "sharpe": round(sharpe, 2) if sharpe is not None else None,
        "max_drawdown": round(mdd * 100, 2),
        "cum_return": round(cum_ret * 100, 2),
        "n_days": n_days,
        "window_years": round(n_days / 252, 2),
    }


def benchmark_metrics(returns_df, rf=0.015, codes=("000300", "000012"), names=None):
    """拉取宽基/债券基准，与组合同窗口比较年化波动/收益/夏普。
    用 stock_zh_index_daily(symbol="sh{code}")；网络不可达时跳过该基准。"""
    names = names or {}
    if returns_df.empty:
        return []
    out = []
    for code in codes:
        try:
            df = ak.stock_zh_index_daily(symbol=f"sh{code}")
            df["date"] = df["date"].astype(str)
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            price = df.set_index("date")["close"].dropna()
            price = price[~price.index.duplicated(keep="last")].sort_index()
            price = price.reindex(returns_df.index).dropna()
            if len(price) < 30:
                continue
            ret = price.pct_change().dropna()
            ret = ret.reindex(returns_df.index).dropna()
            if ret.empty:
                continue
            vol = float(ret.std() * SQRT252)
            mean_ann = float(ret.mean() * 252)
            sharpe = float((mean_ann - rf) / vol) if vol > 0 else None
            cum = float((1 + ret).prod() - 1.0)
            out.append({
                "code": code, "name": names.get(code, code),
                "vol_annual": round(vol * 100, 2),
                "mean_annual": round(mean_ann * 100, 2),
                "sharpe": round(sharpe, 2) if sharpe is not None else None,
                "cum_return": round(cum * 100, 2),
            })
        except Exception as e:
            print(f"   ⚠️ 基准 {code} 获取失败: {e}")
            continue
    return out


def rebalance_suggestions(conc, buckets, corr, cfg):
    """规则化再平衡建议（提示，非指令）。"""
    sug = []
    # 单只超限
    over_single = [s for s in conc["single"] if s["weight"] > cfg["single_limit"]]
    if over_single:
        names = "、".join(f"{s['name'][:6]}…({s['weight']}%)" for s in over_single)
        sug.append({"level": "warning",
                    "text": f"单只占比偏高：{names} 超过 {cfg['single_limit']}% 阈值，建议定投时适度降速或设置单只上限。"})
    # 风险桶超限
    over_bucket = {b: w for b, w in buckets.items() if w > cfg["bucket_limit"]}
    if over_bucket:
        names = "、".join(f"{b}({w}%)" for b, w in over_bucket.items())
        sug.append({"level": "warning",
                    "text": f"风险桶集中：{names} 超过 {cfg['bucket_limit']}% 阈值，整体暴露于同一类风险，建议增配低相关资产（如债券/黄金）平衡。"})
    # HHI
    if conc["hhi"] > cfg["hhi_limit"]:
        sug.append({"level": "warning",
                    "text": f"集中度偏高：HHI={conc['hhi']} > {cfg['hhi_limit']}，前三大占比 {conc['top3_weight']}%，分散度不足。"})
    # 高相关对（假分散）
    if corr["high_pairs"]:
        pairs = "、".join(f"{a}↔{b}({c})" for a, b, c in
                         [(p["a"], p["b"], p["corr"]) for p in corr["high_pairs"][:4]])
        sug.append({"level": "warning",
                    "text": f"假分散提示：{pairs} 相关性高，看似多只实则同涨同跌；减少重复敞口比单纯加数量更有效。"})
    if not sug:
        sug.append({"level": "ok",
                    "text": "当前集中度、风险桶、相关性均在合理范围内，维持既定周定投节奏即可。"})
    return sug


def run_diagnostics(portfolio_path=None, cfg=None):
    """主入口：返回完整诊断 dict。"""
    pf = load_portfolio()
    cfg = {**DEFAULT_CFG, **(cfg or {}), **(pf.get("diagnostics", {}) or {})}
    # 兼容 benchmarks 命名
    if "benchmarks" in cfg:
        cfg["benchmark"] = cfg.pop("benchmarks")
    holdings = pf["holdings"]
    returns_df, weights, info = load_returns_matrix(holdings)
    if returns_df.empty:
        return {"error": "无可用净值数据，请先运行 Phase 1 抓取历史。"}

    conc = concentration_metrics(weights, holdings)
    buckets = risk_bucket_metrics(weights, holdings)
    corr = correlation_analysis(returns_df, cfg["corr_limit"])
    risk = risk_metrics(returns_df, weights, cfg["rf"])
    bench = benchmark_metrics(returns_df, cfg["rf"], cfg["benchmark"], cfg.get("benchmark_names", {}))
    sug = rebalance_suggestions(conc, buckets, corr, cfg)

    return {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_amount": round(info["total_amount"], 2),
        "n_funds": conc["n_funds"],
        "window": risk.get("window_years"),
        "concentration": conc,
        "buckets": buckets,
        "correlation": corr,
        "risk": risk,
        "benchmarks": bench,
        "suggestions": sug,
        "cfg": {k: cfg[k] for k in ("rf", "single_limit", "bucket_limit", "hhi_limit", "corr_limit")},
    }


if __name__ == "__main__":
    import pprint
    d = run_diagnostics()
    pprint.pprint({k: v for k, v in d.items() if k not in ("correlation",)})
    print("\n=== 高相关对(假分散) ===")
    for p in d["correlation"]["high_pairs"]:
        print(f"  {p['a']} ↔ {p['b']} : {p['corr']}")
    print("\n=== 再平衡建议 ===")
    for s in d["suggestions"]:
        print(f"  [{s['level']}] {s['text']}")
