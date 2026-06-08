# CODE_MAP — Yuanta OneAPI Python 專案程式碼地圖

> 最後更新: 2026-06-08 (v2.1)

## 專案架構總覽

```
YuantaOneAPI.dll (C# 元大證券 API)
    │  pythonnet (clr.AddReference)
    ▼
YuantaAPI_Pythonnet.py          ← 即時報價訂閱 + 5秒 CSV 持久化
    │                              StockQuoteState 狀態管理
    │                              _update_estimates() 預估量 v2（速率加權）
    │                              _write_daily_summary() 日總結
    │                              _write_snapshots() 0.5s 快照（原子寫入）
    │                              watchlist.json mtime 自動偵測
    │
    ├──▶ {stockID}.csv           ← 5 秒 OHLCV（單位：股 / 元）
    ├──▶ @stockID.csv            ← 日總結（每交易日一筆，12 欄中文）
    ├──▶ yesterday/{stockID}.csv ← 昨日收盤快照
    ├──▶ snapshot/{stockID}.json ← Dashboard 0.5s 快照（~1KB，原子寫入）
    └──▶ stock_ref.json          ← 參考價快取（yst_price/up_price/down_price ×10000）

web_dashboard.py                ← Flask + SSE 即時監控面板 (0.5s 更新)
    │                              讀取 snapshot/*.json 優先，降級 CSV
    │                              主力/散戶分類、Put/Call 計算、PE/PB/PEG
    │                              累積總量/總額顯示、漲跌停（API 優先）
    │
hedge_dashboard.py              ← 避險儀表板 Blueprint (/hedge)
    │                              TXF 期現貨基差 + 理論價 + 大戶動向 + 個股期避險
    │
run.py                          ← v2 每日一站式啟動器（API + Dashboard + 盤前檢查）
    │                              stdout reader thread + .api_active 驗證
    │                              自動執行 update_financials.py + fetch_analyst_eps.py
sim_run.py                      ← 非交易日模擬器

cStocks.py                      ← Matplotlib K 線四聯圖（優先級較低）
    │                              MACD / KDJ / Bollinger / 支撐壓力
    │                              讀取 1min/{code}_1min.csv 或 {code}.csv
    │
resample_1min.py                ← 5 秒 CSV → 1 分 K 轉換工具
snapshot_writer.py              ← 獨立 Snapshot 產生器（從 CSV 讀取寫入 snapshot/，原子寫入）
option_pricing.py               ← Black-Scholes 選擇權定價 + PCR 分析
    └── 被 web_dashboard.py import

fetch_daily_close.py            ← TWSE/TPEx OpenAPI 收盤數據校正
repair_daily_summary.py         ← 從 5 秒 CSV 重建日總結
repair_csv.py                   ← CSV 診斷與修復工具
update_stock_names.py           ← 股名對照表更新（TWSE/TPEx 爬取）

update_market_cap.py            ← 市值排名更新（TWSE BWIBBU + TPEx API）
    │                              output → market_cap.json (PE/PB/tier/排名)
update_financials.py            ← 近四季 EPS + PEG 計算
    │                              output → stock_financials.json
fetch_analyst_eps.py            ← 法人預估 EPS 聚合 + trimmed mean + PEG
    │                              output → analyst_eps.json
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
| `run.py` | v2 每日一站式啟動：雙開防護 → 交易日判斷 → 盤前檢查（@stockID.csv + stock_ref.json + stock_financials.json + analyst_eps.json）→ 啟動 API subprocess（stdout reader + .api_active 驗證）→ Dashboard |
| `sim_run.py` | 模擬模式：啟動 test_simulate + web_dashboard。檢查 .api_active 避免衝突 |

### 數據工具層

| 檔案 | 職責 | 使用時機 |
|------|------|----------|
| `fetch_daily_close.py` | 從 TWSE/TPEx OpenAPI 拉取收盤數據，寫入 @stockID.csv 與 stock_ref.json（含 up/down_price）。自動偵測 API 回傳日期避免標記錯誤 | 每日收盤後或隔日開盤前 |
| `resample_1min.py` | 5 秒 CSV → 1 分 K 轉換（OHLCV），輸出對齊 cStock.load_data() 格式。支援單股/全股/指定日期 | 需要技術分析時（餵給 cStocks.py） |
| `snapshot_writer.py` | 獨立 Snapshot 產生器：從 CSV 讀取最後有效資料寫入 snapshot/*.json。原子寫入（tmp→replace）供 sim_run 或盤後測試使用 | 非 API 場景的 dashboard 加速 |
| `repair_daily_summary.py` | 從 5 秒 CSV 重建日總結 @stockID.csv，修正 int32 溢位、格式不一致 | 資料損壞時 |
| `repair_csv.py` | CSV 診斷（負值成交量、價格比例異常、金額誤差） | 資料異常排查 |
| `update_stock_names.py` | 爬取 TWSE/TPEx 更新 stock_names.json（股名對照表） | 新股上市或更名時 |

### 財務數據層

| 檔案 | 職責 | 輸出 |
|------|------|------|
| `update_market_cap.py` | 市值排名更新：TWSE BWIBBU_ALL (PE/PB) + STOCK_DAY_ALL (收盤價) + TPEx API → 全市場排名分類。支援 --dry-run / --stocks | `market_cap.json` |
| `update_financials.py` | 近四季 EPS + PEG 計算。從 _QUARTERLY_EPS 內建資料 + market_cap.json PE/PB 組合。自動涵蓋所有自選股 | `stock_financials.json` |
| `fetch_analyst_eps.py` | 法人預估 EPS 聚合：Yahoo TW + Google Finance 爬取 → trimmed mean 20% 去極端值 → 共識 EPS → 動態 PEG。降級: manual_eps → trailing_4q | `analyst_eps.json` |

### 避險層

| 檔案 | 職責 |
|------|------|
| `hedge_dashboard.py` | Flask Blueprint (/hedge)：TXF 期現貨基差監控 + 持有成本理論價 + 動態避險門檻（歷史標準差 ×1.5）+ 大戶動向（TAIFEX 前5/前10）+ 個股期貨避險對照 |
| `option_pricing.py` | Black-Scholes 選擇權定價 + IV + Put/Call Parity + PCR 分析。純計算，被 web_dashboard.py import |

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
| `stock_ref.json` | 參考價快取：yst_price, up_price, down_price, yst_vol (×10000 原始值) | fetch_daily_close.py, YuantaAPI_Pythonnet.py (ReadWatchListAll) |
| `market_cap.json` | 全市場市值排名：TWSE/OTC 分類 (large/mid/small) + PE/PB/收盤價 | update_market_cap.py |
| `stock_financials.json` | 近四季 EPS + EPS 成長率 + PEG | update_financials.py |
| `analyst_eps.json` | 法人預估 EPS 共識 + forward PE + PEG。支援 manual_eps 手動覆蓋 | fetch_analyst_eps.py |
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
run.py 執行盤前檢查
    │  1. 檢查 @stockID.csv 昨日資料完整性
    │  2. 檢查 stock_ref.json 涵蓋率（缺值自動執行 fetch_daily_close.py）
    │  3. 執行 update_financials.py → stock_financials.json
    │  4. 執行 fetch_analyst_eps.py → analyst_eps.json (PEG 更新)
    │  5. 啟動 YuantaAPI_Pythonnet.py subprocess
    │     └── stdout reader thread（防止 pipe 阻塞）
    │     └── 等待 .api_active 旗標（最多 30s）
    │  6. 啟動 web_dashboard.py
    │
    ▼
YuantaAPI_Pythonnet.py 啟動
    │  open_api() → login_api()
    │  SubscribeFiveTick / SubscribeWatchlist / SubscribeWatchlistAll / SubscribeStockTick
    │  ReadWatchListAll → stock_ref.json
    │  show() 主循環:
    │
    ├──每 5 秒 ──▶ _save_to_csv_async() → {code}.csv
    │               commit_save_snapshot() 更新區間 delta 基準
    │
    ├──每 0.5 秒 ▶ _write_snapshots() → snapshot/{code}.json（原子寫入 tmp→replace）
    │              cumulative_deal_volume + cumulative_deal_amount（累積值）
    │
    ├──每 5 秒 ──▶ SubscribeFiveTick_api() 重訂（防止掉線）
    │
    ├──每 60 秒 ─▶ 四種訂閱全重訂 + watchlist.json mtime 變更偵測
    │              若 watchlist.json 有變更 → ReadWatchListAll 補參考價
    │
    ├──13:30 收盤 ──▶ 最後一筆 CSV + @{code}.csv 日總結 + yesterday/ 備份
    │
    ├──14:30 後 ───▶ 日總結寫入 + CSV 凍結，保持進程供 dashboard 讀取
    │
    ▼
web_dashboard.py ── poll_worker() 每 0.5s:
    │                  1. 檢查 snapshot mtime（只讀有更新的檔案）
    │                  2. read_snapshot() 優先（累積值）
    │                  3. 降級 read_latest_csv()
    │                  4. SSE push 到瀏覽器 :5000
    │
    └── hedge_dashboard.py (/hedge) — 獨立 Blueprint
cStocks.py ─────── 讀取 1min CSV → Matplotlib K 線圖

    ▼
盤後 / 隔日開盤前
fetch_daily_close.py ── TWSE/TPEx API → @{code}.csv 校正 + yesterday/ + stock_ref.json
repair_daily_summary.py ── 5秒CSV → @{code}.csv 重建
update_market_cap.py ── 每月 1-4 號更新市值排名 → market_cap.json
```

---

## 重要規則（2026-06-08 更新 v2.1）

- **CSV 價格單位**：元（整數），經 `build_save_record()._norm()` 正規化
- **CSV 成交量單位**：股（非張），顯示時才 ÷1000
- **API 原始格式**：×10000（價格），×1（量為股）
- **_norm() 規則**：`abs(p) > 100000` → `round(p/10000)` else `round(p,2)`
- **Snapshot 累積值**：`cumulative_deal_volume` + `cumulative_deal_amount`（API 64-bit total_amt），供 dashboard 顯示總量/總額
- **Snapshot 原子寫入**：`tmp → os.replace()` 避免 dashboard 讀到半寫入檔案
- **@stockID.csv 格式**：12 欄中文，三 writer 已統一（_write_daily_summary / _save_stock_ref_json / fetch_daily_close.py）
- **預估量算法 v2**：固定曲線投影（_intraday_volume_progress）+ 5 分鐘速率加權（開盤 50:50，盤中 70:30）
- **昨均% 顯示**：增/縮 XX.X%（正值=增加，負值=減少）
- **漲跌停判斷**：優先 stock_ref.json API 值（up_price/down_price 已考量除權息），驗證 up > yst > down 合理性，無效時降級為昨收 ×1.10/0.90
- **PE/PB/PEG 三層降級**：analyst_eps.json（法人預估）→ stock_financials.json（近四季 EPS）→ market_cap.json（PE/PB only）
- **API subprocess**：stdout PIPE 需 reader thread 防止緩衝阻塞；啟動後等待 .api_active 旗標（最多 30s）
- **盤中新增個股**：watchlist.json mtime 自動偵測 → 60s 週期重訂時自動訂閱新股 + 補參考價
- **cStocks.py 優先級較低**：先處理 YuantaAPI_Pythonnet.py 與 web_dashboard.py

### 常用指令速查

```bash
# 每日啟動（開盤日）
python run.py                    # 完整啟動（API + Dashboard + 盤前檢查）
python run.py --no-api           # 僅 Dashboard（測試用）
python run.py --skip-preflight   # 跳過盤前資料檢查

# 模擬測試（非開盤日）
python sim_run.py                # 模擬器 + Dashboard

# 收盤數據校正
python fetch_daily_close.py                  # 更新今日 @stockID.csv + stock_ref.json
python fetch_daily_close.py --compare-only   # 僅比對不寫入
python fetch_daily_close.py --date 20260604  # 指定日期

# 1 分 K 轉換
python resample_1min.py 2330                # 單股最近 1 天
python resample_1min.py --all               # 全自選股
python resample_1min.py 2330 --date 20260605  # 指定日期
python resample_1min.py 2330 --days 5       # 最近 5 天

# Snapshot 產生（非 API 場景）
python snapshot_writer.py --once            # 一次性產生
python snapshot_writer.py --interval 0.5    # 持續更新（模擬 0.5s）

# 財務數據
python update_market_cap.py                 # 更新全市場市值排名
python update_market_cap.py --dry-run       # 預覽不寫入
python update_financials.py                 # 更新近四季 EPS + PEG
python update_financials.py --stocks 2330   # 指定股票
python fetch_analyst_eps.py                 # 更新法人預估 EPS + PEG
python fetch_analyst_eps.py --dry-run       # 預覽不寫入

# 資料修復
python repair_daily_summary.py              # 從 5 秒 CSV 重建 @stockID.csv
python repair_csv.py                        # CSV 診斷

# Dashboard
http://localhost:5000                       # 即時監控面板
http://localhost:5000/hedge                 # 避險儀表板
```
