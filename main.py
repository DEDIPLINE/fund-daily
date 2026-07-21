# -*- coding: utf-8 -*-
"""
AI 基金助手 — 统一入口
用法：
  python main.py daily          生成每日收盘日报
  python main.py news           生成消息面参考卡
  python main.py diag           生成持仓诊断报告（月报）
  python main.py diag --period weekly   生成周报
  python main.py all            全部跑一遍（daily + news + diag）
  python main.py help           显示帮助
"""
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "src")
sys.path.insert(0, SRC_DIR)


def run_daily():
    """运行 Phase1+1.5 每日收盘日报"""
    print("=" * 50)
    print("📊 每日收盘日报")
    print("=" * 50)
    import phase1_daily_report
    phase1_daily_report.main()


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
    phase4_diagnostic_report.main()


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
    elif cmd == "all":
        run_daily()
        print()
        run_news()
        print()
        run_diag("monthly")
    else:
        print(f"❌ 未知命令: {cmd}")
        show_help()


if __name__ == "__main__":
    main()
