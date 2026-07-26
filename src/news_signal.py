# -*- coding: utf-8 -*-
"""
M5 · 每日消息面参考卡 — 消息面/舆情聚合
数据层（双源：腾讯自选股 MCP / akshare 1.18.66）：
  - 个股新闻：MCP data_news (type=2) 优先 → akshare stock_news_em fallback
  - news_economic_baidu：宏观经济日历（按日期，按关键词过滤）
  - stock_research_report_em：机构研报（近 N 天）
  - stock_js_weibo_report：微博情绪系数（按关联股票匹配）
  - stock_hot_tweet_xq：雪球热度榜（过滤持仓关联股 → Top 非持仓热门股）
  - fund_announcement_report_em：基金公告（近 N 天）

MCP 缓存机制：
  - MCP 工具仅在 WorkBuddy 环境中可调用，Python 脚本通过缓存文件读取
  - 缓存路径：data/mcp_news_cache.json
  - 缓存有效期：当天（按日期判断）
  - 缓存过期或不存在时，自动降级到 akshare

输出：data/reports/news_YYYYMMDD.html
运行：python src/news_signal.py

注意：
  - 本脚本只做信息聚合与展示，不构成任何投资建议。
  - 雪球/微博只能拿到情绪代理数字，拿不到大V原话。
  - 所有新闻来源标注原文链接，点击可跳转原文。
"""
import json
import os
import re
import datetime
import traceback
import pandas as pd
import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = os.path.join(ROOT, "portfolio.json")
REPORT_DIR = os.path.join(ROOT, "data", "reports")
MCP_CACHE_PATH = os.path.join(ROOT, "data", "mcp_news_cache.json")
os.makedirs(REPORT_DIR, exist_ok=True)

UP_COLOR = "#d40000"
DOWN_COLOR = "#008000"
FLAT_COLOR = "#888888"


def load_portfolio():
    with open(PORTFOLIO, encoding="utf-8") as f:
        return json.load(f)


# ── MCP 缓存管理 ──────────────────────────────────────────────

def to_mcp_symbol(stock_code):
    """裸代码转 MCP symbol：6/9 开头→sh，0/3 开头→sz。"""
    code = str(stock_code).strip()
    if code[0] in ("6", "9"):
        return f"sh{code}"
    elif code[0] in ("0", "3"):
        return f"sz{code}"
    return f"sh{code}"


def load_mcp_cache():
    """加载 MCP 新闻缓存，过期则返回 None。"""
    if not os.path.exists(MCP_CACHE_PATH):
        return None
    try:
        with open(MCP_CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)
        cache_date = cache.get("date", "")
        today = datetime.date.today().strftime("%Y-%m-%d")
        if cache_date != today:
            print(f"  ℹ️ MCP 缓存过期（{cache_date}），降级到 akshare")
            return None
        return cache
    except Exception:
        return None


def get_mcp_news_for_stock(mcp_cache, stock_code):
    """从 MCP 缓存中提取指定股票的新闻。"""
    if not mcp_cache:
        return []
    symbol = to_mcp_symbol(stock_code)
    news_list = mcp_cache.get("news", {}).get(symbol, [])
    return news_list


# ── 数据抓取 ──────────────────────────────────────────────────

# 腾讯自选股 MCP 工具（通过缓存文件读取，降级到 akshare）
# MCP 缓存由 WorkBuddy 环境调用 mcp__westock-mcp__data_news 生成


def fetch_stock_news(stock_code, stock_name, max_n=5, use_mcp=False, mcp_cache=None):
    """拉取个股新闻，返回 list of dict。
    use_mcp=True 时优先读 MCP 缓存，降级到 akshare。
    use_mcp=False 时直接用 akshare。
    """
    # 尝试 MCP 缓存
    if use_mcp and mcp_cache:
        mcp_news = get_mcp_news_for_stock(mcp_cache, stock_code)
        if mcp_news:
            results = []
            for n in mcp_news[:max_n]:
                results.append({
                    "title": n.get("title", ""),
                    "content": n.get("content", ""),  # MCP list 模式无 content
                    "time": n.get("time", ""),
                    "source": n.get("source", "腾讯自选股"),
                    "url": n.get("url", ""),
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                })
            return results
        # MCP 缓存中没有该股票，继续降级

    # akshare fallback
    try:
        df = ak.stock_news_em(symbol=stock_code)
        if df is None or df.empty:
            return []
        results = []
        for _, row in df.head(max_n).iterrows():
            results.append({
                "title": str(row.get("新闻标题", "")),
                "content": str(row.get("新闻内容", ""))[:300],
                "time": str(row.get("发布时间", "")),
                "source": str(row.get("文章来源", "")),
                "url": str(row.get("新闻链接", "")),
                "stock_code": stock_code,
                "stock_name": stock_name,
            })
        return results
    except Exception as e:
        print(f"  ⚠️ {stock_name}({stock_code}) 新闻获取失败: {e}")
        return []


def fetch_macro_news(keywords, today_str):
    """拉取宏观经济日历，按关键词过滤。"""
    try:
        df = ak.news_economic_baidu(date=today_str.replace("-", ""))
        if df is None or df.empty:
            return []
        results = []
        for _, row in df.iterrows():
            event = str(row.get("事件", ""))
            # 过滤：只保留重要性 >= 2 或事件包含关键词
            importance = row.get("重要性", 0)
            matched_kw = [kw for kw in keywords if kw in event]
            if importance >= 2 or matched_kw:
                results.append({
                    "time": str(row.get("时间", "")),
                    "region": str(row.get("地区", "")),
                    "event": event,
                    "actual": str(row.get("公布", "")),
                    "expected": str(row.get("预期", "")),
                    "importance": importance,
                    "keywords_hit": matched_kw,
                })
        # 按重要性降序
        results.sort(key=lambda x: x["importance"], reverse=True)
        return results[:20]
    except Exception as e:
        print(f"  ⚠️ 宏观经济日历获取失败: {e}")
        return []


def fetch_research_reports(stock_code, stock_name, days=7):
    """拉取机构研报，返回近 N 天的。"""
    try:
        df = ak.stock_research_report_em(symbol=stock_code)
        if df is None or df.empty:
            return []
        cutoff = datetime.date.today() - datetime.timedelta(days=days)
        results = []
        for _, row in df.iterrows():
            date_str = str(row.get("日期", ""))
            try:
                report_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue
            if report_date < cutoff:
                continue
            results.append({
                "title": str(row.get("报告名称", "")),
                "rating": str(row.get("东财评级", "")),
                "org": str(row.get("机构", "")),
                "date": date_str,
                "industry": str(row.get("行业", "")),
                "stock_code": stock_code,
                "stock_name": stock_name,
            })
        return results[:3]
    except Exception as e:
        print(f"  ⚠️ {stock_name}({stock_code}) 研报获取失败: {e}")
        return []


def fetch_fund_announcements(fund_code, days=7):
    """拉取基金公告，返回近 N 天的。"""
    try:
        df = ak.fund_announcement_report_em(symbol=fund_code)
        if df is None or df.empty:
            return []
        cutoff = datetime.date.today() - datetime.timedelta(days=days)
        results = []
        for _, row in df.iterrows():
            date_str = str(row.get("公告日期", ""))
            try:
                ann_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue
            if ann_date < cutoff:
                continue
            results.append({
                "title": str(row.get("公告标题", "")),
                "date": date_str,
                "fund_code": fund_code,
            })
        return results
    except Exception as e:
        print(f"  ⚠️ {fund_code} 公告获取失败: {e}")
        return []


def fetch_weibo_sentiment():
    """拉取微博情绪系数，返回 dict: stock_name → rate。"""
    try:
        df = ak.stock_js_weibo_report(time_period="CNHOUR12")
        if df is None or df.empty:
            return {}
        return {str(row["name"]): float(row["rate"]) for _, row in df.iterrows()}
    except Exception as e:
        print(f"  ⚠️ 微博情绪获取失败: {e}")
        return {}


def fetch_xueqiu_hot():
    """拉取雪球热度榜，返回 DataFrame。"""
    try:
        df = ak.stock_hot_tweet_xq(symbol="最热门")
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"  ⚠️ 雪球热度榜获取失败: {e}")
        return pd.DataFrame()


# ── 汇聚 ─────────────────────────────────────────────────────

def collect_all(pf):
    """汇聚所有数据源，返回结构化结果。"""
    theme_map = pf.get("theme_map", {})
    news_cfg = pf.get("news", {})
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    news_per_stock = news_cfg.get("news_per_stock", 5)
    research_days = news_cfg.get("research_days", 7)
    ann_days = news_cfg.get("fund_announcement_days", 7)
    macro_keywords = news_cfg.get("macro_keywords", ["黄金", "白银", "PMI", "GDP", "CPI", "降息", "利率", "LPR"])
    hot_stocks_count = news_cfg.get("hot_stocks_count", 5)
    use_mcp = news_cfg.get("use_mcp", False)

    # 加载 MCP 缓存（如果启用）
    mcp_cache = None
    if use_mcp:
        mcp_cache = load_mcp_cache()
        if mcp_cache:
            print(f"  ✅ MCP 缓存已加载（{mcp_cache.get('date', '?')}），优先使用腾讯自选股数据")
        else:
            print("  ℹ️ MCP 缓存不可用，全部使用 akshare 数据源")

    print("📡 正在拉取数据...")

    # 1. 持仓消息区
    print("  [1/6] 持仓关联股新闻...")
    holding_news = {}
    for h in pf["holdings"]:
        code = h["code"]
        tm = theme_map.get(code, {})
        stocks = tm.get("stocks", [])
        stock_names = tm.get("stock_names", [])
        fund_news = []
        for sc, sn in zip(stocks, stock_names):
            print(f"    → {sn}({sc})")
            news = fetch_stock_news(sc, sn, max_n=news_per_stock, use_mcp=use_mcp, mcp_cache=mcp_cache)
            fund_news.extend(news)
        holding_news[code] = {
            "news": fund_news,
            "stocks": list(zip(stocks, stock_names)),
            "keywords": tm.get("keywords", []),
        }

    # 2. 微博情绪
    print("  [2/6] 微博情绪系数...")
    weibo = fetch_weibo_sentiment()

    # 3. 雪球热度榜
    print("  [3/6] 雪球热度榜...")
    xueqiu = fetch_xueqiu_hot()

    # 4. 机构研报（仅对有股票关联的基金）
    print("  [4/6] 机构研报...")
    holding_reports = {}
    for h in pf["holdings"]:
        code = h["code"]
        tm = theme_map.get(code, {})
        stocks = tm.get("stocks", [])
        stock_names = tm.get("stock_names", [])
        reports = []
        for sc, sn in zip(stocks, stock_names):
            rpts = fetch_research_reports(sc, sn, days=research_days)
            reports.extend(rpts)
        holding_reports[code] = reports

    # 5. 基金公告
    print("  [5/6] 基金公告...")
    fund_announcements = {}
    for h in pf["holdings"]:
        anns = fetch_fund_announcements(h["code"], days=ann_days)
        fund_announcements[h["code"]] = anns

    # 6. 宏观经济日历
    print("  [6/6] 宏观经济日历...")
    macro = fetch_macro_news(macro_keywords, today_str)

    # 7. 市场热点区：雪球 Top 热门中非持仓关联股
    print("  [bonus] 市场热点新闻...")
    # 收集所有持仓关联股票名称
    all_holding_stock_names = set()
    for h in pf["holdings"]:
        tm = theme_map.get(h["code"], {})
        for sn in tm.get("stock_names", []):
            all_holding_stock_names.add(sn)

    hot_market_stocks = []
    if not xueqiu.empty:
        for _, row in xueqiu.head(50).iterrows():
            name = str(row.get("股票简称", ""))
            if name in all_holding_stock_names:
                continue
            hot_market_stocks.append({
                "name": name,
                "code": str(row.get("股票代码", "")).replace("SZ", "").replace("SH", ""),
                "followers": int(row.get("关注", 0)),
                "price": row.get("最新价", 0),
            })
            if len(hot_market_stocks) >= hot_stocks_count:
                break

    hot_market_news = []
    for hs in hot_market_stocks:
        print(f"    → {hs['name']}({hs['code']})")
        news = fetch_stock_news(hs["code"], hs["name"], max_n=3, use_mcp=use_mcp, mcp_cache=mcp_cache)
        hs["news"] = news
        hot_market_news.append(hs)

    # 微博情绪匹配
    holding_weibo = {}
    for h in pf["holdings"]:
        tm = theme_map.get(h["code"], {})
        stock_names = tm.get("stock_names", [])
        scores = []
        for sn in stock_names:
            if sn in weibo:
                scores.append({"name": sn, "rate": weibo[sn]})
        holding_weibo[h["code"]] = scores

    hot_weibo = []
    for hs in hot_market_stocks:
        if hs["name"] in weibo:
            hot_weibo.append({"name": hs["name"], "rate": weibo[hs["name"]]})

    return {
        "today": today_str,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "holding_news": holding_news,
        "holding_reports": holding_reports,
        "fund_announcements": fund_announcements,
        "holding_weibo": holding_weibo,
        "macro": macro,
        "hot_market_stocks": hot_market_stocks,
        "hot_weibo": hot_weibo,
        "weibo_all": weibo,
        "xueqiu_top10": (
            [{"name": str(r.get("股票简称", "")), "followers": int(r.get("关注", 0)),
              "price": r.get("最新价", 0)}
             for _, r in xueqiu.head(10).iterrows()]
            if not xueqiu.empty else []
        ),
    }


# ── HTML 生成 ────────────────────────────────────────────────

def sentiment_emoji(rate):
    if rate > 0.3:
        return "🟢"
    if rate < -0.3:
        return "🔴"
    return "⚪"


def build_html(pf, data):
    generated_at = data["generated_at"]
    today = data["today"]
    use_mcp = pf.get("news", {}).get("use_mcp", False)
    mcp_active = use_mcp and os.path.exists(MCP_CACHE_PATH)
    data_source = "腾讯自选股 MCP + akshare" if mcp_active else "akshare（东方财富/百度/雪球/微博）"

    # ── 持仓消息区 ──
    holding_html = ""
    for h in pf["holdings"]:
        code = h["code"]
        tm = pf.get("theme_map", {}).get(code, {})
        news_list = data["holding_news"].get(code, {}).get("news", [])
        reports = data["holding_reports"].get(code, [])
        anns = data["fund_announcements"].get(code, [])
        weibo_scores = data["holding_weibo"].get(code, [])
        stocks = data["holding_news"].get(code, {}).get("stocks", [])
        keywords = data["holding_news"].get(code, {}).get("keywords", [])

        # 微博情绪
        weibo_html = ""
        if weibo_scores:
            for ws in weibo_scores:
                emoji = sentiment_emoji(ws["rate"])
                weibo_html += f'{emoji} {ws["name"]} 情绪 {ws["rate"]:+.2f} &nbsp; '
        else:
            weibo_html = '<span style="color:#b0b4bb">无关联股情绪数据</span>'

        # 关联股票
        stocks_html = ""
        if stocks:
            stocks_html = "关联股：" + " / ".join(f"{sn}({sc})" for sc, sn in stocks)
        else:
            stocks_html = '<span style="color:#8a8f99">无A股关联（QDII/债券），展示宏观新闻</span>'

        # 新闻
        news_html = ""
        if news_list:
            for n in news_list:
                url_link = f' <a href="{n["url"]}" target="_blank" style="color:#2b6cb0;font-size:11px">原文↗</a>' if n["url"] else ""
                content_preview = n["content"][:200].replace("\n", " ")
                news_html += f"""
                <div style="margin-bottom:8px;padding:8px 10px;background:#f8f9fa;border-radius:6px;border-left:3px solid #2b6cb0">
                  <div style="font-weight:500;font-size:13px;">{n['title']}{url_link}</div>
                  <div style="font-size:12px;color:#555;margin-top:3px;">{content_preview}...</div>
                  <div style="font-size:11px;color:#8a8f99;margin-top:2px;">{n['time']} | {n['source']} | {n['stock_name']}</div>
                </div>"""
        else:
            news_html = '<div style="color:#b0b4bb;font-size:12px;padding:8px;">暂无相关新闻</div>'

        # 研报
        report_html = ""
        if reports:
            for rpt in reports:
                rating_color = "#d40000" if "买入" in rpt["rating"] or "增持" in rpt["rating"] else (
                    "#c47f00" if "中性" in rpt["rating"] else "#008000")
                report_html += f"""
                <div style="display:inline-flex;align-items:center;gap:6px;margin:3px 6px 3px 0;padding:4px 10px;background:#f8f9fa;border-radius:6px;font-size:12px;">
                  <span style="color:{rating_color};font-weight:600">{rpt['rating']}</span>
                  <span style="color:#555">{rpt['org']}</span>
                  <span style="color:#8a8f99">{rpt['date']}</span>
                  <span style="color:#8a8f99;font-size:11px">{rpt['title'][:30]}</span>
                </div>"""
        else:
            report_html = '<span style="color:#b0b4bb;font-size:12px">近7天无研报</span>'

        # 公告
        ann_html = ""
        if anns:
            for ann in anns:
                ann_html += f'<span style="display:inline-block;margin:2px 6px 2px 0;padding:3px 8px;background:#f0f8ff;border-radius:4px;font-size:12px;color:#2b6cb0">📄 {ann["title"][:40]} ({ann["date"]})</span>'
        else:
            ann_html = '<span style="color:#b0b4bb;font-size:12px">近7天无公告</span>'

        holding_html += f"""
        <div style="background:#fff;border-radius:12px;padding:16px 18px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.06);">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
            <div style="font-weight:600;font-size:15px;">{h['code']} {h['name']}</div>
            <span style="font-size:12px;color:#8a8f99;background:#f1f3f5;padding:2px 8px;border-radius:4px;">{h['category']}</span>
          </div>
          <div style="font-size:12px;color:#555;margin-bottom:8px;">{stocks_html}</div>
          <div style="font-size:12px;margin-bottom:8px;">微博情绪：{weibo_html}</div>
          <div style="margin-bottom:8px;">{news_html}</div>
          <div style="margin-bottom:6px;">
            <div style="font-size:12px;font-weight:500;color:#555;margin-bottom:4px;">机构研报（近{pf.get('news',{}).get('research_days',7)}天）</div>
            {report_html}
          </div>
          <div>
            <div style="font-size:12px;font-weight:500;color:#555;margin-bottom:4px;">基金公告</div>
            {ann_html}
          </div>
        </div>"""

    # ── 市场热点区 ──
    hot_html = ""
    for hs in data["hot_market_stocks"]:
        weibo_info = ""
        for hw in data["hot_weibo"]:
            if hw["name"] == hs["name"]:
                emoji = sentiment_emoji(hw["rate"])
                weibo_info = f' {emoji} 微博情绪 {hw["rate"]:+.2f}'
                break

        news_html = ""
        for n in hs.get("news", []):
            url_link = f' <a href="{n["url"]}" target="_blank" style="color:#2b6cb0;font-size:11px">原文↗</a>' if n["url"] else ""
            news_html += f"""
            <div style="margin-bottom:6px;padding:6px 10px;background:#f8f9fa;border-radius:6px;border-left:3px solid #c47f00">
              <div style="font-weight:500;font-size:13px;">{n['title']}{url_link}</div>
              <div style="font-size:11px;color:#8a8f99;margin-top:2px;">{n['time']} | {n['source']}</div>
            </div>"""
        if not news_html:
            news_html = '<div style="color:#b0b4bb;font-size:12px;padding:4px;">暂无新闻</div>'

        hot_html += f"""
        <div style="background:#fff;border-radius:10px;padding:14px 16px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.06);">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <div style="font-weight:600;font-size:14px;">🔥 {hs['name']}</div>
            <span style="font-size:12px;color:#8a8f99;">关注度 {hs['followers']:,}</span>
            <span style="font-size:12px;color:#555;">最新价 {hs['price']}</span>
            <span style="font-size:11px;color:#c47f00;">{weibo_info}</span>
          </div>
          {news_html}
        </div>"""

    # ── 宏观日历区 ──
    macro_html = ""
    for m in data["macro"]:
        imp_icon = "🔴" if m["importance"] >= 3 else ("🟡" if m["importance"] >= 2 else "⚪")
        kw_badge = ""
        if m["keywords_hit"]:
            kw_badge = ' <span style="color:#2b6cb0;font-size:11px;background:#e8f1fb;padding:1px 6px;border-radius:3px;">' + "/".join(m["keywords_hit"]) + "</span>"
        macro_html += f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid #f0f1f3;font-size:12px;">
          <span>{imp_icon}</span>
          <span style="color:#8a8f99;width:50px;">{m['time']}</span>
          <span style="color:#555;width:40px;">{m['region']}</span>
          <span style="flex:1;color:#1f2329;">{m['event']}{kw_badge}</span>
          <span style="font-weight:500;width:60px;text-align:right;">{m['actual']}</span>
          <span style="color:#8a8f99;width:60px;text-align:right;">预期 {m['expected']}</span>
        </div>"""

    if not macro_html:
        macro_html = '<div style="color:#b0b4bb;font-size:12px;padding:12px;">今日无重要宏观事件</div>'

    # ── 雪球热度 Top10 ──
    xueqiu_html = ""
    for idx, x in enumerate(data.get("xueqiu_top10", []), 1):
        # 检查是否是持仓关联股
        is_holding = any(
            x["name"] in (pf.get("theme_map", {}).get(h["code"], {}).get("stock_names", []))
            for h in pf["holdings"]
        )
        badge = ' <span style="font-size:10px;color:#2b6cb0;background:#e8f1fb;padding:1px 5px;border-radius:3px;">持仓关联</span>' if is_holding else ""
        xueqiu_html += f'<span style="display:inline-flex;align-items:center;gap:4px;margin:3px 8px 3px 0;padding:4px 10px;background:#f8f9fa;border-radius:6px;font-size:12px;"><span style="color:#8a8f99">#{idx}</span> <span style="font-weight:500">{x["name"]}</span> <span style="color:#8a8f99">{x["followers"]:,}</span>{badge}</span>'

    # ── 拼接完整 HTML ──
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>消息面参考卡 {today}</title>
<style>
  body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f8;color:#1f2329;margin:0;padding:24px;line-height:1.6;}}
  .wrap{{max-width:960px;margin:0 auto;}}
  h1{{font-size:22px;margin:0 0 4px;}}
  .meta{{color:#8a8f99;font-size:13px;margin-bottom:18px;}}
  a{{text-decoration:none;}}
  a:hover{{text-decoration:underline;}}
  .section-title{{font-size:16px;font-weight:600;margin:20px 0 10px;color:#1f2329;border-left:4px solid #2b6cb0;padding-left:10px;}}
  .section-title.hot{{border-left-color:#c47f00;}}
  .section-title.macro{{border-left-color:#008000;}}
  .section-title.xq{{border-left-color:#534AB7;}}
  .disclaimer{{margin-top:20px;font-size:12px;color:#8a8f99;line-height:1.6;background:#fff;border-left:3px solid #d0d3d9;padding:10px 14px;border-radius:6px;}}
</style></head>
<body><div class="wrap">
  <h1>📰 每日消息面参考卡</h1>
  <div class="meta">生成时间：{generated_at} ｜ 数据来源：{data_source}</div>
  <div class="meta" style="color:#c47f00">⚠️ 本卡仅做信息聚合与展示，<b>不构成任何投资建议</b>。新闻/研报来源已标注，点击可跳转原文。微博/雪球仅提供情绪代理数字，不代表大V原话。</div>

  <div class="section-title">📌 一、持仓消息区</div>
  {holding_html}

  <div class="section-title hot">🔥 二、市场热点区（你没持仓但全市场在关注的方向）</div>
  {hot_html if hot_html else '<div style="color:#b0b4bb;padding:12px;">暂无热点数据</div>'}

  <div class="section-title macro">🌐 三、宏观经济日历</div>
  <div style="background:#fff;border-radius:12px;padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,.06);">
    <div style="display:flex;align-items:center;gap:6px;padding:6px 10px;border-bottom:1px solid #e8e9eb;font-size:12px;font-weight:500;color:#8a8f99;">
      <span></span><span>时间</span><span>地区</span><span style="flex:1">事件</span><span style="width:60px;text-align:right">公布</span><span style="width:60px;text-align:right">预期</span>
    </div>
    {macro_html}
  </div>

  <div class="section-title xq">📊 四、雪球关注度 Top10</div>
  <div style="background:#fff;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.06);">
    {xueqiu_html if xueqiu_html else '<div style="color:#b0b4bb;">暂无数据</div>'}
  </div>

  <div class="disclaimer">
    ⚠️ <b>风险提示</b>：本消息面参考卡仅基于公开数据接口做信息聚合，<b>不构成任何投资建议</b>。
    新闻来源：{'腾讯自选股（MCP）、' if mcp_active else ''}东方财富、证券时报、财联社等公开来源，点击「原文↗」可跳转查看。
    微博情绪系数为第三方聚合的讨论热度指标（-1 到 +3），不代表具体博主观点。
    雪球关注度为粉丝数量排行，与投资价值无关。
    基金有风险，投资须谨慎，决策请结合自身情况。
  </div>
</div></body></html>"""


def main():
    pf = load_portfolio()
    data = collect_all(pf)
    html = build_html(pf, data)
    today = datetime.date.today().strftime("%Y%m%d")
    out = os.path.join(REPORT_DIR, f"news_{today}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ 消息面参考卡已生成：{out}")
    # 统计
    total_news = sum(len(v["news"]) for v in data["holding_news"].values())
    total_reports = sum(len(v) for v in data["holding_reports"].values())
    total_anns = sum(len(v) for v in data["fund_announcements"].values())
    hot_n = len(data["hot_market_stocks"])
    macro_n = len(data["macro"])
    print(f"   持仓新闻 {total_news} 条 | 研报 {total_reports} 条 | 公告 {total_anns} 条")
    print(f"   市场热点 {hot_n} 只 | 宏观事件 {macro_n} 条")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        traceback.print_exc()
