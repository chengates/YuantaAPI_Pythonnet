#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
1 分 K 轉換工具 — 從 5 秒 CSV 轉出 1 分鐘 K 線。
輸出格式對齊 cStock.load_data() 需求（日期,開盤價,最高價,最低價,收盤價,成交股數,成交金額,成交筆數）。

用法:
  python resample_1min.py 2330                # 單一股票
  python resample_1min.py --all               # 全部自選股
  python resample_1min.py 2330 --days 5       # 最近 5 個交易日
  python resample_1min.py 2330 --date 20260605 # 指定日期
  python resample_1min.py 2330 --output-dir 1min  # 指定輸出目錄

輸出: {output_dir}/{stock_id}_1min.csv
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, date, timedelta

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "1min")


def load_watchlist_stocks():
    try:
        with open(os.path.join(BASE_DIR, "watchlist.json"), encoding="utf-8") as f:
            config = json.load(f)
        return config.get("自選股1", {}).get("stocks", [])
    except Exception:
        return ["2330", "2317", "2344"]


def resample_5sec_to_1min(stock_id, date_str=None, days=1, output_dir=None):
    """從 {stock_id}.csv 讀取 5 秒數據，resample 為 1 分 K，寫入輸出檔。

    Args:
        stock_id: 股票代碼
        date_str: 指定日期 YYYYMMDD，None 則取最近 days 天
        days: 取最近 N 個交易日（date_str 指定時忽略）
        output_dir: 輸出目錄，預設 1min/

    Returns:
        輸出檔案路徑，若無數據則回傳 None
    """
    csv_path = os.path.join(BASE_DIR, f"{stock_id}.csv")
    if not os.path.exists(csv_path):
        print(f"[{stock_id}] CSV 不存在: {csv_path}")
        return None

    # 讀取 5 秒 CSV
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except Exception as e:
        print(f"[{stock_id}] 讀取失敗: {e}")
        return None

    # 欄位名稱對齊（支援中英文）
    col_map = {
        "timestamp": "timestamp",
        "open_price": "open_price",
        "high_price": "high_price",
        "low_price": "low_price",
        "close_price": "close_price",
        "deal_volume": "deal_volume",
        "deal_amount": "deal_amount",
        "trade_count": "trade_count",
    }
    for col in col_map:
        if col not in df.columns:
            print(f"[{stock_id}] 缺少欄位: {col}")
            return None

    # 解析 timestamp → datetime
    df["datetime"] = pd.to_datetime(df["timestamp"], format="%Y%m%d %H:%M:%S", errors="coerce")
    df = df.dropna(subset=["datetime"])

    if len(df) == 0:
        print(f"[{stock_id}] 無有效 timestamp")
        return None

    # 過濾日期範圍
    if date_str:
        target_date = datetime.strptime(date_str, "%Y%m%d")
        df = df[df["datetime"].dt.date == target_date.date()]
    else:
        # 取最近 N 個交易日
        cutoff = df["datetime"].max() - timedelta(days=days + 2)  # +2 涵蓋週末
        df = df[df["datetime"] >= cutoff]

    if len(df) == 0:
        print(f"[{stock_id}] 指定日期範圍內無數據")
        return None

    # 過濾交易時段 (09:00-13:30)
    df = df[(df["datetime"].dt.hour >= 9) & (df["datetime"].dt.hour < 14)]
    df = df[~((df["datetime"].dt.hour == 13) & (df["datetime"].dt.minute > 30))]

    # 數值轉換
    for col in ["open_price", "high_price", "low_price", "close_price",
                "deal_volume", "deal_amount", "trade_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 過濾無效資料（OHLC 全為 0 的 row）
    ohlc_cols = ["open_price", "high_price", "low_price", "close_price"]
    df = df[df[ohlc_cols].sum(axis=1) > 0]

    if len(df) == 0:
        print(f"[{stock_id}] 過濾後無有效數據")
        return None

    # 設為索引準備 resample
    df = df.set_index("datetime").sort_index()

    # ---- Resample 為 1 分鐘 ----
    agg = {
        "open_price": "first",
        "high_price": "max",
        "low_price": "min",
        "close_price": "last",
        "deal_volume": "sum",
        "deal_amount": "sum",
        "trade_count": "last",  # 累積值，取最後一筆
    }
    df_1min = df.resample("1min").apply(agg)

    # 移除全無數據的分鐘
    df_1min = df_1min.dropna(subset=["open_price", "close_price"], how="all")
    df_1min = df_1min[df_1min[ohlc_cols].sum(axis=1) > 0]

    # 整理輸出欄位
    df_1min = df_1min.reset_index()
    df_1min = df_1min.rename(columns={
        "datetime": "日期",
        "open_price": "開盤價",
        "high_price": "最高價",
        "low_price": "最低價",
        "close_price": "收盤價",
        "deal_volume": "成交股數",
        "deal_amount": "成交金額",
        "trade_count": "成交筆數",
    })
    df_1min["日期"] = df_1min["日期"].dt.strftime("%Y-%m-%d %H:%M:%S")

    # 確保所有欄位為整數（股數/金額/筆數）
    for col in ["成交股數", "成交金額", "成交筆數"]:
        df_1min[col] = df_1min[col].fillna(0).astype(int)

    # 寫入輸出
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{stock_id}_1min.csv")

    out_cols = ["日期", "開盤價", "最高價", "最低價", "收盤價", "成交股數", "成交金額", "成交筆數"]
    df_1min[out_cols].to_csv(out_path, index=False, encoding="utf-8")

    # 統計資訊
    date_range = f"{df_1min['日期'].iloc[0][:10]} ~ {df_1min['日期'].iloc[-1][:10]}"
    print(f"[{stock_id}] {len(df_1min)} 根 1 分 K → {out_path} ({date_range})")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="5 秒 CSV → 1 分 K 轉換工具")
    parser.add_argument("stock", nargs="?", default=None,
                        help="股票代碼（省略時用 --all）")
    parser.add_argument("--all", action="store_true",
                        help="轉換全部自選股")
    parser.add_argument("--date", default=None,
                        help="指定日期 YYYYMMDD")
    parser.add_argument("--days", type=int, default=1,
                        help="最近 N 個交易日（預設 1，--date 指定時忽略）")
    parser.add_argument("--output-dir", default=None,
                        help="輸出目錄（預設 1min/）")
    args = parser.parse_args()

    if args.all or not args.stock:
        stocks = load_watchlist_stocks()
    else:
        stocks = [args.stock]

    print(f"1 分 K 轉換: {len(stocks)} 檔, "
          f"日期={'指定' if args.date else f'最近 {args.days} 天'}")
    print()

    ok = 0
    for sid in stocks:
        result = resample_5sec_to_1min(
            sid,
            date_str=args.date,
            days=args.days,
            output_dir=args.output_dir,
        )
        if result:
            ok += 1

    print(f"\n完成: {ok}/{len(stocks)} 檔")


if __name__ == "__main__":
    main()
