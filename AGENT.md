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

## 驗證中: 6/9

- 💬run.py 啟動時,畫面顯示api已啟動,YuantaAPI_Pythonnet.py實際運作首筆會當機 → v2.2: .api_active 移到登入成功後才建立，run.py 加入 CSV 產出二次驗證? 9:00一比csv後,API就沒了,隨後api從起
- 💬 pe/pb/peg一樣光有label無顯示值 → v2.2: `read_snapshot()` 財務數據存取從 `fin["stocks"][stock_id]` 改為 `fin[stock_id]`（_load_financials() 回傳 flat dict 但被當成 nested dict 存取）? 6123 隨機消失,理論它不需要一直更新,一直更新也容易閃爍
- 💬 9:49 2330估量已改進,但仍有誤差 → v2.2: WatchlistAll byTemp 29 total_in/out/vol 已 ×1000（張→股），累積量正確性提升，預估量計算應更準確，但實際驗證需觀察今日盤中 ? 可能10:00以前的今日盤中都用收盤量當基準,導致全部都變量縮,更新過程會先出現 -- 導致容易閃爍
- 💬 9:55:2317估量縮22%,實際約39% → 同上，累積量修正後應改善，待盤中驗證? 同上,全部縮不應該
- ⚠️ 盤中預估量計算仍有改善空間 → 核心公式未改（曲線70%+速率30%），因實際總量/比率仍不完整，待累積量修正後再觀察
- ✅ 個股右上角的成交總額/總量會全部變成x → v2.2: cum_vol 改用 total_in+total_out（股），cum_deal_amount改用 cum_vol×close_price
- 💬 盤中新增各股9907,dashboard,成交價不會更新 → v2.2: stock_ref.json 補齊 2354/9907，定期 300s 呼叫 ReadWatchListAll 取得參考價，60s 重訂含新股 ? 猜可能因300s 呼叫 ReadWatchListAll 似乎每隔一段時間 全部價量紀錄會內縮變成,只有3筆-- 導致容易閃爍
- 💬 漲跌停判斷：6412 -10.11% → v2.2: 定期刷新參考價機制改善；若仍發生表示 stock_ref.json 昨收價過期，需執行 fetch_daily_close.py ? 我新增亮燈漲停的2327並執行stock_ref.json後,它還是沒有亮燈,後來我把它移除了,debug可參考相關csv.再度添加一樣沒亮燈,除此之外其 pe/pb/peg 都會--缺失
- ✅ 2356一值維持70元與實際不符 → v2.2: _norm() 四份拷貝改 `round(p/10000.0, 2)`，保留小數精度
- ⚠️💬 百元內個股小數點價位處理（權證低於0.5元跳動0.01元）→ 門檻已改 `>=10000` 涵蓋≥1元股票；<1元極低價股仍需個別處理?無法輸入測試權證為6位數

# todo 6/10

- error\0230僅 "2stocksWithPeg6123NoRefresh.html" 2:30盤後更新只有2330,2317有 peg ,其他都沒顯示, html 可觀察個股不同因素,其中6123上奇,因最後紀錄時間13:31:00我猜可能盤後交易0,被排除了,所以它除了 pb,pe,peg ,甚至總成交價量都被排除掉了
- 盤中成交筆數經常會回退到5。盤中外盤則會回退到0張。ma10時而會變成 -- ,似乎跟上面提到的 -- 導致容易閃爍有連動關係
- 自選股設限4碼會導致如006201 元大富櫃50無法加入，建議改4-6碼(有些etf為6碼,非全數字,如00980A,權證也是6碼)，（0062）可能已下市,可加入但一直等待資料,占用刪除位置導致無法刪除,目前是4位數字防呆,仍不足已驟校,追加改可自行刪除
- 個股商品逐比明細中的大單與分佈。 大單：顯示 tick 是否為大單或特大單 N>5,N 與每張單價掛勾,假設每股100元,5張=100*1000*5=50萬,若每股50元則 N=10,N 不可小於5也就是每股200元5張=100萬,成為基本單位。 分佈：顯示大小單金額所算出的百分比，像是特大單,大單,中單,小單 差額佔比。EX:
14:30:00 70.60 50,429 0 50,429 356028.74萬  深紅色表示特大單,用閾值千萬級別 & >N張,賣出改用深綠色
12:57:53 46.20 76 76 0 351.12萬  紅色表示大單,用閾值百萬級別 & >N張,賣出改用綠色
            淺紅色用閾值50萬級別 & >N張,賣出改用淺綠色
            小單白色不變
  差額佔比:顯示大小單金額所算出的百分比，像是特大單,大單,中單,小單 差額佔比。例如開盤至此
  10:30:20 小單:20%,中單:20%,大單:30%,特大單:30%
- 進階peg,試算.根據經驗,當Q2財報後peg,eps法人都已預估明年eps,股價也會提前反應,特別穩定成長股甚至反映更長未來,我要此dashboad於此時全部改用此條件,若上修用紅字;若下修用綠色字形,若無法取得,我會自行預估,根據eps成長率及稅後淨利率,月營收加上總經條件微調條權重(排除景氣循環股及季節性循環股,包含景氣指標:景氣對策信號,領先指標」、「同時指標」,PMI 製造業採購經理人指數,美國領先經濟指標綜合指數,經濟成長率 (GDP/GNP) 預測上修或下修及趨勢,物價指數 (CPI) 漲幅趨緩及M1B VS M2,盯緊FED下一步動做,全球景氣,配合個股位階作為我資產配置的參考條件
- 這個部分我相信AI一定有充分的歷史經驗值,個人需耗費很長時間,需要你協助規劃,設計可選工具(根據成長股,高殖利率股,高資本支出股,高在手訂單股,毛利率高中低排除負eps,產業龍頭股,尋找低位階的老二哲學)尤其在這百年難得的終端AI的起始點,我需事先更精準的好好準備
- 何謂"尋找低位階的老二哲學",例如2026晶圓代工漲幅Intel>TSMC,因為龍頭的溢出就回成為老二甚至老三的大補丸

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
