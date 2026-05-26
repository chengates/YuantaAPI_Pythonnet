"""股名對照表更新工具 — 從 TWSE/TPEx 公開資料抓取股票代號與名稱，更新 stock_names.json。
Usage: python update_stock_names.py
"""
import json
import re
import os
import requests

STOCK_NAMES_PATH = "stock_names.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch_twse_stocks() -> dict:
    """從 TWSE ISIN 頁面解析上市股票代號與名稱。"""
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    print(f"fetching TWSE: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.encoding = "big5"
    html = resp.text

    stocks = {}
    for m in re.finditer(r"<td[^>]*>(\d{4})[　\s]+(\S+)</td>", html):
        code, name = m.group(1), m.group(2)
        if not name.isdigit():
            stocks[code] = name
    return stocks


def fetch_tpex_stocks() -> dict:
    """從 TPEx ISIN 頁面解析上櫃股票代號與名稱。"""
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"
    print(f"fetching TPEx: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.encoding = "big5"
    html = resp.text

    stocks = {}
    for m in re.finditer(r"<td[^>]*>(\d{4})[　\s]+(\S+)</td>", html):
        code, name = m.group(1), m.group(2)
        if not name.isdigit():
            stocks[code] = name
    return stocks


def merge_names(existing: dict, new_stocks: dict) -> dict:
    """合併：保留既有名稱，補入新名稱。"""
    merged = dict(existing)
    added = 0
    for code, name in new_stocks.items():
        if code not in merged:
            merged[code] = name
            added += 1
    return merged, added


def main():
    existing = {}
    if os.path.exists(STOCK_NAMES_PATH):
        with open(STOCK_NAMES_PATH, encoding="utf-8") as f:
            existing = json.load(f)
    print(f"existing stock_names.json: {len(existing)} entries")

    all_stocks = {}
    try:
        twse = fetch_twse_stocks()
        print(f"TWSE listed: {len(twse)} entries")
        all_stocks.update(twse)
    except Exception as e:
        print(f"TWSE fetch failed: {e}")

    try:
        tpex = fetch_tpex_stocks()
        print(f"TPEx OTC: {len(tpex)} entries")
        all_stocks.update(tpex)
    except Exception as e:
        print(f"TPEx fetch failed: {e}")

    if not all_stocks:
        print("no stock name data retrieved, aborting.")
        return

    merged, added = merge_names(existing, all_stocks)
    with open(STOCK_NAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"updated stock_names.json: added {added}, total {len(merged)} entries")

    # 顯示自選股對照結果
    watchlist_path = "watchlist.json"
    if os.path.exists(watchlist_path):
        with open(watchlist_path, encoding="utf-8") as f:
            wl = json.load(f)
        stocks = set()
        for v in wl.values():
            if isinstance(v, dict):
                stocks.update(v.get("stocks", []))
        print("\n自選股名稱對照:")
        for sid in sorted(stocks):
            name = merged.get(sid, "** 未找到 **")
            print(f"  {sid} → {name}")


if __name__ == "__main__":
    main()
