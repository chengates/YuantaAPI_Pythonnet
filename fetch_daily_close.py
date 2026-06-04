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
    """TPEx: 最近交易日全體上櫃股票日數據"""
    from datetime import datetime
    now = datetime.now()
    roc_date = f"{now.year - 1911}/{now.month:02d}/{now.day:02d}"
    url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?d={roc_date}&response=json"
    print(f"[TPEx] 查詢 {roc_date} ...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[TPEx] 查詢失敗: {e}")
        return {}

    if data.get("stat") != "ok":
        print(f"[TPEx] API stat={data.get('stat')}")
        return {}

    result = {}
    # 第一個 table 是股票報價，第二個是特別處理
    tables = data.get("tables", [])
    if not tables:
        return {}
    # fields: 代號, 名稱, 收盤, 漲跌, 開盤, 最高, 最低, 均價, 成交股數, 成交金額(元), 成交筆數, ...
    for row in tables[0].get("data", []):
        try:
            code = row[0].strip()
            if not code:
                continue
            vol = int(row[8].replace(",", "")) if len(row) > 8 else 0
            amt = int(row[9].replace(",", "")) if len(row) > 9 else 0
            trades = int(row[10].replace(",", "")) if len(row) > 10 else 0
            result[code] = {
                "open": float(row[4].replace(",", "")) if len(row) > 4 else 0,
                "high": float(row[5].replace(",", "")) if len(row) > 5 else 0,
                "low": float(row[6].replace(",", "")) if len(row) > 6 else 0,
                "close": float(row[2].replace(",", "")) if len(row) > 2 else 0,
                "vol": vol,
                "amount": amt,
                "trades": trades,
            }
        except (ValueError, IndexError):
            continue
    print(f"[TPEx] 取得 {len(result)} 筆")
    return result


# ---- 寫入 ----

def write_daily_summary(stock_id, date_str, info):
    """寫入 @stockID.csv（去重）。若同日已有記錄則更新 OHLCV，
    保留既有 total_in_volume/total_out_volume 不被覆蓋為 0。"""
    path = f"@{stock_id}.csv"
    fieldnames = ["日期", "stock_id", "開盤價", "最高價", "最低價",
                  "收盤價", "成交股數", "成交金額", "成交筆數",
                  "total_in_volume", "total_out_volume", "estimated_day_volume"]

    existing_rows = []
    date_found = False
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                for r in csv.DictReader(f):
                    d = r.get("日期", r.get("date", ""))
                    if d == date_str:
                        date_found = True
                        # 保留既有的 total_in/total_out
                        existing_rows.append({
                            "日期": date_str, "stock_id": stock_id,
                            "開盤價": info["open"], "最高價": info["high"],
                            "最低價": info["low"], "收盤價": info["close"],
                            "成交股數": info["vol"], "成交金額": info["amount"],
                            "成交筆數": info["trades"],
                            "total_in_volume": r.get("total_in_volume", 0) or 0,
                            "total_out_volume": r.get("total_out_volume", 0) or 0,
                            "estimated_day_volume": info["vol"],
                        })
                    else:
                        existing_rows.append(r)
        except Exception:
            pass

    if date_found:
        # 重寫整個檔案（更新同日記錄）
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in existing_rows:
                writer.writerow(row)
        print(f"  @{stock_id}.csv: {date_str} 已更新 (vol={info['vol']:,})")
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
