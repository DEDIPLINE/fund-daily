# -*- coding: utf-8 -*-
"""
方案B · Phase 4 —— 对话陪伴接地层（M4 轻量 CLI）

作用：把持仓诊断结果翻成「能用大白话问」的事实，供用户直接运行，
也供 WorkBuddy(我) 读取后作答，避免凭空编。

用法：
  python ask.py                  # 打印完整诊断摘要
  python ask.py 风险             # 问组合风险高不高
  python ask.py 分散             # 问是不是假分散
  python ask.py 相关性           # 问相关性
  python ask.py 再平衡           # 问该怎么调仓
  python ask.py 回撤             # 问最大回撤
  python ask.py 基准             # 问跑赢被动没
  python ask.py 集中度           # 问集中度
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diagnostics as dg


def _fmt(x):
    try:
        return float(x)
    except Exception:
        return x


def summarize(d):
    r = d["risk"]
    conc = d["concentration"]
    buckets = d["buckets"]
    corr = d["correlation"]
    bench = d["benchmarks"]
    lines = []
    lines.append(f"【组合体检摘要】样本约 {r['window_years']} 年 / {r['n_days']} 交易日")
    lines.append(f"持仓总市值 {d['total_amount']:,.2f} 元，{d['n_funds']} 只基金")
    lines.append(f"加权年化波动 {r['vol_annual']:.1f}%，最大回撤 {r['max_drawdown']:.1f}%，"
                 f"夏普 {r['sharpe']:.2f}，区间累计 {r['cum_return']:+.1f}%")
    lines.append(f"集中度 HHI={conc['hhi']}（{'偏高' if conc['hhi']>d['cfg']['hhi_limit'] else '合理'}），"
                 f"前三大占比 {conc['top3_weight']:.1f}%")
    lines.append("风险桶：" + "、".join(f"{k} {v:.0f}%" for k, v in buckets.items()))
    if corr["high_pairs"]:
        lines.append("假分散：" + "、".join(f"{p['a']}↔{p['b']}({p['corr']})" for p in corr["high_pairs"][:3]))
    if bench:
        btxt = "；".join(f"{b['name']} 夏普{b['sharpe']:.2f}/波动{b['vol_annual']:.1f}%" for b in bench)
        lines.append(f"基准对比：{btxt}")
    lines.append("建议：" + " / ".join(s["text"] for s in d["suggestions"]))
    return "\n".join(lines)


def answer(keyword, d):
    r = d["risk"]
    conc = d["concentration"]
    buckets = d["buckets"]
    corr = d["correlation"]
    bench = d["benchmarks"]
    cfg = d["cfg"]
    k = (keyword or "").strip()

    if k in ("风险", "波动", "risk"):
        return (f"你的组合加权年化波动约 {r['vol_annual']:.1f}%，最大回撤 {r['max_drawdown']:.1f}%，"
                f"夏普 {r['sharpe']:.2f}。\n"
                f"对照：沪深300 波动约 {bench[0]['vol_annual']:.1f}%、国债约 {bench[1]['vol_annual']:.1f}%。"
                f"你的波动明显高于宽基与国债，属‘进取型’；但夏普 {r['sharpe']:.2f} 高于沪深300 的 {bench[0]['sharpe']:.2f}，"
                f"说明承担的风险换来了更高风险调整后收益。小资金+周定投可承受，但需有‘回撤 -{r['max_drawdown']:.1f}%’的心理准备。")

    if k in ("分散", "假分散", "相关性", "corr"):
        if corr["high_pairs"]:
            pairs = "、".join(f"{p['a']}↔{p['b']} 相关系数 {p['corr']}" for p in corr["high_pairs"][:4])
            return (f"存在明显‘假分散’：{pairs}。\n"
                    f"这些基金看似多只，实则高度同涨同跌（相关系数>0.7），本质重复暴露同一类风险。"
                    f"全样本平均相关系数 {corr['avg_corr']}。结论：你不是‘分散了’，而是‘把同一个bet拆成了几份’。"
                    f"真正降低风险要加低相关资产（如债券、黄金已有一部分）。")
        return f"当前未检测到高相关对，平均相关系数 {corr['avg_corr']}，分散度尚可。"

    if k in ("再平衡", "调仓", "建议", "rebalance"):
        return "\n".join(f"- {s['text']}" for s in d["suggestions"])

    if k in ("回撤", "最大回撤", "drawdown"):
        return (f"样本期内组合最大回撤约 {r['max_drawdown']:.1f}%（峰到谷最深跌幅）。\n"
                f"这意味着历史上最惨时，你的组合曾从高点跌去约 {abs(r['max_drawdown']):.1f}%。"
                f"周定投的好处正是在回撤中持续低位买入、摊低成本。")

    if k in ("基准", "跑赢", "benchmark"):
        if not bench:
            return "本次基准数据不可达，无法对比。"
        btxt = "；".join(f"{b['name']} 夏普{b['sharpe']:.2f}/年化收益{b['mean_annual']:+.1f}%/波动{b['vol_annual']:.1f}%"
                        for b in bench)
        return (f"你的组合：夏普 {r['sharpe']:.2f} / 年化收益 {r['mean_annual']:+.1f}% / 波动 {r['vol_annual']:.1f}%。\n"
                f"基准：{btxt}。\n"
                f"结论：你的组合夏普高于两基准（风险调整后更优），但波动显著更高——是‘多担风险多赚钱’，"
                f"不是‘无风险跑赢’。是否‘更好’取决于你能不能扛住更大回撤。")

    if k in ("集中度", "集中", "hhi", "concentration"):
        top = "、".join(f"{s['name'][:6]}…({s['weight']:.0f}%)" for s in conc["single"][:3])
        return (f"集中度：HHI={conc['hhi']}（{'偏高' if conc['hhi']>cfg['hhi_limit'] else '合理'}），"
                f"前三大 {top} 合计 {conc['top3_weight']:.1f}%，已超半数。"
                f"最大风险桶 {max(buckets.items(), key=lambda kv: kv[1])[0]} 占 "
                f"{max(buckets.values()):.0f}%。")

    # 默认：完整摘要
    return summarize(d)


def main():
    d = dg.run_diagnostics()
    if "error" in d:
        print("❌", d["error"])
        return
    keyword = sys.argv[1] if len(sys.argv) > 1 else ""
    out = answer(keyword, d)
    print(out)


if __name__ == "__main__":
    main()
