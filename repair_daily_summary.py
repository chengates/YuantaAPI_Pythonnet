#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修復 @stockID.csv 日總結檔 — 從 5 秒 CSV 重建昨日(6/2)盤後資料
修正: int32 溢位、格式不一致、缺少 yesterday/ 備份
使用 csv 模組逐行解析，避免 extra_data JSON 欄位逗號干擾
"""

import os
import csv
import json
from datetime import datetime
from collections import defaultdict

BASE_DIR = r"D:\workCS\TEST\2026\YuantaOneAPI_Python\YuantaOneAPI_Python"
os.chdir(BASE_DIR)

TARGET_DATE = "20260602"
STOCKS = ["2317", "2330", "2344", "2356", "2609", "2610", "6412",
          "6122", "6123", "8936"]

# ---- helpers ----

def norm_price(p):
    """正規化價格: API 原始值為 ×10000, 若 >100000 則除以 10000"""
    if p is None or p == '' or p == 'None':
        return 0.0
    try:
        p = float(p)
    except (ValueError, TypeError):
        return 0.0
    return round(p / 10000.0, 2) if abs(p) > 100000 else round(p, 2)

def safe_int(v):
    """安全轉整數, 處理 NaN / None / 溢位負值"""
    if v is None or v == '' or v == 'None':
        return 0
    try:
        v = int(float(str(v)))
    except (ValueError, TypeError):
        return 0
    if v < -2_000_000_000:  # int32 溢位
        return 0
    return max(v, 0)

def read_csv_rows(stock_id):
    """用 csv.DictReader 逐行讀取，回傳 list[dict]"""
    csv_path = os.path.join(BASE_DIR, f"{stock_id}.csv")
    if not os.path.exists(csv_path):
        return []
    rows = []
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 清理欄位名稱
            cleaned = {}
            for k, v in row.items():
                if k is None:
                    continue
                ck = k.strip().lstrip('﻿')
                cleaned[ck] = v.strip() if isinstance(v, str) else v
            rows.append(cleaned)
    return rows

def group_by_date(rows):
    """將 rows 按日期分組，回傳 {date_str: [rows]}"""
    groups = defaultdict(list)
    for row in rows:
        ts = row.get('timestamp', '')
        if len(ts) >= 8:
            date_str = ts[:8]
            groups[date_str].append(row)
    return dict(groups)

def compute_daily_summary(day_rows, actual_date):
    """從單日 rows 計算 OHLCV 日總結"""
    if not day_rows:
        return None

    # 分離 13:30+ 收盤記錄
    intraday = []
    closing = []
    for row in day_rows:
        ts = row.get('timestamp', '')
        if len(ts) >= 12:
            hour = int(ts[9:11]) if ts[9:11].isdigit() else 0
        else:
            hour = 0
        if hour >= 13:
            closing.append(row)
        else:
            intraday.append(row)

    # 若有 13:30 收盤記錄（trade_count == 1 表示日總結列）
    closing_summary = [r for r in closing if safe_int(r.get('trade_count', 0)) == 1]

    if closing_summary and intraday:
        cr = closing_summary[-1]
        # 從盤中資料取 OHLC
        opens = [norm_price(r.get('open_price')) for r in intraday if norm_price(r.get('open_price')) > 0]
        highs = [norm_price(r.get('high_price')) for r in intraday]
        lows = [norm_price(r.get('low_price')) for r in intraday if norm_price(r.get('low_price')) > 0]
        closes = [norm_price(r.get('close_price')) for r in intraday]

        open_p = opens[0] if opens else 0
        high_p = max(highs) if highs else 0
        low_p = min(lows) if lows else 0
        close_p = closes[-1] if closes else 0

        last_ii = intraday[-1]
        # 成交量：用最後一筆內外盤累積量，或加總所有區間 deal_volume
        total_in = safe_int(last_ii.get('total_in_volume', 0))
        total_out = safe_int(last_ii.get('total_out_volume', 0))
        if total_in or total_out:
            total_vol = total_in + total_out
        else:
            deals = [safe_int(r.get('deal_volume', 0)) for r in intraday]
            total_vol = sum(deals)
        total_amt_raw = safe_int(cr.get('deal_amount', 0))
        total_amt = int(total_amt_raw / 10000) if total_amt_raw > 1e10 else total_amt_raw
        est_vol = safe_int(last_ii.get('estimated_day_volume', 0))
        trades = safe_int(last_ii.get('trade_count', 0))

        # 轉換 張→股: 若日總量 < 100000 且最後盤中 trade_count > 100, 可能是 張
        if total_vol < 100000 and trades > 100:
            total_vol = total_vol * 1000
            total_in = total_in * 1000
            total_out = total_out * 1000

        return {
            'date': actual_date,
            'stock_id': str(safe_int(intraday[0].get('stock_id', '0'))),
            'open': open_p, 'high': high_p, 'low': low_p, 'close': close_p,
            'volume': total_vol, 'amount': total_amt, 'trades': trades,
            'total_in': total_in, 'total_out': total_out, 'est_vol': est_vol,
            'source': 'closing_record'
        }

    # 無 13:30 記錄：從盤中資料計算
    if not intraday:
        intraday = closing  # fallback

    if not intraday:
        return None

    # OHLC
    opens = [norm_price(r.get('open_price')) for r in intraday if norm_price(r.get('open_price')) > 0]
    highs = [norm_price(r.get('high_price')) for r in intraday]
    lows = [norm_price(r.get('low_price')) for r in intraday if norm_price(r.get('low_price')) > 0]
    closes = [norm_price(r.get('close_price')) for r in intraday]

    open_p = opens[0] if opens else 0
    high_p = max(highs) if highs else 0
    low_p = min(lows) if lows else 0
    close_p = closes[-1] if closes else 0

    # 成交量: 檢查 total_in/total_out 是否為累積值
    first_row = intraday[0]
    last_row = intraday[-1]

    total_in_first = safe_int(first_row.get('total_in_volume', 0))
    total_out_first = safe_int(first_row.get('total_out_volume', 0))
    total_in_last = safe_int(last_row.get('total_in_volume', 0))
    total_out_last = safe_int(last_row.get('total_out_volume', 0))

    # 判斷累積 vs per-tick: 若末筆 >> 首筆, 就是累積
    if total_in_last > total_in_first * 2 and total_out_last > total_out_first * 2:
        total_vol = total_in_last + total_out_last
    else:
        # per-tick: sum deal_volume (排除溢位值)
        deals = [safe_int(r.get('deal_volume', 0)) for r in intraday]
        total_vol = sum(deals)

    # 成交金額
    amts = [safe_int(r.get('deal_amount', 0)) for r in intraday]
    total_amt = sum(amts)
    if total_amt > 1e12:
        total_amt = int(total_amt / 10000)
    elif total_amt > 0 and total_vol > 0:
        implied_price = total_amt / total_vol
        if implied_price < 0.01:  # 金額太小
            total_amt = int(total_vol * close_p)
        elif implied_price > 100000:  # 原始單位
            total_amt = int(total_amt / 10000)

    trades = safe_int(last_row.get('trade_count', 0))
    est_vol = safe_int(last_row.get('estimated_day_volume', 0))

    # 單位轉換 張→股: 若為 6/2 資料且量 < 1000000
    is_target_date = (actual_date == TARGET_DATE)
    if is_target_date and total_vol < 1_000_000:
        total_vol = total_vol * 1000
        total_in_last = total_in_last * 1000
        total_out_last = total_out_last * 1000

    return {
        'date': actual_date,
        'stock_id': str(safe_int(first_row.get('stock_id', '0'))),
        'open': open_p, 'high': high_p, 'low': low_p, 'close': close_p,
        'volume': total_vol, 'amount': total_amt, 'trades': trades,
        'total_in': total_in_last, 'total_out': total_out_last, 'est_vol': est_vol,
        'source': 'intraday_computed'
    }

# ---- main ----

print("=" * 60)
print(f"修復 @stockID.csv — 目標日期: {TARGET_DATE}")
print(f"執行時間: {datetime.now()}")
print("=" * 60)

results = {}
skipped = []

for stock_id in STOCKS:
    print(f"\n--- {stock_id} ---")
    rows = read_csv_rows(stock_id)
    if not rows:
        print(f"  [SKIP] CSV 不存在或為空")
        skipped.append(stock_id)
        continue

    groups = group_by_date(rows)
    print(f"  可用日期: {sorted(groups.keys())}")

    if TARGET_DATE in groups:
        day_rows = groups[TARGET_DATE]
        actual_date = TARGET_DATE
        print(f"  {len(day_rows)} 筆 {TARGET_DATE} 資料")
    else:
        # 使用最後可用日期
        last_date = sorted(groups.keys())[-1]
        day_rows = groups[last_date]
        actual_date = last_date
        print(f"  [WARN] 無 {TARGET_DATE} 資料, 使用最後可用: {actual_date} ({len(day_rows)} 筆)")

    summary = compute_daily_summary(day_rows, actual_date)
    if summary is None:
        print(f"  [SKIP] 無法計算日總結")
        skipped.append(stock_id)
        continue

    results[stock_id] = summary
    print(f"  開:{summary['open']} 高:{summary['high']} 低:{summary['low']} 收:{summary['close']}")
    print(f"  量:{summary['volume']:,} 額:{summary['amount']:,} 筆:{summary['trades']}")
    print(f"  來源: {summary['source']} 日期: {summary['date']}")

# ---- 寫入 @stockID.csv (新格式, 中文欄位, cStock.load_data() 相容) ----
print("\n" + "=" * 60)
print("寫入 @stockID.csv 與 yesterday/ 備份")
print("=" * 60)

fieldnames = ["日期", "stock_id", "開盤價", "最高價", "最低價",
              "收盤價", "成交股數", "成交金額", "成交筆數",
              "total_in_volume", "total_out_volume", "estimated_day_volume"]

for stock_id, s in results.items():
    filename = f"@{stock_id}.csv"

    # 若已有舊格式 @ 檔，先重建為新格式
    existing_rows = []
    need_rebuild = False
    if os.path.exists(filename):
        try:
            with open(filename, encoding="utf-8", errors="replace") as f:
                content = f.read()
                # 檢查是否為舊格式（英文欄位名）
                if 'open_price' in content[:200] or 'total_volume' in content[:200]:
                    need_rebuild = True
                else:
                    # 新格式: 檢查日期是否已存在
                    f.seek(0)
                    for row in csv.DictReader(f):
                        existing_rows.append(row)
        except Exception:
            need_rebuild = True

    date_key = s['date']

    if not need_rebuild:
        # 檢查是否已有同日記錄
        existing_dates = {r.get('日期', r.get('date', '')) for r in existing_rows}
        if date_key in existing_dates:
            print(f"  @{stock_id}.csv: 日期 {date_key} 已存在, 跳過")
            continue

    # 寫入 (append for new format, overwrite for old format rebuild)
    mode = "w" if need_rebuild else "a"
    try:
        with open(filename, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            # 若為 rebuild, 先寫入既有記錄（轉換格式）
            if need_rebuild and existing_rows:
                for old_row in existing_rows:
                    d = old_row.get('日期', old_row.get('date', ''))
                    if d == date_key:
                        continue  # 跳過同日，會寫入新值
                    # 轉換舊格式 → 新格式
                    new_row = {
                        '日期': d,
                        'stock_id': old_row.get('stock_id', ''),
                        '開盤價': norm_price(old_row.get('open_price', old_row.get('開盤價', 0))),
                        '最高價': norm_price(old_row.get('high_price', old_row.get('最高價', 0))),
                        '最低價': norm_price(old_row.get('low_price', old_row.get('最低價', 0))),
                        '收盤價': norm_price(old_row.get('close_price', old_row.get('收盤價', 0))),
                        '成交股數': safe_int(old_row.get('total_volume', old_row.get('成交股數', 0))),
                        '成交金額': 0,
                        '成交筆數': safe_int(old_row.get('trade_count', old_row.get('成交筆數', 0))),
                        'total_in_volume': safe_int(old_row.get('total_in_volume', 0)),
                        'total_out_volume': safe_int(old_row.get('total_out_volume', 0)),
                        'estimated_day_volume': safe_int(old_row.get('estimated_day_volume', 0)),
                    }
                    writer.writerow(new_row)
            # 寫入新日總結
            writer.writerow({
                "日期": date_key,
                "stock_id": stock_id,
                "開盤價": s['open'],
                "最高價": s['high'],
                "最低價": s['low'],
                "收盤價": s['close'],
                "成交股數": s['volume'],
                "成交金額": s['amount'],
                "成交筆數": s['trades'],
                "total_in_volume": s['total_in'],
                "total_out_volume": s['total_out'],
                "estimated_day_volume": s['est_vol'],
            })
        action = "重建+寫入" if need_rebuild else "追加"
        print(f"  @{stock_id}.csv: {action} (date={date_key}, vol={s['volume']:,})")
    except Exception as e:
        print(f"  @{stock_id}.csv: 寫入失敗 - {e}")

    # yesterday/ 備份
    os.makedirs("yesterday", exist_ok=True)
    ypath = os.path.join("yesterday", f"{stock_id}.csv")
    price_diff = round(s['close'] - s['open'], 2)
    try:
        with open(ypath, "w", newline="", encoding="utf-8") as yf:
            yf.write("日期,成交股數,成交金額,開盤價,最高價,最低價,收盤價,漲跌價差,成交筆數\n")
            yf.write(f"{date_key},{s['volume']},{s['amount']},{s['open']},{s['high']},{s['low']},{s['close']},{price_diff},{s['trades']}\n")
        print(f"  yesterday/{stock_id}.csv: 已建立")
    except Exception as e:
        print(f"  yesterday/{stock_id}.csv: 寫入失敗 - {e}")

# ---- 更新 stock_ref.json ----
print("\n" + "=" * 60)
print("更新 stock_ref.json")
print("=" * 60)

try:
    if os.path.exists("stock_ref.json"):
        with open("stock_ref.json", encoding="utf-8") as f:
            ref = json.load(f)
    else:
        ref = {}

    for stock_id, s in results.items():
        if stock_id not in ref:
            ref[stock_id] = {}
        ref[stock_id]['yst_price'] = int(s['close'] * 10000)  # 回存原始格式
        ref[stock_id]['yst_vol'] = s['volume']
        print(f"  stock_ref[{stock_id}]: yst_price={int(s['close']*10000)}, yst_vol={s['volume']}")

    with open("stock_ref.json", "w", encoding="utf-8") as f:
        json.dump(ref, f, ensure_ascii=False, indent=2)
    print("  stock_ref.json 已更新")
except Exception as e:
    print(f"  stock_ref.json 更新失敗: {e}")

# ---- 總結 ----
print("\n" + "=" * 60)
print("修復完成")
print("=" * 60)
print(f"成功: {list(results.keys())}")
if skipped:
    print(f"跳過: {skipped}")
print(f"\n驗證命令:")
for stock_id in results:
    print(f"  type @{stock_id}.csv")
print(f"  dir yesterday")
