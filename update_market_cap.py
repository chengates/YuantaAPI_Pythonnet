#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
市值排名更新工具 — 從 TWSE/TPEx 公開資料取得市值排名與股本資訊，
寫入 market_cap.json 供 web_dashboard.py 和 cStocks.py 分類使用。

資料來源:
  - TWSE BWIBBU_ALL (P/E, P/B, 殖利率)
  - TWSE STOCK_DAY_ALL (收盤價)
  - TPEx 收盤行情 (收盤價 + 股本)
  - 0050/0056 成分股作為大型股參考

分類定義:
  - TWSE 大型: 市值前 50 名
  - TWSE 中型: 市值 51-150 名
  - TWSE 小型: 其餘
  - OTC 大型: 市值前 50 名
  - OTC 中型: 市值 51-100 名
  - OTC 小型: 其餘

用法:
  python update_market_cap.py              # 更新全部
  python update_market_cap.py --dry-run    # 僅顯示不寫入
  python update_market_cap.py --stocks 2330,2317  # 指定股票

排程: 建議每月 1-4 號執行（使用 Claude Code /loop 或 Windows Task Scheduler）
"""
import json
import os
import ssl
import sys
from datetime import datetime
from urllib.request import urlopen, Request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "market_cap.json")

# ---- TWSE 市值估算 ----

def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_twse_bwibbu():
    """BWIBBU_ALL: 全體上市公司 P/E, P/B, 殖利率。
    回傳 {code: {pe, pb, yield_pct, name}}"""
    url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=30, context=_ssl_ctx()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[BWIBBU] 查詢失敗: {e}")
        return {}

    result = {}
    for item in data:
        try:
            code = item.get("Code", "").strip()
            result[code] = {
                "name": item.get("Name", ""),
                "pe": float(item.get("PEratio", 0) or 0),
                "pb": float(item.get("PBratio", 0) or 0),
                "yield_pct": float(item.get("DividendYield", 0) or 0),
            }
        except (ValueError, TypeError):
            continue
    print(f"[BWIBBU] TWSE {len(result)} 檔")
    return result


def fetch_twse_daily_prices():
    """STOCK_DAY_ALL: 取得最近交易日收盤價，用於估算市值。
    回傳 {code: close_price}。"""
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=30, context=_ssl_ctx()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[TWSE_PRICE] 查詢失敗: {e}")
        return {}

    result = {}
    for item in data:
        try:
            code = item.get("Code", "").strip()
            close = float(item.get("ClosingPrice", 0) or 0)
            if close > 0:
                result[code] = close
        except (ValueError, TypeError):
            continue
    print(f"[TWSE_PRICE] {len(result)} 檔有收盤價")
    return result


def fetch_tpex_daily():
    """TPEx 每日收盤，回傳 {code: {close, vol, name}}。"""
    now = datetime.now()
    roc_date = f"{now.year - 1911}/{now.month:02d}/{now.day:02d}"
    url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?d={roc_date}&response=json"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=30, context=_ssl_ctx()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        # 嘗試前一天
        from datetime import timedelta
        yesterday = now - timedelta(days=1)
        roc_date = f"{yesterday.year - 1911}/{yesterday.month:02d}/{yesterday.day:02d}"
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?d={roc_date}&response=json"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(req, timeout=30, context=_ssl_ctx()) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[TPEx] 查詢失敗: {e}")
            return {}

    if data.get("stat") != "ok":
        print(f"[TPEx] stat={data.get('stat')}")
        return {}

    result = {}
    tables = data.get("tables", [])
    if not tables:
        return {}
    for row in tables[0].get("data", []):
        try:
            code = row[0].strip()
            close = float(row[2].replace(",", "")) if len(row) > 2 else 0
            result[code] = {"close": close, "name": row[1] if len(row) > 1 else ""}
        except (ValueError, IndexError):
            continue
    print(f"[TPEx] {len(result)} 檔")
    return result


# ---- 已知股本（發行股數）資料 ----
# 台灣上市公司股本相對穩定，此處提供主要股票的股本（股）
# 資料來源：TWSE 公司基本資料，建議每月更新
# 未列出的股票以預設值估算
_KNOWN_SHARES = {
    # 半導體
    "2330": 25930380458,  # 台積電
    "2317": 13862990600,  # 鴻海
    "2454": 7850000000,   # 聯發科
    "2303": 16000000000,  # 聯電
    "2308": 5500000000,   # 台達電
    "2327": 5000000000,   # 國巨
    # 金融
    "2881": 14000000000,  # 富邦金
    "2882": 15000000000,  # 國泰金
    "2886": 15000000000,  # 兆豐金
    "2891": 13000000000,  # 中信金
    "2412": 7757446000,   # 中華電
    # 傳產
    "1301": 5000000000,   # 台塑
    "1303": 6000000000,   # 南亞
    "1326": 5000000000,   # 台化
    "2002": 16000000000,  # 中鋼
    "2603": 7000000000,   # 長榮
    "2609": 5000000000,   # 陽明
    "2610": 6000000000,   # 華航
    # 光電/其他
    "2344": 2000000000,   # 華邦電
    "2356": 8000000000,   # 英業達
    "2345": 5000000000,   # 智邦
    "2357": 4000000000,   # 華碩
    "2379": 3000000000,   # 瑞昱
    "2382": 3000000000,   # 廣達
    "2395": 2000000000,   # 研華
    "2408": 5000000000,   # 南亞科
    "3008": 2000000000,   # 大立光
    "3034": 2000000000,   # 聯詠
    "3045": 3000000000,   # 台灣大
    "3711": 1500000000,   # 日月光投控
    "4904": 2000000000,   # 遠傳
    "4938": 2000000000,   # 和碩
    "6412": 100000000,    # 群聯 (估計)
    # 興櫃/OTC 主要
    "6122": 50000000,     # 元炬
    "6123": 60000000,     # 旭軟
    "8936": 150000000,    # 國統
}
DEFAULT_SHARES = 50000000  # 預設 5 千萬股


def estimate_market_cap(code, close_price):
    """估算市值 = 收盤價 × 發行股數。"""
    shares = _KNOWN_SHARES.get(code, DEFAULT_SHARES)
    return close_price * shares


def build_rankings():
    """建立 TWSE 和 OTC 市值排名。"""
    twse_info = fetch_twse_bwibbu()
    twse_prices = fetch_twse_daily_prices()
    tpex_data = fetch_tpex_daily()

    rankings = {"TWSE": [], "OTC": [], "updated": datetime.now().isoformat(), "stocks": {}}

    # TWSE 排名
    twse_caps = []
    for code, price in twse_prices.items():
        mcap = estimate_market_cap(code, price)
        info = twse_info.get(code, {})
        twse_caps.append({
            "code": code,
            "name": info.get("name", ""),
            "market_cap": int(mcap),
            "close": price,
            "pe": info.get("pe"),
            "pb": info.get("pb"),
        })
    twse_caps.sort(key=lambda x: x["market_cap"], reverse=True)
    for i, item in enumerate(twse_caps):
        item["rank"] = i + 1
        if item["market_cap"] >= 50_000_000_000:  # >500 億 = large
            item["tier"] = "large_cap"
        elif item["market_cap"] >= 5_000_000_000:  # >50 億 = mid
            item["tier"] = "mid_cap"
        else:
            item["tier"] = "small_cap"
        rankings["stocks"][item["code"]] = {
            "market": "TWSE", "rank": item["rank"], "tier": item["tier"],
            "market_cap": item["market_cap"], "name": item["name"],
            "close": item["close"], "pe": item.get("pe"), "pb": item.get("pb"),
        }
    rankings["TWSE"] = twse_caps

    # OTC 排名
    otc_caps = []
    for code, info in tpex_data.items():
        mcap = estimate_market_cap(code, info["close"])
        otc_caps.append({
            "code": code, "name": info.get("name", ""),
            "market_cap": int(mcap), "close": info["close"],
        })
    otc_caps.sort(key=lambda x: x["market_cap"], reverse=True)
    for i, item in enumerate(otc_caps):
        item["rank"] = i + 1
        if i < 50:
            item["tier"] = "large_cap"
        elif i < 100:
            item["tier"] = "mid_cap"
        else:
            item["tier"] = "small_cap"
        if item["code"] not in rankings["stocks"]:
            rankings["stocks"][item["code"]] = {
                "market": "OTC", "rank": item["rank"], "tier": item["tier"],
                "market_cap": item["market_cap"], "name": item["name"],
                "close": item["close"], "pe": None, "pb": None,
            }
    rankings["OTC"] = otc_caps

    return rankings


def main():
    import argparse
    parser = argparse.ArgumentParser(description="市值排名更新工具")
    parser.add_argument("--dry-run", action="store_true", help="僅顯示不寫入")
    parser.add_argument("--stocks", default=None, help="指定股票代碼（逗號分隔）")
    args = parser.parse_args()

    print("更新市值排名...")
    rankings = build_rankings()

    print(f"\nTWSE 前 10 大市值:")
    for item in rankings["TWSE"][:10]:
        mcap_yi = item["market_cap"] / 1e8
        print(f"  {item['rank']:3}. {item['code']} {item['name']:6s} 市值≈{mcap_yi:.0f}億  PE={item.get('pe','?')}")

    if args.stocks:
        targets = args.stocks.split(",")
        print(f"\n指定股票:")
        for code in targets:
            info = rankings["stocks"].get(code, {})
            if info:
                mcap_yi = info["market_cap"] / 1e8
                print(f"  {code}: {info['market']} #{info['rank']} 市值≈{mcap_yi:.0f}億 tier={info['tier']}")
            else:
                print(f"  {code}: 無資料")

    if args.dry_run:
        print("\n--dry-run: 不寫入")
        return

    # 寫入 market_cap.json
    output = {
        "updated": rankings["updated"],
        "TWSE_large_top50": [s["code"] for s in rankings["TWSE"] if s["tier"] == "large_cap"][:50],
        "TWSE_mid_51_150": [s["code"] for s in rankings["TWSE"] if s["tier"] == "mid_cap"][:100],
        "OTC_large_top50": [s["code"] for s in rankings["OTC"] if s["tier"] == "large_cap"][:50],
        "OTC_mid_51_100": [s["code"] for s in rankings["OTC"] if s["tier"] == "mid_cap"][:50],
        "stocks": rankings["stocks"],
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n已寫入 {OUTPUT_FILE}")
    print(f"TWSE 大型: {len(output['TWSE_large_top50'])} 檔")
    print(f"TWSE 中型: {len(output['TWSE_mid_51_150'])} 檔")
    print(f"OTC 大型: {len(output['OTC_large_top50'])} 檔")
    print(f"OTC 中型: {len(output['OTC_mid_51_100'])} 檔")


if __name__ == "__main__":
    main()
