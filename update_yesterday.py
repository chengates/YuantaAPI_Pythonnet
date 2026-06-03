#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""更新 yesterday/ 備份檔案"""
import os

BASE_DIR = r"D:\workCS\TEST\2026\YuantaOneAPI_Python\YuantaOneAPI_Python"
os.chdir(BASE_DIR)

data = {
    '2317': {'vol': 2554000, 'open': 297.0, 'high': 302.0, 'low': 294.0, 'close': 298.0, 'trades': 964},
    '2330': {'vol': 5150000, 'open': 2382.5, 'high': 2400.0, 'low': 2370.0, 'close': 2385.0, 'trades': 279},
    '2344': {'vol': 2557000, 'open': 181.25, 'high': 184.5, 'low': 177.0, 'close': 184.5, 'trades': 346},
    '2356': {'vol': 3532000, 'open': 78.0, 'high': 83.5, 'low': 77.9, 'close': 79.5, 'trades': 1397},
}

for sid, d in data.items():
    amt = int(d['vol'] * d['close'])
    diff = round(d['close'] - d['open'], 2)
    path = os.path.join("yesterday", f"{sid}.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("日期,成交股數,成交金額,開盤價,最高價,最低價,收盤價,漲跌價差,成交筆數\n")
        f.write(f"20260602,{d['vol']},{amt},{d['open']},{d['high']},{d['low']},{d['close']},{diff},{d['trades']}\n")
    print(f"  yesterday/{sid}.csv 已更新")

print("完成")
