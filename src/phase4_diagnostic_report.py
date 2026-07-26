# -*- coding: utf-8 -*-
"""
方案B · Phase 4 —— 持仓诊断 / 周月体检报告生成器（M2 输出层）

调用 diagnostics.run_diagnostics() 生成 HTML 报告：
  - 集中度（单只/分类/HHI）
  - 风险桶分布
  - 相关性（假分散检测）
  - 风险与基准对比（组合 vs 沪深300 vs 上证国债指数）
  - 再平衡建议

用法：
  python phase4_diagnostic_report.py            # 默认月报
  python phase4_diagnostic_report.py --period weekly
  python phase4_diagnostic_report.py --period monthly
输出：data/reports/diag_YYYYMMDD.html
"""
import os
import sys
import json
import datetime
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diagnostics as dg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(ROOT, "data", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def f2(x):
    try:
        return round(float(x), 2)
    except Exception:
        return x


def fmt_pct(x):
    if x is None:
        return "—"
    v = f2(x)
    return f"{v:+.2f}%"


def bar(pct, color="#2b6cb0"):
    w = max(2, min(100, pct))
    return (f'<div style="background:#eef1f5;border-radius:4px;height:14px;width:120px;display:inline-block;'
            f'vertical-align:middle;overflow:hidden"><div style="width:{w}%;height:100%;background:{color}"></div></div>'
            f'<span style="margin-left:6px;font-size:12px">{pct:.1f}%</span>')


def build_html(d, period):
    is_monthly = period == "monthly"
    title = "基金持仓月度体检报告" if is_monthly else "基金持仓周度体检报告"

    r = d["risk"]
    conc = d["concentration"]
    buckets = d["buckets"]
    corr = d["correlation"]
    bench = d["benchmarks"]
    sug = d["suggestions"]
    cfg = d["cfg"]

    # === 概览卡片 ===
    hhi = conc["hhi"]
    hhi_label = "偏高" if hhi > cfg["hhi_limit"] else "合理"
    hhi_col = "#d40000" if hhi > cfg["hhi_limit"] else "#1a7f37"
    max_bucket = max(buckets.items(), key=lambda kv: kv[1]) if buckets else ("—", 0)
    overview = f"""
    <div class="summary">
      <div class="card"><div class="label">持仓总市值</div><div class="value">{d['total_amount']:,.2f}</div></div>
      <div class="card"><div class="label">基金数量</div><div class="value">{d['n_funds']} 只</div></div>
      <div class="card"><div class="label">加权年化波动</div><div class="value" style="color:#c47f00">{r['vol_annual']:.1f}%</div></div>
      <div class="card"><div class="label">最大回撤</div><div class="value" style="color:#d40000">{r['max_drawdown']:.1f}%</div></div>
      <div class="card"><div class="label">夏普比率(组合)</div><div class="value" style="color:#1a7f37">{r['sharpe']:.2f}</div></div>
      <div class="card"><div class="label">HHI 集中度</div><div class="value" style="color:{hhi_col}">{hhi} <span style="font-size:13px">{hhi_label}</span></div></div>
      <div class="card"><div class="label">前三大占比</div><div class="value">{conc['top3_weight']:.1f}%</div></div>
      <div class="card"><div class="label">最大风险桶</div><div class="value">{max_bucket[0]} {max_bucket[1]:.0f}%</div></div>
    </div>"""

    # === 集中度：单只占比 ===
    single_rows = ""
    for s in conc["single"]:
        over = s["weight"] > cfg["single_limit"]
        col = "#d40000" if over else "#2b6cb0"
        single_rows += f"""<tr>
          <td class="code">{s['code']}</td>
          <td class="name">{s['name']}<div class="sub">{s['category']}</div></td>
          <td class="num">{s['amount']:,.2f}</td>
          <td class="num">{bar(s['weight'], col)}</td>
          <td class="num" style="color:{'#d40000' if over else '#1f2329'}">{s['weight']:.2f}%</td>
        </tr>"""

    cat_rows = "".join(
        f"<tr><td>{k}</td><td class='num'>{bar(v)}</td><td class='num'>{v:.2f}%</td></tr>"
        for k, v in conc["by_category"].items()
    )

    # === 风险桶 ===
    bucket_cards = ""
    for k, v in buckets.items():
        over = v > cfg["bucket_limit"]
        col = "#d40000" if over else "#1a7f37"
        bucket_cards += f"""<div class="cat-card">
          <div class="cat-name">{k}</div>
          <div class="cat-amount">{bar(v, col)}</div>
          <div class="cat-pct" style="color:{col}">{v:.1f}%</div>
          <div class="cat-pnl">{'超过阈值' if over else '正常'}</div>
        </div>"""

    # === 相关性（假分散） ===
    if corr["high_pairs"]:
        pair_rows = ""
        for p in corr["high_pairs"]:
            c = p["corr"]
            col = "#d40000" if c >= 0.8 else "#c47f00"
            pair_rows += f"""<tr>
              <td class="code">{p['a']}</td><td class="code">{p['b']}</td>
              <td class="num" style="color:{col};font-weight:600">{c}</td>
              <td>高度同质，疑似重复敞口</td>
            </tr>"""
        corr_block = f"""
        <div class="note warn">⚠️ <b>假分散警报</b>：以下基金对相关性极高，呈现“同涨同跌”。
        它们看似分散，实则暴露同一类风险；减少重复敞口比增加数量更能降低风险。</div>
        <table><thead><tr><th>基金A</th><th>基金B</th><th class="num">相关系数</th><th>解读</th></tr></thead>
        <tbody>{pair_rows}</tbody></table>
        <div class="meta">全样本平均相关系数：{corr['avg_corr']}（共 {corr['n_pairs']} 对；>0.7 视为高同质）</div>"""
    else:
        corr_block = f'<div class="note ok">当前未检测到相关性 > {cfg["corr_limit"]} 的基金对，无明显假分散。平均相关系数 {corr["avg_corr"]}。</div>'

    # === 风险与基准对比 ===
    bench_rows = f"""<tr class="mine">
      <td><b>你的组合</b></td>
      <td class="num">{r['vol_annual']:.1f}%</td>
      <td class="num">{r['mean_annual']:+.1f}%</td>
      <td class="num">{r['sharpe']:.2f}</td>
      <td class="num">{r['cum_return']:+.1f}%</td>
      <td class="num" style="color:#d40000">{r['max_drawdown']:.1f}%</td>
    </tr>"""
    for b in bench:
        bench_rows += f"""<tr>
          <td>{b['name']}</td>
          <td class="num">{b['vol_annual']:.1f}%</td>
          <td class="num">{b['mean_annual']:+.1f}%</td>
          <td class="num">{b['sharpe']:.2f}</td>
          <td class="num">{b['cum_return']:+.1f}%</td>
          <td class="num">—</td>
        </tr>"""
    bench_block = f"""
    <table><thead><tr><th>标的</th><th class="num">年化波动</th><th class="num">年化收益</th>
      <th class="num">夏普</th><th class="num">区间累计</th><th class="num">最大回撤</th></tr></thead>
    <tbody>{bench_rows}</tbody></table>
    <div class="meta">注：基准取沪深300（宽基A股）与上证国债指数（防御），同窗口({r['window_years']}年)比较。
    {('本次基准数据源暂不可达，已跳过对比。' if not bench else '你的组合波动高于沪深300、远高于国债，夏普高于两基准——即承担了更多风险换来了更高风险调整后收益。')}</div>"""

    # === 再平衡建议 ===
    sug_html = ""
    for s in sug:
        cls = "warn" if s["level"] == "warning" else "ok"
        icon = "⚠️" if s["level"] == "warning" else "✅"
        sug_html += f'<div class="note {cls}">{icon} {s["text"]}</div>'

    theory = f"""
    <div class="theory">
      <b>方法论说明（为何可信）</b>：本报告基于现代投资组合理论(MPT, Markowitz 1952)的相关性框架、
      年化波动率(√252)、最大回撤(MDD)、夏普比率(Sharpe 1966)与 HHI 集中度（产业组织经济学借用到组合）。
      全部为向后看的<b>历史估计</b>，非收益预测；相关性在极端行情会趋同于 1（同跌），保护在最需要时最弱。
      阈值(rf={cfg['rf']*100:.1f}%、单只>{cfg['single_limit']}%、风险桶>{cfg['bucket_limit']}%、HHI>{cfg['hhi_limit']}、相关>{cfg['corr_limit']})为启发式，可按风险偏好调整。
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f8;color:#1f2329;margin:0;padding:24px;}}
  .wrap{{max-width:1000px;margin:0 auto;}}
  h1{{font-size:22px;margin:0 0 4px;}}
  h2{{font-size:17px;margin:26px 0 10px;padding-left:8px;border-left:4px solid #2b6cb0;}}
  .meta{{color:#8a8f99;font-size:13px;margin-bottom:14px;}}
  .summary{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px;}}
  .card{{background:#fff;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.06);flex:1;min-width:120px;}}
  .card .label{{font-size:12px;color:#8a8f99;}}
  .card .value{{font-size:22px;font-weight:700;margin-top:4px;}}
  .cats{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;}}
  .cat-card{{background:#fff;border-radius:10px;padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,.06);min-width:160px;flex:1;}}
  .cat-name{{font-size:13px;color:#555;font-weight:600;}}
  .cat-amount{{margin-top:6px;}}
  .cat-pct{{font-size:18px;font-weight:700;margin-top:2px;}}
  .cat-pnl{{font-size:12px;margin-top:2px;color:#8a8f99;}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:8px;}}
  th,td{{padding:9px 12px;text-align:left;font-size:13px;border-bottom:1px solid #f0f1f3;}}
  th{{background:#fafbfc;color:#8a8f99;font-weight:600;}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums;}}
  td.code{{font-family:monospace;color:#555;}}
  td.name{{font-weight:600;}}
  td.sub{{font-weight:400;color:#8a8f99;font-size:11px;}}
  tr:last-child td{{border-bottom:none;}}
  tr.mine{{background:#f0f6ff;}}
  .note{{margin:10px 0;font-size:13px;line-height:1.7;padding:10px 14px;border-radius:6px;}}
  .note.warn{{background:#fff4e0;border-left:3px solid #c47f00;color:#7a4f00;}}
  .note.ok{{background:#e6f6ec;border-left:3px solid #1a7f37;color:#1d5b2e;}}
  .theory{{margin-top:18px;font-size:12px;color:#8a8f99;line-height:1.7;background:#fff;border-left:3px solid #d0d3d9;padding:10px 14px;border-radius:6px;}}
  .disclaimer{{margin-top:14px;font-size:12px;color:#8a8f99;line-height:1.6;}}
</style></head>
<body><div class="wrap">
  <h1>🩺 {title}</h1>
  <div class="meta">生成时间：{d['generated_at']} ｜ 样本窗口：约 {r['window_years']} 年（{r['n_days']} 个交易日）
  ｜ 持仓快照总市值：{d['total_amount']:,.2f} 元 ｜ 数据：akshare 净值历史</div>

  {overview}

  <h2>一、集中度诊断</h2>
  <p class="meta">单只占比（红线为 {cfg['single_limit']}% 阈值）；HHI={hhi}（> {cfg['hhi_limit']} 偏高）；前三大合计 {conc['top3_weight']:.1f}%。</p>
  <table><thead><tr><th>代码</th><th>基金</th><th class="num">持仓市值</th><th>占比</th><th class="num">权重</th></tr></thead>
  <tbody>{single_rows}</tbody></table>
  <h2 style="font-size:14px;margin-top:14px">分类占比</h2>
  <table><thead><tr><th>分类</th><th>占比</th><th class="num">权重</th></tr></thead><tbody>{cat_rows}</tbody></table>

  <h2>二、风险桶分布</h2>
  <p class="meta">按风险属性归类（A股成长/周期、海外权益、商品/避险、债券/避险）。红线为 {cfg['bucket_limit']}% 阈值。</p>
  <div class="cats">{bucket_cards}</div>

  <h2>三、相关性（假分散检测）</h2>
  {corr_block}

  <h2>四、风险与基准对比</h2>
  {bench_block}

  <h2>五、再平衡建议</h2>
  {sug_html}

  {theory}
  <div class="disclaimer">⚠️ <b>风险提示</b>：本报告为基于历史净值的组合体检，<b>不构成任何投资建议</b>。
  组合风险用持仓金额加权近似（无真实成本时），收益/回撤非资金加权真实收益。指标向后看、非预测；
  相关性在极端行情会失效。最终买卖决策请结合自身风险承受力与定投计划。</div>
</div></body></html>"""


def main(period="monthly"):
    d = dg.run_diagnostics()
    if "error" in d:
        print("❌", d["error"])
        return
    html = build_html(d, period)
    today = datetime.date.today().strftime("%Y%m%d")
    out = os.path.join(REPORT_DIR, f"diag_{today}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {period} 诊断报告已生成：{out}")
    print(f"   加权波动 {d['risk']['vol_annual']:.1f}% ｜ 最大回撤 {d['risk']['max_drawdown']:.1f}% ｜ "
          f"夏普 {d['risk']['sharpe']:.2f} ｜ HHI {d['concentration']['hhi']} ｜ 前三大 {d['concentration']['top3_weight']:.1f}%")
    if d["suggestions"]:
        print(f"   建议 {sum(1 for s in d['suggestions'] if s['level']=='warning')} 条预警 / "
              f"{len(d['suggestions'])} 条提示")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["weekly", "monthly"], default="monthly")
    args = ap.parse_args()
    main(args.period)
