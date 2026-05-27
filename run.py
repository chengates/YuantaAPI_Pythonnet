"""Smart launcher — 嘗試連接 UAT API，失敗 2 次後自動進入模擬模式。
Usage: python run.py [--port 5000] [--interval 5]

  啟動流程:
  1. 檢查 .dashboard_pid 防止雙開
  2. 嘗試偵測 API (檢查 .api_active 標記檔 + PID 存活)
  3. 若失敗，等待 3 秒後重試第 2 次
  4. 2 次都失敗 → 進入 SIM_RUN 模擬模式
  5. 任一次成功 → API 模式 (僅 dashboard，API 寫 CSV)
"""
import argparse
import ctypes.wintypes
import glob
import os
import sys
import threading
import time
from datetime import datetime
import test_simulate
import web_dashboard

API_FLAG = ".api_active"
PID_FILE = ".dashboard_pid"
API_RETRY_MAX = 2
API_RETRY_DELAY = 3  # 秒

SYNCHRONIZE = 0x100000
PROCESS_QUERY_INFORMATION = 0x0400


def _pid_alive(pid: int) -> bool:
    """Windows: 用 OpenProcess 檢查 PID 是否存在。"""
    try:
        handle = ctypes.windll.kernel32.OpenProcess(
            SYNCHRONIZE | PROCESS_QUERY_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
    except Exception:
        pass
    return False


def _check_duplicate():
    """檢查是否已有 dashboard 在運行，避免雙開。"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, encoding="utf-8") as f:
                old_pid = int(f.read().strip())
            if _pid_alive(old_pid):
                return old_pid
            os.remove(PID_FILE)
        except (ValueError, OSError):
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
    return None


def _check_api_active() -> bool:
    """檢查 UAT API 是否真正 active：.api_active 存在 + CSV 最近有更新。
    避免 .api_active 殘留但 UAT 已死的空白 dashboard。"""
    if not os.path.exists(API_FLAG):
        return False
    # 確認 API 真的有在寫數據：任一 CSV 在 15 秒內有更新
    csv_files = glob.glob("*.csv")
    if csv_files:
        newest = max(os.path.getmtime(f) for f in csv_files)
        if time.time() - newest < 15:
            return True
        # CSV 存在但超過 15 秒未更新 → API 可能已死
        return False
    # 無 CSV 但 .api_active 剛建立 (< 30s) → 可能 API 剛啟動
    flag_mtime = os.path.getmtime(API_FLAG)
    return (time.time() - flag_mtime) < 30


def _after_market_close() -> bool:
    """14:30 後不收盤後資料，不叫模擬器。"""
    now = datetime.now()
    return now.hour >= 14 and now.minute >= 30


def _try_connect_api() -> bool:
    """嘗試連接 API: 最多 RETRY_MAX 次，每次間隔 RETRY_DELAY 秒。
    回傳 True 表示 API 可用，False 表示應進入模擬模式。
    14:30 後不進入模擬模式，保留收盤數據。"""
    for attempt in range(1, API_RETRY_MAX + 1):
        if _check_api_active():
            print(f"[RUN] 第 {attempt} 次嘗試: API 信號 active")
            return True
        if attempt < API_RETRY_MAX:
            print(f"[RUN] 第 {attempt} 次嘗試: API 未回應，{API_RETRY_DELAY}s 後重試...")
            time.sleep(API_RETRY_DELAY)
        else:
            if _after_market_close():
                print(f"[RUN] 第 {attempt} 次嘗試: API 未回應，已收盤 → 顯示收盤數據")
                return None  # None = 收盤模式，不叫模擬器
            print(f"[RUN] 第 {attempt} 次嘗試: API 未回應，進入 SIM_RUN 模擬模式")
    return False


def _write_pid():
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def _cleanup_pid():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except OSError:
        pass


def main():
    dup_pid = _check_duplicate()
    if dup_pid is not None:
        print(f"[RUN] Dashboard 已在運行中 (PID {dup_pid})，拒絕重複啟動。")
        print(f"[RUN] 若確定未運行，請手動刪除 {PID_FILE}")
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--stocks", type=str, default=None)
    args = parser.parse_args()

    api_active = _try_connect_api()

    if api_active is True:
        print("[RUN] API 模式 — 僅啟動 dashboard (API 寫入 CSV)")
    elif api_active is False:
        print("[RUN] SIM_RUN 模式 — 啟動模擬器 + dashboard")
        sim_thread = threading.Thread(
            target=_run_sim, args=(args,), daemon=True)
        sim_thread.start()
    else:
        print("[RUN] 收盤模式 — 顯示最後收盤數據，不啟動模擬器")

    _write_pid()
    try:
        poll_thread = threading.Thread(target=web_dashboard.poll_worker, daemon=True)
        poll_thread.start()
        print(f"Dashboard -> http://localhost:{args.port}")
        web_dashboard.app.run(host="0.0.0.0", port=args.port,
                              debug=False, threaded=True)
    finally:
        _cleanup_pid()


def _run_sim(args):
    sys.argv = ["test_simulate.py"]
    if args.stocks:
        sys.argv.extend(["--stocks", args.stocks])
    sys.argv.extend(["--interval", str(args.interval)])
    test_simulate.simulate()


if __name__ == "__main__":
    main()
