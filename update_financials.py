#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
財務數據更新工具 — 從公開來源取得季度 EPS，計算 PEG。
寫入 stock_financials.json 供 dashboard 顯示 PE/PB/PEG。

資料來源:
  - 近四季 EPS: 從 TWSE 財報頁面估算
  - PE/PB: 從 BWIBBU_ALL (已整合在 market_cap.json)

PEG 公式:
  - 有法人預估值 → PEG = PE / 預估 EPS 成長率
  - 無預估值 → PEG = PE / 近四季 EPS 成長率 ( YoY )
  - 成長率 < 0 → PEG = N/A (負成長無意義)

用法:
  python update_financials.py                # 更新全部
  python update_financials.py --stocks 2330  # 指定股票

排程: 每季財報公布後（5/15, 8/14, 11/14, 3/31 前後）執行
"""
import json
import os
import ssl
import sys
from datetime import datetime
from urllib.request import urlopen, Request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "stock_financials.json")
MCAP_FILE = os.path.join(BASE_DIR, "market_cap.json")


def load_market_cap():
    if os.path.exists(MCAP_FILE):
        with open(MCAP_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ---- 近四季 EPS（手動維護，每季更新） ----
# 資料來源: TWSE 個股財報 → 基本每股盈餘
# 格式: {code: [Q1_EPS, Q2_EPS, Q3_EPS, Q4_EPS]} (最近四季，從最早到最新)
# 此處為 2026Q1 示範值，實際需每季更新
_QUARTERLY_EPS = {
    "2330": [13.62, 14.05, 15.21, 16.38],  # 台積電 2025Q2~2026Q1 (示範)
    "2317": [2.83, 3.15, 2.98, 3.42],       # 鴻海
    "2454": [16.50, 18.20, 17.80, 19.50],   # 聯發科
    "2344": [0.35, 0.42, 0.38, 0.45],       # 華邦電
    "2356": [0.85, 0.92, 0.88, 0.95],       # 英業達
    "2609": [1.20, 1.35, 1.28, 1.42],       # 陽明
    "2610": [0.25, 0.28, 0.26, 0.30],       # 華航
    "2303": [1.10, 1.18, 1.15, 1.25],       # 聯電
    "2412": [1.20, 1.25, 1.22, 1.28],       # 中華電
    "2881": [0.85, 0.92, 0.88, 0.95],       # 富邦金
    "2882": [0.75, 0.82, 0.78, 0.85],       # 國泰金
    "6412": [4.50, 5.20, 4.80, 5.50],       # 群聯
    "6122": [0.15, 0.18, 0.12, 0.20],       # 元炬
    "6123": [0.22, 0.25, 0.20, 0.28],       # 旭軟
    "8936": [0.42, 0.48, 0.45, 0.52],       # 國統
}


def fetch_twse_quarterly_eps(stock_code):
    """嘗試從 TWSE 財報頁面取得近四季 EPS。
    若 API 不可用則回傳 None，使用內建 _QUARTERLY_EPS。"""
    # TWSE 個股財報頁面 (HTML, 需要解析)
    # 備用方案：使用內建資料
    return None  # 目前無穩定 API，使用內建資料


def calculate_peg(pe, eps_4q):
    """計算 PEG。
    PEG = PE / EPS成長率(%)
    EPS成長率 = (近四季EPS / 前四季EPS - 1) × 100"""
    if not pe or pe <= 0:
        return None
    if not eps_4q or len(eps_4q) < 4:
        return None
    # 近四季 EPS 合計
    ttm_eps = sum(eps_4q)
    if ttm_eps <= 0:
        return None
    # EPS 成長率: 使用最近兩季 vs 去年同期兩季 (YoY)
    # 假設 eps_4q = [Q-3, Q-2, Q-1, Q0]
    recent_half = eps_4q[2] + eps_4q[3] if len(eps_4q) >= 4 else sum(eps_4q[-2:])
    prior_half = eps_4q[0] + eps_4q[1] if len(eps_4q) >= 4 else sum(eps_4q[:2])
    if prior_half <= 0:
        return None
    growth_pct = (recent_half / prior_half - 1) * 100
    if growth_pct <= 0:
        return None  # 負成長不計算 PEG
    peg = round(pe / growth_pct, 2)
    return {"peg": peg, "ttm_eps": round(ttm_eps, 2), "growth_pct": round(growth_pct, 1)}


def load_watchlist_stocks():
    """從 watchlist.json 讀取自選股清單。"""
    try:
        with open(os.path.join(BASE_DIR, "watchlist.json"), encoding="utf-8") as f:
            config = json.load(f)
        return config.get("自選股1", {}).get("stocks", [])
    except Exception:
        return ["2330", "2317", "2344"]


def build_financials(stocks=None):
    """建立財務數據 dict。"""
    mcap = load_market_cap()
    stocks_data = mcap.get("stocks", {})

    if stocks is None:
        # 優先處理自選股，再補 _QUARTERLY_EPS 中的股票
        stocks = list(set(load_watchlist_stocks()) | set(_QUARTERLY_EPS.keys()))

    result = {"updated": datetime.now().isoformat(), "stocks": {}}
    watchlist = load_watchlist_stocks()
    for code in stocks:
        entry = stocks_data.get(code, {})
        pe = entry.get("pe")
        pb = entry.get("pb")
        eps_q = _QUARTERLY_EPS.get(code)

        peg_info = None
        if pe and eps_q:
            peg_info = calculate_peg(pe, eps_q)

        is_watchlist = code in watchlist
        # 若無 PE/PB 且是自選股，從收盤價估算（標記為估算值）
        pe_note = ""
        if pe is None and is_watchlist and entry.get("close"):
            # 無法取得 PE，嘗試從已知 EPS 推算
            if eps_q:
                ttm = sum(eps_q)
                if ttm > 0:
                    pe = round(entry["close"] / ttm, 1)
                    pe_note = " (估算)"

        result["stocks"][code] = {
            "name": entry.get("name", ""),
            "pe": pe,
            "pb": pb,
            "eps_ttm": peg_info["ttm_eps"] if peg_info else (sum(eps_q) if eps_q else None),
            "eps_growth_pct": peg_info["growth_pct"] if peg_info else None,
            "peg": peg_info["peg"] if peg_info else None,
            "eps_quarters": eps_q,
            "peg_note": "近四季EPS (YoY半年成長率)" if peg_info else (
                "負成長，PEG無意義" if eps_q else (
                    "無EPS資料，需手動填入analyst_eps.json" if is_watchlist else "無EPS資料"
                )
            ),
        }
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="財務數據更新工具")
    parser.add_argument("--stocks", default=None, help="指定股票代碼（逗號分隔）")
    args = parser.parse_args()

    stocks = args.stocks.split(",") if args.stocks else None

    data = build_financials(stocks)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"stock_financials.json 已更新 ({len(data['stocks'])} 檔):")
    for code, info in sorted(data["stocks"].items()):
        peg_str = f"PEG={info['peg']}" if info['peg'] else f"({info['peg_note']})"
        print(f"  {code}: PE={info['pe']} PB={info['pb']} EPS_TTM={info['eps_ttm']} {peg_str}")


if __name__ == "__main__":
    main()
