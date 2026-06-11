# CHANGELOG - YuantaAPI_Pythonnet.py

## [2026-06-11] — PE forward_eps + 上修下修顏色 + BPS全面更新 + API cp950崩潰修復

### Fixed
- **PE 改用 forward_eps 優先**: `_compute_pe_pb_peg()` 回傳值擴充（pe_source/pe_revision），PE = forward_pe 優先，無法人預估時降級 eps_ttm。cardHTML 紅色表示使用法人預估，灰色為近四季 EPS
- **上修/下修顏色標籤**: forward_eps > eps_ttm → 紅色「上修」；forward_eps < eps_ttm → 綠色「下修」。台灣股市慣例（紅漲綠跌）
- **BPS 全數真實更新**: 12 檔自選股從 26Q1 資產負債表更新（先前 8 檔為 market_cap 推估不準確）
  - 2330: 227.14→227.2, 2317: 127.39→127.12, 2344: 25.9→25.92, 2354: 75.98→75.6
  - 2356: 20.47(吻合), 2609: 95.0→94.2, 2610: 16.86→16.84, 6412: 36.14→36.13
- **6412 eps_ttm 修正**: 舊 demo 假數據 20.0 → 真實 TTM 5.21（26Q1+25Q4+Q3+Q2），PE 從 4.3 恢復為 16.7
- **API 每天 13:31 崩潰根因**: `_display_quote_info()` print 中文字在 cp950 console 觸發 `UnicodeEncodeError`（字元「額」無法編碼）→ show() 崩潰退出。`error/error.log` 確認 traceback
- **API 崩潰防護**: `_display_quote_info()` 強制 `sys.stdout.reconfigure(utf-8)`；show() 主循環兩處 `_display_quote_info` + snapshot 寫入 + 訂閱重訂 全部外包 try/except
- **run.py 編碼**: API subprocess 傳入 `PYTHONIOENCODING=utf-8` + `PYTHONUTF8=1` + `-X utf8`
- **stock_names.json**: 修復 6174 亂碼（安��→安碁科技），清除 12 筆損壞條目，新增 006201/00631L/00632R/006208 等 ETF
- **股名編碼防護**: `_save_stock_ref_json()` 自動從 stock_names.json 修復 pythonnet 編碼損壞的股名
- **自選股驗證**: 從 `isdigit()+len==4` 改為 `alphanumeric+4<=len<=6`（支援 00980A 等權證）
- **新股 fundamentals 佔位**: `_ensure_fund_placeholder()` 加入新股票時自動建立 fundamentals.json 佔位，PE/PB/PEG 顯示 `--` 而非缺失
- **6123 基本面備註**: 26Q1 EPS +18.6% YoY 未衰退（年度 -25.2% 但單季反轉），Google AI 雲端代理+3D列印無人機+Anthropic AI 代理授權

### Changed
- `web_dashboard.py`: `_compute_pe_pb_peg()` 回傳 6-tuple；PE/PB/PEG cardHTML 紅色/灰色+上修下修標籤；`_ensure_fund_placeholder()` 補 _FUND 佔位；`_empty_card` 補 pe_source/pe_revision
- `YuantaAPI_Pythonnet.py`: `_display_quote_info()` utf-8 強制；show() 主循環 3 處 try/except；`_save_stock_ref_json()` 股名修復；例外寫入 error.log
- `run.py`: API subprocess 加入 utf-8 環境變數 + `-X utf8` 旗標
- `stock_names.json`: 修復 6174 + 清除 12 筆亂碼 + 新增 ETF 代碼
- `fundamentals.json`: BPS 全數真實更新；6122 growth 確認；6412 eps_ttm/forward_eps 修正；6123 備註擴充

### Removed
- 舊 `stock_financials.json` / `analyst_eps.json` / `market_cap.json` 不再作為 PE/PB/PEG 來源（僅 fundamentals.json）

## [2026-06-10] — PE/PB/PEG 自算系統 + fundamentals.json + API 穩定度

### Fixed
- **PE/PB/PEG 全數自算**：新增 `fundamentals.json` 為基本面唯一來源（eps_ttm/bps/eps_growth_pct/forward_eps），Dashboard 啟動時載入一次存入 `_FUND`，盤中以即時價自算 PE=close/eps, PB=close/bps, PEG=PE/|growth|。不再需要每日跑 `update_financials.py`/`update_market_cap.py`/`fetch_analyst_eps.py` 來更新 PE/PB/PEG
- **盤後 PE/PB/PEG 全滅**：`_compute_pe_pb_peg()` 移到 `@stockID.csv` 覆蓋 close_price **之後**才執行，確保盤後使用正確收盤價計算
- **盤後成交總額/總量變極小值**：`read_snapshot()` 盤後新增 actual_vol 覆蓋 deal_volume/deal_amount，不再顯示 5 秒 interval delta (e.g. 2330 從 88 股 → 38,847 張)
- **PE/PB/PEG 盤中閃爍**：`_FUND` 模組級常數，每 0.5s poll 不再重複讀取三個 JSON 檔，永不閃爍
- **MA5/MA10 閃爍為 "--"**：新增 `_LAST_KNOWN` dict 保留上次有效值，API 暫時掉失時沿用上一筆
- **0062 無法刪除**：cardHTML early return 路徑（無成交價時）補上移除按鈕
- **4碼限制無法加入ETF/權證**：自選股新增驗證從 `len==4` 改為 `4 <= len <= 6`
- **API show() 崩潰無 traceback**：except block 加入 `traceback.format_exc()` 並寫入 `error/error.log`
- **5秒/60秒重訂閱崩潰**：SubscribeFiveTick 和四種全重訂外包 try/except
- **snapshot 寫入崩潰**：`_write_snapshots()` 外包 try/except
- **fundamentals.json**：補齊 6122/6123/8936/9907/2354 真實財務數據（TTM EPS/BPS/YoY growth）

### Changed
- `web_dashboard.py`: `_load_financials()` → `_load_fundamentals()` + `_compute_pe_pb_peg()`; 新增 `_FUND`/`_LAST_KNOWN` 模組常數; PE/PB/PEG 移至 close_price 覆蓋後計算; 盤後 deal_volume/deal_amount 以 actual_vol 覆蓋; 4-6碼驗證; MA persistence
- `YuantaAPI_Pythonnet.py`: show() crash traceback→error.log; 訂閱/snapshot 外包 try/except
- `run.py`: API subprocess 固定加 `-B` 旗標
- `fundamentals.json`: 新建，13 檔自選股基本面

### Removed
- 不再依賴 `stock_financials.json` / `analyst_eps.json` / `market_cap.json` 來計算 PE/PB/PEG（僅 fundamentals.json 為來源）

## [2026-06-09] — 價格精度 + 累積量單位 + PE/PB/PEG 修復

### Fixed
- **價格精度（百元內股票被整數捨入）**: `_norm()` 四份拷貝均用 `round(p/10000.0)` 整數捨入，造成 50-100 元股票（跳動 0.1 元）失去小數位精度（如 2356 永遠顯示 70.0 而非 70.2/70.4）。改為 `round(p/10000.0, 2)` 保留 2 位小數。同時門檻從 `> 100000` 改為 `>= 10000`，覆蓋所有 ≥1 元的股票。影響四處：`build_save_record()`, `_write_daily_summary()`, `_write_snapshots()`, `_load_yesterday_data()`
- **成交總額/總量變成「x」**: `_write_snapshots()` 的 `cum_vol` 使用 `state.total_volume`，但 WatchlistAll byTemp 29 的 `total_vol` 單位是「張」且未 ×1000 轉換，而 `total_in/out_volume` 已由 Watchlist flags 4/6 正確轉為「股」。修正為優先使用 `total_in_volume + total_out_volume`（可靠的股值），並將 `cum_deal_amount` 改為 `cum_vol × close_price` 計算
- **WatchlistAll byTemp 29 單位轉換**: `total_in/total_out/total_vol` 從 API 取值後未 ×1000（張→股），與 Watchlist flags 4/6 已轉換的值不一致。修正 `OnWatchListAllData` callback 中的賦值為 `total_in * 1000`、`total_out * 1000`、`total_vol * 1000`
- **PE/PB/PEG 永遠無值**: `_load_financials()` 回傳 flat dict `{code: {pe, pb, peg}}`，但 `read_snapshot()` 用 `fin.get("stocks", {})` 存取（expects nested `{stocks: {code: {...}}}`），永遠取得空 dict。修正 `read_snapshot()` 直接使用 `fin[stock_id]`
- **run.py API 啟動驗證不確實**: `.api_active` 原本在登入檢查前就建立，run.py 看到旗標即認為啟動成功但實際登入可能失敗。修正為登入成功後才建立 `.api_active`。同時 run.py 新增 CSV 產出二次驗證（等待 20s 確認 2330/2317.csv 有更新）
- **stock_ref.json 缺 2354/9907**: 補齊參考價（含漲停/跌停），確保新股有顏色基準和漲跌停判斷
- **盤中新增個股參考價更新**: 60 秒重訂週期新增每 300 秒定期呼叫 `ReadWatchListAll_api()`（不限於 mtime 變更時），確保新股和現有股票的參考價持續更新

### Changed
- `YuantaAPI_Pythonnet.py`: `_norm()` ×4 改用 `round(x/10000.0, 2)` + 門檻 `>= 10000`；`_write_snapshots()` cum_vol 改用 in+out；WatchlistAll byTemp 29 值 ×1000；`.api_active` 移到登入後建立；新增 `last_ref_price_time` 定期刷新參考價
- `web_dashboard.py`: `read_snapshot()` 財務數據存取從 `fin["stocks"][stock_id]` 改為 `fin[stock_id]`
- `run.py`: 新增 CSV 產出驗證（`.api_active` 出現後 20s 內確認 CSV mtime）；`_normalize_price()` 已使用 2 位小數（v2.1 已修正）
- `stock_ref.json`: 新增 2354（鴻準）、9907（統一實）參考價

## [2026-06-08] — 啟動穩定性 + 資料一致性修復

### Fixed
- **run.py API subprocess stdout 阻塞**: `stdout=PIPE` 無人讀取導致子程序緩衝區滿後阻塞，CSV 無法產出。新增 background reader thread + `.api_active` 旗標驗證（最多等 30s），確保 API 實際啟動
- **PE/PB/PEG 僅 2 檔有值**: `analyst_eps.json` 只有 2330/2317；`update_financials.py` 只處理 `_QUARTERLY_EPS` 中的 15 檔。修正為自動涵蓋所有自選股，無 EPS 資料時從 PE 反推估算，`run.py` 盤前檢查自動執行 `update_financials.py`
- **Dashboard 成交總額/總量消失**: snapshot 的 `deal_amount`/`deal_volume` 為 5 秒區間 delta（無成交時為 0）。新增 `cumulative_deal_volume` + `cumulative_deal_amount` 欄位（API 64-bit 累積值），dashboard 優先使用累積值
- **Snapshot 原子寫入**: `_write_snapshots()` 直接寫入 JSON → dashboard 同時讀取可能讀到半寫入檔案，導致數值瞬間跳動。改為 `tmp → os.replace()` 原子操作
- **漲跌停判斷降級順序**: `_get_limit_prices()` 之前直接無視 API 提供的 up_price/down_price（已考量除權息調整）。修正為優先使用 API 值（驗證 up > yst > down 合理性），僅無效時降級到計算值
- **盤中新增個股無 CSV**: Dashboard UI 新增股票後 API 程序無感知。`load_watchlist_config()` 改為自動偵測 mtime 變更；60s 重訂週期偵測 watchlist.json 變更並自動訂閱新股 + 讀取參考價
- **昨日量載入編碼**: `_load_yesterday_data()` 使用 `pd.read_csv()` 無指定 encoding，可能因 BOM 導致欄位錯位。加入 `encoding="utf-8"` + 日總結格式單列值保護

### Changed
- `YuantaAPI_Pythonnet.py`: `_write_snapshots()` 改用原子寫入；`_load_yesterday_data()` 加入編碼與格式判斷；`load_watchlist_config()` 支援 mtime 自動重載；60s 重訂週期偵測新股票
- `run.py`: API subprocess 啟動加入 stdout reader thread + `.api_active` 等待驗證（30s timeout）；新增 `_run_financials_update()` 盤前自動執行
- `web_dashboard.py`: `read_snapshot()` 優先使用 `cumulative_deal_volume`/`cumulative_deal_amount`；`_get_limit_prices()` 優先使用 API up_price/down_price
- `update_financials.py`: `build_financials()` 自動涵蓋自選股清單；無 PE/PB 時從已知 EPS 估算
- `snapshot_writer.py`: 改用原子寫入

## [2026-06-05] — Dashboard 全面升級 + PEG 系統 + 避險儀表板

### Fixed
- **fetch_daily_close.py 日期錯亂**: TWSE OpenAPI (`STOCK_DAY_ALL`) 不回傳日期，15:00 前回傳前日資料卻標記為今日，導致 @stockID.csv 被寫入錯誤日期。新增 `_detect_twse_data_date()` / `_detect_tpex_data_date()` 自動偵測 API 實際日期後才寫入
- **@stockID.csv 全修復**: 06-03/06-04 開盤價=0 補齊官方數據；06-05 被 fetch_daily_close.py 誤覆蓋的資料從 TWSE STOCK_DAY API 還原；@6412.csv 日期偏移完全重建
- **yesterday/ + stock_ref.json**: 10 檔全修正為正確 06-05 收盤資料，補齊 up_price/down_price（±10% 計算）
- **漲跌停燈號**: `_get_limit_prices()` 不再依賴 stock_ref.json 的過期 API 值，改為 `昨收 × 1.10 / 0.90` 直接計算
- **全部價量紀錄三 bug**: (1) 負值 — records table 改用 `vol()` 函數 + `Math.max(0, r.amt)` 防護 (2) 展開後收合 — `_recsOpen` 狀態嵌入 cardHTML，0.5s 刷新不再閃爍 (3) 盤後資料空 — 收盤後 fallback 到 CSV 讀取完整 records
- **PE/PB 未寫入 market_cap.json**: `build_rankings()` 存入 stocks dict 時遺漏 PE/PB 欄位，修正 pass-through
- **web_dashboard.py PEP/PB/PEG 語法錯誤**: 財務資料載入時 `_records` 誤放在 dict 外，修正結構

### Added
- **Dashboard 0.5s 快照系統**: API 端 `_write_snapshots()` 每 0.5s 寫入 `snapshot/{stock_id}.json`（~1KB），dashboard 讀取加速 **469 倍**（0.1ms vs 56.2ms），poll interval 2s→0.5s
- **snapshot_writer.py**: 獨立 snapshot 產生器，從 CSV 讀取寫入 snapshot/，供 sim_run 或盤後測試使用
- **盤中預估量 v2**: 固定曲線投影 + 5 分鐘速率加權（開盤 50:50，盤中 70:30）；新增 `total_volume` 備援（OTC/Watchlist 掉線時）
- **run.py v2**: 每日一站式啟動 — 雙開防護 → 交易日判斷 → 盤前資料檢查（@stockID.csv + stock_ref.json + PEG）→ 啟動 API subprocess → 啟動 Dashboard；關閉時自動清理 API 子程序
- **resample_1min.py**: 5 秒 CSV → 1 分 K 轉換工具，對齊 cStock.load_data() 格式（日期,OHLCV）。支援單股/全股/指定日期/多日範圍。實測: 2330 產出 271 根完整交易日
- **自選股 UI 增刪改查**: POST `/api/watchlist/add` + `/api/watchlist/remove` + GET `/api/stock/search`。前端搜尋列 + 下拉建議 + 卡片移除按鈕。新增時自動執行 fetch_daily_close.py 補齊參考價
- **市值排名系統**: `update_market_cap.py` — 從 TWSE BWIBBU_ALL + STOCK_DAY_ALL + TPEx API 估算全市場市值排名。`market_cap.json` — TWSE 1078 檔 + OTC 5440 檔的排名/PE/PB/tier。`_detect_stock_type()` 優先使用市值排名，降級內建 0050 清單
- **連線狀態監控**: SSE 狀態 dot（綠/紅/灰燈）+ 資料滯後 >10 秒警告 + 卡片邊框變紅（>30 秒無更新）
- **避險儀表板**: `hedge_dashboard.py` 獨立 Blueprint（/hedge）— TXF 期現貨基差監控 + 理論期貨價（持有成本模型）+ 動態避險門檻（歷史標準差 ×1.5）+ 大戶動向（TAIFEX 前5/前10）+ 個股期貨避險
- **PE/PB/PEG 系統**: `update_financials.py` — 從 BWIBBU PE 反推 EPS + 近四季 EPS 計算 PEG。`fetch_analyst_eps.py` — 多來源聚合 + trimmed mean 20% 去極端值 + 動態 PEG。dashboard 卡片顯示 PE/PB/PEG（tooltip 顯示公式）。三層降級: `analyst_eps.json` → `stock_financials.json` → `market_cap.json`
- **stock_financials.json**: 近四季 EPS + 成長率 + PEG 快取
- **analyst_eps.json**: 法人預估 EPS（手動填入 → 自動計算 PEG）
- **CODE_MAP.md**: 全面更新 — 新增 resample_1min.py, snapshot_writer.py, hedge_dashboard.py, update_market_cap.py, update_financials.py, fetch_analyst_eps.py；常用指令速查表；資料流更新

### Changed
- `web_dashboard.py` DATA_INTERVAL: 2s → 0.5s；新增 `read_snapshot()` 優先讀取快照；`_get_limit_prices()` 改為計算式；`_detect_stock_type()` 整合市值排名；新增 PE/PB/PEG 顯示列
- `fetch_daily_close.py`: `update_stock_ref()` 同步寫入 up_price/down_price；`update_yesterday()` 日期格式 YYYYMMDD→YYYY-MM-DD
- `YuantaAPI_Pythonnet.py`: `show()` 新增 snapshot 計時器；`StockQuoteState` 新增 `_vol_snapshot` 預估量欄位
- `market_cap.json`: stocks dict 新增 pe/pb/close 欄位
- `watchlist.json`: futures 欄位預留期貨代碼空間

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
