# -*- coding: utf-8 -*-
"""
Hugging Face Spaces Storage Bucket 同步模块

功能：
  - 启动时从 Storage Bucket 下载数据到本地
  - 关闭时从本地上传数据到 Storage Bucket
  - 定时同步（每 2 分钟）
  - 使用 huggingface_hub 库操作 Storage Bucket
"""
import os
import json
import shutil
import atexit
import signal
import sys
import threading
import time
from pathlib import Path

# HF Spaces 环境变量
HF_TOKEN = os.environ.get("HF_TOKEN")
HF_BUCKET_ID = os.environ.get("HF_BUCKET_ID")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))  # Storage Bucket 挂载点
LOCAL_DATA_DIR = Path(__file__).parent.parent / "data"  # 本地数据目录

# 同步间隔（秒）
SYNC_INTERVAL = 120  # 2 分钟

# 同步的文件列表
SYNC_FILES = [
    "fund_daily.db",          # SQLite 数据库
    "dashboard.json",         # 仪表盘数据
    "mcp_news_cache.json",    # MCP 新闻缓存
]

# 同步的目录列表
SYNC_DIRS = [
    "history",                # 净值历史缓存
    "reports",                # HTML 报告
]


def is_hf_spaces() -> bool:
    """判断是否在 HF Spaces 环境中运行"""
    return HF_TOKEN is not None and HF_BUCKET_ID is not None


def get_hf_api():
    """获取 HF API 客户端"""
    try:
        from huggingface_hub import HfApi
        return HfApi(token=HF_TOKEN)
    except ImportError:
        print("⚠️ huggingface_hub 未安装，跳过存储桶同步")
        return None


def sync_from_bucket():
    """从 Storage Bucket 下载数据到本地"""
    if not is_hf_spaces():
        print("ℹ️  非 HF Spaces 环境，跳过存储桶下载")
        return False

    api = get_hf_api()
    if not api:
        return False

    try:
        print(f"📥 从 Storage Bucket 下载数据: {HF_BUCKET_ID}")
        
        # 确保本地数据目录存在
        LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

        # 下载文件
        for filename in SYNC_FILES:
            try:
                # 尝试下载文件
                api.hf_hub_download(
                    repo_id=HF_BUCKET_ID,
                    filename=filename,
                    local_dir=str(LOCAL_DATA_DIR),
                    repo_type="dataset"
                )
                print(f"  ✅ 下载 {filename}")
            except Exception as e:
                if "404" in str(e) or "EntryNotFound" in str(e):
                    print(f"  ℹ️  {filename} 不存在，跳过")
                else:
                    print(f"  ⚠️  下载 {filename} 失败: {e}")

        # 下载目录
        for dirname in SYNC_DIRS:
            try:
                # 尝试下载目录中的文件
                api.hf_hub_download(
                    repo_id=HF_BUCKET_ID,
                    filename=f"{dirname}/",
                    local_dir=str(LOCAL_DATA_DIR),
                    repo_type="dataset"
                )
                print(f"  ✅ 下载 {dirname}/")
            except Exception as e:
                if "404" in str(e) or "EntryNotFound" in str(e):
                    print(f"  ℹ️  {dirname}/ 不存在，跳过")
                else:
                    print(f"  ⚠️  下载 {dirname}/ 失败: {e}")

        print("✅ 存储桶数据下载完成")
        return True

    except Exception as e:
        print(f"❌ 从存储桶下载失败: {e}")
        return False


def sync_to_bucket():
    """上传本地数据到 Storage Bucket"""
    if not is_hf_spaces():
        return False

    api = get_hf_api()
    if not api:
        return False

    try:
        print(f"📤 上传数据到 Storage Bucket: {HF_BUCKET_ID}")

        # 上传文件
        for filename in SYNC_FILES:
            src = LOCAL_DATA_DIR / filename
            if src.exists():
                try:
                    api.upload_file(
                        path_or_fileobj=str(src),
                        path_in_repo=filename,
                        repo_id=HF_BUCKET_ID,
                        repo_type="dataset"
                    )
                    print(f"  ✅ 上传 {filename}")
                except Exception as e:
                    print(f"  ⚠️  上传 {filename} 失败: {e}")

        # 上传目录
        for dirname in SYNC_DIRS:
            src_dir = LOCAL_DATA_DIR / dirname
            if src_dir.exists():
                for file in src_dir.iterdir():
                    if file.is_file():
                        try:
                            api.upload_file(
                                path_or_fileobj=str(file),
                                path_in_repo=f"{dirname}/{file.name}",
                                repo_id=HF_BUCKET_ID,
                                repo_type="dataset"
                            )
                        except Exception as e:
                            print(f"  ⚠️  上传 {dirname}/{file.name} 失败: {e}")
                print(f"  ✅ 上传 {dirname}/")

        print("✅ 数据上传完成")
        return True

    except Exception as e:
        print(f"❌ 上传到存储桶失败: {e}")
        return False


def sync_from_startup():
    """启动时同步数据"""
    if is_hf_spaces():
        print("🔄 启动时同步存储桶数据...")
        sync_from_bucket()
    else:
        print("ℹ️  非 HF Spaces 环境，跳过启动同步")


def sync_on_exit():
    """退出时同步数据"""
    if is_hf_spaces():
        print("🔄 退出时同步数据到存储桶...")
        sync_to_bucket()


def start_periodic_sync():
    """启动定时同步线程"""
    if not is_hf_spaces():
        return

    def sync_loop():
        while True:
            time.sleep(SYNC_INTERVAL)
            try:
                sync_to_bucket()
            except Exception as e:
                print(f"⚠️  定时同步失败: {e}")

    sync_thread = threading.Thread(target=sync_loop, daemon=True)
    sync_thread.start()
    print(f"⏰ 定时同步已启动（每 {SYNC_INTERVAL // 60} 分钟）")


# 注册退出时的同步钩子
atexit.register(sync_on_exit)

# 处理信号（SIGTERM, SIGINT）
def signal_handler(signum, frame):
    print(f"\n🛑 收到信号 {signum}，正在同步数据...")
    sync_on_exit()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# 测试函数
if __name__ == "__main__":
    print("测试 storage_sync 模块...")
    print(f"HF Spaces 环境: {is_hf_spaces()}")
    print(f"HF_TOKEN: {'已设置' if HF_TOKEN else '未设置'}")
    print(f"HF_BUCKET_ID: {HF_BUCKET_ID}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"LOCAL_DATA_DIR: {LOCAL_DATA_DIR}")

    if is_hf_spaces():
        print("\n测试从存储桶下载...")
        sync_from_bucket()