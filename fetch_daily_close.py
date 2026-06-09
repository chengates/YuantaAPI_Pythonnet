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

def _detect_twse_data_date(ref_code="2330"):
    """比對 OpenAPI 與 STOCK_DAY 網站 API，偵測 OpenAPI 回傳的實際日期。
    STOCK_DAY_ALL 不回傳日期欄位，且可能回傳前一交易日資料（當日尚未發布）。
    回傳格式: 'YYYYMMDD'，失敗回傳 None。"""
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={datetime.now().strftime('%Y%m%d')}&stockNo={ref_code}"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=15, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if data.get("stat") != "OK" or not data.get("data"):
        return None
    # 最後一筆為最近交易日，第一欄為 ROC 日期 (115/MM/DD)
    last_row = data["data"][-1]
    roc_date = last_row[0].strip()  # e.g. "115/06/05"
    parts = roc_date.split("/")
    if len(parts) != 3:
        return None
    year = int(parts[0]) + 1911
    return f"{year}{parts[1]}{parts[2]}"


def fetch_twse_daily():
    """TWSE OpenAPI: 最近交易日全體上市股票日數據。
    回傳 (data_dict, actual_date_str)，actual_date_str 為 YYYYMMDD 格式。"""
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
        return {}, None

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

    # 偵測資料實際日期（OpenAPI 不回傳日期，需比對）
    actual_date = _detect_twse_data_date()
    if actual_date:
        print(f"[TWSE] 取得 {len(result)} 筆，實際日期={actual_date}")
    else:
        print(f"[TWSE] 取得 {len(result)} 筆，日期偵測失敗")
    return result, actual_date


# ---- TPEx 上櫃 (OpenAPI) ----

def _detect_tpex_data_date():
    """從 TPEx API 表格標題偵測實際資料日期。
    TPEx API 可能回傳前一日資料（當日尚未發布），需從回應中提取日期。
    回傳格式: 'YYYYMMDD'，失敗回傳 None。"""
    # 嘗試多個日期 (今天/昨天) 查詢，比對回傳資料判斷
    now = datetime.now()
    for days_back in [0, 1, 2]:
        d = now.replace(day=now.day - days_back) if days_back > 0 else now
        roc_date = f"{d.year - 1911}/{d.month:02d}/{d.day:02d}"
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?d={roc_date}&response=json"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
        if data.get("stat") == "ok" and data.get("tables"):
            # 有資料表示此日期已發布
            return f"{d.year}{d.month:02d}{d.day:02d}"
    return None


def fetch_tpex_daily():
    """TPEx: 最近交易日全體上櫃股票日數據。
    回傳 (data_dict, actual_date_str)。"""
    # 先偵測最新可用日期
    actual_date = _detect_tpex_data_date()
    if actual_date:
        d = datetime.strptime(actual_date, "%Y%m%d")
        roc_date = f"{d.year - 1911}/{d.month:02d}/{d.day:02d}"
    else:
        now = datetime.now()
        roc_date = f"{now.year - 1911}/{now.month:02d}/{now.day:02d}"
        actual_date = now.strftime("%Y%m%d")

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
        return {}, None

    if data.get("stat") != "ok":
        print(f"[TPEx] API stat={data.get('stat')}")
        return {}, None

    result = {}
    # 第一個 table 是股票報價，第二個是特別處理
    tables = data.get("tables", [])
    if not tables:
        return {}, None
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
    print(f"[TPEx] 取得 {len(result)} 筆，實際日期={actual_date}")
    return result, actual_date


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
    """更新 stock_ref.json（含昨收價、漲跌停價、昨量）。"""
    ref = {}
    if os.path.exists("stock_ref.json"):
        try:
            with open("stock_ref.json", encoding="utf-8") as f:
                ref = json.load(f)
        except Exception:
            pass

    for code, info in results.items():
        close = info["close"]
        ref[code] = ref.get(code, {})
        ref[code]["yst_price"] = int(close * 10000)
        ref[code]["yst_vol"] = info["vol"]
        # 同時寫入漲跌停價（±10%，raw 格式 ×10000）
        ref[code]["up_price"] = int(round(close * 1.10, 2) * 10000)
        ref[code]["down_price"] = int(round(close * 0.90, 2) * 10000)

    with open("stock_ref.json", "w", encoding="utf-8") as f:
        json.dump(ref, f, ensure_ascii=False, indent=2)
    print(f"stock_ref.json 已更新 {len(results)} 檔")


def update_yesterday(stock_id, date_str, info):
    """寫入 yesterday/ 備份（日期格式 YYYY-MM-DD）"""
    os.makedirs("yesterday", exist_ok=True)
    ypath = f"yesterday/{stock_id}.csv"
    # 轉換日期格式: YYYYMMDD → YYYY-MM-DD
    date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    with open(ypath, "w", encoding="utf-8") as f:
        f.write("日期,成交股數,成交金額,開盤價,最高價,最低價,收盤價,漲跌價差,成交筆數\n")
        price_diff = round(info["close"] - info["open"], 2)
        f.write(f"{date_formatted},{info['vol']},{info['amount']},{info['open']},{info['high']},{info['low']},{info['close']},{price_diff},{info['trades']}\n")


# ---- 主流程 ----

def main():
    import argparse
    parser = argparse.ArgumentParser(description="從公開資訊站取得收盤數據，寫入 @stockID.csv")
    parser.add_argument("--stocks", default=None, help="股票代碼逗號分隔 (預設: watchlist.json)")
    parser.add_argument("--no-tpex", action="store_true", help="跳過 TPEx")
    parser.add_argument("--compare-only", action="store_true", help="僅比對不寫入")
    parser.add_argument("--date", default=None, help="指定日期 YYYYMMDD (預設: 自動偵測)")
    args = parser.parse_args()

    stocks = args.stocks.split(",") if args.stocks else load_watchlist_stocks()
    print(f"目標股票: {stocks}")

    twse_data, twse_date = fetch_twse_daily()
    time.sleep(1)
    tpex_data, tpex_date = ({} if args.no_tpex else fetch_tpex_daily())

    # 決定寫入日期：優先使用 --date，否則使用 API 偵測到的日期
    if args.date:
        target_date = args.date
        print(f"使用指定日期: {target_date}")
    else:
        # 取 TWSE/TPEx 日期中較晚者（通常 TWSE 較快發布）
        dates = [d for d in [twse_date, tpex_date] if d]
        target_date = max(dates) if dates else datetime.now().strftime("%Y%m%d")
        today_str = datetime.now().strftime("%Y%m%d")
        if target_date != today_str:
            print(f"⚠ 官方數據最新日期={target_date}，非今日({today_str})。將寫入 {target_date} 的資料。")
        else:
            print(f"數據日期={target_date}（今日）")

    all_data = {**twse_data, **tpex_data}
    if not all_data:
        print("未取得任何資料，請稍後再試（當日數據約 15:00 後發布）")
        return

    if args.compare_only:
        print("--compare-only 模式：僅比對不寫入\n")
        print_comparison(stocks, target_date, all_data)
        return

    print(f"\n寫入 @stockID.csv 與 yesterday/ (日期={target_date}):")
    written = 0
    results = {}
    for sid in stocks:
        if sid in all_data:
            info = all_data[sid]
            write_daily_summary(sid, target_date, info)
            update_yesterday(sid, target_date, info)
            results[sid] = info
            written += 1
        else:
            print(f"  {sid}: 未找到，跳過")

    if results:
        update_stock_ref(results)

    print(f"\n完成: {written}/{len(stocks)} 筆")

    # 收盤比對
    print_comparison(stocks, target_date, all_data)


if __name__ == "__main__":
    main()
