# -*- coding: utf-8 -*-
"""
方案B · Phase 1.5 —— 每日收盘日报（场外基金版 + 盘中估值）
数据层：
  - 官方净值：akshare fund_open_fund_info_em（单位净值走势），含增量缓存。
  - 盘中估值：akshare fund_value_estimation_em(symbol="全部")，取当日预估涨幅。
输出：data/reports/report_YYYYMMDD.html（红涨绿跌，中文习惯）

注意：
  - 持仓金额为截图日的市值，并非成本；日报用「市值 × 当日净值增长率」估算当日盈亏。
  - 盘中估值为平台按持仓实时估算的【预估值】，收盘后常与官方净值有偏差，仅作盘中决策参考，不对账。
  - QDII 基金净值/预估通常滞后 1-2 个交易日（如纳斯达克只到上周五），报告中标注「滞后」。
  - 约 1/6 基金平台不提供盘中估值，这类回退官方净值并标注「无估值」。
  - 本脚本只做数据跟踪与展示，不构成任何投资建议。
"""
import json
import os
import datetime
import pandas as pd
import akshare as ak
import signals

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = os.path.join(ROOT, "portfolio.json")
HISTORY_DIR = os.path.join(ROOT, "data", "history")
REPORT_DIR = os.path.join(ROOT, "data", "reports")
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

UP_COLOR = "#d40000"      # 涨 = 红
DOWN_COLOR = "#008000"    # 跌 = 绿
FLAT_COLOR = "#888888"


def load_portfolio():
    with open(PORTFOLIO, encoding="utf-8") as f:
        return json.load(f)


def fetch_and_cache(code):
    """抓取净值历史并增量写入本地缓存；返回 (cache_df, error_or_None)。"""
    cache_path = os.path.join(HISTORY_DIR, f"{code}.csv")
    if os.path.exists(cache_path):
        cache = pd.read_csv(cache_path)
    else:
        cache = pd.DataFrame(columns=["净值日期", "单位净值", "日增长率"])

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    cache_max = cache["净值日期"].astype(str).max() if not cache.empty else ""
    need_fetch = cache.empty or (cache_max < today_str)

    if need_fetch:
        try:
            df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            df = df[["净值日期", "单位净值", "日增长率"]].copy()
            df["净值日期"] = df["净值日期"].astype(str).str[:10]
            existing = set(cache["净值日期"].astype(str)) if not cache.empty else set()
            new_rows = df[~df["净值日期"].isin(existing)]
            if not new_rows.empty:
                cache = pd.concat([cache, new_rows], ignore_index=True)
                cache = cache.drop_duplicates(subset=["净值日期"], keep="last")
                cache = cache.sort_values("净值日期").reset_index(drop=True)
                cache.to_csv(cache_path, index=False, encoding="utf-8-sig")
        except Exception as e:
            return cache, f"抓取失败: {e}"
    return cache, None


def fetch_estimation():
    """盘中估值：一次性拉全市场估值表，返回 {code: {...}}。
    返回字段含 est_pct(预估涨幅%)、est_nav(预估净值)、est_date(估值日期)、
    pub_nav(今日官方净值，未公布为None)、dev(估算偏差)、has_est(是否覆盖)。"""
    try:
        df = ak.fund_value_estimation_em(symbol="全部")
    except Exception as e:
        return {}, None, f"盘中估值抓取失败: {e}"

    # 动态识别带日期前缀的列名
    est_val_col = est_pct_col = pub_nav_col = dev_col = None
    prev_nav_col = None
    for c in df.columns:
        if "估算数据-估算值" in c:
            est_val_col = c
        elif "估算数据-估算增长率" in c:
            est_pct_col = c
        elif "公布数据-单位净值" in c:
            pub_nav_col = c
        elif "估算偏差" in c:
            dev_col = c
        elif "单位净值" in c and "公布数据" not in c and "估算数据" not in c:
            prev_nav_col = c  # 尾部"昨日单位净值"列

    import re
    m = re.search(r"(\d{4}-\d{2}-\d{2})", est_pct_col or "")
    est_date = m.group(1) if m else datetime.date.today().strftime("%Y-%m-%d")

    out = {}
    for _, row in df.iterrows():
        code = str(row.get("基金代码", "")).strip()
        if not code:
            continue

        def to_float(v):
            try:
                if v is None or (isinstance(v, str) and v.strip() in ("", "---", "NaN", "nan")):
                    return None
                return float(str(v).replace("%", "").replace(",", "").strip())
            except Exception:
                return None

        est_pct = to_float(row.get(est_pct_col)) if est_pct_col else None
        est_nav = to_float(row.get(est_val_col)) if est_val_col else None
        pub_raw = row.get(pub_nav_col) if pub_nav_col else None
        pub_nav = to_float(pub_raw)
        dev = to_float(row.get(dev_col)) if dev_col else None
        out[code] = {
            "est_pct": est_pct, "est_nav": est_nav, "est_date": est_date,
            "pub_nav": pub_nav, "dev": dev, "has_est": est_pct is not None,
        }
    return out, est_date, None


def latest_of(cache):
    if cache is None or cache.empty:
        return None
    row = cache.iloc[-1]
    recent = cache.tail(20)
    try:
        nav = float(row["单位净值"])
    except Exception:
        nav = None
    try:
        pct = float(row["日增长率"]) if pd.notna(row["日增长率"]) else None
    except Exception:
        pct = None
    return {
        "date": str(row["净值日期"]),
        "nav": nav,
        "pct": pct,
        "spark": recent["单位净值"].astype(float).tolist(),
    }


def color_for(v):
    if v is None:
        return FLAT_COLOR
    if v > 0:
        return UP_COLOR
    if v < 0:
        return DOWN_COLOR
    return FLAT_COLOR


def fmt_pct(v):
    return "—" if v is None else f"{v:+.2f}%"


def fmt_money(v):
    return f"{v:,.2f}"


def sparkline(values, width=120, height=28):
    if not values or len(values) < 2:
        return ""
    vmin, vmax = min(values), max(values)
    rng = (vmax - vmin) or 1
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = 2 + i * (width - 4) / (n - 1)
        y = height - 2 - (v - vmin) / rng * (height - 4)
        pts.append(f"{x:.1f},{y:.1f}")
    col = color_for(values[-1] - values[0])
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<polyline fill="none" stroke="{col}" stroke-width="1.5" points="{" ".join(pts)}"/>'
            f'</svg>')


def build_html(pf, rows, generated_at, est_date):
    total_amount = sum(r["amount"] for r in rows)
    total_pnl = sum(r["pnl"] for r in rows)
    total_pct = (total_pnl / total_amount * 100) if total_amount else 0.0

    # 今日预估（仅计入有盘中估值的基金）
    est_rows = [r for r in rows if r.get("has_est")]
    est_total_pnl = sum(r["est_pnl"] for r in est_rows if r.get("est_pnl") is not None)
    est_total_pct = (est_total_pnl / total_amount * 100) if total_amount else 0.0
    no_est_codes = [r["code"] for r in rows if not r.get("has_est")]

    # 分类聚合（沿用官方净值口径做分类小结）
    cat = {}
    for r in rows:
        c = cat.setdefault(r["category"], {"amount": 0.0, "pnl": 0.0, "wp": 0.0})
        c["amount"] += r["amount"]
        c["pnl"] += r["pnl"]
        if r["pct"] is not None:
            c["wp"] += r["amount"] * r["pct"]
    for c in cat.values():
        c["pct"] = (c["wp"] / c["amount"]) if c["amount"] else 0.0

    # 基金行（按金额降序）
    fund_rows = sorted(rows, key=lambda r: r["amount"], reverse=True)
    fund_html = ""
    for r in fund_rows:
        pct_c = color_for(r["pct"])
        pnl_c = color_for(r["pnl"])
        lag = "" if r["nav_date"] == r["max_date"] else f' <span class="lag">滞后</span>'

        # 盘中估值单元
        if r.get("has_est") and r.get("est_pct") is not None:
            est_c = color_for(r["est_pct"])
            qdii_tag = ' <span class="est-lag">预估(滞后)</span>' if r.get("is_qdii") else ""
            pub_tag = ' <span class="pub">官方已出</span>' if r.get("pub_published") else ""
            est_pct_html = f'<span style="color:{est_c};font-weight:600">{fmt_pct(r["est_pct"])}</span>{qdii_tag}{pub_tag}'
            est_pnl_html = f'<span style="color:{color_for(r["est_pnl"])}">{("+" if r["est_pnl"]>=0 else "")}{fmt_money(r["est_pnl"])}</span>'
        else:
            est_pct_html = '<span class="no-est">无估值</span>'
            est_pnl_html = '<span class="no-est">—</span>'

        # ===== Phase 2 信号单元 =====
        sig = r.get("sig") or {}
        light = sig.get("light", "unknown")
        light_col = signals.LIGHT_COLOR.get(light, "#888888")
        light_lbl = signals.LIGHT_LABEL.get(light, "—")
        pct_rank = sig.get("pct_rank")
        gain = sig.get("gain_since_base")
        tier = sig.get("take_profit_tier", 0) or 0
        anom = sig.get("anomaly", {}) or {}
        light_html = (f'<span style="color:{light_col};font-weight:600">● {light_lbl}</span>'
                      + (f'<br><span class="tiny">{pct_rank:.0f}%分位</span>' if pct_rank is not None else ''))
        if gain is not None:
            gain_c = color_for(gain)
            gain_html = f'<td class="num" style="color:{gain_c}">{fmt_pct(gain)}</td>'
        else:
            gain_html = '<td class="num">—</td>'
        sig_parts = []
        if tier > 0:
            sig_parts.append(f'<span class="sig-tp">止盈{tier}档</span>')
        if anom.get("triggered"):
            sig_parts.append('<span class="sig-an">异动</span>')
        sig_html = (" ".join(sig_parts) if sig_parts else '<span class="sig-none">—</span>')
        sig_html = f'<td class="num sig">{sig_html}</td>'

        fund_html += f"""
        <tr>
          <td class="code">{r['code']}</td>
          <td class="name">{r['name']}<div class="sub">{r['category']} · {r['type']}</div></td>
          <td class="num">{fmt_money(r['amount'])}</td>
          <td class="num">{r['nav'] if r['nav'] is not None else '—'}</td>
          <td class="num small">{r['nav_date']}{lag}</td>
          <td class="num" style="color:{pct_c};font-weight:600">{fmt_pct(r['pct'])}</td>
          <td class="num" style="color:{pnl_c}">{('+' if r['pnl']>=0 else '')}{fmt_money(r['pnl'])}</td>
          <td class="num est">{est_pct_html}</td>
          <td class="num est">{est_pnl_html}</td>
          <td class="num">{light_html}</td>
          {gain_html}
          {sig_html}
          <td>{sparkline(r['spark'])}</td>
        </tr>"""

    # 分类块
    cat_html = ""
    for name, c in sorted(cat.items(), key=lambda kv: kv[1]["amount"], reverse=True):
        c_col = color_for(c["pct"])
        cat_html += f"""
        <div class="cat-card">
          <div class="cat-name">{name}</div>
          <div class="cat-amount">{fmt_money(c['amount'])} 元</div>
          <div class="cat-pct" style="color:{c_col}">{fmt_pct(c['pct'])}</div>
          <div class="cat-pnl" style="color:{color_for(c['pnl'])}">最新净值日 {('+' if c['pnl']>=0 else '')}{fmt_money(c['pnl'])} 元</div>
        </div>"""

    total_col = color_for(total_pct)
    pnl_col = color_for(total_pnl)
    est_col = color_for(est_total_pct)
    est_pnl_col = color_for(est_total_pnl)
    snapshot = pf.get("meta", {}).get("snapshot_date", "—")
    platform = pf.get("meta", {}).get("platform", "支付宝")
    no_est_note = (f'｜ 无盘中估值基金：{", ".join(no_est_codes)}（已回退官方净值）' if no_est_codes else "")

    # ===== Phase 2 信号总览 =====
    sig_rows = [r for r in rows if r.get("sig")]
    red_n = sum(1 for r in sig_rows if r["sig"]["light"] == "red")
    yellow_n = sum(1 for r in sig_rows if r["sig"]["light"] == "yellow")
    green_n = sum(1 for r in sig_rows if r["sig"]["light"] == "green")
    tp_n = sum(1 for r in sig_rows if (r["sig"]["take_profit_tier"] or 0) > 0)
    an_n = sum(1 for r in sig_rows if r["sig"]["anomaly"]["triggered"])
    summary_text = signals.signal_summary(rows) if sig_rows else "信号数据不足。"
    signal_section = f"""
    <div class="sig-overview">
      <div class="sig-card"><div class="sl">过热(红)</div><div class="sv" style="color:{signals.LIGHT_COLOR['red']}">{red_n}</div></div>
      <div class="sig-card"><div class="sl">中性(黄)</div><div class="sv" style="color:{signals.LIGHT_COLOR['yellow']}">{yellow_n}</div></div>
      <div class="sig-card"><div class="sl">低估(绿)</div><div class="sv" style="color:{signals.LIGHT_COLOR['green']}">{green_n}</div></div>
      <div class="sig-card"><div class="sl">止盈触发</div><div class="sv" style="color:#d40000">{tp_n}</div></div>
      <div class="sig-card"><div class="sl">异动预警</div><div class="sv" style="color:#d40000">{an_n}</div></div>
    </div>
    <div class="sig-summary">
      <div class="sig-title">信号白话小结（Phase 2）</div>
      <div class="sig-body">{summary_text.replace(chr(10), '<br>')}</div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>基金每日收盘日报</title>
<style>
  body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f8;color:#1f2329;margin:0;padding:24px;}}
  .wrap{{max-width:1000px;margin:0 auto;}}
  h1{{font-size:22px;margin:0 0 4px;}}
  .meta{{color:#8a8f99;font-size:13px;margin-bottom:18px;}}
  .summary{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px;}}
  .card{{background:#fff;border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,.06);flex:1;min-width:180px;}}
  .card .label{{font-size:13px;color:#8a8f99;}}
  .card .value{{font-size:26px;font-weight:700;margin-top:4px;}}
  .card.est{{border-top:3px solid #2b6cb0;}}
  .cats{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;}}
  .cat-card{{background:#fff;border-radius:10px;padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,.06);min-width:150px;flex:1;}}
  .cat-name{{font-size:13px;color:#555;font-weight:600;}}
  .cat-amount{{font-size:15px;margin-top:4px;}}
  .cat-pct{{font-size:18px;font-weight:700;margin-top:2px;}}
  .cat-pnl{{font-size:12px;margin-top:2px;}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06);}}
  th,td{{padding:10px 12px;text-align:left;font-size:13px;border-bottom:1px solid #f0f1f3;}}
  th{{background:#fafbfc;color:#8a8f99;font-weight:600;}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums;}}
  td.code{{font-family:monospace;color:#555;}}
  td.name{{font-weight:600;}}
  td.sub{{font-weight:400;color:#8a8f99;font-size:11px;margin-top:2px;}}
  td.small{{font-size:11px;color:#8a8f99;}}
  td.est{{background:#f7faff;}}
  .lag{{color:#c47f00;background:#fff4e0;border-radius:4px;padding:0 4px;font-size:10px;}}
  .est-lag{{color:#2b6cb0;background:#e8f1fb;border-radius:4px;padding:0 4px;font-size:10px;}}
  .pub{{color:#1a7f37;background:#e6f6ec;border-radius:4px;padding:0 4px;font-size:10px;}}
  .no-est{{color:#b0b4bb;font-size:12px;}}
  tr:last-child td{{border-bottom:none;}}
  .disclaimer{{margin-top:18px;font-size:12px;color:#8a8f99;line-height:1.6;background:#fff;border-left:3px solid #d0d3d9;padding:10px 14px;border-radius:6px;}}
  .est-note{{margin-top:10px;font-size:12px;color:#2b6cb0;line-height:1.6;background:#f7faff;border-left:3px solid #2b6cb0;padding:10px 14px;border-radius:6px;}}
  .sig-overview{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;}}
  .sig-card{{background:#fff;border-radius:10px;padding:10px 14px;box-shadow:0 1px 3px rgba(0,0,0,.06);min-width:110px;flex:1;text-align:center;}}
  .sig-card .sl{{font-size:12px;color:#8a8f99;}}
  .sig-card .sv{{font-size:24px;font-weight:700;margin-top:2px;}}
  .sig-summary{{background:#fff;border-radius:12px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:20px;line-height:1.8;}}
  .sig-title{{font-size:14px;font-weight:600;color:#1f2329;margin-bottom:6px;}}
  .sig-body{{font-size:13px;color:#444441;}}
  td.sig{{background:#fcfcfd;}}
  .tiny{{font-size:10px;color:#8a8f99;}}
  .sig-tp{{color:#d40000;background:#fdeaea;border-radius:4px;padding:1px 5px;font-size:11px;font-weight:600;}}
  .sig-an{{color:#c47f00;background:#fff4e0;border-radius:4px;padding:1px 5px;font-size:11px;font-weight:600;}}
  .sig-none{{color:#b0b4bb;font-size:12px;}}
</style></head>
<body><div class="wrap">
  <h1>📊 基金每日收盘日报</h1>
  <div class="meta">生成时间：{generated_at} ｜ 持仓快照日：{snapshot} ｜ 平台：{platform} ｜ 数据：akshare（官方净值 + 盘中估值）</div>
  <div class="meta" style="color:#c47f00">⚠️ <b>两套口径请分清</b>：①「净值日盈亏」基于基金<b>官方单位净值</b>（每日收盘后 20:00-22:00 公布，非实时），是<b>最近一个已公布交易日</b>的变动；②「今日预估」为平台按持仓实时估算的<b>预估值</b>，收盘后常与官方净值有偏差（波动大时 0.5%-1%+），<b>仅作盘中决策参考，不对账</b>。QDII 预估对应前一美股交易日，标「预估(滞后)」。</div>

  <div class="summary">
    <div class="card"><div class="label">持仓总市值(快照)</div><div class="value">{fmt_money(total_amount)}</div></div>
    <div class="card"><div class="label">最新净值日盈亏</div><div class="value" style="color:{pnl_col}">{('+' if total_pnl>=0 else '')}{fmt_money(total_pnl)} 元</div></div>
    <div class="card"><div class="label">最新净值日涨跌幅</div><div class="value" style="color:{total_col}">{fmt_pct(total_pct)}</div></div>
    <div class="card est"><div class="label">今日预估盈亏 ({est_date})</div><div class="value" style="color:{est_pnl_col}">{('+' if est_total_pnl>=0 else '')}{fmt_money(est_total_pnl)} 元</div></div>
    <div class="card est"><div class="label">今日预估涨跌幅</div><div class="value" style="color:{est_col}">{fmt_pct(est_total_pct)}</div></div>
    <div class="card"><div class="label">基金数量</div><div class="value">{len(rows)} 只</div></div>
  </div>

  <div class="cats">{cat_html}</div>
  {signal_section}

  <table>
    <thead><tr>
      <th>代码</th><th>基金</th><th class="num">持仓市值(元)</th><th class="num">最新净值</th>
      <th class="num">净值日期</th><th class="num">日增长率</th><th class="num">净值日盈亏</th>
      <th class="num est">今日预估涨幅</th><th class="num est">今日预估盈亏</th><th class="num">红绿灯</th><th class="num">近1年涨幅</th><th class="num sig">信号</th><th>近20日走势</th>
    </tr></thead>
    <tbody>{fund_html}</tbody>
  </table>

  <div class="est-note">
    💡 <b>关于「今日预估」</b>：数据来自东方财富同源的盘中估值接口（akshare fund_value_estimation_em），每个交易日 9:30-15:00 随行情实时跳动，15:00 后冻结。
    {no_est_note}
    若你在 15:00 前查看，可用「今日预估盈亏」辅助判断当天是否买入/卖出（15:00 后的操作顺延至下一交易日）。
  </div>

  <div class="disclaimer">
    ⚠️ <b>风险提示</b>：本日报仅基于基金公开单位净值与平台盘中估值做数据跟踪与可视化，<b>不构成任何投资建议</b>。
    持仓金额为截图日市值（非成本）；「净值日盈亏」为「市值 × 当日净值增长率」估算，「今日预估」为「市值 × 盘中预估涨幅」估算，二者均为参考值。
    QDII 类基金（纳斯达克等）净值/预估通常滞后 1-2 个交易日，表中以「滞后 / 预估(滞后)」标注。
    基金有风险，投资须谨慎，决策请结合自身情况。
  </div>
</div></body></html>"""


def main():
    pf = load_portfolio()
    cfg = pf.get("signals", {})
    # 盘中估值：全市场一次拉取
    est_map, est_date, est_err = fetch_estimation()
    if est_err:
        print("⚠️", est_err, "（将仅展示官方净值口径）")
        est_date = datetime.date.today().strftime("%Y-%m-%d")

    rows = []
    errors = []
    for h in pf["holdings"]:
        code = h["code"]
        cache, err = fetch_and_cache(code)
        if err:
            errors.append(f"{code} {h['name']}: {err}")
            continue
        info = latest_of(cache)
        if not info:
            errors.append(f"{code} {h['name']}: 无净值数据")
            continue
        pct = info["pct"]
        pnl = (h["amount"] * pct / 100.0) if pct is not None else 0.0
        max_date = cache["净值日期"].astype(str).max()

        # Phase 2 信号计算
        try:
            sig = signals.compute_signals(cache, cfg, h.get("type", ""), h.get("category", ""))
        except Exception as e:
            sig = {}
            print(f"   ⚠️ {code} 信号计算失败: {e}")

        # 盘中估值字段
        is_qdii = ("QDII" in h["type"]) or ("QDII" in h["name"])
        e = est_map.get(code)
        has_est = bool(e and e.get("has_est"))
        est_pct = e["est_pct"] if has_est else None
        est_pnl = (h["amount"] * est_pct / 100.0) if has_est and est_pct is not None else None
        pub_published = bool(e and e.get("pub_nav") is not None)

        rows.append({
            "code": code, "name": h["name"], "category": h["category"],
            "type": h["type"], "amount": h["amount"],
            "nav": info["nav"], "nav_date": info["date"], "max_date": max_date,
            "pct": pct, "pnl": pnl, "spark": info["spark"],
            "is_qdii": is_qdii, "has_est": has_est,
            "est_pct": est_pct, "est_pnl": est_pnl, "pub_published": pub_published,
            "sig": sig,
        })

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html = build_html(pf, rows, generated_at, est_date)
    today = datetime.date.today().strftime("%Y%m%d")
    out = os.path.join(REPORT_DIR, f"report_{today}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    # 控制台摘要
    total_amount = sum(r["amount"] for r in rows)
    total_pnl = sum(r["pnl"] for r in rows)
    est_total = sum((r["est_pnl"] or 0.0) for r in rows if r["has_est"])
    est_cnt = sum(1 for r in rows if r["has_est"])
    print(f"✅ 日报已生成：{out}")
    print(f"   成功 {len(rows)}/{len(pf['holdings'])} 只；总市值 {total_amount:,.2f} 元；"
          f"最新净值日盈亏 {total_pnl:+,.2f} 元 ({total_pnl/total_amount*100:+.2f}%)")
    print(f"   盘中估值覆盖 {est_cnt}/{len(rows)} 只；今日预估盈亏 {est_total:+,.2f} 元")
    if errors:
        print("⚠️ 以下基金获取数据异常：")
        for e in errors:
            print("   -", e)


if __name__ == "__main__":
    main()
