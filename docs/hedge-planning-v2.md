# 期貨／選擇權避險系統 — 完整規劃書 v2

> 版本: 2026-06-08
> 狀態: **Phase 1 已上線，Phase 2-4 規劃中（待確認後開工）**
> 對應: agent.md §7 / CHANGELOG 06-05 / memory `[[futures-hedge-planning]]`

---

## 目錄

1. [現況總覽](#1-現況總覽-phase-1-已上線)
2. [Phase 2: 個股期貨獨立頁面](#2-phase-2-個股期貨獨立頁面)
3. [Phase 3: 選擇權獨立頁面](#3-phase-3-選擇權獨立頁面)
4. [Phase 4: 自動化排程](#4-phase-4-自動化排程)
5. [技術架構建議](#5-技術架構建議)
6. [風險與取捨](#6-風險與取捨)

---

## 1. 現況總覽 (Phase 1 ✅ 已上線)

### 1.1 已實作模組

| 模組 | 位置 | 功能 |
|------|------|------|
| 避險儀表板 | `hedge_dashboard.py` | Flask Blueprint `/hedge` |
| 選擇權定價 | `option_pricing.py` | Black-Scholes + IV + Put/Call Parity + PCR |

### 1.2 hedge_dashboard.py 功能清單

```
✅ TXF/TXFPM1 台指期貨 vs 加權指數現貨基差監控
✅ 理論期貨價（持有成本模型：F = S × (1 + r × t/365)）
✅ 下一個到期日計算（每月第三個週三）
✅ 動態避險門檻（歷史基差標準差 × 1.5）
✅ 大戶動向（TAIFEX 前5/前10大交易人未平倉淨部位）
✅ 個股期貨避險（依自選股 futures 對照）
✅ 合約乘數自動判斷（TXFPM1=50, TXF=200）
✅ 每口避險價值試算
```

### 1.3 已知限制（Phase 1）

| 限制 | 影響 | 預計解決 |
|------|------|----------|
| 加權指數為估算值（權值股加權） | 基差精度 ±50 點 | Phase 2: 訂閱 TWSE 指數即時報價 |
| 個股期貨缺乏正式對照表 | 只能手動在 watchlist.json 填 futures | Phase 2: 建立股票↔個股期對照表 |
| 無保證金試算 | 無法評估資金需求 | Phase 2: 串接期交所保證金 API |
| 選擇權僅有計算函式 | 無視覺化介面 | Phase 3: 獨立選擇權頁面 |
| 大戶資料依賴 HTML 爬取 | 可能因網頁改版失效 | Phase 4: 監控 + 降級備援 |

---

## 2. Phase 2: 個股期貨獨立頁面

### 2.1 目標

將 `hedge_dashboard.py` 中已初步實作的個股期貨分析，升級為**獨立功能頁面**。核心差異：個股期的標的是「個股」而非「指數」，需考量除權息調整、保證金、合約規格。

### 2.2 功能規格

#### A. 股票 ↔ 個股期貨對照引擎
```
輸入: 股票代碼（如 2330）
輸出: 對應的個股期貨代碼（如 QF 台積電期貨）

資料來源:
  - 期交所「股票期貨契約規格」頁面
  - https://www.taifex.com.tw/cht/2/stockFutures
  - 約 260+ 檔個股期（每月隨新增調整）

實作方式:
  1. 建立 stock_futures_map.json（手動初始化 → 自動更新）
  2. 格式: {"2330": {"futures_code": "QF", "multiplier": 2000, "name": "台積電期貨"}}
  3. 每月從期交所爬取更新
```

#### B. 個股期 vs 現股基差即時計算
```
現股價格 → 從 snapshot/{code}.json 讀取
期貨價格 → 從 snapshot/{futures_code}.json 讀取（需先訂閱期貨報價）

基差 = 期貨價 - 現股價
理論期貨價 = 現股價 × (1 + r × t/365) - 預期股利
  r = 無風險利率 (預設 1.5%)
  t = 到期天數
  預期股利: 從除權息預告表查詢（TWSE 公開資料）

偏離度 = 基差 - 理論基差
```

#### C. 除權息自動調整
```
台灣個股期貨合約規格:
  - 除權息時，契約調整：開盤參考價 = (現股除權參考價) × 調整係數
  - 調整係數 = 除權前日現股收盤價 / 除權參考價

需整合: TWSE 除權息預告表
  - https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DIVIDEND
  - 含: 現金股利、股票股利、除權息日期
```

#### D. 保證金試算
```
資料來源: 期交所「結算保證金及維持保證金」
  - https://www.taifex.com.tw/cht/5/stockMargining

個股期原始保證金 = 期貨價 × 合約乘數 × 保證金比率
  合約乘數: 2,000 股（大多數個股期）
  保證金比率: 依個股波動分級（13.5% ~ 20.25%）

試算 UI: 輸入現貨持有張數 → 輸出所需避險口數 + 保證金需求
```

#### E. 到期日管理
```
個股期到期日: 同台指期（每月第三個週三）

近月 vs 遠月切換:
  - 自動顯示近月合約（預設）
  - 可手動切換遠月（下拉選單）
  - 到期前 5 天提示轉倉
```

### 2.3 UI 佈局建議

```
┌──────────────────────────────────────────────────────────┐
│  個股期貨避險儀表板                      [近月 ▼] [更新中] │
├──────────┬──────────┬──────────┬──────────┬──────────────┤
│  股票     │ 現股價    │ 期貨價    │  基差     │  避險訊號    │
│ 2330 台積電│ 2,425    │ 2,430    │ +5 (0.2%) │ 觀望         │
│ 2317 鴻海  │ 309      │ 312      │ +3 (1.0%) │ 偏貴 → 放空  │
│ 2344 華邦電│ 38.5     │ --       │ --       │ 無對應期貨    │
├──────────┴──────────┴──────────┴──────────┴──────────────┤
│  展開明細: [2330 台積電]                                   │
│  ├ 合約規格: QF / 乘數 2,000股 / 保證金比率 13.5%          │
│  ├ 理論價: 2,427 (1.5% / 剩 12 天 / 股利 16元)            │
│  ├ 偏離度: +3 點 (門檻 ±8 點)                              │
│  ├ 保證金試算: 持有 10 張現貨 → 空 5 口期貨 → 保證金約 66萬 │
│  └ 除權息: 06/18 除息 16 元 → 契約調整係數 1.0066           │
└──────────────────────────────────────────────────────────┘
```

### 2.4 實作範圍估計

| 項目 | 複雜度 | 檔案 |
|------|--------|------|
| stock_futures_map.json 建立 | 中 | 新 JSON |
| 個股期對照引擎 (爬取+更新) | 中 | `update_stock_futures.py` |
| 個股期基差計算 | 低 | 擴充 `hedge_dashboard.py` |
| 除權息整合 | 中 | `update_dividend.py` |
| 保證金試算 | 低 | 擴充 `hedge_dashboard.py` |
| UI 獨立頁面 | 中 | `hedge_dashboard.py` 擴充或新 Blueprint |

---

## 3. Phase 3: 選擇權獨立頁面

### 3.1 目標

將 `option_pricing.py`（純計算）升級為**全功能選擇權分析頁面**。核心差異：選擇權有履約價矩陣、IV 曲面、Greeks、策略組合，複雜度遠高於期貨。

### 3.2 功能規格

#### A. TXO 台指選擇權報價矩陣

```
概念: 類似 CBOE 選擇權鏈 (Option Chain)

         Calls (買權)              Strike (履約價)        Puts (賣權)
    IV    成交價   量   OI    │                      OI   量  成交價   IV
  18.2%   520    120  8500   22800                  3200  85   280   19.5%
  17.8%   380    210  6200   22900                  2800  120  340   19.1%
  17.1%   250    340  4800   23000                  2200  190  420   18.4%
  ...     ...    ...  ...    ...                    ...   ...  ...   ...

資料來源:
  - 期交所「選擇權每日交易行情」
  - 或透過 YuantaOneAPI 訂閱 TXO 選擇權報價（FiveTick / Watchlist）
```

#### B. IV 曲面 (Implied Volatility Surface)

```
三維視覺化: X=履約價, Y=到期日, Z=隱含波動率

用途:
  - 偵測 IV Skew（價平 vs 價外 IV 差異）
  - 偵測 IV Term Structure（近月 vs 遠月 IV 差異）
  - 異常 IV 事件 → 波動率套利機會

實作: matplotlib 3D surface plot 或 Plotly.js 互動圖
```

#### C. PCR 即時監控

```
Put/Call Ratio 多維度分析:

  Volume PCR = Put 成交量 / Call 成交量
  OI PCR = Put 未平倉 / Call 未平倉
  金額 PCR = Put 成交金額 / Call 成交金額

現有基礎: option_pricing.py 的 put_call_ratio_analysis()
待擴充: 即時數據來源（TAIFEX API 或 YuantaOneAPI 訂閱）
```

#### D. Greeks 計算

```
現有: option_pricing.py 已有 Black-Scholes + IV 反推

待擴充:
  Delta (Δ): 標的價格變動 1 點 → 選擇權價格變動
  Gamma (Γ): Delta 變動速率
  Theta (Θ): 時間價值衰減（每日）
  Vega (ν): 波動率變動 1% → 選擇權價格變動
  Rho (ρ): 利率變動 1% → 選擇權價格變動

適用場景:
  - 動態避險（Delta Hedging）: 持有現貨 + 動態調整選擇權口數
  - Gamma Scalping: 利用 Gamma 進行短線交易
```

#### E. 策略盈虧圖

```
常用策略模板:
  單腳策略: Buy Call, Buy Put, Sell Call, Sell Put
  垂直價差: Bull Call Spread, Bear Put Spread
  時間價差: Calendar Spread
  波動率策略: Straddle, Strangle, Butterfly, Iron Condor

每個策略顯示:
  - 到期損益圖 (Payoff Diagram)
  - 最大獲利 / 最大虧損
  - 損益兩平點
  - Greeks 總合
```

#### F. 避險口數試算

```
Delta 避險公式:
  避險口數 = (現貨市值 × 目標 Delta) / (選擇權 Delta × 合約乘數)

例:
  持有 2,300 萬現貨（約 1,000 點 × 23000）
  目標 Delta = 0（完全避險）
  使用價平 Put (Delta ≈ -0.5)
  合約乘數 = 50 點/口
  → 避險口數 = 23,000 × 1000 / (0.5 × 50) = 920 口
```

### 3.3 UI 佈局建議

```
┌─────────────────────────────────────────────────────────┐
│  台指選擇權分析                        [近月 ▼] [更新中]  │
├─────────────────────────────────────────────────────────┤
│  現貨指數: 23,000  |  Call/Put Volume PCR: 1.15        │
│  隱含波動率: 18.5% |  OI PCR: 0.92                     │
├──────────┬──────────┬──────────┬─────────────────────────┤
│ 選擇權鏈  │ IV 曲面   │ Greeks   │  策略實驗室              │
│ [選項卡]  │ [選項卡]  │ [選項卡] │  [選項卡]               │
├──────────┴──────────┴──────────┴─────────────────────────┤
│  [依選項卡切換內容區]                                     │
│                                                         │
│  (選擇權鏈: C/P 矩陣表格)                                │
│  (IV 曲面: Plotly 3D 互動圖)                             │
│  (Greeks: 持倉總合儀表板)                                │
│  (策略實驗室: 策略下拉 + Payoff 圖 + 盈虧表)              │
└─────────────────────────────────────────────────────────┘
```

### 3.4 實作範圍估計

| 項目 | 複雜度 | 檔案 |
|------|--------|------|
| TXO 報價訂閱 + 矩陣 UI | 高 | 新 `options_dashboard.py` |
| IV 曲面 (Plotly.js) | 中 | 前端 JS |
| Greeks 計算擴充 | 低 | 擴充 `option_pricing.py` |
| 策略盈虧圖 | 中 | 新 `option_strategies.py` |
| PCR 即時監控 | 低 | 擴充 `option_pricing.py` |
| 避險口數試算 | 低 | 前端計算 |

---

## 4. Phase 4: 自動化排程

### 4.1 目標

將手動執行的資料更新，轉為自動化定期排程。

### 4.2 排程項目

| 排程 | 頻率 | 工具 |
|------|------|------|
| 市值排名更新 | 每月 1-4 號 | `update_market_cap.py` |
| 個股期對照表更新 | 每月 1-4 號 | `update_stock_futures.py` (新) |
| 除權息資料更新 | 每日 | `update_dividend.py` (新) |
| 法人預估 EPS 爬取 | 每週 | `fetch_analyst_eps.py` |
| 大戶部位備份 | 每日收盤 | 整合進 `hedge_dashboard.py` |
| 保證金比率更新 | 每月 | `update_margin.py` (新) |

### 4.3 排程方式選項

```
選項 A: Claude Code /loop
  /loop "1d at 18:00" python fetch_daily_close.py
  優: 簡單，失敗有通知
  缺: 依賴 Claude Code 持續運行

選項 B: Windows Task Scheduler
  schtasks /create /tn "YuantaMarketCap" /tr "python update_market_cap.py" /sc monthly /d 1
  優: 系統原生，不需額外程序
  缺: 失敗無通知

選項 C: APScheduler (Python)
  在 run.py 或 sim_run.py 中內建排程器
  優: 可程式化控制、失敗重試
  缺: 需程序持續運行

建議: A (開發期) → C (正式上線)
```

---

## 5. 技術架構建議

### 5.1 模組拆分（避免單一檔案過大）

```
現況:
  web_dashboard.py (1080 行) — 監控面板
  hedge_dashboard.py (499 行) — 避險面板
  option_pricing.py — 選擇權計算

建議拆分 (Phase 2-3 完成後):
  web_dashboard.py       — 核心監控面板（不變）
  hedge_dashboard.py     — 避險面板 + 個股期分析
  options_dashboard.py   — 選擇權獨立面板 (新)
  option_pricing.py      — 選擇權計算引擎（擴充 Greeks/策略）
  update_stock_futures.py — 個股期對照表更新 (新)
  update_dividend.py     — 除權息資料更新 (新)
  scheduler.py           — 自動化排程 (新)
```

### 5.2 前端共用元件

```
為避免三頁重複 CSS/JS:
  建議: 建立 templates/base.html (Jinja2 繼承)
  共用: Dark theme CSS, fmt()/vol() 格式化函數
  差異: 各頁面獨立的 render 邏輯
```

### 5.3 資料來源彙整

| 資料 | 來源 | API/爬取 | 穩定性 |
|------|------|----------|--------|
| 現股報價 | YuantaOneAPI | 即時訂閱 | 高（API 直接） |
| 期貨報價 | YuantaOneAPI | 即時訂閱 | 高 |
| 選擇權報價 | YuantaOneAPI | 即時訂閱 | 需驗證 |
| 昨收/漲跌停 | stock_ref.json | ReadWatchListAll | 高 |
| 大戶部位 | TAIFEX | HTML 爬取 | 中（可能改版） |
| 個股期規格 | TAIFEX | HTML 爬取 | 中 |
| 除權息 | TWSE OpenAPI | REST API | 高 |
| 保證金 | TAIFEX | HTML 爬取 | 中 |
| PE/PB | TWSE BWIBBU | REST API | 高 |
| 法人 EPS | Yahoo/Google | HTML 爬取 | 低（經常失效） |

---

## 6. 風險與取捨

### 6.1 已知風險

| 風險 | 影響 | 緩解措施 |
|------|------|----------|
| TAIFEX 網頁改版 | 大戶資料/規格爬取失效 | 多來源備援 + 降級顯示「資料暫無」 |
| 選擇權報價延遲 | IV/Greeks 計算偏差 | 標記資料時間，滯後 >30s 警告 |
| 法人 EPS 爬取不穩 | PEG 無法更新 | 手動填入 analyst_eps.json 為最終備援 |
| 除權息期間基差異常 | 避險訊號誤判 | 除權息前 3 天自動放寬門檻 |
| 檔案持續增長 | 單一檔案 500+ 行 → AI 失憶 | 限定每檔案 ≤800 行，必要時拆分 |

### 6.2 建議優先序

```
第一優先（Phase 2，1-2 週）:
  1. stock_futures_map.json + 更新腳本
  2. 個股期基差計算 (除權息整合)
  3. 個股期獨立 UI 卡片

第二優先（Phase 3 前期，2-3 週）:
  4. TXO 選擇權報價訂閱驗證
  5. 選擇權矩陣 UI
  6. IV + Greeks 計算擴充

第三優先（Phase 3 後期 + Phase 4）:
  7. 策略盈虧圖
  8. 自動化排程
  9. 前端共用元件重構
```

---

> **請確認：** 以上規劃是否涵蓋你的需求？確認後我會從 Phase 2 第一項（個股期對照表）開始實作。
> 如有任何方向需要調整，或想先跳過某些功能，請告訴我。
