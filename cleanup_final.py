#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清理 @stockID.csv — 移除重複 header、修正 yesterday/ 備份
"""
import os
import csv

BASE_DIR = r"D:\workCS\TEST\2026\YuantaOneAPI_Python\YuantaOneAPI_Python"
os.chdir(BASE_DIR)

FIELDNAMES = ["日期", "stock_id", "開盤價", "最高價", "最低價",
              "收盤價", "成交股數", "成交金額", "成交筆數",
              "total_in_volume", "total_out_volume", "estimated_day_volume"]

# ---- 1. 重建 6122/6123/8936 ----
# 這些檔案 v1+v2 造成雙 header (英文+中文), 需完全重建

REBUILD_DATA = {
    "6122": [{
        "日期": "20260528",
        "stock_id": "6122",
        "開盤價": "46.83",
        "最高價": "46.87",
        "最低價": "46.77",
        "收盤價": "46.83",
        "成交股數": "6124077",
        "成交金額": "286780010",
        "成交筆數": "515",
        "total_in_volume": "219528",
        "total_out_volume": "208743",
        "estimated_day_volume": "12848130",
    }],
    "6123": [{
        "日期": "20260528",
        "stock_id": "6123",
        "開盤價": "43.06",
        "最高價": "43.08",
        "最低價": "42.99",
        "收盤價": "43.08",
        "成交股數": "5201046",
        "成交金額": "223881443",
        "成交筆數": "111",
        "total_in_volume": "50836",
        "total_out_volume": "36329",
        "estimated_day_volume": "2614950",
    }],
    "8936": [{
        "日期": "20260528",
        "stock_id": "8936",
        "開盤價": "50.01",
        "最高價": "50.08",
        "最低價": "50.0",
        "收盤價": "50.05",
        "成交股數": "5032791",
        "成交金額": "251845459",
        "成交筆數": "462",
        "total_in_volume": "117346",
        "total_out_volume": "113804",
        "estimated_day_volume": "6934500",
    }],
}

for stock_id, rows in REBUILD_DATA.items():
    filename = f"@{stock_id}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  @{stock_id}.csv: 完全重建 ({len(rows)} 筆)")

# ---- 2. 修正 yesterday/2344.csv (high=50000 → 184.5) ----
ypath = "yesterday/2344.csv"
if os.path.exists(ypath):
    lines = []
    with open(ypath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("20260602,2344,") or line.startswith("20260602,"):
                parts = line.split(",")
                # 格式: 日期,成交股數,成交金額,開盤價,最高價,最低價,收盤價,漲跌價差,成交筆數
                if len(parts) >= 8:
                    parts[4] = "184.5"  # 最高價
                    parts[5] = "177.0"  # 最低價
                    parts[6] = "184.5"  # 收盤價
                    parts[7] = "3.25"   # 漲跌價差
                    line = ",".join(parts)
            lines.append(line)
    with open(ypath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  yesterday/2344.csv: 已修正 high/low/close")

# ---- 3. 修正 yesterday/6412.csv (成交量單位) ----
ypath = "yesterday/6412.csv"
if os.path.exists(ypath):
    lines = []
    with open(ypath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("20260602,"):
                parts = line.split(",")
                if len(parts) >= 8:
                    parts[1] = "18061000"     # 成交股數
                    parts[2] = "1869313500"   # 成交金額
                    parts[7] = "-3.25"        # 漲跌價差
                    line = ",".join(parts)
            lines.append(line)
    with open(ypath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  yesterday/6412.csv: 已修正成交量")

# ---- 最終驗證 ----
print("\n=== 最終 @stockID.csv 驗證 ===")
for stock_id in ["2317", "2330", "2344", "2356", "2609", "2610", "6412",
                  "6122", "6123", "8936"]:
    filename = f"@{stock_id}.csv"
    with open(filename, encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    headers = sum(1 for l in lines if l.startswith("日期") or l.startswith("date"))
    data_rows = sum(1 for l in lines if l[0].isdigit())
    issues = []
    if headers > 1:
        issues.append(f"多重 header ({headers})")
    for l in lines:
        if '50000' in l:
            issues.append("含 50000 異常值")
        if l.startswith("20260602") and stock_id in ["6122", "6123", "8936"]:
            issues.append("錯誤的 20260602 日期")
    status = "OK" if not issues else ", ".join(issues)
    print(f"  @{stock_id}.csv: {data_rows} 筆資料, {headers} header → {status}")

print("\n=== yesterday/ 驗證 ===")
for f in sorted(os.listdir("yesterday")):
    fpath = os.path.join("yesterday", f)
    with open(fpath, encoding="utf-8") as yf:
        content = yf.read().strip()
    issues = []
    if "50000" in content:
        issues.append("含 50000 異常值")
    status = "OK" if not issues else ", ".join(issues)
    print(f"  {f}: {status}")

print("\n完成!")
