# -*- coding: utf-8 -*-
"""
AI 基金助手 — 统一入口
用法：
  python main.py daily          生成每日收盘日报
  python main.py news           生成消息面参考卡
  python main.py diag           生成持仓诊断报告（月报）
  python main.py diag --period weekly   生成周报
  python main.py export         导出仪表盘 JSON 数据（全量）
  python main.py noon           午间导出（盘中估值+新闻，不跑诊断）
  python main.py mcp-fetch      提示：通过 WorkBuddy 环境预取 MCP 新闻缓存
  python main.py all            全部跑一遍（daily + news + diag + export）
  python main.py help           显示帮助
"""
import sys
import os
import logging
from datetime import datetime

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('fund-daily.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('fund-daily')

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "src")
sys.path.insert(0, SRC_DIR)

logger.info(f"程序启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def run_daily():
    """运行 Phase1+1.5 每日收盘日报"""
    logger.info("开始生成每日收盘日报")
    print("=" * 50)
    print("📊 每日收盘日报")
    print("=" * 50)
    try:
        import phase1_daily_report
        phase1_daily_report.main()
        logger.info("每日收盘日报生成完成")
    except Exception as e:
        logger.error(f"每日收盘日报生成失败: {e}", exc_info=True)
        raise


def run_news():
    """运行 M5 消息面参考卡"""
    print("=" * 50)
    print("📰 消息面参考卡")
    print("=" * 50)
    import news_signal
    news_signal.main()


def run_diag(period="monthly"):
    """运行 Phase4 持仓诊断报告"""
    print("=" * 50)
    print(f"🩺 持仓诊断报告（{period}）")
    print("=" * 50)
    import phase4_diagnostic_report
    phase4_diagnostic_report.main(period)


def run_export():
    """导出仪表盘 JSON 数据"""
    logger.info("开始导出仪表盘 JSON 数据")
    print("=" * 50)
    print("📡 仪表盘数据导出")
    print("=" * 50)
    try:
        import export_json
        export_json.main()
        logger.info("仪表盘 JSON 数据导出完成")
        
        # 检查导出结果
        import json
        dashboard_path = os.path.join(ROOT, "data", "dashboard.json")
        if os.path.exists(dashboard_path):
            with open(dashboard_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"导出数据检查 - 生成时间: {data.get('generatedAt')}")
            logger.info(f"导出数据检查 - 持仓数量: {len(data.get('holdings', []))}")
        else:
            logger.warning("dashboard.json 文件不存在")
    except Exception as e:
        logger.error(f"仪表盘 JSON 数据导出失败: {e}", exc_info=True)
        raise


def run_noon_export():
    """午间导出（盘中估值+新闻，不跑诊断）"""
    print("=" * 50)
    print("☀️ 午间数据导出")
    print("=" * 50)
    import export_json
    export_json.run_noon_export()


def run_mcp_fetch():
    """提示 MCP 新闻缓存预取方式"""
    print("=" * 50)
    print("📡 MCP 新闻缓存预取")
    print("=" * 50)
    print("""
MCP 新闻工具仅在 WorkBuddy 环境中可用。

请在 WorkBuddy 对话中执行：
  "帮我刷新 MCP 新闻缓存"

WorkBuddy 会调用腾讯自选股 MCP 工具拉取持仓关联股新闻，
保存到 data/mcp_news_cache.json，供 news_signal.py 读取。

缓存有效期为当天，过期后自动降级到 akshare。

当前配置（portfolio.json → news.use_mcp）:
  - use_mcp=true:  优先 MCP 缓存，降级 akshare
  - use_mcp=false: 纯 akshare
""")


def show_help():
    print(__doc__)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("help", "-h", "--help"):
        show_help()
        return

    cmd = args[0].lower()

    if cmd == "daily":
        run_daily()
    elif cmd == "news":
        run_news()
    elif cmd == "diag":
        period = "monthly"
        if "--period" in args:
            idx = args.index("--period")
            if idx + 1 < len(args):
                period = args[idx + 1]
        run_diag(period)
    elif cmd == "export":
        run_export()
    elif cmd == "noon":
        run_noon_export()
    elif cmd == "mcp-fetch":
        run_mcp_fetch()
    elif cmd == "all":
        run_daily()
        print()
        run_news()
        print()
        run_diag("monthly")
        print()
        run_export()
    else:
        print(f"❌ 未知命令: {cmd}")
        show_help()


if __name__ == "__main__":
    main()
