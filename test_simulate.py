"""Test simulator — 模擬報價數據寫入 CSV 供 dashboard 驗證。
Usage: python test_simulate.py [--stocks 2330,2317,2344] [--interval 5] [--once]
  若未指定 --stocks，自動從 watchlist.json 讀取所有自選股。

  API 優先: 若偵測到 .api_active 標記檔，模擬器自動暫停寫入，
  等到 API 中斷連線（標記檔消失）後恢復寫入。
"""
import argparse
import csv
import json
import math
import os
import random
import time
from datetime import datetime

API_FLAG = ".api_active"
API_CHECK_INTERVAL = 5  # 每 N 秒檢查一次 API 是否 active

BASE_PRICES = {"2330": 2315.0, "2317": 264.5, "2344": 155.0, "2454": 1245.0,
               "2412": 126.0, "2881": 92.0, "2882": 75.0, "9907": 25.0,
               "2356": 62.0, "2609": 52.6, "2610": 18.45, "6122": 46.85,
               "6123": 43.05, "8936": 50.0}
DEFAULT_INTERVAL = 5


def _all_watchlist_stocks(path="watchlist.json"):
    """從 watchlist.json 收集所有自選股中的股票代碼。"""
    stocks = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            wl = json.load(f)
        for entry in wl.values():
            for s in entry.get("stocks", []):
                stocks.add(s)
    return sorted(stocks) if stocks else ["2330", "2317", "2344"]


def _write_daily_summary(stock_id: str):
    """寫入每日總結 CSV (@stockID.csv)，模擬版本。"""
    filename = f"@{stock_id}.csv"
    now = datetime.now()
    # 從5秒CSV取最後一筆
    csv5 = f"{stock_id}.csv"
    row = {"open_price": None, "high_price": None, "low_price": None,
           "close_price": None, "deal_volume": 0, "trade_count": 0,
           "total_in_volume": 0, "total_out_volume": 0, "estimated_day_volume": 0}
    if os.path.exists(csv5):
        with open(csv5, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    row["open_price"] = float(r.get("open_price", 0) or 0)
                    row["high_price"] = float(r.get("high_price", 0) or 0)
                    row["low_price"] = float(r.get("low_price", 0) or 0)
                    row["close_price"] = float(r.get("close_price", 0) or 0)
                    row["deal_volume"] = int(float(r.get("deal_volume", 0) or 0))
                    row["trade_count"] = int(float(r.get("trade_count", 0) or 0))
                    row["total_in_volume"] = int(float(r.get("total_in_volume", 0) or 0))
                    row["total_out_volume"] = int(float(r.get("total_out_volume", 0) or 0))
                    row["estimated_day_volume"] = int(float(r.get("estimated_day_volume", 0) or 0))
                except (ValueError, TypeError):
                    pass
    file_exists = os.path.exists(filename)
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "stock_id", "open_price", "high_price", "low_price",
            "close_price", "total_volume", "total_in_volume", "total_out_volume",
            "estimated_day_volume", "trade_count"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "date": now.strftime("%Y%m%d"),
            "stock_id": stock_id,
            "open_price": row["open_price"],
            "high_price": row["high_price"],
            "low_price": row["low_price"],
            "close_price": row["close_price"],
            "total_volume": row["deal_volume"],
            "total_in_volume": row["total_in_volume"],
            "total_out_volume": row["total_out_volume"],
            "estimated_day_volume": row["estimated_day_volume"],
            "trade_count": row["trade_count"],
        })
    print(f"[{now.strftime('%H:%M:%S')}] @{stock_id}.csv 日總結已寫入")


def _ensure_headers(filename, fieldnames):
    if os.path.exists(filename):
        return
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def simulate():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stocks", type=str, default=None,
                        help="Comma-separated stock IDs. Default: read all from watchlist.json")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    parser.add_argument("--once", action="store_true", help="Write one record and exit")
    args = parser.parse_args()

    stocks = [s.strip() for s in args.stocks.split(",")] if args.stocks else _all_watchlist_stocks()
    fieldnames = [
        "timestamp", "stock_id", "deal_volume", "deal_amount", "open_price",
        "high_price", "low_price", "close_price", "price_diff", "trade_count",
        "estimated_day_volume", "pct_of_yesterday_avg",
        "total_in_volume", "total_out_volume", "buy_total_volume",
        "sell_total_volume", "buy_sell_imbalance", "buy_sell_pressure",
        "buy_prices", "buy_volumes", "sell_prices", "sell_volumes",
        "ma5", "ma10", "price_momentum", "byIndexFlag",
        "stock_type", "participation_score", "participation_label", "extra_data",
    ]

    prices = {s: BASE_PRICES.get(s, 100.0) for s in stocks}
    # 開盤價、最高價、最低價 — 全天固定/累積
    open_prices = {}   # 開盤價: 只在啟動時設定一次
    high_prices = {}   # 最高價: 累積更新
    low_prices = {}    # 最低價: 累積更新

    print(f"模擬寫入啟動: {stocks} / 每 {args.interval}s / Ctrl+C 停止")
    print(f"Dashboard: http://localhost:5000")

    last_api_check = 0
    api_paused = False

    while True:
        # ---- API 優先: 若 UAT 送來信號，模擬器暫停寫入 ----
        now_ts = time.time()
        if now_ts - last_api_check >= API_CHECK_INTERVAL:
            last_api_check = now_ts
            if os.path.exists(API_FLAG):
                if not api_paused:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] API 信號 active，模擬器暫停寫入")
                    api_paused = True
                time.sleep(args.interval)
                continue
            else:
                if api_paused:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] API 信號消失，模擬器恢復寫入")
                    api_paused = False

        for stock_id in stocks:
            filename = f"{stock_id}.csv"
            _ensure_headers(filename, fieldnames)

            prev = prices[stock_id]
            base_price = BASE_PRICES.get(stock_id, 100.0)
            # 均值回歸隨機漫步: 小雜訊 + 微弱拉回基準價，模擬真實盤中走勢
            noise = random.gauss(0, 0.0003)          # ±0.03% per tick
            reversion = (base_price - prev) / base_price * 0.005  # 0.5% 回歸拉力
            change_pct = noise + reversion
            close = round(prev * (1 + change_pct), 2)

            # 開盤價: 全天只在第一筆設定，之後固定不變
            if stock_id not in open_prices:
                open_prices[stock_id] = close
                high_prices[stock_id] = close
                low_prices[stock_id] = close
            open_price = open_prices[stock_id]

            # 最高/最低: 累積更新
            if close > high_prices[stock_id]:
                high_prices[stock_id] = close
            if close < low_prices[stock_id]:
                low_prices[stock_id] = close

            volume = int(random.uniform(50000, 500000))
            in_vol = int(volume * random.uniform(0.4, 0.6))
            out_vol = volume - in_vol

            score = round((in_vol - out_vol) / max(volume, 1) * 50, 1)
            if score > 30:
                label = "主力強力買進"
            elif score > 10:
                label = "主力溫和買進"
            elif score > -10:
                label = "散戶盤整"
            elif score > -30:
                label = "主力溫和賣出"
            else:
                label = "主力強力賣出"

            prices[stock_id] = close

            now = datetime.now()
            row = {
                "timestamp": now.strftime("%Y%m%d %H:%M:%S"),
                "stock_id": stock_id,
                "deal_volume": volume,
                "deal_amount": round(close * volume, 0),
                "open_price": open_price,
                "high_price": high_prices[stock_id],
                "low_price": low_prices[stock_id],
                "close_price": close,
                "price_diff": round(close - open_price, 2),
                "trade_count": random.randint(100, 2000),
                "estimated_day_volume": int(volume * 30),
                "pct_of_yesterday_avg": round(random.uniform(80, 120), 1),
                "total_in_volume": in_vol,
                "total_out_volume": out_vol,
                "buy_total_volume": random.randint(10000, 100000),
                "sell_total_volume": random.randint(10000, 100000),
                "buy_sell_imbalance": random.randint(-5000, 5000),
                "buy_sell_pressure": round(random.uniform(-10, 10), 2),
                "buy_prices": str([round(close * (1 - 0.001 * i), 2) for i in range(5)]),
                "buy_volumes": str([random.randint(1000, 5000) for _ in range(5)]),
                "sell_prices": str([round(close * (1 + 0.001 * i), 2) for i in range(5)]),
                "sell_volumes": str([random.randint(1000, 5000) for _ in range(5)]),
                "ma5": round(close * random.uniform(0.98, 1.02), 2),
                "ma10": round(close * random.uniform(0.95, 1.05), 2),
                "price_momentum": round(random.uniform(-2, 2), 2),
                "byIndexFlag": "50",
                "stock_type": "large_cap" if stock_id in ("2330", "2317") else "small_cap",
                "participation_score": score,
                "participation_label": label,
                "extra_data": "{}",
            }

            with open(filename, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerow(row)

            print(f"[{now.strftime('%H:%M:%S')}] {stock_id}: {close} vol={volume} {label}")

        if args.once:
            print("--once: done")
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    simulate()
