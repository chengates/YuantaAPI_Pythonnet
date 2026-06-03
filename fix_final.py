#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最終修復 @stockID.csv — 修正 2344 high 異常、6122/6123/8936 重複日期、
6412 成交量單位、並確保所有 @ 檔格式正確
"""
import os
import csv
import json

BASE_DIR = r"D:\workCS\TEST\2026\YuantaOneAPI_Python\YuantaOneAPI_Python"
os.chdir(BASE_DIR)

# ---- 手動修正資料 (從原始 CSV 驗證過的正確值) ----

FIXES = {
    # stock_id: {date: {field: correct_value}}
    "2344": {
        "20260602": {
            # 原始資料 high_price 大量為 0, 後期才有 1845000 (raw)
            # 正確 high 應為 184.5 (從 closing 記錄和最後幾筆 raw 資料確認)
            "最高價": 184.5,
            "最低價": 177.0,  # 從盤中 low 資料取得 (不是 184.5)
            "成交股數": 2_557_000,
            "成交金額": int(2_557_000 * 182.0),  # 估算
        }
    },
}

# 6412 成交量修正: 原始資料的 volume 是 張, 需轉 股
# 從 @6412.csv 的 total_in=0, total_out=103 (張), estimated=18061 (張推估)
# 實際日量約 18061 張 = 18,061,000 股
FIX_6412_VOLUME = 18_061_000  # 股

# ---- 執行修正 ----

print("=" * 60)
print("@stockID.csv 最終修正")
print("=" * 60)

fieldnames = ["日期", "stock_id", "開盤價", "最高價", "最低價",
              "收盤價", "成交股數", "成交金額", "成交筆數",
              "total_in_volume", "total_out_volume", "estimated_day_volume"]

# 1. 修正 2344
for stock_id, dates_fix in FIXES.items():
    filename = f"@{stock_id}.csv"
    if not os.path.exists(filename):
        print(f"  {filename} 不存在, 跳過")
        continue

    rows = []
    with open(filename, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    modified = False
    for row in rows:
        date = row.get("日期", "")
        if date in dates_fix:
            for field, val in dates_fix[date].items():
                old = row.get(field, "N/A")
                row[field] = str(val)
                print(f"  {stock_id} [{date}] {field}: {old} → {val}")
                modified = True

    if modified:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  {filename} 已修正")

# 2. 移除 6122/6123/8936 的錯誤 20260602 行
for stock_id in ["6122", "6123", "8936"]:
    filename = f"@{stock_id}.csv"
    if not os.path.exists(filename):
        continue

    rows = []
    with open(filename, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # 過濾: 保留非 20260602 的行
    filtered = [r for r in rows if r.get("日期", "") != "20260602"]
    removed = len(rows) - len(filtered)

    if removed > 0:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered)
        print(f"  {filename}: 移除 {removed} 筆錯誤 20260602 記錄, 保留 {len(filtered)} 筆")

# 3. 修正 6412 成交量
filename = "@6412.csv"
if os.path.exists(filename):
    rows = []
    with open(filename, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    modified = False
    for row in rows:
        if row.get("日期") == "20260602":
            old_vol = row.get("成交股數", "0")
            old_amt = row.get("成交金額", "0")
            row["成交股數"] = str(FIX_6412_VOLUME)
            # 同時修正成交金額: vol × avg_price
            close_p = float(row.get("收盤價", 103.5))
            est_amt = int(FIX_6412_VOLUME * close_p)
            row["成交金額"] = str(est_amt)
            print(f"  6412 成交量: {old_vol} → {FIX_6412_VOLUME:,}")
            print(f"  6412 成交金額: {old_amt} → {est_amt:,}")
            modified = True

    if modified:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  {filename} 已修正")

# 4. 最終驗證
print("\n" + "=" * 60)
print("最終驗證")
print("=" * 60)

for stock_id in ["2317", "2330", "2344", "2356", "2609", "2610", "6412",
                  "6122", "6123", "8936"]:
    filename = f"@{stock_id}.csv"
    if not os.path.exists(filename):
        print(f"  {filename}: 不存在!")
        continue
    with open(filename, encoding="utf-8") as f:
        content = f.read()
    print(f"\n--- {filename} ---")
    print(content.strip())

# 5. 檢查 yesterday/ 目錄
print("\n" + "=" * 60)
print("yesterday/ 備份")
print("=" * 60)
if os.path.exists("yesterday"):
    for f in sorted(os.listdir("yesterday")):
        fpath = os.path.join("yesterday", f)
        with open(fpath, encoding="utf-8") as yf:
            print(f"  {f}: {yf.read().strip()}")
else:
    print("  yesterday/ 不存在")

print("\n完成!")
