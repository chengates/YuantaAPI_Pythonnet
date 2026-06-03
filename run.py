"""Dashboard scheduler — 自動於交易日 08:30 啟動 web dashboard。
Usage: python run.py [--port 5000]

  市場行事曆邏輯:
  - 週六/週日 → 不啟動
  - 國定假日 (holidays.json) → 不啟動
  - 平日 08:30 前 → 等待至 08:30
  - 平日 14:30 後 → 不啟動（已收盤）
  - 若當天已過 14:30 → 不啟動，提示已收盤

  無任何 API 檢測或模擬器邏輯。僅管理 dashboard 的生命週期。
"""
import argparse
import ctypes
import json
import os
import sys
import threading
import time
from datetime import datetime, date

import web_dashboard

PID_FILE = ".dashboard_pid"
HOLIDAYS_FILE = "holidays.json"


def load_holidays() -> list:
    """載入休市日清單。格式: ["2026-01-01", "2026-02-28", ...]"""
    if os.path.exists(HOLIDAYS_FILE):
        with open(HOLIDAYS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def is_trading_day(d: date = None) -> bool:
    """判斷是否為交易日（排除週末與休市日）。"""
    if d is None:
        d = date.today()
    if d.weekday() >= 5:  # 週六(5) 週日(6)
        return False
    holidays = load_holidays()
    if d.isoformat() in holidays:
        return False
    return True


def market_status() -> str:
    """回傳目前市場狀態。"""
    if not is_trading_day():
        return "holiday"
    now = datetime.now()
    t = now.hour * 60 + now.minute
    if t < 8 * 60 + 30:
        return "pre_open"
    if t < 13 * 60 + 30:
        return "trading"
    if t < 14 * 60 + 30:
        return "matching"
    return "closed"


def _try_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _is_process_running(pid: int) -> bool:
    """檢查指定 PID 的程序是否仍在執行（Windows Kernel32）。"""
    try:
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_INFORMATION = 0x0400
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if handle == 0:
            return False
        kernel32.CloseHandle(handle)
        return True
    except Exception:
        return False


def _check_existing() -> bool:
    """檢查是否已有 dashboard 在執行，若有則拒絕雙開。
    回傳 True 表示可以繼續啟動，False 表示應中止。"""
    if not os.path.exists(PID_FILE):
        return True
    try:
        with open(PID_FILE, encoding="utf-8") as f:
            old_pid = _try_int(f.read().strip())
    except OSError:
        _cleanup_pid()
        return True

    if old_pid is None:
        _cleanup_pid()
        return True

    if _is_process_running(old_pid):
        print(f"[RUN] Dashboard 已在執行中 (PID={old_pid})，拒絕雙開。")
        print(f"      如需重啟，請先關閉舊程序: taskkill /f /pid {old_pid}")
        return False
    else:
        print(f"[RUN] 清除殘留的 PID 檔案 (PID={old_pid} 已不存在)")
        _cleanup_pid()
        return True


def _write_pid():
    with open(PID_FILE, "w", encoding="utf-8") as f:
        strPid =str(os.getpid())
        print(f"before wr pid to get pid={strPid}")
        f.write(strPid)


def _cleanup_pid():
    try:
        isPidExist = os.path.exists(PID_FILE)
        if isPidExist:
            print(f"isPidExist={isPidExist}")
            os.remove(PID_FILE)
    except OSError:
        pass


def main():
    # Initialize the parser
    parser = argparse.ArgumentParser()
    #用於將命令列字串解析為 Python 物件的物件。
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    # 雙開防護：若已有 dashboard 在執行則拒絕啟動
    if not _check_existing():
        sys.exit(1)

    status = market_status()

    if status == "holiday":
        today = date.today()
        day_names = ["一", "二", "三", "四", "五", "六", "日"]
        reason = "週末" if today.weekday() >= 5 else "休市日"
        print(f"[RUN] 今日({today} {day_names[today.weekday()]})為{reason}，不啟動")
        return

    if status == "closed":
        print(f"[RUN] 已收盤 (14:30+)，不啟動")
        return

    if status == "pre_open":
        print(f"[RUN] 尚未開盤 (08:30 前)，等待中...")

    print(f"[RUN] 交易日，啟動 dashboard → http://localhost:{args.port}")

    _write_pid()
    try:
        poll_thread = threading.Thread(target=web_dashboard.poll_worker, daemon=True)
        poll_thread.start()
        web_dashboard.app.run(host="0.0.0.0", port=args.port,
                              debug=False, threaded=True)
    finally:
        _cleanup_pid()


if __name__ == "__main__":
    main()
