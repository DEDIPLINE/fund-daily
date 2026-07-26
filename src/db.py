# -*- coding: utf-8 -*-
"""
fund-daily SQLite 数据持久化层

表结构:
  - daily_snapshot: 每日仪表盘快照（完整 JSON 数据）
  - signal_events:  信号触发事件记录（红绿灯/止盈/异动）
  - run_log:        定时任务执行日志
"""
import os
import json
import sqlite3
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 支持 HF Spaces 环境：优先使用 /data 目录（Storage Bucket 挂载点）
# 如果 /data 不存在或不可写，则回退到本地 data 目录
def _get_data_dir():
    """获取数据存储目录"""
    # 检查是否在 HF Spaces 环境中
    hf_data_dir = os.environ.get("DATA_DIR", "/data")
    if os.path.exists(hf_data_dir) and os.access(hf_data_dir, os.W_OK):
        try:
            # 测试是否可写
            test_file = os.path.join(hf_data_dir, ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            return hf_data_dir
        except (OSError, IOError):
            pass
    
    # 回退到本地目录
    local_data_dir = os.path.join(ROOT, "data")
    os.makedirs(local_data_dir, exist_ok=True)
    return local_data_dir

DATA_DIR = _get_data_dir()
DB_PATH = os.path.join(DATA_DIR, "fund_daily.db")


def get_db():
    """获取数据库连接（确保目录存在）"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS daily_snapshot (
            date        TEXT PRIMARY KEY,
            json_data   TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS signal_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            fund_code   TEXT NOT NULL,
            fund_name   TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            detail      TEXT,
            notified    INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name   TEXT NOT NULL,
            status      TEXT NOT NULL,
            started_at  TEXT NOT NULL,
            finished_at TEXT,
            error_msg   TEXT
        );
    """)
    conn.commit()
    conn.close()


def save_snapshot(data: dict) -> str:
    """保存当天仪表盘快照"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO daily_snapshot (date, json_data, created_at) VALUES (?, ?, ?)",
        (today, json.dumps(data, ensure_ascii=False), now)
    )
    conn.commit()
    conn.close()
    return today


def load_snapshot(date: str = None) -> dict | None:
    """加载指定日期的快照，默认当天"""
    if date is None:
        date = datetime.date.today().strftime("%Y-%m-%d")
    conn = get_db()
    row = conn.execute(
        "SELECT json_data FROM daily_snapshot WHERE date = ?", (date,)
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row["json_data"])
    return None


def load_latest_snapshot() -> dict | None:
    """加载最新一份快照（不限日期）"""
    conn = get_db()
    row = conn.execute(
        "SELECT json_data, date FROM daily_snapshot ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row["json_data"])
    return None


def list_snapshot_dates(limit: int = 30) -> list[str]:
    """获取最近 N 天的快照日期列表"""
    conn = get_db()
    rows = conn.execute(
        "SELECT date FROM daily_snapshot ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [r["date"] for r in rows]


def load_snapshot_range(start_date: str, end_date: str) -> list[dict]:
    """加载日期范围内的快照（用于历史趋势）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT date, json_data FROM daily_snapshot WHERE date BETWEEN ? AND ? ORDER BY date",
        (start_date, end_date)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = json.loads(r["json_data"])
        d["_date"] = r["date"]
        result.append(d)
    return result


def save_signal_event(fund_code: str, fund_name: str, signal_type: str, detail: str = "") -> int:
    """记录一条信号触发事件"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO signal_events (date, fund_code, fund_name, signal_type, detail, notified, created_at) "
        "VALUES (?, ?, ?, ?, ?, 0, ?)",
        (today, fund_code, fund_name, signal_type, detail, now)
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return event_id


def mark_event_notified(event_id: int):
    """标记事件已推送"""
    conn = get_db()
    conn.execute("UPDATE signal_events SET notified = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()


def get_unnotified_events() -> list[dict]:
    """获取未推送的信号事件"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM signal_events WHERE notified = 0 ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_run_log(task_name: str, status: str, started_at: str,
                 finished_at: str = None, error_msg: str = None) -> int:
    """记录任务执行日志"""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO run_log (task_name, status, started_at, finished_at, error_msg) "
        "VALUES (?, ?, ?, ?, ?)",
        (task_name, status, started_at, finished_at, error_msg)
    )
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    return log_id


def update_run_log(log_id: int, status: str = None, finished_at: str = None, error_msg: str = None):
    """更新任务执行日志"""
    conn = get_db()
    fields = []
    values = []
    if status:
        fields.append("status = ?")
        values.append(status)
    if finished_at:
        fields.append("finished_at = ?")
        values.append(finished_at)
    if error_msg:
        fields.append("error_msg = ?")
        values.append(error_msg)
    if not fields:
        conn.close()
        return
    values.append(log_id)
    conn.execute(
        f"UPDATE run_log SET {', '.join(fields)} WHERE id = ?", values
    )
    conn.commit()
    conn.close()


# 初始化数据库（模块加载时自动执行）
init_db()
