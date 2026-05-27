"""Simulation-only launcher — 模擬器 + dashboard 單一進程。
Usage: python sim_run.py [--port 5000] [--interval 5]

  API 優先: 若偵測到 .api_active（UAT 已送來信號），則不啟動。
  啟動前檢查 .dashboard_pid，防止重複啟動。
"""
import argparse
import os
import sys
import threading
import test_simulate
import web_dashboard

API_FLAG = ".api_active"
PID_FILE = ".dashboard_pid"


def _check_duplicate():
    """檢查是否已有 dashboard 在運行，避免雙開。"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, encoding="utf-8") as f:
                old_pid = int(f.read().strip())
            import ctypes.wintypes
            SYNCHRONIZE = 0x100000
            PROCESS_QUERY_INFORMATION = 0x0400
            handle = ctypes.windll.kernel32.OpenProcess(
                SYNCHRONIZE | PROCESS_QUERY_INFORMATION, False, old_pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return old_pid
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except (ValueError, OSError):
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
    return None


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
    if os.path.exists(API_FLAG):
        print("[SIM] API 信號 active，模擬器不啟動。請使用 run.py 或等待 API 中斷。")
        return

    dup_pid = _check_duplicate()
    if dup_pid is not None:
        print(f"[SIM] Dashboard 已在運行中 (PID {dup_pid})，拒絕重複啟動。")
        print(f"[SIM] 若確定未運行，請手動刪除 {PID_FILE}")
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--stocks", type=str, default=None)
    args = parser.parse_args()

    print("[SIM] 模擬模式啟動 (API 未連線)")

    sim_thread = threading.Thread(target=_run_sim, args=(args,), daemon=True)
    sim_thread.start()

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
