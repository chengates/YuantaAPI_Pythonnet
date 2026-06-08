#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Snapshot 寫入器 — 從 5 秒 CSV 讀取最後一筆資料，寫入 snapshot/{stock_id}.json。
供非 API 場景使用（sim_run.py、盤後 dashboard 測試）。
API 運行時由 YuantaAPI_Pythonnet.py 的 _write_snapshots() 直接寫入，不需此腳本。

用法: python snapshot_writer.py [--interval 0.5] [--stocks 2330,2317]
"""

import csv
import json
import os
import sys
import time
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = os.path.join(BASE_DIR, "snapshot")


def load_watchlist_stocks():
    try:
        with open(os.path.join(BASE_DIR, "watchlist.json"), encoding="utf-8") as f:
            config = json.load(f)
        return config.get("自選股1", {}).get("stocks", [])
    except Exception:
        return ["2330", "2317", "2344"]


def _read_csv_header(stock_id):
    """讀取 CSV 的 header 行（欄位名稱）。"""
    path = os.path.join(BASE_DIR, f"{stock_id}.csv")
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        return next(reader)


def read_last_valid_csv_row(stock_id):
    """讀取 5 秒 CSV 最後一筆有效資料（close_price 非空）。
    只讀檔案尾部 8KB，避免載入整份 2MB+ 的 CSV。"""
    path = os.path.join(BASE_DIR, f"{stock_id}.csv")
    if not os.path.exists(path):
        return None
    try:
        fsize = os.path.getsize(path)
        if fsize < 100:
            return None
        # 先取得 header
        fieldnames = _read_csv_header(stock_id)
        # 從檔案尾部讀取最後 8KB
        read_size = min(fsize, 8192)
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            if fsize > read_size:
                f.seek(fsize - read_size)
                f.readline()  # 跳過不完整行
            tail = f.read()
        lines = tail.strip().split("\n")
        if len(lines) < 1:
            return None
        # 用正確的 header + 尾部資料行建立 DictReader
        reader = csv.DictReader(lines, fieldnames=fieldnames)
        rows = list(reader)
        # 從最後往前找第一筆有效資料（close_price 非空且非 0）
        for row in reversed(rows):
            cp = row.get("close_price")
            if cp and cp not in ("", "None", "0", "0.0"):
                return row
        # 降級：回傳最後一筆
        return rows[-1] if rows else None
    except Exception:
        return None


def read_recent_csv_rows(stock_id, n=10):
    """讀取 CSV 最後 N 筆（用於 records）。"""
    path = os.path.join(BASE_DIR, f"{stock_id}.csv")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))
        return rows[-n:]
    except Exception:
        return []


def write_snapshot(stock_id):
    """從 CSV 讀取最後一筆有效資料，寫入 snapshot/{stock_id}.json。"""
    row = read_last_valid_csv_row(stock_id)
    if not row:
        return False

    def _np(val):
        if val is None or val == "" or val == "None":
            return None
        try:
            v = float(val)
            return round(v / 10000.0) if abs(v) > 100000 else round(v, 2)
        except (ValueError, TypeError):
            return None

    def _ni(val):
        try:
            return max(0, int(float(val)))
        except (ValueError, TypeError):
            return 0

    # 最近 10 筆交易記錄
    recent = read_recent_csv_rows(stock_id, n=10)
    records = []
    for r in recent:
        price = _np(r.get("close_price"))
        vol = _ni(r.get("deal_volume"))
        in_vol = _ni(r.get("total_in_volume"))
        out_vol = _ni(r.get("total_out_volume"))
        amt = float(r.get("deal_amount", 0) or 0)
        if vol > 0 or in_vol > 0 or out_vol > 0:
            records.append({
                "time": r.get("timestamp", "")[-8:],
                "price": price,
                "vol": vol,
                "in_vol": in_vol,
                "out_vol": out_vol,
                "amt": max(0, amt),
            })

    snap = {
        "timestamp": row.get("timestamp", ""),
        "stock_id": stock_id,
        "open_price": _np(row.get("open_price")),
        "high_price": _np(row.get("high_price")),
        "low_price": _np(row.get("low_price")),
        "close_price": _np(row.get("close_price")),
        "price_diff": _np(row.get("price_diff")),
        "deal_volume": _ni(row.get("deal_volume")),
        "deal_amount": float(row.get("deal_amount", 0) or 0),
        "trade_count": _ni(row.get("trade_count")),
        "total_in_volume": _ni(row.get("total_in_volume")),
        "total_out_volume": _ni(row.get("total_out_volume")),
        "estimated_day_volume": _ni(row.get("estimated_day_volume")),
        "volume_label": row.get("volume_label", "估日量"),
        "pct_of_yesterday_avg": _np(row.get("pct_of_yesterday_avg")),
        "buy_total_volume": _ni(row.get("buy_total_volume")),
        "sell_total_volume": _ni(row.get("sell_total_volume")),
        "buy_sell_imbalance": _ni(row.get("buy_sell_imbalance")),
        "buy_sell_pressure": _np(row.get("buy_sell_pressure")),
        "buy_prices": _parse_list(row.get("buy_prices", "[]")),
        "buy_volumes": _parse_list(row.get("buy_volumes", "[]")),
        "sell_prices": _parse_list(row.get("sell_prices", "[]")),
        "sell_volumes": _parse_list(row.get("sell_volumes", "[]")),
        "ma5": _np(row.get("ma5")),
        "ma10": _np(row.get("ma10")),
        "price_momentum": _np(row.get("price_momentum")),
        "stock_type": row.get("stock_type", ""),
        "participation_score": _np(row.get("participation_score")),
        "participation_label": row.get("participation_label", ""),
        "records": records,
    }

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    fpath = os.path.join(SNAPSHOT_DIR, f"{stock_id}.json")
    # 原子寫入：先寫 .tmp 再 rename，避免讀取半寫入檔案
    tmp_path = fpath + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False)
        os.replace(tmp_path, fpath)
    except Exception:
        pass
    return True


def _parse_list(val):
    try:
        if isinstance(val, str) and val.startswith("["):
            return [float(x.strip()) for x in val.strip("[]").split(",") if x.strip()]
    except Exception:
        pass
    return []


def main():
    parser = argparse.ArgumentParser(description="從 CSV 產生 dashboard snapshot")
    parser.add_argument("--interval", type=float, default=0.5, help="更新間隔秒數 (預設 0.5)")
    parser.add_argument("--stocks", default=None, help="股票代碼逗號分隔")
    parser.add_argument("--once", action="store_true", help="只執行一次後退出")
    args = parser.parse_args()

    stocks = args.stocks.split(",") if args.stocks else load_watchlist_stocks()
    print(f"Snapshot writer 啟動: {stocks}, 間隔={args.interval}s")

    while True:
        for sid in stocks:
            try:
                ok = write_snapshot(sid)
                if ok:
                    print(f"  snapshot/{sid}.json 已更新")
            except Exception as e:
                print(f"  {sid}: {e}")
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
