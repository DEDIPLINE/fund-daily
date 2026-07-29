# -*- coding: utf-8 -*-
"""
将 analysis.json 转换为前端 appState.analysis 格式
"""
import json
import os
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def convert_analysis():
    input_path = os.path.join(ROOT, "data", "analysis.json")
    output_path = os.path.join(ROOT, "data", "analysis_frontend.json")

    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # 提取板块分布
    categories = raw.get("category_distribution", {})
    total_value = raw.get("total_value", 0)
    hhi_current = raw.get("hhi_index", 0)
    high_corr = raw.get("high_correlations", [])
    suggestions = raw.get("suggestions", [])

    # 构建 chartData
    xAxis = list(categories.keys())
    current = [round(v["weight"] * 100, 1) for v in categories.values()]

    # 建议配置：基于分散化原则
    n = len(xAxis)
    target_per_sector = min(18, 100 / n)  # 单板块不超过 18%
    suggested = [round(target_per_sector, 1)] * n

    # 构建 comparisonTable
    comparisonTable = []
    major_adjustments = 0
    increase_count = 0
    decrease_count = 0
    new_count = 0

    for i, (sector, data) in enumerate(categories.items()):
        current_pct = round(data["weight"] * 100, 1)
        suggested_pct = suggested[i]
        adjustment = round(suggested_pct - current_pct, 1)

        # 判断调整类型
        if adjustment > 5:
            adj_type = "increase_large"
            type_text = "大幅增配"
            increase_count += 1
        elif adjustment > 2:
            adj_type = "increase"
            type_text = "增配"
            increase_count += 1
        elif adjustment < -5:
            adj_type = "decrease_large"
            type_text = "大幅减配"
            decrease_count += 1
            major_adjustments += 1
        elif adjustment < -2:
            adj_type = "decrease"
            type_text = "减配"
            decrease_count += 1
            major_adjustments += 1
        else:
            adj_type = "maintain"
            type_text = "维持"

        # 生成理由
        reason = ""
        if adj_type in ("decrease", "decrease_large"):
            reason = f"当前占比 {current_pct}%，建议降至 {suggested_pct}% 以降低集中度"
        elif adj_type in ("increase", "increase_large"):
            reason = f"当前占比 {current_pct}%，建议升至 {suggested_pct}% 以均衡配置"
        else:
            reason = f"当前占比 {current_pct}%，在合理范围内"

        comparisonTable.append({
            "sector": sector,
            "current": current_pct,
            "suggested": suggested_pct,
            "adjustment": adjustment,
            "type": adj_type,
            "typeText": type_text,
            "reason": reason
        })

    # 计算建议 HHI
    suggested_hhi = sum((p / 100) ** 2 for p in suggested)

    # 构建 actionItems
    actionItems = []
    for item in comparisonTable:
        if item["type"] in ("decrease_large", "decrease"):
            actionItems.append({
                "label": "减配建议",
                "action": f"减配 {item['sector']}",
                "description": f"{item['sector']} 当前占比 {item['current']}%，建议降至 {item['suggested']}%",
                "timeframe": "short" if item["type"] == "decrease_large" else "medium"
            })
        elif item["type"] in ("increase_large", "increase"):
            actionItems.append({
                "label": "增配建议",
                "action": f"增配 {item['sector']}",
                "description": f"{item['sector']} 当前占比 {item['current']}%，建议升至 {item['suggested']}%",
                "timeframe": "medium" if item["type"] == "increase_large" else "long"
            })

    # 如果没有特别的建议，添加一个通用建议
    if not actionItems:
        actionItems.append({
            "label": "维持现状",
            "action": "保持当前配置",
            "description": "当前配置较为均衡，建议维持定投节奏",
            "timeframe": "long"
        })

    # 构建 configurationNotes
    current_sectors = len(categories)
    suggested_sectors = len(categories)  # 保持相同板块数

    # 找出高占比板块
    high_pct_sectors = [s for s in comparisonTable if s["current"] > 15]
    high_pct_names = "、".join([s["sector"] for s in high_pct_sectors[:3]])

    configurationNotes = {
        "currentConfig": {
            "description": f"基于实际持仓，偏重 {high_pct_names if high_pct_names else '各板块均衡'}",
            "sectors": current_sectors,
            "characteristics": f"集中度 HHI={hhi_current:.4f}，{'偏高' if hhi_current > 0.15 else '合理'}"
        },
        "suggestedConfig": {
            "description": "基于分散化原则，单板块不超过 18%",
            "sectors": suggested_sectors,
            "characteristics": f"建议 HHI={suggested_hhi:.4f}，风险分散优化"
        },
        "adjustmentPrinciples": [
            {
                "principle": "降低集中度",
                "measure": "减配高占比板块至 18% 以下",
                "effect": f"HHI 从 {hhi_current:.4f} 降至 {suggested_hhi:.4f}"
            },
            {
                "principle": "减少假分散",
                "measure": "关注高相关性基金对，避免重复敞口",
                "effect": "降低组合整体风险"
            }
        ]
    }

    # 构建最终输出
    frontend_data = {
        "meta": {
            "reportDate": datetime.date.today().strftime("%Y-%m-%d"),
            "totalValue": round(total_value, 2),
            "currency": "CNY"
        },
        "summary": {
            "currentSectors": current_sectors,
            "suggestedSectors": suggested_sectors,
            "hhiCurrent": round(hhi_current, 4),
            "hhiSuggested": round(suggested_hhi, 4),
            "majorAdjustments": major_adjustments,
            "adjustmentTypes": {
                "increase": increase_count,
                "decrease": decrease_count,
                "new": new_count
            }
        },
        "chartData": {
            "xAxis": xAxis,
            "current": current,
            "suggested": suggested
        },
        "comparisonTable": comparisonTable,
        "configurationNotes": configurationNotes,
        "actionItems": actionItems[:6],  # 限制为 6 个
        "signalOverview": {
            "summary": {
                "highCorrelation": len(high_corr),
                "totalFunds": raw.get("fund_count", 0)
            },
            "details": [
                {
                    "fund1": p["fund1"],
                    "fund2": p["fund2"],
                    "correlation": round(p["correlation"], 3)
                }
                for p in high_corr
            ]
        }
    }

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(frontend_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 转换完成: {output_path}")
    print(f"   板块数: {current_sectors}")
    print(f"   HHI: {hhi_current:.4f} -> {suggested_hhi:.4f}")
    print(f"   重大调整: {major_adjustments} 个")


if __name__ == "__main__":
    convert_analysis()
