#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
從公開資訊站 (TWSE/TPEx OpenAPI) 取得每日收盤數據，寫入 @stockID.csv 與 stock_ref.json。
用法: python fetch_daily_close.py [--stocks 2330,2317,...]
預設使用 watchlist.json 自選股。TWSE 資料為最近交易日，TPEx 可能當日 14:30 後才發布。
"""

import csv
import json
import os
import ssl
import sys
import time
from datetime import datetime
from urllib.request import urlopen, Request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)


def load_watchlist_stocks():
    try:
        with open("watchlist.json", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("自選股1", {}).get("stocks", [])
    except Exception:
        return ["2330", "2317", "2344"]


# ---- TWSE 上市 (OpenAPI) ----

def fetch_twse_daily():
    """TWSE OpenAPI: 最近交易日全體上市股票日數據"""
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    print("[TWSE] 查詢 (openapi) ...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[TWSE] 查詢失敗: {e}")
        return {}

    result = {}
    for item in data:
        try:
            code = item.get("Code", "").strip()
            if not code:
                continue
            result[code] = {
                "open": float(item.get("OpenPrice", 0) or 0),
                "high": float(item.get("HighestPrice", 0) or 0),
                "low": float(item.get("LowestPrice", 0) or 0),
                "close": float(item.get("ClosingPrice", 0) or 0),
                "vol": int(float(item.get("TradeVolume", 0) or 0)),
                "amount": int(float(item.get("TradeValue", 0) or 0)),
                "trades": int(float(item.get("Transaction", 0) or 0)),
            }
        except (ValueError, TypeError):
            continue
    print(f"[TWSE] 取得 {len(result)} 筆")
    return result


# ---- TPEx 上櫃 (OpenAPI) ----

def fetch_tpex_daily():
    """TPEx OpenAPI: 最近交易日全體上櫃股票日數據"""
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quot"
    print("[TPEx] 查詢 ...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=30, context=ctx) as resp:
            text = resp.read().decode("utf-8")
        if text.strip().startswith("{"):
            data = json.loads(text)
        elif text.strip().startswith("["):
            data = json.loads(text)
        else:
            print(f"[TPEx] 非 JSON 回應 (可能當日資料尚未發布): {text[:80]}")
            return {}
    except Exception as e:
        print(f"[TPEx] 查詢失敗: {e}")
        return {}

    result = {}
    items = data if isinstance(data, list) else data.get("data", data)
    if isinstance(items, dict):
        items = list(items.values())
    for item in items:
        try:
            if not isinstance(item, dict):
                continue
            code = str(item.get("SecuritiesCompanyCode", "")).strip()
            if not code:
                continue
            result[code] = {
                "open": float(item.get("Open", 0) or 0),
                "high": float(item.get("High", 0) or 0),
                "low": float(item.get("Low", 0) or 0),
                "close": float(item.get("Close", 0) or 0),
                "vol": int(float(item.get("TradingVolume", 0) or 0)),
                "amount": int(float(item.get("TradingValue", 0) or 0)),
                "trades": int(float(item.get("Transaction", 0) or 0)),
            }
        except (ValueError, TypeError):
            continue
    print(f"[TPEx] 取得 {len(result)} 筆")
    return result


# ---- 寫入 ----

def write_daily_summary(stock_id, date_str, info):
    """寫入 @stockID.csv（去重）"""
    path = f"@{stock_id}.csv"
    fieldnames = ["日期", "stock_id", "開盤價", "最高價", "最低價",
                  "收盤價", "成交股數", "成交金額", "成交筆數",
                  "total_in_volume", "total_out_volume", "estimated_day_volume"]

    existing_dates = set()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for r in csv.DictReader(f):
                    existing_dates.add(r.get("日期", ""))
        except Exception:
            pass

    if date_str in existing_dates:
        print(f"  @{stock_id}.csv: {date_str} 已存在，跳過")
        return

    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "日期": date_str, "stock_id": stock_id,
            "開盤價": info["open"], "最高價": info["high"],
            "最低價": info["low"], "收盤價": info["close"],
            "成交股數": info["vol"], "成交金額": info["amount"],
            "成交筆數": info["trades"],
            "total_in_volume": 0, "total_out_volume": 0,
            "estimated_day_volume": info["vol"],
        })
    print(f"  @{stock_id}.csv: {date_str} vol={info['vol']:,}")


def update_stock_ref(results):
    """更新 stock_ref.json"""
    ref = {}
    if os.path.exists("stock_ref.json"):
        try:
            with open("stock_ref.json", encoding="utf-8") as f:
                ref = json.load(f)
        except Exception:
            pass

    for code, info in results.items():
        ref[code] = ref.get(code, {})
        ref[code]["yst_price"] = int(info["close"] * 10000)
        ref[code]["yst_vol"] = info["vol"]

    with open("stock_ref.json", "w", encoding="utf-8") as f:
        json.dump(ref, f, ensure_ascii=False, indent=2)
    print(f"stock_ref.json 已更新 {len(results)} 檔")


def update_yesterday(stock_id, date_str, info):
    """寫入 yesterday/ 備份"""
    os.makedirs("yesterday", exist_ok=True)
    ypath = f"yesterday/{stock_id}.csv"
    with open(ypath, "w", encoding="utf-8") as f:
        f.write("日期,成交股數,成交金額,開盤價,最高價,最低價,收盤價,漲跌價差,成交筆數\n")
        price_diff = round(info["close"] - info["open"], 2)
        f.write(f"{date_str},{info['vol']},{info['amount']},{info['open']},{info['high']},{info['low']},{info['close']},{price_diff},{info['trades']}\n")


# ---- 主流程 ----

def main():
    import argparse
    parser = argparse.ArgumentParser(description="從公開資訊站取得收盤數據，寫入 @stockID.csv")
    parser.add_argument("--stocks", default=None, help="股票代碼逗號分隔 (預設: watchlist.json)")
    parser.add_argument("--no-tpex", action="store_true", help="跳過 TPEx")
    args = parser.parse_args()

    stocks = args.stocks.split(",") if args.stocks else load_watchlist_stocks()
    print(f"目標股票: {stocks}")

    twse_data = fetch_twse_daily()
    time.sleep(1)
    tpex_data = {} if args.no_tpex else fetch_tpex_daily()

    all_data = {**twse_data, **tpex_data}
    if not all_data:
        print("未取得任何資料，請稍後再試（當日數據約 15:00 後發布）")
        return

    # 使用最近一筆資料的日期
    today_str = datetime.now().strftime("%Y%m%d")

    print(f"\n寫入 @stockID.csv 與 yesterday/:")
    written = 0
    results = {}
    for sid in stocks:
        if sid in all_data:
            info = all_data[sid]
            write_daily_summary(sid, today_str, info)
            update_yesterday(sid, today_str, info)
            results[sid] = info
            written += 1
        else:
            print(f"  {sid}: 未找到，跳過")

    if results:
        update_stock_ref(results)

    print(f"\n完成: {written}/{len(stocks)} 筆")


if __name__ == "__main__":
    main()
