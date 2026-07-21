"""
Phase 0 — 数据层连通性验证
目的：确认 akshare / easyquotation / yfinance 三个库在隔离 venv 中
      能成功 import 并分别从网络拉到目标标的行情。
注意：本脚本只用"代表性标的"验证链路，不依赖用户真实持仓。
      真实基金代码待用户截图后固化到 portfolio.json。
"""
import time
import json
from datetime import datetime

# 代表性标的（板块 -> ETF 映射，来自方案B调研）
TARGET_ETF = {
    "半导体": "512480",   # 国联安半导体ETF(上交所)
    "黄金":   "518880",   # 华安黄金ETF(上交所)
    "新能源车": "515030", # 华夏新能源车ETF(上交所)
    "纳指":   "513100",   # 国泰纳指ETF(上交所)
    "纳指(深)": "159941", # 广发纳指ETF(深交所)
}
EASY_CODES = ["sh512480", "sh518880", "sh515030", "sh513100", "sz159941"]


def banner(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


results = {}

# ---------- 1. AKShare ----------
banner("1. AKShare  —  A股ETF实时行情 (fund_etf_spot_em)")
try:
    t0 = time.time()
    import akshare as ak
    print(f"akshare version : {ak.__version__}")
    df = ak.fund_etf_spot_em()
    sub = df[df["代码"].isin(list(TARGET_ETF.values()))][
        ["代码", "名称", "最新价", "涨跌幅", "成交额"]
    ]
    elapsed = time.time() - t0
    print(f"全市场ETF行数   : {len(df)}  (耗时 {elapsed:.2f}s)")
    print(sub.to_string(index=False))
    results["akshare"] = {"ok": True, "time_s": round(elapsed, 2), "total_rows": int(len(df))}
except Exception as e:
    print(f"ERROR: {repr(e)}")
    results["akshare"] = {"ok": False, "error": str(e)}

# ---------- 2. easyquotation ----------
banner("2. easyquotation  —  实时快照 (sina)")
try:
    t0 = time.time()
    import easyquotation
    quotation = easyquotation.use("sina")
    data = quotation.stocks(EASY_CODES)
    elapsed = time.time() - t0
    print(f"请求 {len(EASY_CODES)} 只, 返回 {len(data)} 只 (耗时 {elapsed:.2f}s)")
    print("  注: sina源无直接涨跌幅字段, 由 (现价-昨收)/昨收 计算; 其 close 字段=昨收")
    for code, v in data.items():
        name = v.get("name", "?")
        now = v.get("now")
        pre_close = v.get("close")  # sina 源 close 实为昨收价
        if now is not None and pre_close:
            pct = (now - pre_close) / pre_close * 100
            pct_str = f"{pct:+.2f}%"
        else:
            pct_str = "?"
        print(f"  {code:>10}  {name:<12} 现价 {now:<8} 昨收 {pre_close:<8} 涨跌幅 {pct_str}")
    results["easyquotation"] = {"ok": True, "time_s": round(elapsed, 2), "got": len(data)}
except Exception as e:
    print(f"ERROR: {repr(e)}")
    results["easyquotation"] = {"ok": False, "error": str(e)}

# ---------- 3. yfinance ----------
banner("3. yfinance  —  纳指/美股 (513100.SS, ^IXIC, QQQ)")
try:
    t0 = time.time()
    import yfinance as yf
    tk = yf.Tickers("513100.SS ^IXIC QQQ")
    hist = tk.history(period="5d")
    elapsed = time.time() - t0
    print(f"耗时 {elapsed:.2f}s, 行数 {len(hist)}")
    print(hist.tail(3).to_string())
    results["yfinance"] = {"ok": True, "time_s": round(elapsed, 2), "rows": int(len(hist))}
except Exception as e:
    print(f"ERROR: {repr(e)}")
    results["yfinance"] = {"ok": False, "error": str(e)}

# ---------- 总结 ----------
banner("PHASE 0 SUMMARY  @ " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
ok_count = sum(1 for r in results.values() if r.get("ok"))
print(f"可用数据源: {ok_count}/{len(results)}")
print(json.dumps(results, ensure_ascii=False, indent=2))
