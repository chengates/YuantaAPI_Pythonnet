#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
法人預估 EPS 聚合器 — 多來源收集 + 去除極端值 + 每日動態更新 PEG。

核心邏輯:
  1. 從多個免費來源收集法人預估 EPS
  2. 去除極端值（Trimmed Mean: 去掉最高/最低 20%）
  3. 計算共識 EPS → PEG = PE / EPS_Growth
  4. 寫入 analyst_eps.json → 供 dashboard 即時顯示

資料來源（優先序）:
  A. Yahoo Finance TW (網頁爬取分析師預估)
  B. Google Finance (網頁爬取)
  C. 使用者手動輸入（analyst_eps.json 直接編輯）
  D. 內建近四季 EPS 備援（update_financials.py）

用法:
  python fetch_analyst_eps.py                    # 更新全部自選股
  python fetch_analyst_eps.py --stocks 2330,2317 # 指定股票
  python fetch_analyst_eps.py --source manual    # 僅使用手動輸入值
  python fetch_analyst_eps.py --dry-run          # 預覽不寫入

排程: 每日收盤後執行（run.py 自動觸發）
"""
import json
import os
import re
import ssl
import sys
from datetime import datetime
from statistics import median
from urllib.request import urlopen, Request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "analyst_eps.json")
MCAP_FILE = os.path.join(BASE_DIR, "market_cap.json")


def load_watchlist_stocks():
    try:
        with open(os.path.join(BASE_DIR, "watchlist.json"), encoding="utf-8") as f:
            config = json.load(f)
        return config.get("自選股1", {}).get("stocks", [])
    except Exception:
        return ["2330", "2317", "2344"]


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ---- 來源 A: Yahoo Finance TW ----

def fetch_yahoo_analyst_eps(stock_code):
    """從 Yahoo Finance TW 股票頁面爬取分析師 EPS 預估。
    台灣股票代碼: {code}.TW (上市) 或 {code}.TWO (上櫃)"""
    suffix = ".TW" if stock_code[0] != "8" else ".TWO"
    url = f"https://tw.stock.yahoo.com/quote/{stock_code}{suffix}/analysis"
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    estimates = []
    try:
        with urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return estimates

    # 從頁面擷取 EPS 相關數字
    # Yahoo TW 分析頁面可能包含分析師目標價和 EPS
    patterns = [
        r'每股盈餘[^0-9]*?(\d+\.?\d*)',  # 每股盈餘 12.34
        r'EPS[^0-9]*?(\d+\.?\d*)',       # EPS: 12.34
        r'預估.*?(\d+\.?\d+)',            # 預估 12.34
        r'本益比[^0-9]*?(\d+\.?\d*)',    # 本益比推算
    ]
    for pat in patterns:
        matches = re.findall(pat, html, re.IGNORECASE)
        for m in matches:
            try:
                val = float(m)
                if 0.1 < val < 10000:  # 合理 EPS 範圍
                    estimates.append(val)
            except ValueError:
                pass
    return estimates


# ---- 來源 B: Google Finance ----

def fetch_google_finance_eps(stock_code):
    """從 Google Finance 搜尋分析師 EPS 預估。"""
    suffix = "TWSE" if stock_code[0] != "8" else "TPEX"
    url = f"https://www.google.com/finance/quote/{stock_code}:{suffix}"
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    estimates = []
    try:
        with urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return estimates
    # 擷取數字（Google Finance 顯示分析師數據）
    pats = [r'(\d+\.?\d*)\s*EPS', r'EPS\s*[:\-]?\s*(\d+\.?\d*)']
    for pat in pats:
        for m in re.findall(pat, html, re.IGNORECASE):
            try:
                val = float(m)
                if 0.1 < val < 10000:
                    estimates.append(val)
            except ValueError:
                pass
    return estimates


# ---- 來源 D: 近四季 EPS 降級 (stock_financials.json) ----

def get_trailing_eps(stock_code):
    """從 stock_financials.json 取得近四季合計 EPS 作為降級備援。"""
    path = os.path.join(BASE_DIR, "stock_financials.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            s = data.get("stocks", {}).get(stock_code, {})
            eps_q = s.get("eps_quarters", [])
            return sum(eps_q) if eps_q else None
        except Exception:
            pass
    return None


# ---- 核心: 極端值處理 + 共識計算 ----

def trimmed_mean(values, trim_pct=0.20):
    """去除最高/最低 trim_pct% 後取平均。
    例: trim_pct=0.20 → 去掉最高 20% 和最低 20%，取中間 60% 平均。
    若資料不足 5 筆則用中位數。"""
    if not values:
        return None
    n = len(values)
    if n < 5:
        return median(values)
    sorted_vals = sorted(values)
    trim_n = max(1, int(n * trim_pct))
    trimmed = sorted_vals[trim_n:n - trim_n]
    if not trimmed:
        return median(values)
    return round(sum(trimmed) / len(trimmed), 2)


def aggregate_analyst_eps(stock_code):
    """聚合法人預估 EPS：
    1. 從多來源收集 EPS 預估值
    2. 去除極端值（trimmed mean 20%）
    3. 回傳共識 EPS
    """
    all_estimates = []

    # A. Yahoo Finance TW
    yahoo = fetch_yahoo_analyst_eps(stock_code)
    if yahoo:
        all_estimates.extend(yahoo)

    # B. Google Finance
    google = fetch_google_finance_eps(stock_code)
    if google:
        all_estimates.extend(google)

    # 去重
    all_estimates = list(set(round(v, 2) for v in all_estimates))

    # Trimmed mean
    consensus = trimmed_mean(all_estimates) if all_estimates else None

    return {
        "sources": {"yahoo": yahoo, "google": google},
        "all_estimates": sorted(all_estimates),
        "count": len(all_estimates),
        "consensus_eps": consensus,
        "method": "trimmed_mean_20pct" if len(all_estimates) >= 5 else "median",
    }


def calculate_peg_dynamic(stock_code, consensus_eps, close_price):
    """動態計算 PEG。
    PEG = PE / EPS_Growth
      PE = close_price / consensus_eps
      EPS_Growth = (consensus_eps / trailing_eps - 1) × 100
    若無共識 EPS 則降級使用近四季 EPS。"""
    if not consensus_eps or consensus_eps <= 0:
        return None

    # 目前 PE（根據收盤價和共識 EPS）
    forward_pe = round(close_price / consensus_eps, 2) if close_price else None

    # EPS 成長率: 共識 vs 近四季
    trailing_eps = get_trailing_eps(stock_code)
    eps_growth = None
    if trailing_eps and trailing_eps > 0:
        eps_growth = round((consensus_eps / trailing_eps - 1) * 100, 1)

    # PEG
    peg = None
    if forward_pe and eps_growth and eps_growth > 0:
        peg = round(forward_pe / eps_growth, 2)
    elif forward_pe and eps_growth is not None and eps_growth <= 0:
        peg = None  # 負成長，PEG 無意義

    return {
        "forward_eps": consensus_eps,
        "trailing_eps": trailing_eps,
        "forward_pe": forward_pe,
        "eps_growth_pct": eps_growth,
        "peg": peg,
    }


# ---- 主流程 ----

def fetch_all(stocks=None, dry_run=False):
    """更新所有自選股的分析師 EPS 預估。"""
    if stocks is None:
        stocks = load_watchlist_stocks()

    # 載入現有資料和市值資料
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)

    mcap = {}
    if os.path.exists(MCAP_FILE):
        with open(MCAP_FILE, encoding="utf-8") as f:
            mcap = json.load(f).get("stocks", {})

    result = {"updated": datetime.now().isoformat(), "stocks": {}}

    for code in stocks:
        print(f"[{code}] 收集分析師預估...")

        # 聚合共識 EPS
        aggregate = aggregate_analyst_eps(code)
        consensus = aggregate["consensus_eps"]

        # 若無爬取結果，使用手動輸入值或近四季 EPS
        if consensus is None:
            manual = existing.get("stocks", {}).get(code, {}).get("manual_eps")
            if manual:
                consensus = manual
                aggregate["method"] = "manual_override"
            else:
                # 降級到近四季 EPS
                trailing = get_trailing_eps(code)
                if trailing:
                    consensus = trailing
                    aggregate["method"] = "trailing_4q_fallback"

        # PEG 計算
        close = mcap.get(code, {}).get("close")
        peg_info = calculate_peg_dynamic(code, consensus, close) if consensus else None

        # 輸出摘要
        if peg_info:
            print(f"  → 共識EPS={consensus}, PE(fwd)={peg_info['forward_pe']}, "
                  f"成長={peg_info.get('eps_growth_pct','?')}%, PEG={peg_info.get('peg','--')} "
                  f"[{aggregate['method']}]")
        else:
            print(f"  → 共識EPS={consensus} [{aggregate['method']}] (PEG: 資料不足)")

        result["stocks"][code] = {
            "name": mcap.get(code, {}).get("name", ""),
            "consensus_eps": consensus,
            "method": aggregate["method"],
            "all_estimates": aggregate["all_estimates"],
            "source_count": aggregate["count"],
            "peg": peg_info,
            "manual_eps": existing.get("stocks", {}).get(code, {}).get("manual_eps"),
        }

    if not dry_run:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n已寫入 {OUTPUT_FILE} ({len(result['stocks'])} 檔)")

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="法人預估 EPS 聚合器")
    parser.add_argument("--stocks", default=None, help="股票代碼（逗號分隔）")
    parser.add_argument("--dry-run", action="store_true", help="預覽不寫入")
    args = parser.parse_args()

    stocks = args.stocks.split(",") if args.stocks else None
    fetch_all(stocks, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
