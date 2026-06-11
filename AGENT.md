# OneAPI — AI Agent 工作指南

本文件供Agent 在本 repo 內開發、除錯、重構時遵循。**修改前請通讀`readme.md`與agend.md,為節省上下文,先不管 `PRD.md` 與 `SPEC.md`。**
回應語言：與使用者溝通使用**繁體中文**。程式碼、註解、commit message 維持繁體中文。
請依agent為主,ai的memory存在失憶,反覆相同問題改來改去,改了A錯了B,修改B,又錯了A,我以為你懂了,但你卻失憶

---

## 1. 專案概述

元大證券 OneAPI 的 Python 量化交易分析系統，透過 pythonnet 橋接 YuantaOneAPI.dll (C#)，取得台股即時五檔報價，進行 CSV 持久化、技術指標計算、Web 監控面板、K 線圖表分析與 AI Agent 分析。

**文件基準**：*優先處理`YuantaAPI_Pythonnet.py與web_dashboard.py`為了節省上下文用戶確認後才,修改* `cStocks.py`。

---

## 1.1 已實作 vs 未實作（速查）

| 已實作 | 未實作 |
|--------|--------|
|YuantaAPI_Pythonnet.py：即時報價訂閱、CSV 輸出（5 秒）持久化|資料尚有 error 參考 \error\error.log 資料夾的error.log及附圖|
|web_simulation.py：5秒級別的（觀察 web_dashboard 與 CSV 的一致性）| tool 回測（觀察 web_dashboard 與 CSV 的一致性）|
|run.py  |追加自動啟動YuantaAPI_Pythonnet.py|避免雙開,# 自動排程：交易日 08:30 自動啟動 run.py |

---

## 2. 重要原則

1. **不要移除已標記 ✅ 的功能**；不確定是否影響既有行為時，先與使用者確認。
2. **最小改動**：只改與任務相關的程式；勿順手重構無關模組。
3. **勿提交密鑰**：`.env`、API key、ngrok、accountEvn 設定等勿寫入 commit。
 **cStocks.py 優先級較低**：先處理 YuantaAPI_Pythonnet.py 與 web_dashboard.py 的問題，cStocks.py 待 dashboard 完善後再處理。

---

## 3. 目錄與檔案職責

| 路徑 | 用途 | Agent 注意 |
|------|------|------------|
|YuantaAPI_Pythonnet.py：即時報價訂閱、CSV 輸出（5 秒）持久化|主程式|api相關單位股,寫入csv 價量單位都是股| 修復盤中預估量（待辦）,確保csv持久化單位是股|
| web_simulation.py：5秒級別的（觀察 web_dashboard 與 CSV 的一致性）| 觀察 web_dashboard 與 CSV 的一致性 |量價顯示單位是張,確保csv持久化單位是股|設計tool回測（觀察 web_dashboard 與 CSV 的一致性）,已知bug參考路徑error|
| `PRD.md` / `SPEC.md` / `README.md` | 文件 | 功能變更時同步更新 README.md後,才能github |
| `requirements.txt` | 相依版本 | 含 Pillow；`mplfonts init` 需安裝後手動執行 |
| error|說明附圖|不一定按error list順序,先處理agent認為容易或關鍵重點 |

---

## 4. 類別關係（修改時對照）

```
*YuantaAPI_Pythonnet.py* 透過Pythonnet引用YuantaOneAPI.dll
StockQuoteState(code, name, price, volume, bid_price, ask_price, timestamp)
    └── 實時訂閱 → CSV 持久化（5秒）
*Web Dashboard — 即時多股監控畫面 (Flask + SSE)*
DashboardApp
    └── 讀取 CSV → 更新儀表板（秒級）
```

## 5. 關鍵資料規格

- **CSV 單位**：API 收到的值**不除以 1000**依收到的值合併實務需求持久化保存於 CSV 以「股」為單位。顯示時才 ÷1000 轉為「張」。
- **市場排程**：`pre_open` (09:00 前) → `trading` (09:00-13:30，每 5 秒寫 CSV) → `matching` (13:30後-14:30，暫停 CSV) → `closed` (14:30+，寫入日總結後停止)
- **昨收參考價來源**（web_dashboard 顏色基準）：`stock_ref.json` (API) → `@stockID.csv` 最後一筆 close_price → 今日開盤價
- **watchlist.json**：自選股設定，支援多組自選股（自選股1/2/3），dashboard 可切換,增刪改查
- **stock_names.json**：股票代號 ↔ 公司名稱對照表（~1979 筆），可從 TWSE/TPEx 自動更新
- **accountEnv.json**：帳號密碼設定，已 gitignore，不可提交

---

## 6. 測試與驗證清單

執行：

```bash
pip install -r requirements.txt
python run.py #開盤日
python sim_run.py #模擬器,非開盤日
```

---

## 7. 已知問題/代辦 list（Agent 可優先修）

## 驗證中: 6/11驗證中,⛝ 表示已知還有問題,Agent修改後,務必讓sub-agent驗證,確認修復後再打勾✅,如果修了A又錯了B,請先確認A的修改是否有影響到B,如果有,請一起修復A和B,如果沒有,請回報給我,讓我知道你已經理解了這個問題的關聯性,避免下次再犯同樣的錯誤

- ⛝run.py 自動啟動失效,盤前手動,run.py → v2.2 啟動後log一推亂碼,不曉得跟後面的新增漲停股亂碼有關
- ⛝ pe/pb/peg除了新增漲停股外其他已穩定持有顯示值, → v2.2:但3個值都與app誤差頗大,我覺得算法可能?建議修改時,一起把下面提到的進階版考慮進去
- ⛝ 9:49 2330估量已改進,但仍有誤差 → v2.2: WatchlistAll byTemp 29 total_in/out/vol 已 ×1000（張→股）， 10:00以前的權重可能太高,導致+-變化都被放大,除此之外平滑度(速率)微調目前感覺較激進.尤其9:30前,一下子乎正乎負
- 💬 09:18:2330估量縮11.822%,實際約16% → 9:24 2317估量縮6.8,實際約29,9:26 2344 +109%,實際約(20%) ;09:48:2330估量+38.4%,實際約-20% → 9:24 2317估量縮21.9,實際約09:18:2330估量縮11.822%,實際約16% → 9:24 2317估量縮6.8,實際約29,9:26 2344 +109%,實際約20% ,9:26 2344 +109%,實際約 20%, 9:29 2354 -55%實際約-39
- ⚠️ 盤中預估量計算仍有改善空間 → 核心公式未改（曲線70%+速率30%），因實際總量/比率仍不完整，待累積量修正後再觀察
- ✅ 個股右上角的成交總額/總量會全部變成x → v2.2: cum_vol 改用 total_in+total_out（股），cum_deal_amount改用 cum_vol×close_price
- ⛝ 盤中新增亮燈漲停的6174各股
- ⛝ 漲跌停判斷：需執行 fetch_daily_close.py ? 我新增亮燈漲停的6174並執行 stock_ref.json 後,才見亮燈,但股名亂碼如圖error/亂碼6174.html ,可能json的關係, 因新增時看到的就是亂碼, pe/pb/peg 都會-- 有盤中預估量但沒% 可能沒有同時更新相關 json ,後來我把它移除了,再度添加亮燈漲停ok,但問題依舊.
- ✅ 2356一值維持70元與實際不符 → v2.2: _norm() 四份拷貝改 `round(p/10000.0, 2)`，保留小數精度✅
- ⚠️💬 百元內個股小數點價位處理（權證低於0.5元跳動0.01元）→ 門檻已改 `>=10000` 涵蓋≥1元股票；<1元極低價股仍需個別處理?無法輸入測試權證為6位數
- ✅盤中成交筆數經常會回退到5。盤中外盤則會回退到0張。ma10時而會變成 -- ,似乎跟上面提到的 -- 導致容易閃爍有連動關係✅

# todo 6/11

- ✅ run.py 亂碼 → v2.3: subprocess 傳入 PYTHONIOENCODING=utf-8 + PYTHONUTF8=1
- ✅ 漲停股股名亂碼(6174) → v2.3: stock_names.json 修復+清除12筆損壞條目; _save_stock_ref_json 自動修復
- ✅ pe/pb/peg 全數顯示 → v2.3: _FUND 常數+_compute_pe_pb_peg 自算; 盤後PE移到close_price覆蓋後計算
- ✅ PE改用forward_eps優先 → v2.3: _compute_pe_pb_peg pe_source='forward'/'trailing'
- ✅ PE上修紅/下修綠 → v2.3: cardHTML pe_revision='up'/'down'視覺標籤
- ✅ BPS全數從真實資產負債表更新 (12檔) → v2.3: fundamentals.json
- ✅ 6412 PE 4.3→16.7 (舊demo假數據20.0→真實TTM 5.21) → v2.3
- ✅ API每天13:31崩潰根因確認 → v2.3: _display_quote_info cp950中文崩潰; 外包try/except
- ✅ 自選股4-6碼+英數字 → v2.3
- ✅ 0062可刪除 → v2.3
- ⛝ 元大富櫃50(006201)可加入但後端驗證仍擋 → 需後端驗證邏輯配合
- ⛝ 預估量權重調校 → 方案已設計(/plans/nested-percolating-zebra.md)待實作
- ⛝ 新股auto-fetch financial data → 方案已設計待實作

# todo 6/12 明日驗收重點

開盤前:
- [ ] 啟動 `python -B run.py`（PYTHONDONTWRITEBYTECODE=1）
- [ ] 確認 .api_active 出現 + CSV 產出
- [ ] 確認 Dashboard http://localhost:5000 可訪問

盤中驗收:
- [ ] API 是否在 13:31 崩潰（已修 _display_quote_info cp950 + 外包 try/except）
- [ ] PE: 有forward_eps的股票(2330/2317/2344/2610/2609) PE顯示紅色+上修標籤
- [ ] PE: 無forward_eps的股票 PE顯示灰色(muted)
- [ ] PB: 所有12檔應有值(已從真實BPS計算)
- [ ] PEG: 有growth的股票應有值
- [ ] PE/PB/PEG 不閃爍（_FUND常數+_LAST_KNOWN MA persistence）
- [ ] 成交總額/總量 正確顯示（盤中cum_vol=in+out, 盤後actual_vol覆蓋）
- [ ] 新增股票時 fundamentals.json 自動補佔位
- [ ] 新增股票時股名不再亂碼

盤後(14:30):
- [ ] @stockID.csv 日總結寫入（API需存活到14:30）
- [ ] 盤後 PE/PB/PEG 使用 @csv 收盤價計算
- [ ] 盤後 成交總額/總量 使用 actual_vol
- [ ] 執行 fetch_daily_close.py 校正

已知仍待修(非今日重點):
- ⛝ 預估量開盤30分過激（方案已設計）
- ⛝ 新股auto-fetch financial data（方案已設計）
- ⛝ 006201 ETF後端驗證
- ⛝ 6檔eps_ttm仍為推估值(2344/2356/2609/2610/2330/6412待逐季EPS確認)

error\error.log

## 8. 設定檔

- `watchlist.json` — 自選股分組（stocks + futures）
- `stock_names.json` — 全台股名對照
- `stock_ref.json` — API 查詢的昨收/漲停/跌停參考價
- `{code}_drawings.json` — cStocks 繪圖物件持久化
- `{code}_settings.json` — cStocks 圖表參數持久化
- `holidays.json` — 休市日清單（格式：`["2026-01-01", ...]`）
- `.claude_agent.env` — Agent ID 註冊表（gitignored）

---

## 9. 文件同步義務

| 變更類型 | 更新檔案 |
|----------|----------|
| 新功能／完成待辦 | `PRD.md` 狀態、`README.md` 功能列表 |
| 公式、欄位、JSON、事件 | `SPEC.md` |
| Agent 流程、禁忌、目錄 | `AGENT.md`（本檔） | github前,請把修改重點寫入AGENT.md本檔11.修訂紀錄,詳細細節紀錄在changelog.md以利確認追踪,或bug發生時回退

---

## 10. 溝通模板

向使用者報告時建議包含：

1. 改了什麼、為什麼（一句話目標）
2. 如何驗證（命令 + 目視點 + tool）
3. 是否影響  CSV

---

## 11. 修訂紀錄

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0 | 2026-05-24 | 初版 |
| 1.1 | 2026-05-24 | 對齊現有 `cStocks.py`：實作速查、S/R  |
| 1.2 | 2026-05-24 | S/R、平移條件、Pillow |
| 1.3 | 2026-05-26 | 修復：X軸重疊、重複slice、選取換色、emoji方塊改純文字、載入圖選取、按鈕覆蓋、Ctrl+Y縮放、備註工具、RGBA調色、盤中預估量 |
| 1.4 | 2026-06-02 | 修復：修復昨日的 CSV 數據——將價格標準化（/10000）並使用每日匯總格式,修正：台灣色彩慣例，負成交量保護，昨日價格正常化,修復：修復昨日的 CSV 數據——將價格標準化（/10000）並使用每日匯總格式 |
| 1.5 | 2026-06-03 | 修復：int32 溢位 — 新增 `to_uint32()` 防護 API 回傳負值成交量；僵屍 `.api_active` 旗標偵測與自動清除；`@stockID.csv` 日總結重建（10 檔）、`yesterday/` 備份建立、`stock_ref.json` 擴充 |
| 1.6 | 2026-06-03 | 修復：`run.py` 雙開防護 — Kernel32 `OpenProcess` 檢查 PID 存活，拒絕重複啟動避免 DLL 鎖定當機；`web_dashboard.py` 漲跌停誤判 — `_get_limit_prices()` 驗證 `up_price > 昨收 > down_price`，不合法自動改用計算值 |
| 1.7 | 2026-06-03 | 修復：CSV 成交量全為 0 — Watchlist flags 4/6 累積量取代失效的 byTemp 29，內外盤 ×1000 張→股，5 秒區間 delta 快照分離；OTC 股票 MarketNo 自動判斷（`_stock_market_no()`）；`GetUInt()`→`GetInt()` 對齊 IronPython；`build_save_record` 放寬條件納入五檔推斷 OHLC；CSV 欄位位移修復 |
| 1.8 | 2026-06-03 | agent說已修復但後來檢查csv資料發現有誤,這表示memory沒有清楚紀錄.又做白工,又燒token連續在相同問題繞圈 `fetch_daily_close.py` CSV 去重永久失效 — BOM（`﻿`）導致 DictReader 第一欄位名變成 `日期` ≠ `日期`，`r.get("日期")` 永遠取得空字串；讀取編碼從 `utf-8` 改為 `utf-8-sig` 自動去除 BOM；清理所有 `@stockID.csv` 重複資料,完全解決問題前這件事不該做,反而把某些正確資料抹除,重點是memory沒有把反覆錯誤的點記起來 |
| 1.9 | 2026-06-04 | 價格單位統一：`build_save_record()._norm()` 將所有價格正規化為「元」（整數），消除 5 秒 CSV raw/normalized 混雜；`_save_stock_ref_json()` 英文欄位統一為中文；`_write_daily_summary()` total_in/out 改用 state 累積值；`fetch_daily_close.py` 保留既有 total_in/total_out；預估量改分段時間權重曲線 + 動態投影（actual_cum/progress）；昨均% 改增/縮顯示；`_intraday_volume_progress` 移至 class 外部修復類別中斷；專案架構獨立為 `CODE_MAP.md` |
| 2.0 | 2026-06-05 | **Dashboard 全面升級**: 0.5s snapshot 系統（469x 加速）、漲跌停計算修復、全部價量紀錄三 bug、自選股 UI 增刪改查、連線狀態監控（SSE dot + 滯後警告 + 卡片紅框）。**資料工具**: fetch_daily_close.py 日期偵測修復（不再標記錯誤日期）、@stockID.csv/yesterday/stock_ref.json 全修復、resample_1min.py（5 秒→1 分 K）、update_market_cap.py（TWSE/TPEx 市值排名+PE/PB）、update_financials.py（近四季 EPS+PEG）、fetch_analyst_eps.py（法人預估聚合+trimmed mean+動態 PEG）。**避險**: hedge_dashboard.py（期現貨基差+理論價+動態門檻+大戶動向+個股期）。**啟動**: run.py v2（API subprocess + 盤前檢查 + PEG 更新）。**預估量**: v2 速率加權（固定曲線×0.7 + 5分鐘速率×0.3） |
| 2.1 | 2026-06-08 | **啟動穩定性修復**: run.py API subprocess stdout 阻塞（加入 reader thread + .api_active 驗證 30s timeout）、snapshot 原子寫入（tmp→replace 避免半寫入）、成交總額/總量改累積值、漲跌停優先 API 值、盤中新增個股自動重訂、PE/PB/PEG 涵蓋全部自選股、昨日量載入編碼修正。詳見 CHANGELOG.md |
| 2.2 | 2026-06-09 | **價格精度+累積量單位+PE/PB/PEG修復**: _norm() 四份拷貝改 `round(x/10000.0, 2)` 保留小數（修復百元內股票如 2356 整數化）；cum_vol 改用 in+out（修復成交總額/總量變 x）；WatchlistAll byTemp 29 值 ×1000（張→股）；`read_snapshot()` 財務數據存取修正（flat dict vs nested）；run.py 加入 CSV 產出二次驗證；stock_ref.json 補齊 2354/9907；定期 300s 刷新參考價。詳見 CHANGELOG.md |
| 2.3 | 2026-06-10 | **PE/PB/PEG 自算系統**: 新建 `fundamentals.json` 為唯一來源（eps_ttm/bps/growth/forward_eps），Dashboard `_FUND` 啟動載入一次，`_compute_pe_pb_peg()` 以即時價自算不閃爍。盤後 PE/PB/PEG 改到 @csv 覆蓋 close_price 後計算。盤後成交總額/總量用 actual_vol 覆蓋。MA persistence 防閃。自選股改 4-6 碼。0062 可刪除。API crash traceback→error.log。訂閱/snapshot 加 try/except 防崩。補齊 6122/6123/8936/9907/2354 真實財務數據。詳見 CHANGELOG.md |
| 2.4 | 2026-06-11 | **PE forward_eps優先+上下修顏色+BPS全真實+API cp950崩潰修復**: PE優先法人預估(forward_eps)，上修紅字/下修綠色標籤。12檔BPS全從26Q1資產負債表更新。6412 PE修復(20.0假數據→5.21真實TTM)。API崩潰根因確認(_display_quote_info cp950中文崩潰)。stock_names修復6174亂碼+清除12筆損壞+補入ETF。新股fundamentals自動佔位。run.py傳入utf-8環境變數。詳見 CHANGELOG.md |

## 請agent 協助確認獨立生成 code map ,代補充 *.json , 其他有效*.py

每日開盤前兩件事：
fetch_daily_close.py  TPEx/OTC OpenAPI : 前日收盤數據校正或當日晚上執行它 — 用官方數據覆蓋今日收盤價和總量,
tomorrow-premarket-tasks.md 可恢復上下文,位於C:\Users\gates\.claude\projects\D--workCS-TEST-2026-YuantaOneAPI-Python-YuantaOneAPI-Python\memory\tomorrow-premarket-tasks.md
repair_daily_summary.py — 從 5 秒 CSV 重建日總結檔，修正格式不一致、int32 溢位歷史資料、缺少 yesterday/ 備份
`stock_ref.json`: 自選股擴充code檔數，要同時補齊參考價,例如增加 6412/6122/6123/8936
Web Dashboard: `web_dashboard.py` — Flask + SSE 即時多股監控畫面
run.py 防止雙開,startup api/Dashboard 開盤日
sim_run.py 防止雙開,startup api/Dashboard 非開盤時,增加資料模擬器

---

## 12. 2026-06-09 教訓 — 兩大隱形殺手

### 12.1 Python `.pyc` 快取毒害

**現象**：修改 `.py` 原始碼後重啟，`curl` 確認 HTML 正確，但瀏覽器仍顯示舊版。三個瀏覽器+無痕+Ctrl+Shift+R 全部無效。

**根因**：Python 直譯器優先載入 `__pycache__/*.pyc`。原始碼被編輯但 `.pyc` 未清除 → 直譯器執行舊版程式碼。`curl` 測試走 HTTP 層，看到的是 Flask 渲染結果；但實際執行的模組是舊版。

**強制規則**：

```
每次修改 .py 後 → rm -rf __pycache__/ → 重啟程序
啟動命令固定使用 python -B run.py（禁止寫入 .pyc）
加入版本標記（如 <title>v2.2-0609</title>）快速確認
```

### 12.2 CSS 超長單行被瀏覽器截斷

**現象**：`stat-row` div 在 HTML 中存在、資料正確，但成交總額/總量行不可見（高度為 0）。

**根因**：`.stat-row`、`.stale`、`.status-dot`、`.status-dot.live`、`.status-dot.stale`、`.status-dot.dead` 全部擠在一行（~500 字元）。瀏覽器 CSS 解析器截斷此超長行，最前面的 `.stat-row{...}` 被犧牲 → `display:flex` 從未套用。

**強制規則**：

```
每個 CSS class 獨立成行
關鍵 class 放在 style 區塊最前面（第 2-3 行）
修改後用瀏覽器 DevTools → Computed tab 確認 CSS rule 被套用
```

### 12.3 修改完整性檢查

**現象**：宣稱「已修復」但實際只修了部分（修 A 漏 B/C/D）。

**強制規則**：

1. `_norm()` 等函數有**四份獨立拷貝** — 任何修改必須四處同步
2. 修改資料回傳格式時，**搜尋所有呼叫方**確認存取路徑一致
3. 端到端驗證：API → state → snapshot → `read_snapshot()` → SSE → 前端 JS → 瀏覽器渲染
4. 單位鏈追溯：每個環節確認元/股 vs 張/千元
5. 修改後用 sub-agent 獨立驗證（避免自己改自己驗的盲點）
