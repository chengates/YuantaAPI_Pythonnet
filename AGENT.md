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
## 7. 已知問題/代辦 list（Agent 可優先修）: 
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
| 1.8 | 2026-06-03 | agent說已修復但後來檢查csv資料發現有誤,這表示memory沒有清楚紀錄.又做白工,又燒token連續在相同問題繞圈 `fetch_daily_close.py` CSV 去重永久失效 — BOM（`﻿`）導致 DictReader 第一欄位名變成 `﻿日期` ≠ `日期`，`r.get("日期")` 永遠取得空字串；讀取編碼從 `utf-8` 改為 `utf-8-sig` 自動去除 BOM；清理所有 `@stockID.csv` 重複資料,完全解決問題前這件事不該做,反而把某些正確資料抹除,重點是memory沒有把反覆錯誤的點記起來 |


## 請agent 協助確認獨立生成 code map ,代補充 *.json , 其他有效*.py 
每日開盤前兩件事：
fetch_daily_close.py  TPEx/OTC OpenAPI : 前日收盤數據校正或當日晚上執行它 — 用官方數據覆蓋今日收盤價和總量,
tomorrow-premarket-tasks.md 可恢復上下文,位於C:\Users\gates\.claude\projects\D--workCS-TEST-2026-YuantaOneAPI-Python-YuantaOneAPI-Python\memory\tomorrow-premarket-tasks.md
repair_daily_summary.py — 從 5 秒 CSV 重建日總結檔，修正格式不一致、int32 溢位歷史資料、缺少 yesterday/ 備份
`stock_ref.json`: 自選股擴充code檔數，要同時補齊參考價,例如增加 6412/6122/6123/8936 
Web Dashboard: `web_dashboard.py` — Flask + SSE 即時多股監控畫面
run.py 防止雙開,startup api/Dashboard 開盤日 
sim_run.py 防止雙開,startup api/Dashboard 非開盤時,增加資料模擬器

Resume this session with:
claude --resume 9e573b2c-8886-444c-8ec9-862266f4c584