# -*- coding: utf-8 -*-
"""diagnostics.py 单元测试"""
import sys
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import diagnostics


def test_classify_risk_bucket():
    """风险桶分类"""
    assert diagnostics.classify_risk_bucket("半导体/芯片", "股票型", "芯片") in ("A股成长/周期", "其他")
    assert diagnostics.classify_risk_bucket("黄金", "黄金", "黄金ETF") in ("商品/避险", "其他")
    assert diagnostics.classify_risk_bucket("债券/避险", "债券型", "债券") in ("债券/避险", "其他")


def test_concentration_metrics():
    """集中度指标（weights 为 pd.Series）"""
    weights = pd.Series({"A": 0.3, "B": 0.25, "C": 0.2, "D": 0.15, "E": 0.1})
    holdings = [{"code": c, "name": f"基金{c}", "category": "测试", "amount": 100} for c in weights.index]
    result = diagnostics.concentration_metrics(weights, holdings)
    assert "hhi" in result
    assert "top3_weight" in result
    assert 0 < result["hhi"] < 1
    assert 50 < result["top3_weight"] < 100


def test_concentration_metrics_equal():
    """等权 HHI = 1/N"""
    n = 10
    codes = [f"F{i}" for i in range(n)]
    weights = pd.Series({c: 1.0 / n for c in codes})
    holdings = [{"code": c, "name": f"基金{c}", "category": "测试", "amount": 100} for c in codes]
    result = diagnostics.concentration_metrics(weights, holdings)
    expected_hhi = 1.0 / n
    assert abs(result["hhi"] - expected_hhi) < 0.001, f"HHI 应接近 {expected_hhi}，实际 {result['hhi']}"


def test_risk_metrics():
    """风险指标计算（weights 为 pd.Series）"""
    np.random.seed(42)
    n_days = 252
    returns_df = pd.DataFrame({
        "A": np.random.normal(0.0005, 0.02, n_days),
        "B": np.random.normal(0.0003, 0.015, n_days),
    })
    weights = pd.Series({"A": 0.6, "B": 0.4})
    result = diagnostics.risk_metrics(returns_df, weights, rf=0.015)
    assert "vol_annual" in result
    assert "max_drawdown" in result
    assert "sharpe" in result
    assert result["vol_annual"] > 0
    assert result["max_drawdown"] < 0


def test_correlation_analysis():
    """相关性分析"""
    np.random.seed(42)
    returns_df = pd.DataFrame({
        "A": np.random.normal(0, 0.02, 100),
        "B": np.random.normal(0, 0.02, 100),
    })
    # 让 A 和 B 高度相关
    returns_df["B"] = returns_df["A"] * 0.9 + np.random.normal(0, 0.001, 100)
    result = diagnostics.correlation_analysis(returns_df, corr_limit=0.70)
    assert "high_pairs" in result
    # 应该检测到 A↔B 假分散
    warned = any(
        (p["a"] == "A" and p["b"] == "B") or (p["a"] == "B" and p["b"] == "A")
        for p in result["high_pairs"]
    )
    assert warned, "应检测到 A↔B 高相关性"


def test_rebalance_suggestions():
    """再平衡建议（conc 需含 single 字段）"""
    conc = {
        "hhi": 0.2,
        "top3_pct": 65,
        "top3_weight": 65,
        "single": [
            {"code": "A", "name": "基金A", "weight": 30},
            {"code": "B", "name": "基金B", "weight": 20},
        ]
    }
    buckets = {"A股成长/周期": 70}
    corr = {"high_pairs": [{"a": "A", "b": "B", "corr": 0.85}]}
    cfg = {"single_limit": 25, "bucket_limit": 40, "hhi_limit": 0.15, "corr_limit": 0.70}
    suggestions = diagnostics.rebalance_suggestions(conc, buckets, corr, cfg)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0, "应有再平衡建议"
