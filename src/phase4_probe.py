"""Phase4 可行性探针（只读，不改写任何文件）。
用已缓存的 NAV 历史计算：分类占比、HHI集中度、日收益率相关性、组合波动率/最大回撤。
目的：确认 Phase4 持仓诊断功能有真实数据支撑。
"""
import json
import os
import glob
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HIST = os.path.join(ROOT, "data", "history")
PF = os.path.join(ROOT, "portfolio.json")

pf = json.load(open(PF, encoding="utf-8"))
holdings = pf["holdings"]
cat_of = {h["code"]: h["category"] for h in holdings}
name_of = {h["code"]: h["name"] for h in holdings}
amount_of = {h["code"]: h["amount"] for h in holdings}

# 1) 分类占比
total = sum(amount_of.values())
cat_amt = {}
for c, a in amount_of.items():
    cat_amt.setdefault(cat_of[c], 0.0)
    cat_amt[cat_of[c]] += a
print("=== 分类占比 ===")
for cat, a in sorted(cat_amt.items(), key=lambda kv: -kv[1]):
    print(f"  {cat:<10} {a:8.2f} 元  {a/total*100:5.1f}%")

# 2) HHI 集中度（按单只基金权重）
w = np.array([amount_of[c] / total for c in amount_of])
hhi = float((w**2).sum())
print(f"\n=== 单只基金 HHI 集中度 = {hhi:.4f}  (越接近1越集中；<0.15 算较分散)")
# 按分类的 HHI
wcat = np.array([cat_amt[c] / total for c in cat_amt])
hhi_cat = float((wcat**2).sum())
print(f"=== 按分类 HHI 集中度 = {hhi_cat:.4f}")

# 3) 相关性矩阵（日收益率）
frames = {}
for code in amount_of:
    fp = os.path.join(HIST, f"{code}.csv")
    if not os.path.exists(fp):
        continue
    df = pd.read_csv(fp)
    df["净值日期"] = df["净值日期"].astype(str)
    df["日增长率"] = pd.to_numeric(df["日增长率"], errors="coerce")
    s = df.set_index("净值日期")["日增长率"].dropna() / 100.0
    frames[code] = s

ret = pd.DataFrame(frames)
ret = ret.dropna(how="any")
print(f"\n=== 可比日收益率样本数 = {len(ret)} 天（需各基金同日期才有值）===")
corr = ret.corr()

# 平均两两相关性（排除对角线）
codes = list(corr.columns)
vals = []
for i in range(len(codes)):
    for j in range(i + 1, len(codes)):
        vals.append(corr.iloc[i, j])
print(f"=== 平均两两日收益率相关性 = {np.mean(vals):.3f}  (>0.6 说明高度同质化/假分散) ===")

# 最高相关对
pairs = []
for i in range(len(codes)):
    for j in range(i + 1, len(codes)):
        pairs.append((corr.iloc[i, j], codes[i], codes[j]))
pairs.sort(reverse=True)
print("=== 相关性最高的 5 对（疑似假分散）===")
for v, a, b in pairs[:5]:
    print(f"  {v:+.3f}  {name_of.get(a,a)[:8]}… ↔ {name_of.get(b,b)[:8]}…")

# 4) 组合风险
# 4a) 等权近似（此前口径，供对比）
port_ret_eq = ret.mean(axis=1)
vol_eq = port_ret_eq.std() * np.sqrt(252)
cum_eq = (1 + port_ret_eq).cumprod()
mdd_eq = ((cum_eq - cum_eq.cummax()) / cum_eq.cummax()).min()
print(f"\n=== [等权近似] 年化波动率 ≈ {vol_eq*100:.1f}% ｜ 最大回撤 ≈ {mdd_eq*100:.1f}% ===")

# 4b) 真实加权（用持仓金额作权重）—— 这才是你的实际组合风险
wcol = pd.Series({c: amount_of[c] for c in ret.columns})
wcol = wcol / wcol.sum()
port_ret_w = ret.mul(wcol, axis=1).sum(axis=1)
vol_w = port_ret_w.std() * np.sqrt(252)
cum_w = (1 + port_ret_w).cumprod()
mdd_w = ((cum_w - cum_w.cummax()) / cum_w.cummax()).min()
rf_daily = 0.02 / 252
sharpe = (port_ret_w.mean() - rf_daily) / port_ret_w.std() * np.sqrt(252)
print(f"=== [真实加权] 年化波动率 ≈ {vol_w*100:.1f}% ｜ 最大回撤 ≈ {mdd_w*100:.1f}% ｜ 年化夏普(无风险2%) ≈ {sharpe:.2f} ===")
print(f"   （加权波动率 {vol_w*100:.1f}% > 等权 {vol_eq*100:.1f}%，说明集中度确实推高了你的真实风险）")
print("\n探针完成。以上均为只读计算，未写入任何文件。")
