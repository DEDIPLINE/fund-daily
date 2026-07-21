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
        keywords = ["黄金", "白银", "原油", "美元", "PMI", "GDP", "CPI", "降息", "利率", "LPR"]
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


def fetch_weibo():
    """微博情绪"""
    try:
        df = ak.stock_js_weibo_report(time_period="CNHOUR12")
        if df is None or df.empty:
            return {}
        return {str(row["name"]): round(float(row["rate"]), 2) for _, row in df.iterrows()}
    except Exception:
        return {}


def main():
    print("📡 正在导出仪表盘数据...")
    pf = load_portfolio()
    theme_map = pf.get("theme_map", {})
    news_cfg = pf.get("news", {})

    # 1. 持仓数据
    print("  [1/4] 持仓行情+信号...")
    holdings = fetch_fund_data(pf)
    summary = compute_summary(holdings)

    # 2. 宏观日历
    print("  [2/4] 宏观经济日历...")
    macro = fetch_macro()

    # 3. 微博情绪
    print("  [3/4] 微博情绪...")
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

    # 5. 组装最终 JSON
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

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 仪表盘数据已导出：{JSON_PATH}")
    print(f"   持仓 {len(holdings)} 只 | 宏观 {len(macro)} 条")


if __name__ == "__main__":
    main()
