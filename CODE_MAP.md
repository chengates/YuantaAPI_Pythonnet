# CODE_MAP — Yuanta OneAPI Python 專案程式碼地圖

## 專案架構總覽

```
YuantaOneAPI.dll (C# 元大證券 API)
    │  pythonnet (clr.AddReference)
    ▼
YuantaAPI_Pythonnet.py          ← 即時報價訂閱 + 5秒 CSV 持久化
    │                              StockQuoteState 狀態管理
    │                              _update_estimates() 預估量
    │                              _write_daily_summary() 日總結
    │
    ├──▶ {stockID}.csv           ← 5 秒 OHLCV（單位：股 / 元）
    ├──▶ @stockID.csv            ← 日總結（每交易日一筆，12 欄中文）
    ├──▶ yesterday/{stockID}.csv ← 昨日收盤快照
    └──▶ stock_ref.json          ← 參考價快取（yst_price ×10000）

web_dashboard.py                ← Flask + SSE 即時監控面板
    │                              讀取 CSV 檔案（不需 .NET）
    │                              主力/散戶分類、Put/Call 計算
    │
run.py                          ← 交易日排程器（08:30 自動啟動 dashboard）
sim_run.py                      ← 非交易日模擬器

cStocks.py                      ← Matplotlib K 線四聯圖
    │                              MACD / KDJ / Bollinger / 支撐壓力
    │                              讀取 {stockID}.csv
    │
option_pricing.py               ← Black-Scholes 選擇權定價
    └── 被 web_dashboard.py import

fetch_daily_close.py            ← TWSE/TPEx OpenAPI 收盤數據校正
repair_daily_summary.py         ← 從 5 秒 CSV 重建日總結
repair_csv.py                   ← CSV 診斷與修復工具
update_stock_names.py           ← 股名對照表更新（TWSE/TPEx 爬取）
```

---

## 核心 .py 檔案

### 即時數據層

| 檔案 | 職責 | 輸入 | 輸出 |
|------|------|------|------|
| `YuantaAPI_Pythonnet.py` | **主程式**。pythonnet 橋接 DLL，訂閱報價、管理 StockQuoteState、寫入 CSV | YuantaOneAPI.dll, stock_names.json | `{code}.csv`, `@{code}.csv`, `yesterday/{code}.csv` |
| `test_simulate.py` | 模擬資料產生器，API 離線時使用 | watchlist.json, `{code}.csv` | `{code}.csv` (模擬), `@{code}.csv` |

### 視覺化層

| 檔案 | 職責 | 輸入 | 輸出 |
|------|------|------|------|
| `web_dashboard.py` | Flask + SSE 即時多股監控面板，Dark theme | `{code}.csv`, `@{code}.csv`, watchlist.json, stock_names.json, stock_ref.json | HTML/JSON/SSE (port 5000) |
| `cStocks.py` | Matplotlib K 線四聯圖（日K~月K）| `{code}.csv` (pandas) | `{code}_settings.json`, `{code}_drawings.json`, PNG |
| `option_pricing.py` | Black-Scholes + IV + Put/Call Parity | 純計算，無 I/O | 被 web_dashboard import |

### 排程 / 啟動層

| 檔案 | 職責 |
|------|------|
| `run.py` | 交易日排程：檢查行事曆 → 等待 08:30 → 啟動 web_dashboard。PID 防雙開 |
| `sim_run.py` | 模擬模式：啟動 test_simulate + web_dashboard。檢查 .api_active 避免衝突 |

### 數據工具層

| 檔案 | 職責 | 使用時機 |
|------|------|----------|
| `fetch_daily_close.py` | 從 TWSE/TPEx OpenAPI 拉取收盤數據，寫入 @stockID.csv 與 stock_ref.json | 每日收盤後或隔日開盤前 |
| `repair_daily_summary.py` | 從 5 秒 CSV 重建日總結 @stockID.csv，修正 int32 溢位、格式不一致 | 資料損壞時 |
| `repair_csv.py` | CSV 診斷（負值成交量、價格比例異常、金額誤差） | 資料異常排查 |
| `update_stock_names.py` | 爬取 TWSE/TPEx 更新 stock_names.json（股名對照表） | 新股上市或更名時 |

### 一次性修復腳本（已完成，保留供參考）

| 檔案 | 用途 |
|------|------|
| `fix_final.py` | 修正 @stockID.csv 特定錯誤值（2344/6122/6123/8936/6412） |
| `cleanup_final.py` | 清除重複 header、重建損壞的 @stockID.csv |
| `update_yesterday.py` | 批次更新 yesterday/ 備份 |

### AI Agent 層

| 檔案 | 職責 |
|------|------|
| `claude_agent_setup.py` | 一次性建立 Managed Agent + Environment |
| `claude_agent_runtime.py` | Agent 對話/排程/研究 runtime |

---

## 關鍵 JSON 設定檔

| 檔案 | 用途 | 寫入者 |
|------|------|--------|
| `watchlist.json` | 自選股分組（自選股1/2/3），含 stocks + futures | 手動 / dashboard UI |
| `stock_names.json` | 股票代號 → 公司名稱對照表（~1700+ 筆） | update_stock_names.py |
| `stock_ref.json` | 參考價快取：yst_price(×10000), up_price, down_price, yst_vol | fetch_daily_close.py, repair_daily_summary.py |
| `holidays.json` | 休市日清單 `["2026-01-01", ...]` | 手動 |
| `accountEnv.json` | 帳號密碼（已 gitignore，不可提交） | 手動 |
| `{code}_settings.json` | cStocks 圖表參數（unit, n_days, MA, Bollinger, style） | cStocks.py |
| `{code}_drawings.json` | cStocks 繪圖物件持久化 | cStocks.py |

---

## CSV 資料規格

### 5 秒 CSV (`{code}.csv`)

| 欄位 | 格式 | 範例 |
|------|------|------|
| timestamp | `YYYYMMDD HH:MM:SS` | `20260604 11:48:35` |
| stock_id | string | `2317` |
| deal_volume | 股 (5秒區間) | `17000` |
| deal_amount | 元 | `5066000` |
| open_price | 元 (整數) | `298` |
| high_price | 元 (整數) | `300` |
| low_price | 元 (整數) | `298` |
| close_price | 元 (整數) | `298` |
| price_diff | 元 | `-1` |
| trade_count | 累積筆數 | `733` |
| estimated_day_volume | 股 | `119962162` |
| volume_label | 盤中預估量/盤後總量 | `盤中預估量` |
| pct_of_yesterday_avg | 增/縮% | `-17.89` |
| total_in_volume | 股 (5秒區間) | `10000` |
| total_out_volume | 股 (5秒區間) | `7000` |
| buy_prices / sell_prices | 元 (5檔) | `[298, 298, 297, ...]` |
| buy_volumes / sell_volumes | 股 (5檔) | `[1101, 635, ...]` |
| ma5 / ma10 | 元 | `298` |
| participation_score / label | 主力分數/標籤 | `37.2` / `主力強力買進` |
| extra_data | Watchlist flags | `{'4': 19244, '6': 45997, '7': 2985000}` |

### 日總結 (`@{code}.csv`)

| 欄位 | 格式 |
|------|------|
| 日期 | `YYYYMMDD` |
| stock_id | string |
| 開盤價 / 最高價 / 最低價 / 收盤價 | 元 |
| 成交股數 | 股 (全日) |
| 成交金額 | 元 (全日) |
| 成交筆數 | int |
| total_in_volume / total_out_volume | 股 (全日累積) |
| estimated_day_volume | 股 |

---

## 資料流

```
09:00 開盤
    │
    ▼
YuantaAPI_Pythonnet.py 啟動
    │  SubscribeFiveTick / SubscribeWatchlistAll / SubscribeStockTick
    │  StockQuoteState 管理 per-stock 狀態
    │
    ├── 每 5 秒 ──▶ {code}.csv 寫入（build_save_record → _norm() → 元/股）
    │
    ├── 13:30 收盤 ──▶ @{code}.csv 日總結（_write_daily_summary）
    │                  yesterday/{code}.csv 備份
    │
    ▼
web_dashboard.py ── 讀取 CSV → Flask SSE → 瀏覽器 :5000
cStocks.py ─────── 讀取 CSV → Matplotlib K 線圖

    ▼
盤後 / 隔日開盤前
fetch_daily_close.py ── TWSE/TPEx API → @{code}.csv 校正
repair_daily_summary.py ── 5秒CSV → @{code}.csv 重建
```

---

## 重要規則（2026-06-04 更新）

- **CSV 價格單位**：元（整數），經 `build_save_record()._norm()` 正規化
- **CSV 成交量單位**：股（非張），顯示時才 ÷1000
- **API 原始格式**：×10000（元 ×10000 = 毛 ×1000）
- **_norm() 規則**：`abs(p) > 100000` → `round(p/10000)` else `round(p,2)`
- **@stockID.csv 格式**：12 欄中文，三 writer 已統一
- **預估量算法**：`actual_cum / _intraday_volume_progress(elapsed_min)`（動態投影）
- **昨均% 顯示**：增/縮 XX.X%（正值=增加，負值=減少）
- **cStocks.py 優先級較低**：先處理 YuantaAPI_Pythonnet.py 與 web_dashboard.py
