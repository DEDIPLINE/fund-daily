# -*- coding: utf-8 -*-
"""signals.py 单元测试"""
import sys
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import signals


def test_valuation_percentile():
    """估值百分位：高值应返回高百分位"""
    navs = pd.Series(range(1, 101), dtype=float)
    pct = signals.valuation_percentile(navs, window=252)
    assert 95 <= pct <= 100, f"最后一个值应接近100%分位，实际 {pct}"


def test_valuation_percentile_low():
    """低值应返回低百分位"""
    navs = pd.Series(range(100, 0, -1), dtype=float)
    pct = signals.valuation_percentile(navs, window=252)
    assert 0 <= pct <= 5, f"最后一个值应接近0%分位，实际 {pct}"


def test_valuation_light_red():
    """高分位 → 红灯"""
    assert signals.valuation_light(90) == "red"


def test_valuation_light_green():
    """低分位 → 绿灯"""
    assert signals.valuation_light(10) == "green"


def test_valuation_light_yellow():
    """中间 → 黄灯"""
    assert signals.valuation_light(50) == "yellow"


def test_take_profit_tier():
    """止盈档位测试"""
    assert signals.take_profit_tier(5, [15, 20, 25]) == 0
    assert signals.take_profit_tier(16, [15, 20, 25]) == 15
    assert signals.take_profit_tier(21, [15, 20, 25]) == 20
    assert signals.take_profit_tier(26, [15, 20, 25]) == 25


def test_anomaly_signal_no_trigger():
    """正常数据不触发异动"""
    growth = pd.Series([0.1, -0.2, 0.3, -0.1, 0.2])
    result = signals.anomaly_signal(growth, drop_pct=3.0, consecutive=3)
    assert result["triggered"] == False


def test_anomaly_signal_big_drop():
    """单日大跌触发异动（检查最新一日）"""
    growth = pd.Series([0.1, -0.2, 0.3, -4.0])
    result = signals.anomaly_signal(growth, drop_pct=3.0, consecutive=3)
    assert result["triggered"] == True
    assert result["single_drop"] == True


def test_anomaly_signal_consecutive():
    """连跌触发异动（最后3日连跌）"""
    growth = pd.Series([0.5, -1.0, -1.5, -2.0])
    result = signals.anomaly_signal(growth, drop_pct=3.0, consecutive=3)
    assert result["triggered"] == True
    assert result["consecutive_down"] == 3


def test_trailing_return():
    """近1年涨幅计算（trailing_return 期望 nav 为 pd.Series）"""
    dates = pd.Series(pd.date_range("2025-01-01", periods=300, freq="B"))
    nav = pd.Series([1.0 + i * 0.001 for i in range(300)])
    gain = signals.trailing_return(nav, dates, "2025-01-01")
    assert gain is not None
    assert 20 < gain < 40, f"300天每天+0.1% 应在20-40%之间，实际 {gain}"


def test_signal_summary():
    """信号汇总生成白话"""
    rows = [
        {"light": "red", "take_profit_tier": 25, "anomaly": {"triggered": False}},
        {"light": "green", "take_profit_tier": 0, "anomaly": {"triggered": True}},
    ]
    summary = signals.signal_summary(rows)
    assert isinstance(summary, str)
    assert len(summary) > 0
