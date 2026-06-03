# CHANGELOG - YuantaAPI_Pythonnet.py
## [2026-06-03]

### Fixed
- **int32 溢位修復**: API 回傳的成交量欄位（`total_out`, `total_in`, `deal_vol`, `total_vol`）在 C# 端以 signed int32 儲存，累積超過 2^31-1 時變負值。新增 `to_uint32()` 函式，在 4 個 API 進入點（`SubscribeWatclistAll_Out`、`SubscribeStocktick_out`、`SubscribeWatchlist_Out`、`update_watchlist_all`、`update_stocktick`）將溢位負值轉為正確的 Python 無號整數
- **僵屍 .api_active 旗標**: `sim_run.py` 新增 `_check_api_active()` — API 行程異常關閉後，旗標檔殘留會阻止模擬器啟動。現在檢查 PID 是否仍存活，僵屍旗標自動清除
- **WatchlistAll/Stocktick 訂閱掉線**: `show()` 只定期重訂 `SubscribeFiveTick_api`，未重訂 `SubscribeWatchlistAll_api` 和 `SubscribeStocktick_api`，導致 6122/6123/8936 在 5/28 後停止接收資料。新增每 60 秒重訂機制
- **web_dashboard 全部價量紀錄**: 展開/內縮改用 CSS class 控制，修正 SSE 刷新時狀態遺失；`_recent_rows_api` 加入 int32 溢位負值防護
- **run.py 雙開防護**: 多次啟動 `run.py` 會產生多個 Python 程序競爭 `YuantaOneAPI.dll`，導致 `clr.AddReference` 組件載入失敗。新增 `_is_process_running()`（Kernel32 `OpenProcess`）與 `_check_existing()` 檢查 `.dashboard_pid`，若舊程序仍存活則拒絕啟動並提示 `taskkill` 指令
- **web_dashboard 漲跌停誤判**: `stock_ref.json` 中部分個股（2317/2344）的 `up_price` 低於 `yst_price`，導致 `_calc_limit_state` 永遠判定為漲停。`_get_limit_prices()` 新增驗證 `up_price > 昨收 > down_price`，不合法時自動改用 `昨收 × 1.10 / 0.90` 計算
- **CSV 成交量全為 0**: WatchlistAll byTemp 29（累積量）API 從未推送，Watchlist flag 7 實測回傳成交價而非成交量。改為訂閱 Watchlist flags 4（累計外盤量）與 6（累計內盤量），值單位為「張」需 ×1000 轉「股」，並以 5 秒區間 delta 寫入 CSV
- **`to_display_dict()` 頻繁重置快照**: Watchlist 回呼每次觸發都呼叫 `to_display_dict()` → `build_save_record()`，導致區間量快照被過度重置，5 秒 delta 趨近 0。拆分 `commit_save_snapshot()` 僅在 CSV 真正寫入後更新快照
- **OTC 股票訂閱失效**: 所有訂閱（FiveTick/WatchlistAll/Watchlist）硬編碼 `MarketNo=1`（TSE），導致 OTC 股票（代碼首碼 3-9）無法接收資料。新增 `_stock_market_no()` 自動判斷市場別，CSV 刪除後 OTC 股票無法重建 CSV
- **CSV 欄位位移**: 舊 CSV header 缺少 `volume_label` 欄位，新版 fieldnames 新增後導致附加列位移一欄，所有欄位資料錯位。刪除舊 CSV 重建解決
- **`GetUInt()` 對齊 IronPython**: 三個訂閱回呼（Stocktick/WatchlistAll/Watchlist）改用 `GetInt()` 與 IronPython 版本一致，保留 `to_uint32()` 處理溢位。實測 `GetInt()` 與 `GetUInt()` 回傳值相同
- **成交總額全為 0**: `build_save_record()` 的 `deal_amount` 僅依賴 `last_deal_price`（僅 StockTick 設定），無 StockTick 的股票永遠為 None。改用 `close_price`（可從五檔推斷）作為 fallback 計算
- **成交筆數全為 0**: `SubscribeStocktick_out` 回呼中 `state = get_quote_state()` 與 `state.update_stocktick()` 兩行在 debug 清理時誤刪，導致逐筆成交資料解析後從未寫入 state
- **StockTick 訂閱 MarketNo 遺漏**: `SubscribeStocktick_api` / `UnSubscribeStocktick_api` 仍硬編碼 `MarketNo=1`，OTC 股票無法接收逐筆成交。改用 `_stock_market_no()`
- **deal_amount 價格未正規化**: StockTick 的 `last_deal_price` 為 API 原始整數（需 ÷10000），直接用於金額計算導致數值錯誤。新增正規化判斷（≥100000 時 ÷10000）
- **6412 被誤判為 OTC**: `_stock_market_no()` 僅依首碼判斷，6412 首碼 6 被歸為 OTC（MarketNo=2），但 API 查詢證明其為 TSE 股票。改為優先查 `stock_ref.json`（API 以 MarketNo=1 查得即為 TSE），首碼僅作 fallback

### Added
- **@stockID.csv 修復工具**: `repair_daily_summary.py` — 從 5 秒 CSV 重建日總結檔，修正格式不一致、int32 溢位歷史資料、缺少 yesterday/ 備份
- **yesterday/ 備份**: 全部 10 檔自選股的盤後日總結備份
- **`commit_save_snapshot()`**: StockQuoteState 新增快照提交方法，與 `build_save_record()` 分離，確保區間 delta 只在 CSV 寫入時更新
- **`_stock_market_no()`**: 根據股票代碼首碼自動判斷 TSE(1) 或 OTC(2)，應用於所有訂閱函式
- **Watchlist flags 4/6 訂閱**: 新增累計外盤量(flag 4)與累計內盤量(flag 6)的 Watchlist 訂閱，補足 byTemp 29 不推送的資料缺口

### Changed
- `stock_ref.json`: 從 3 檔擴充至 10 檔，補齊 6412/6122/6123/8936 參考價
- `build_save_record()`: `deal_volume` 改用 `interval_in + interval_out`（內外盤區間量和），取代 StockTick 逐筆 tick 量（1~5 股無法顯示）
- `has_trade_activity()` / `has_data()`: 放寬條件納入五檔報價（`buy_prices`）與推斷 OHLC，確保僅有 FiveTick 資料的股票也能寫入 CSV
- 所有訂閱函式（`SubscribeFiveTick_api`/`SubscribeWatchlistAll_api`/`SubscribeWatchlist_api` 等）: `MarketNo` 改用 `_stock_market_no()` 動態判斷
- `web_dashboard.py` 金額單位: 成交總額與全部價量紀錄的金額從「億」改為「萬」，5 秒區間交易金額約數萬~數百萬，單位更合適
- `web_dashboard.py` 全部價量紀錄: 過濾條件改為「量、內盤、外盤、成交筆數全為 0」才跳過，讓有逐筆成交但累積量未更新的列也能保留
- `build_save_record()`: `deal_volume` 改用 `max(interval_in + interval_out, interval_vol)`，低量股 Watchlist 更新慢時自動 fallback 到 StockTick 累積量

## [2026-06-02]
### Changed (web_dashboard.py)
- `_normalize_price()`: 顯示端價格bug ÷10000 處理舊 CSV 混合模擬器資料,校正,正確原始整數
-  dashboard  全部價量紀錄,展開後自動內縮,的修正,盤後部分確認ok

## [2026-05-26]

### Fixed

- **5-tick field order**: `SubscribeFiveTick_out` 解析順序修正為 買價→買量→賣價→賣量（與 IronPython API spec 一致），先前價格/數量互換導致資料錯誤
- **Watchlist OHLC overwrite**: `update_watchlist_all` 不再覆蓋五檔推斷的 OHLC（byTemp 29 的 deal_price 尺度與五檔不同，覆蓋會導致價格變為原始整數）
- **Dictionary iteration crash**: `show()` 5 處迭代 `SUBSCRIPTION_STATE['stocks']` 改用 `list()` 快照，防止背景回呼新增股票時觸發 `dictionary changed size during iteration`
- **Watchlist single-value overwrite**: byTemp 22/28 不再以單點買賣覆蓋五檔五層陣列
- **14:30 CSV save**: `matching→closed` 轉換時強制寫入最後一筆 CSV 再寫日總結

### Added

- **update_stock_names.py**: 從 TWSE/TPEx 公開資料自動抓取全台股名對照，`stock_names.json` 從 10 筆擴充至 1979 筆
- **Server selection**: `open_api()` 從 `accountEnv.json` 讀取 `server` 欄位（UAT/PROD）
- **Account config**: `login_api()` 改從 `accountEnv.json` 讀取帳號，支援多組現貨/期貨帳號

### Security

- 帳密移至 `accountEnv.json`，加入 `.gitignore` 排除上傳
- 移除 `login_api()` 中的 hardcoded 帳密

### Changed (web_dashboard.py)

- `_normalize_price()`: 顯示端安全網，價格 >100000 時自動 ÷10000 處理舊 CSV 殘留的原始整數

## [2026-05-20]

### Added

- **Market Schedule Control**: `_market_phase()` 市場排程輔助函數
  - `pre_open`: 09:00 前
  - `trading`: 09:00-13:30 正常交易，每 5 秒保存 CSV
  - `matching`: 13:30-14:30 盤後搓合，暫停 CSV 輸出
  - `closed`: 14:30 後寫入日總結後停止
- **Daily Summary CSV**: `_write_daily_summary()` 寫入 `@stockID.csv` 每日一筆 OHLCV
  - 同步更新 `yesterday/{stockID}.csv` 供隔日 `_load_yesterday_data()` 載入
- **Yesterday Volume Loader**: `StockQuoteState._load_yesterday_data()`
  - 從 `yesterday/{stockID}.csv` 載入昨日成交量作為 `prev_average_volume`
  - 修復 `pct_of_yesterday_avg` 欄位在 CSV 中缺失的 bug (CHANGELOG#142)

### Changed

- **show()** 重構: 整合市場排程邏輯，階段控制 CSV 寫入
- **StockQuoteState.**init**()** 自動呼叫 `_load_yesterday_data()`

### Fixed

- `pct_of_yesterday_avg` CSV 欄位始終為空 → 現在從 yesterday/ 載入昨量計算
- `_display_quote_info()` 內外盤分析程式碼重複 → 已合併

### Added (Claude API Integration)

- **claude_agent_setup.py**: 一次性建立 3 個 Managed Agent + Environment
  - Yuanta-Analyst-Opus (`claude-opus-4-7`)
  - Yuanta-Analyst-Sonnet (`claude-sonnet-4-6`)
  - Yuanta-Analyst-Haiku (`claude-haiku-4-5`)
- **claude_agent_runtime.py**: 4 種運行模式
  - 互動式對話 / 排程分析 (`--cron`) / 任務執行 (`--task`) / 研究報告 (`--research`)
- **README.md**: GitHub 專案首頁文件
- **.gitignore**: Git 版控排除規則

### Added (Evening Session — Analysis & Dashboard)

- **主力/散戶分類系統**: `StockQuoteState._classify_participation()`
  - 五檔買賣壓力 + 內外盤成交偏向 + 大單偵測 + 價格 vs 均價位置
  - 評分制: 主力強力買進 (>30) / 主力溫和買進 (>10) / 散戶盤整 (-10~10) / 主力溫和賣出 (>-30) / 主力強力賣出
- **股票分類**: `StockQuoteState.detect_stock_type()` 依成交值自動分類 large_cap/mid_cap/small_cap/speculative
- **Web Dashboard**: `web_dashboard.py` — Flask + SSE 即時多股監控畫面
  - Dark theme card layout 顯示 OHLCV / MA / 買賣佔比 / 主力標籤
  - 讀取 CSV 檔案無需依賴 .NET Runtime，可獨立執行
- **CSV 欄位擴充**: `stock_type`, `participation_score`, `participation_label`

### Changed (cStocks Performance)

- **向量化 K 線繪製**: 逐根 Rectangle → 單次 ax.vlines + ax.bar, artist 數量 180+ → ~6
- **向量化成量色彩**: for loop + print() → np.where 單次計算
- **支撐/壓力快取**: `_sr_cache` / `_sr_dirty`, 避免每次 update_view 重算
- **移除** orphaned `getMaxMinDf` 方法

---

## [Unreleased]

### Added

- **StockQuoteState Class**: New class for encapsulating stock quote state management
  - Supports five-tick quotes, transaction details, watchlist data updates
  - Automatic calculation of OHLC, price change, estimated daily volume
  - In/out volume analysis for major/minor player ratio assessment
- **Global SUBSCRIPTION_STATE Dictionary**: Unified storage for subscription data
  - `stocks`: Quote states for each stock (StockQuoteState instances)
  - `system`: System messages
  - `rq_rp`: Query responses
- **Async show() Method**: Asynchronous display of subscription response information
  - Updates UI every 1/60 seconds with all subscribed stock information
  - Saves complete quote records to CSV every 5 seconds
  - Supports paginated display and in/out volume analysis
- **Optimized Subscription Response Handlers**:
  - `SubscribeFiveTick_out`: Handles five-tick quotes (tested heartbeat signal)
  - `SubscribeWatclistAll_Out`: Handles watchlist quotes
  - `SubscribeStocktick_out`: Handles tick-by-tick transaction details
  - `SubscribeWatchlist_Out`: Handles specific field quotes
- **Async CSV Saving**: Non-blocking data persistence functionality
  - `_save_to_csv_async`: Asynchronous CSV file saving
  - Supports concurrent saving for multiple stocks
- **Technical Indicator Calculations**: Added basic price momentum and moving average analysis
  - `ma5`, `ma10`, `price_momentum` included in saved records and runtime display
- **Buy/Sell Pressure Analysis**: Added buy/sell total volume, imbalance, and pressure metrics
  - `buy_total_volume`, `sell_total_volume`, `buy_sell_imbalance`, `buy_sell_pressure` saved to CSV
- **Enhanced Error Handling**: Improved exception catching and logging
  - Added error handling to all critical functions
  - Detailed debug information output
- **Program Architecture Optimization**:
  - Modular design for easier maintenance and extension
  - Unified data processing workflow
  - Framework support for large-cap/mid-cap/small-cap/speculative stock analysis

### Changed

- **Data Storage Unification**: All received messages now stored in SUBSCRIPTION_STATE dictionary
- **UI Update Frequency**: Changed from synchronous to asynchronous updates every 1/60 seconds
- **Data Persistence**: Implemented periodic saving every 5 seconds instead of on-demand

### Technical Details

- **Language**: All comments and documentation in Traditional Chinese
- **Framework**: Uses pythonnet for .NET DLL integration
- **Async Processing**: Implemented with asyncio for non-blocking operations
- **Data Analysis**: Added volume analysis for institutional vs retail trading patterns
- **File Output**: CSV format with timestamp, OHLC, volume, and ratio data

### Testing

- Verified FiveTick subscription returns heartbeat signal with stock_id 2317 data
- Confirmed data persistence and UI updates work correctly
- Validated in/out volume ratio calculations

### Documentation

- Added comprehensive docstrings to all new classes and methods
- Included usage examples and parameter descriptions
- Referenced Yuanta OneAPI documentation (page 22+) for protocol details

## 版本 [2025-02-28]

### 功能改進

#### 1. 統一訂閱回應格式為字典結構

- **修改**: `SubscribeFiveTick_out()` 函數
- **變更**: 將訂閱五檔報價回應從 `result` 字符串格式改為字典格式
- **好處**: 便於後續 UI 顯示和數據分析，易於擴展其他訂閱回應

#### 2. 實現異步 show() 方法

- **新增**: `async def show()` 函數，支持異步 UI 更新
- **功能**:
  - 每 1/60 秒更新一次 UI 顯示訂閱信息
  - 每 5 秒完整保存一筆數據記錄到本地 CSV 檔案
  - 使用 asyncio 異步方法避免阻塞主線程
  - 支持多檔股票同時管理

#### 3. 數據持久化功能

- **新增**: `_save_to_csv_async()` 異步函數
- **功能**:
  - 每 5 秒自動保存數據到 CSV 檔案（檔名格式: `{stock_id}.csv`）
  - 包含欄位:
    - 時間 (timestamp)
    - 股票代碼 (stock_id)
    - 索引值 (byIndexFlag)
    - 五檔買價、買量、賣價、賣量
  - 自動檢測文件是否存在，決定是否寫入表頭

#### 4. UI 顯示功能

- **新增**: `_display_quote_info()` 函數
- **功能**:
  - 實時顯示五檔買賣盤
  - 計算並顯示買盤和賣盤佔比
  - 便於分析主力/散戶行為和內外盤成交量

#### 5. 代碼修正

- **修正**: 第 2482 行 `asyncio.show()` 改為 `asyncio.run(show())`
  - 原因: `asyncio.show()` 不是有效的 asyncio 函數，應使用 `asyncio.run()` 執行異步函數

### 技術細節

#### 數據結構改進

```python
# 舊格式 (result 字符串)
result = 'FiveTick五檔訂閱結果:\r\n...'

# 新格式 (字典結構)
fivetick_data = {
    'abyKey': str,
    'byMarketNo': str,
    'stock_id': str,
    'byIndexFlag': str,
    'timestamp': float,
    'five_tick_data': {
        'buy_prices': [int, ...],
        'buy_volumes': [int, ...],
        'sell_prices': [int, ...],
        'sell_volumes': [int, ...],
    }
}
```

#### 異步流程

1. 訂閱回應事件觸發 → `SubscribeFiveTick_out()` 處理
2. 數據保存為字典格式到 `dtsFiveTickOrder`
3. `show()` 異步任務監控數據字典
4. 每 1/60 秒顯示當前報價
5. 每 5 秒保存一筆完整記錄到 CSV
6.- [ ] 考慮收盤時間~盤後搓合,這之間,暫停輸出~盤後搓合後保存一筆完整記錄到csv->停止輸出csv
7.- [ ] 完成盤後搓合後,最終再append一筆,以日為單位的"@股號D.csv"(例如:@2317D.csv,@2330D.csv...,依追蹤的自選股來生成,資料格式除了timestamp省略時間改成日期,其餘欄位同5秒csv),利於隔日快速取得今日資訊
8.- [ ] bug,目前csv缺失pct_of_yesterday_avg,可根據"@股號D.csv"快速取得資料

### 待完成項目

- [ ] 實現其他訂閱回應（如 Watchlist、StockTick 等）的字典格式轉換
- [ ] 完善大戶/散戶佔比分析算法
- [ ] 實現日成交量預估邏輯
- [ ] 添加 Web UI 顯示報價和分析結果
- [ ] 支持多股票實時監控

### 相關文檔

- 參考: 元大證券OneAPI_Python使用說明.pdf (第 22 頁起)
- 參考: IO_Doc 資料夾中的各項回應說明
