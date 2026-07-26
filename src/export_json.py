# -*- coding: utf-8 -*-
"""
数据导出 → data/dashboard.json
将各模块数据汇聚为 JSON，供前端 index.html 读取。
运行：python src/export_json.py
"""
import json
import os
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd
import akshare as ak

DATA_DIR = os.path.join(ROOT, "data")
JSON_PATH = os.path.join(DATA_DIR, "dashboard.json")
os.makedirs(DATA_DIR, exist_ok=True)


def load_portfolio():
    with open(os.path.join(ROOT, "portfolio.json"), encoding="utf-8") as f:
        return json.load(f)


def fetch_fund_data(pf):
    """抓取每只基金的最新净值、涨跌、信号等"""
    import signals
    cfg = pf.get("signals", {})
    results = []

    # 盘中估值
    try:
        est_df = ak.fund_value_estimation_em(symbol="全部")
        est_map = {}
        for _, row in est_df.iterrows():
            code = str(row.get("基金代码", "")).strip()
            if not code:
                continue
            est_pct_col = None
            for c in est_df.columns:
                if "估算数据-估算增长率" in c:
                    est_pct_col = c
                    break
            if est_pct_col:
                try:
                    val = row[est_pct_col]
                    if val and str(val).strip() not in ("", "---", "NaN"):
                        est_map[code] = float(str(val).replace("%", "").replace(",", "").strip())
                except Exception:
                    pass
    except Exception:
        est_map = {}

    for h in pf["holdings"]:
        code = h["code"]
        cache_path = os.path.join(DATA_DIR, "history", f"{code}.csv")
        if not os.path.exists(cache_path):
            results.append({
                "code": code, "shortName": h["name"][:6],
                "amount": h["amount"], "nav": None, "pct": None,
                "estPct": est_map.get(code), "light": None, "lightLabel": "—",
                "gain": None, "tpTier": 0, "anomaly": False, "pctRank": None,
                "lag": False, "sparkPoints": ""
            })
            continue

        cache = pd.read_csv(cache_path)
        if cache.empty:
            continue

        row = cache.iloc[-1]
        try:
            nav = float(row["单位净值"])
        except Exception:
            nav = None
        try:
            pct = float(row["日增长率"]) if pd.notna(row["日增长率"]) else None
        except Exception:
            pct = None

        # 信号
        sig = {}
        try:
            sig = signals.compute_signals(cache, cfg, h.get("type", ""), h.get("category", ""))
        except Exception:
            pass

        # 迷你走势
        recent = cache.tail(20)
        try:
            vals = recent["单位净值"].astype(float).tolist()
            if len(vals) >= 2:
                vmin, vmax = min(vals), max(vals)
                rng = (vmax - vmin) or 1
                pts = []
                for i, v in enumerate(vals):
                    x = 2 + i * 96 / (len(vals) - 1)
                    y = 22 - (v - vmin) / rng * 20
                    pts.append(f"{x:.0f},{y:.0f}")
                spark = " ".join(pts)
            else:
                spark = ""
        except Exception:
            spark = ""

        # QDII 滞后判断
        is_qdii = "QDII" in h.get("type", "") or "QDII" in h.get("name", "")
        cache_max = str(cache["净值日期"].astype(str).max())[:10]
        today = datetime.date.today().strftime("%Y-%m-%d")
        lag = is_qdii and cache_max < today

        results.append({
            "code": code,
            "shortName": h["name"][:6],
            "amount": h["amount"],
            "nav": nav,
            "pct": pct,
            "estPct": est_map.get(code),
            "light": sig.get("light"),
            "lightLabel": signals.LIGHT_LABEL.get(sig.get("light"), "—"),
            "gain": sig.get("gain_since_base"),
            "tpTier": sig.get("take_profit_tier") or 0,
            "anomaly": sig.get("anomaly", {}).get("triggered", False),
            "pctRank": sig.get("pct_rank"),
            "lag": lag,
            "sparkPoints": spark,
        })

    return results


def compute_summary(holdings_data):
    total_amount = sum(h["amount"] for h in holdings_data)
    total_pnl = 0
    est_pnl = 0
    est_pct_weighted = 0
    for h in holdings_data:
        if h["pct"] is not None:
            total_pnl += h["amount"] * h["pct"] / 100
        if h["estPct"] is not None:
            est_pnl += h["amount"] * h["estPct"] / 100
            est_pct_weighted += h["amount"] * h["estPct"]

    est_pct = (est_pct_weighted / total_amount) if total_amount else 0

    red = sum(1 for h in holdings_data if h["light"] == "red")
    yellow = sum(1 for h in holdings_data if h["light"] == "yellow")
    green = sum(1 for h in holdings_data if h["light"] == "green")
    tp = sum(1 for h in holdings_data if h["tpTier"] > 0)
    anomaly = sum(1 for h in holdings_data if h["anomaly"])

    return {
        "totalAmount": round(total_amount, 2),
        "totalPnl": round(total_pnl, 2),
        "estPnl": round(est_pnl, 2),
        "estPct": round(est_pct, 2),
        "signals": {"red": red, "yellow": yellow, "green": green, "tp": tp, "anomaly": anomaly},
    }


def fetch_macro():
    """宏观经济日历"""
    try:
        today_str = datetime.date.today().strftime("%Y%m%d")
        df = ak.news_economic_baidu(date=today_str)
        if df is None or df.empty:
            return []
        keywords = pf_news_cfg().get("macro_keywords", ["黄金", "白银", "原油", "美元", "PMI", "GDP", "CPI", "降息", "利率", "LPR"])
        results = []
        for _, row in df.iterrows():
            event = str(row.get("事件", ""))
            importance = int(row.get("重要性", 0))
            matched = [kw for kw in keywords if kw in event]
            if importance >= 2 or matched:
                results.append({
                    "time": str(row.get("时间", "")),
                    "region": str(row.get("地区", "")),
                    "event": event,
                    "actual": str(row.get("公布", "")),
                    "importance": importance,
                })
        results.sort(key=lambda x: x["importance"], reverse=True)
        return results[:10]
    except Exception:
        return []


def pf_news_cfg():
    """辅助：从 portfolio.json 取 news 配置"""
    pf = load_portfolio()
    return pf.get("news", {})


def fetch_weibo():
    """微博情绪"""
    try:
        df = ak.stock_js_weibo_report(time_period="CNHOUR12")
        if df is None or df.empty:
            return {}
        return {str(row["name"]): round(float(row["rate"]), 2) for _, row in df.iterrows()}
    except Exception:
        return {}


def fetch_diagnostic_data(pf):
    """调用 diagnostics.py 计算诊断数据，输出为前端需要的格式。"""
    import diagnostics
    diag_result = diagnostics.run_diagnostics()
    if "error" in diag_result:
        return None

    risk = diag_result.get("risk", {})
    conc = diag_result.get("concentration", {})
    corr = diag_result.get("correlation", {})
    buckets = diag_result.get("buckets", {})
    bench = diag_result.get("benchmarks", [])
    sug = diag_result.get("suggestions", [])

    # 前端需要的扁平格式
    diag_flat = {
        "volatility": str(round(risk.get("vol_annual", 0), 1)),
        "mdd": str(round(risk.get("max_drawdown", 0), 1)),
        "sharpe": str(round(risk.get("sharpe", 0), 2)) if risk.get("sharpe") else "—",
        "hhi": str(round(conc.get("hhi", 0), 3)),
    }

    # 相关性预警对
    corr_warnings = []
    for p in corr.get("high_pairs", []):
        # 用短名替换 code
        a_name = p["a"]
        b_name = p["b"]
        for h in pf["holdings"]:
            if h["code"] == p["a"]:
                a_name = h["name"][:6]
            if h["code"] == p["b"]:
                b_name = h["name"][:6]
        corr_warnings.append({
            "pair": f"{a_name} ↔ {b_name}",
            "value": str(p["corr"]),
        })

    # 分类占比（给 ECharts 饼图）
    category_pie = []
    cat_data = conc.get("by_category", {})
    color_pool = ["#ef4444", "#3b82f6", "#eab308", "#22c55e", "#a855f7",
                  "#06b6d4", "#f97316", "#64748b", "#8b5cf6", "#14b8a6"]
    for idx, (cat_name, cat_weight) in enumerate(cat_data.items()):
        category_pie.append({
            "value": cat_weight,
            "name": cat_name,
            "itemStyle": {"color": color_pool[idx % len(color_pool)]},
        })

    # 基准对比（给 ECharts 柱状图）
    benchmark_data = {
        "categories": ["组合"],
        "sharpe": [risk.get("sharpe", 0)],
        "volatility": [risk.get("vol_annual", 0)],
    }
    for b in bench:
        benchmark_data["categories"].append(b.get("name", b["code"]))
        benchmark_data["sharpe"].append(b.get("sharpe", 0) or 0)
        benchmark_data["volatility"].append(b.get("vol_annual", 0) or 0)

    # 再平衡建议
    suggestions = []
    for s in sug:
        suggestions.append({"level": s["level"], "text": s["text"]})

    return {
        "diag": diag_flat,
        "corrWarnings": corr_warnings,
        "categoryPie": category_pie,
        "benchmarkData": benchmark_data,
        "suggestions": suggestions,
        "buckets": buckets,
        "top3Weight": conc.get("top3_weight", 0),
        "nFunds": conc.get("n_funds", 0),
    }


def fetch_news_data(pf):
    """调用 news_signal.py 的 collect_all，输出为前端需要的格式。"""
    import news_signal
    news_result = news_signal.collect_all(pf)
    if not news_result:
        return None

    # 持仓新闻 → newsItems（扁平列表，每条带 tag 标签）
    news_items = []
    for h in pf["holdings"]:
        code = h["code"]
        holding_news = news_result.get("holding_news", {}).get(code, {})
        tag = h.get("category", "").split("/")[0]
        for n in holding_news.get("news", []):
            news_items.append({
                "title": n.get("title", ""),
                "summary": n.get("content", "")[:150],
                "source": n.get("source", ""),
                "time": n.get("time", ""),
                "tag": tag,
                "url": n.get("url", ""),
            })

    # 市场热点 → hotStocks
    hot_stocks = []
    for hs in news_result.get("hot_market_stocks", []):
        # 尝试获取涨跌幅，MCP 新闻源可提供
        change = 0
        hot_stocks.append({
            "name": hs.get("name", ""),
            "change": change,
            "followers": hs.get("followers", 0),
        })

    # 宏观事件（已从 fetch_macro 获取，此处复用 news_result 的更完整版本）
    macro_events = []
    for m in news_result.get("macro", []):
        macro_events.append({
            "time": m.get("time", ""),
            "region": m.get("region", ""),
            "event": m.get("event", ""),
            "actual": m.get("actual", ""),
            "importance": m.get("importance", 0),
        })

    return {
        "newsItems": news_items,
        "hotStocks": hot_stocks,
        "macroEvents": macro_events if macro_events else None,
    }


def main():
    print("📡 正在导出仪表盘数据...")
    pf = load_portfolio()
    theme_map = pf.get("theme_map", {})
    news_cfg = pf.get("news", {})

    # 1. 持仓数据
    print("  [1/6] 持仓行情+信号...")
    holdings = fetch_fund_data(pf)
    summary = compute_summary(holdings)

    # 2. 宏观日历
    print("  [2/6] 宏观经济日历...")
    macro = fetch_macro()

    # 3. 微博情绪
    print("  [3/6] 微博情绪...")
    weibo = fetch_weibo()

    # 4. 为每只基金挂微博情绪
    for h in holdings:
        tm = theme_map.get(h["code"], {})
        stock_names = tm.get("stock_names", [])
        scores = []
        for sn in stock_names:
            if sn in weibo:
                scores.append({"name": sn, "rate": weibo[sn]})
        h["weiboScores"] = scores

    # 5. 诊断数据
    print("  [4/6] 持仓诊断...")
    diag_data = fetch_diagnostic_data(pf)

    # 6. 消息面数据
    print("  [5/6] 消息面数据...")
    news_data = fetch_news_data(pf)

    # 7. 组装最终 JSON
    dashboard = {
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": summary,
        "holdings": holdings,
        "macroEvents": macro,
        "navItems": [
            {"id": "daily", "label": "每日日报", "icon": "📊"},
            {"id": "news", "label": "消息面", "icon": "📰", "badge": "NEW"},
            {"id": "diagnosis", "label": "持仓诊断", "icon": "🩺"},
            {"id": "signals", "label": "信号总览", "icon": "🚦"},
        ],
    }

    # 诊断数据注入
    if diag_data:
        dashboard["diag"] = diag_data["diag"]
        dashboard["corrWarnings"] = diag_data["corrWarnings"]
        dashboard["categoryPie"] = diag_data["categoryPie"]
        dashboard["benchmarkData"] = diag_data["benchmarkData"]
        dashboard["suggestions"] = diag_data["suggestions"]

    # 消息面数据注入
    if news_data:
        dashboard["newsItems"] = news_data["newsItems"]
        dashboard["hotStocks"] = news_data["hotStocks"]
        # 消息面宏观事件更完整，覆盖之前的简易版本
        if news_data["macroEvents"]:
            dashboard["macroEvents"] = news_data["macroEvents"]

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 仪表盘数据已导出：{JSON_PATH}")
    print(f"   持仓 {len(holdings)} 只 | 宏观 {len(macro)} 条")
    if diag_data:
        print(f"   诊断 ✅ | 相关性预警 {len(diag_data['corrWarnings'])} 对")
    if news_data:
        print(f"   消息面 ✅ | 新闻 {len(news_data['newsItems'])} 条 | 热点 {len(news_data['hotStocks'])} 只")

    return dashboard


def run_full_export():
    """完整导出流程，返回 dashboard 字典（供后端调用）"""
    return main()


def run_noon_export():
    """午间导出：只刷新盘中估值+新闻，不跑诊断和收盘净值"""
    print("☀️ 午间数据导出（盘中估值+新闻）...")
    pf = load_portfolio()

    # 1. 持仓数据（盘中估值会在这里更新）
    print("  [1/3] 持仓盘中估值+信号...")
    holdings = fetch_fund_data(pf)
    summary = compute_summary(holdings)

    # 2. 消息面数据
    print("  [2/3] 消息面数据...")
    news_data = fetch_news_data(pf)

    # 3. 读取已有数据库中的宏观和诊断数据（午间不重新拉）
    macro = fetch_macro()
    # 诊断数据午间不更新，使用空的 fallback
    diag_data = None

    dashboard = {
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": summary,
        "holdings": holdings,
        "macroEvents": macro,
        "navItems": [
            {"id": "daily", "label": "每日日报", "icon": "📊"},
            {"id": "news", "label": "消息面", "icon": "📰", "badge": "NEW"},
            {"id": "diagnosis", "label": "持仓诊断", "icon": "🩺"},
            {"id": "signals", "label": "信号总览", "icon": "🚦"},
        ],
    }

    if news_data:
        dashboard["newsItems"] = news_data["newsItems"]
        dashboard["hotStocks"] = news_data["hotStocks"]
        if news_data["macroEvents"]:
            dashboard["macroEvents"] = news_data["macroEvents"]

    # 尝试从已有快照中保留诊断数据
    # （午间不跑诊断，但前端需要显示，所以保留上次的）
    try:
        import db as db_module
        prev = db_module.load_latest_snapshot()
        if prev:
            dashboard["diag"] = prev.get("diag", dashboard.get("diag", {}))
            dashboard["corrWarnings"] = prev.get("corrWarnings", dashboard.get("corrWarnings", []))
            dashboard["categoryPie"] = prev.get("categoryPie", dashboard.get("categoryPie", []))
            dashboard["benchmarkData"] = prev.get("benchmarkData", dashboard.get("benchmarkData", {}))
            dashboard["suggestions"] = prev.get("suggestions", dashboard.get("suggestions", []))
    except ImportError:
        pass  # 没有数据库模块就跳过

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 午间数据已导出：{JSON_PATH}")
    print(f"   持仓 {len(holdings)} 只 | 消息面 ✅")
    return dashboard


if __name__ == "__main__":
    main()
