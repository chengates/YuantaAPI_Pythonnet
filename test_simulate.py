"""Test simulator — 模擬報價數據寫入 CSV 供 dashboard 驗證。
Usage: python test_simulate.py [--stocks 2330,2317,2344] [--interval 5]
"""
import argparse
import csv
import math
import os
import random
import time
from datetime import datetime

BASE_PRICES = {"2330": 950.0, "2317": 170.0, "2344": 35.0}
STOCKS = ["2330", "2317", "2344"]
DEFAULT_INTERVAL = 5


def _ensure_headers(filename, fieldnames):
    if os.path.exists(filename):
        return
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def simulate():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stocks", type=str, default="2330,2317,2344")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    parser.add_argument("--once", action="store_true", help="Write one record and exit")
    args = parser.parse_args()

    stocks = [s.strip() for s in args.stocks.split(",")]
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
    iter_count = 0

    print(f"模擬寫入啟動: {stocks} / 每 {args.interval}s / Ctrl+C 停止")
    print(f"Dashboard: http://localhost:5000")

    while True:
        for stock_id in stocks:
            filename = f"{stock_id}.csv"
            _ensure_headers(filename, fieldnames)

            base = prices[stock_id]
            change_pct = random.gauss(0, 0.005)
            close = round(base * (1 + change_pct), 2)
            spread = abs(close * random.uniform(0.002, 0.008))
            high = round(close + spread, 2)
            low = round(close - spread, 2)
            open_price = round(random.uniform(low, high), 2)
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
                "high_price": high,
                "low_price": low,
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
                "buy_prices": str([round(close - i * spread / 5, 2) for i in range(5)]),
                "buy_volumes": str([random.randint(1000, 5000) for _ in range(5)]),
                "sell_prices": str([round(close + i * spread / 5, 2) for i in range(5)]),
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

        iter_count += 1
        if args.once:
            print("--once: done")
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    simulate()
