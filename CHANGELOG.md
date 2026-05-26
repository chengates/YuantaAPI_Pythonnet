# CHANGELOG - YuantaAPI_Pythonnet.py

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
- **StockQuoteState.__init__()** 自動呼叫 `_load_yesterday_data()`

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
