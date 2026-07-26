# -*- coding: utf-8 -*-
"""
fund-daily Flask 后端服务器

功能:
  - REST API: /api/dashboard, /api/refresh, /api/history 等
  - 静态托管: index.html + ECharts CDN
  - APScheduler 定时任务: 交易日 9:00/12:00/15:30 自动更新
  - 局域网绑定: 0.0.0.0:5000

启动:
  python app.py                # 默认端口 5000
  python app.py --port 8080    # 自定义端口
"""
import sys
import os
import json
import datetime
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "src")
sys.path.insert(0, SRC_DIR)

from flask import Flask, jsonify, send_from_directory, request
import db as db_module
import storage_sync


# ── Flask 应用 ──────────────────────────────────────────

app = Flask(__name__,
            static_folder=ROOT,       # 托管项目根目录的静态文件
            static_url_path="")


# ── 页面路由 ─────────────────────────────────────────────

@app.route("/")
def index():
    """仪表盘主页"""
    return send_from_directory(ROOT, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    """静态文件（data/ 目录下的 JSON 也通过此路由访问）"""
    # 安全：只允许访问项目根目录下已知文件
    safe_files = {"index.html"}
    safe_dirs = {"data"}
    parts = filename.split("/")
    if filename in safe_files or (parts and parts[0] in safe_dirs):
        return send_from_directory(ROOT, filename)
    return jsonify({"error": "Not found"}), 404


# ── REST API ─────────────────────────────────────────────

@app.route("/api/dashboard")
def api_dashboard():
    """当天仪表盘完整数据"""
    # 先查数据库
    data = db_module.load_snapshot()
    if data:
        return jsonify(data)

    # 数据库没有当天数据，尝试读静态 JSON（兼容旧模式）
    json_path = os.path.join(ROOT, "data", "dashboard.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 存入数据库
        db_module.save_snapshot(data)
        return jsonify(data)

    return jsonify({"error": "No data available", "generatedAt": ""}), 404


@app.route("/api/dashboard/<date>")
def api_dashboard_by_date(date):
    """指定日期的仪表盘数据"""
    data = db_module.load_snapshot(date)
    if data:
        return jsonify(data)
    return jsonify({"error": f"No data for {date}"}), 404


@app.route("/api/history")
def api_history():
    """最近 N 天快照列表（不含完整 JSON，仅日期+摘要）"""
    limit = request.args.get("limit", 30, type=int)
    dates = db_module.list_snapshot_dates(limit)
    # 读取每天的摘要信息
    result = []
    for d in dates:
        snap = db_module.load_snapshot(d)
        if snap:
            s = snap.get("summary", {})
            result.append({
                "date": d,
                "totalAmount": s.get("totalAmount", 0),
                "totalPnl": s.get("totalPnl", 0),
                "signals": s.get("signals", {}),
            })
    return jsonify(result)


@app.route("/api/history/trend")
def api_history_trend():
    """净值趋势数据（最近 N 天）"""
    limit = request.args.get("limit", 30, type=int)
    dates = db_module.list_snapshot_dates(limit)
    trend = []
    for d in dates:
        snap = db_module.load_snapshot(d)
        if snap:
            s = snap.get("summary", {})
            holdings = snap.get("holdings", [])
            trend.append({
                "date": d,
                "totalAmount": s.get("totalAmount", 0),
                "totalPnl": s.get("totalPnl", 0),
                "estPct": s.get("estPct", 0),
                "holdingCount": len(holdings),
            })
    return jsonify(trend)


@app.route("/api/signals")
def api_signals():
    """当前信号状态"""
    data = db_module.load_latest_snapshot()
    if data and "summary" in data:
        return jsonify(data["summary"].get("signals", {}))
    return jsonify({})


@app.route("/api/news")
def api_news():
    """消息面数据"""
    data = db_module.load_latest_snapshot()
    if data:
        return jsonify({
            "newsItems": data.get("newsItems", []),
            "hotStocks": data.get("hotStocks", []),
            "macroEvents": data.get("macroEvents", []),
        })
    return jsonify({})


@app.route("/api/diag")
def api_diag():
    """诊断数据"""
    data = db_module.load_latest_snapshot()
    if data:
        return jsonify({
            "diag": data.get("diag", {}),
            "corrWarnings": data.get("corrWarnings", []),
            "categoryPie": data.get("categoryPie", []),
            "benchmarkData": data.get("benchmarkData", {}),
            "suggestions": data.get("suggestions", []),
        })
    return jsonify({})


@app.route("/api/holdings")
def api_holdings():
    """持仓详情列表"""
    data = db_module.load_latest_snapshot()
    if data:
        return jsonify(data.get("holdings", []))
    return jsonify([])


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """手动触发一次数据刷新"""
    try:
        result = run_data_update("manual")
        return jsonify({"status": "ok", "date": result.get("date", ""), "message": "数据已刷新"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/refresh/noon", methods=["POST"])
def api_refresh_noon():
    """手动触发午间更新（只刷新盘中估值+新闻）"""
    try:
        result = run_noon_update()
        return jsonify({"status": "ok", "message": "午间数据已刷新"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/events")
def api_events():
    """信号触发事件"""
    limit = request.args.get("limit", 20, type=int)
    conn = db_module.get_db()
    rows = conn.execute(
        "SELECT * FROM signal_events ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/runlog")
def api_runlog():
    """任务执行日志"""
    limit = request.args.get("limit", 20, type=int)
    conn = db_module.get_db()
    rows = conn.execute(
        "SELECT * FROM run_log ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/status")
def api_status():
    """服务器状态"""
    latest = db_module.load_latest_snapshot()
    return jsonify({
        "status": "running",
        "lastUpdate": latest.get("generatedAt", "") if latest else "",
        "snapshotDates": db_module.list_snapshot_dates(5),
        "serverTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


# ── 数据更新逻辑 ────────────────────────────────────────

def run_data_update(task_name="scheduled"):
    """执行完整数据更新（daily + news + diag + export）"""
    started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_id = db_module.save_run_log(task_name, "running", started)

    try:
        import export_json
        dashboard_data = export_json.run_full_export()

        # 保存到数据库
        date_str = db_module.save_snapshot(dashboard_data)

        # 同时保留静态 JSON（兼容直接浏览器打开 index.html 的场景）
        json_path = os.path.join(ROOT, "data", "dashboard.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

        # 检查信号并记录事件
        check_and_record_signals(dashboard_data)

        finished = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_module.update_run_log(log_id, status="ok", finished_at=finished)
        return {"date": date_str}

    except Exception as e:
        finished = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_module.update_run_log(log_id, status="error", finished_at=finished, error_msg=str(e))
        raise


def run_noon_update():
    """午间更新：只刷新盘中估值+新闻，不跑诊断和收盘净值"""
    started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_id = db_module.save_run_log("noon_update", "running", started)

    try:
        import export_json
        dashboard_data = export_json.run_noon_export()

        # 保存到数据库（覆盖当天快照）
        date_str = db_module.save_snapshot(dashboard_data)

        # 同时保留静态 JSON
        json_path = os.path.join(ROOT, "data", "dashboard.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)

        finished = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_module.update_run_log(log_id, status="ok", finished_at=finished)
        return {"date": date_str}

    except Exception as e:
        finished = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_module.update_run_log(log_id, status="error", finished_at=finished, error_msg=str(e))
        raise


def check_and_record_signals(data: dict):
    """检查仪表盘数据中的信号，记录新触发的事件"""
    holdings = data.get("holdings", [])
    today = datetime.date.today().strftime("%Y-%m-%d")

    for h in holdings:
        code = h.get("code", "")
        name = h.get("name", "")
        signals = h.get("signals", {})

        # 红绿灯
        light = signals.get("light", "")
        if light in ("red", "yellow"):
            detail = f"净值百分位 {signals.get('percentile', '?')}%"
            # 检查是否今天已有相同事件（避免重复记录）
            conn = db_module.get_db()
            existing = conn.execute(
                "SELECT id FROM signal_events WHERE date=? AND fund_code=? AND signal_type=?",
                (today, code, f"light_{light}")
            ).fetchone()
            conn.close()
            if not existing:
                db_module.save_signal_event(code, name, f"light_{light}", detail)

        # 异动
        if signals.get("anomaly"):
            anomaly_desc = signals.get("anomaly_desc", "")
            conn = db_module.get_db()
            existing = conn.execute(
                "SELECT id FROM signal_events WHERE date=? AND fund_code=? AND signal_type='anomaly'",
                (today, code)
            ).fetchone()
            conn.close()
            if not existing:
                db_module.save_signal_event(code, name, "anomaly", anomaly_desc)

        # 止盈
        tp = signals.get("take_profit_tier", 0)
        if tp > 0:
            conn = db_module.get_db()
            existing = conn.execute(
                "SELECT id FROM signal_events WHERE date=? AND fund_code=? AND signal_type='take_profit'",
                (today, code)
            ).fetchone()
            conn.close()
            if not existing:
                db_module.save_signal_event(code, name, "take_profit", f"触发 {tp}% 档位")


# ── 定时调度 ─────────────────────────────────────────────

def is_trading_day(date: datetime.date = None) -> bool:
    """判断是否为交易日（简化版：排除周末，不含法定假日）"""
    if date is None:
        date = datetime.date.today()
    # 周末不是交易日
    if date.weekday() >= 5:
        return False
    # TODO: 接入 akshare 的交易日历做更精确判断
    return True


def start_scheduler():
    """启动 APScheduler 定时任务"""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # 交易日 9:00 — 新闻早报更新
    scheduler.add_job(
        run_news_morning,
        trigger="cron",
        hour=9, minute=0,
        id="news_morning",
        name="新闻早报更新",
    )

    # 交易日 12:00 — 午间盘中估值+新闻更新
    scheduler.add_job(
        run_noon_update_wrapper,
        trigger="cron",
        hour=12, minute=0,
        id="noon_update",
        name="午间数据更新",
    )

    # 交易日 15:30 — 收盘后全量更新
    scheduler.add_job(
        run_daily_update_wrapper,
        trigger="cron",
        hour=15, minute=30,
        id="daily_update",
        name="收盘全量更新",
    )

    # 每月第1个交易日 16:00 — 月度诊断
    scheduler.add_job(
        run_monthly_diag,
        trigger="cron",
        day=1, hour=16, minute=0,
        id="monthly_diag",
        name="月度诊断",
    )

    scheduler.start()
    print("⏰ 定时调度已启动:")
    print("   09:00  新闻早报")
    print("   12:00  午间盘中更新")
    print("   15:30  收盘全量更新")
    print("   每月1日 16:00  月度诊断")
    return scheduler


def run_news_morning():
    """9:00 新闻早报"""
    if not is_trading_day():
        return
    print(f"[9:00] 新闻早报更新...")
    try:
        run_data_update("news_morning")
    except Exception as e:
        print(f"[9:00] 更新失败: {e}")


def run_noon_update_wrapper():
    """12:00 午间更新"""
    if not is_trading_day():
        return
    print(f"[12:00] 午间数据更新...")
    try:
        run_noon_update()
    except Exception as e:
        print(f"[12:00] 更新失败: {e}")


def run_daily_update_wrapper():
    """15:30 收盘全量更新"""
    if not is_trading_day():
        return
    print(f"[15:30] 收盘全量更新...")
    try:
        run_data_update("daily_close")
    except Exception as e:
        print(f"[15:30] 更新失败: {e}")


def run_monthly_diag():
    """月度诊断"""
    # 简化判断：每月1号跑，如果是周末则跳过（下次手动跑）
    if not is_trading_day():
        return
    print(f"[每月1日] 月度诊断更新...")
    try:
        run_data_update("monthly_diag")
    except Exception as e:
        print(f"[每月1日] 更新失败: {e}")


# ── 主入口 ───────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="fund-daily 后端服务器")
    ap.add_argument("--port", type=int, default=5000, help="监听端口 (默认 5000)")
    ap.add_argument("--host", default="0.0.0.0", help="监听地址 (默认 0.0.0.0 局域网)")
    ap.add_argument("--no-scheduler", action="store_true", help="不启动定时任务")
    ap.add_argument("--debug", action="store_true", help="Flask debug 模式")
    args = ap.parse_args()

    print("=" * 50)
    print("🖥️  fund-daily 后端服务器")
    print("=" * 50)

    # HF Spaces 环境：启动时同步存储桶数据
    if storage_sync.is_hf_spaces():
        print("🔄 检测到 HF Spaces 环境，同步存储桶数据...")
        storage_sync.sync_from_bucket()

    # 启动前先跑一次数据更新（确保启动时有数据）
    print("📦 初始化数据...")
    try:
        run_data_update("startup")
        print("✅ 初始数据已就绪")
    except Exception as e:
        print(f"⚠️  初始数据加载失败: {e}（可稍后手动刷新）")

    # 启动定时调度
    scheduler = None
    if not args.no_scheduler:
        scheduler = start_scheduler()

    # HF Spaces 环境：启动定时同步
    if storage_sync.is_hf_spaces():
        storage_sync.start_periodic_sync()

    print(f"\n🚀 服务器启动: http://{args.host}:{args.port}")
    print(f"   仪表盘: http://localhost:{args.port}")
    print(f"   API:    http://localhost:{args.port}/api/dashboard")
    print(f"   局域网: http://<你的内网IP>:{args.port}")
    print(f"\n   Ctrl+C 停止服务器\n")

    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    finally:
        if scheduler:
            scheduler.shutdown()


if __name__ == "__main__":
    main()
