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


# ---- 收盤比對 ----

def compare_and_report(stock_id, date_str, official, threshold=0.005):
    """比對 @stockID.csv 既有數據與官方數據，回傳誤差清單。
    門檻 threshold 預設 0.5%（0.005）。
    回傳 list[dict]：欄位、CSV值、官方值、誤差%。"""
    path = f"@{stock_id}.csv"
    csv_row = None
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                for r in csv.DictReader(f):
                    d = r.get("日期", r.get("date", ""))
                    if d == date_str:
                        csv_row = r
                        break
        except Exception:
            pass

    if csv_row is None:
        return [{"field": "-", "csv": "N/A", "official": "N/A", "pct": None, "flag": "CSV 無此日資料"}]

    def _num(v):
        try:
            return float(v) if v else 0.0
        except (ValueError, TypeError):
            return 0.0

    checks = [
        ("收盤價", "收盤價", "close"),
        ("最高價", "最高價", "high"),
        ("最低價", "最低價", "low"),
        ("成交股數", "成交股數", "vol"),
        ("成交金額", "成交金額", "amount"),
    ]

    diffs = []
    for label, csv_field, off_field in checks:
        csv_val = _num(csv_row.get(csv_field, 0))
        off_val = float(official.get(off_field, 0))
        if off_val == 0:
            continue
        pct = abs(csv_val - off_val) / abs(off_val)
        if pct > threshold:
            diffs.append({
                "field": label,
                "csv": csv_val,
                "official": off_val,
                "pct": round(pct * 100, 2),
                "flag": "超過0.5%"
            })

    # 檢查是否 OHLC 全部相同（資料未更新）
    ohlc_fields = ["開盤價", "最高價", "最低價", "收盤價"]
    if not diffs:
        # 即使沒超過門檻，也檢查 OHLC 一致性
        vals = [_num(csv_row.get(f, 0)) for f in ohlc_fields]
        if len(set(vals)) == 1 and vals[0] > 0:
            diffs.append({
                "field": "OHLC",
                "csv": vals[0],
                "official": official.get("close", 0),
                "pct": round(abs(vals[0] - official.get("close", 0)) / official.get("close", 0) * 100, 2),
                "flag": "OHLC全部相同(可能五檔推斷)"
            })

    return diffs


def print_comparison(stocks, date_str, all_data):
    """列印比對報表"""
    print(f"\n{'='*70}")
    print(f"  收盤比對報告 ({date_str})  —  門檻 0.5%")
    print(f"{'='*70}")
    total_issues = 0
    ok_count = 0

    for sid in stocks:
        if sid not in all_data:
            continue
        official = all_data[sid]
        diffs = compare_and_report(sid, date_str, official)
        if not diffs:
            ok_count += 1
            continue
        print(f"\n--- {sid} ---")
        for d in diffs:
            flag = d.get("flag", "")
            if d["field"] == "-":
                print(f"  {flag}")
            else:
                print(f"  {d['field']}: CSV={d['csv']}  官方={d['official']}  誤差={d['pct']}%  [{flag}]")
            total_issues += 1

    print(f"\n{'='*70}")
    print(f"  比對完成: {ok_count}/{len([s for s in stocks if s in all_data])} 無異常")
    if total_issues > 0:
        print(f"  發現 {total_issues} 項誤差超過 0.5%，請檢查上方明細")
    print(f"{'='*70}\n")
    return total_issues


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
    parser.add_argument("--compare-only", action="store_true", help="僅比對不寫入")
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

    if args.compare_only:
        print("--compare-only 模式：僅比對不寫入\n")
        issues = print_comparison(stocks, today_str, all_data)
        return

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

    # 收盤比對
    print_comparison(stocks, today_str, all_data)


if __name__ == "__main__":
    main()
