# Yuanta OneAPI Python — 元大證券量化交易系統

基於元大證券 OneAPI 的 Python 量化交易分析系統，支援台股即時報價、技術指標計算、K 線視覺化與 AI 驅動的 Managed Agent 分析。

## 架構

```text
YuantaOneAPI.dll (C#) ──pythonnet──▶ YuantaAPI_Pythonnet.py (即時報價 + CSV 持久化)
                                     │
                                     ├── StockQuoteState (五檔 / 分時 / 觀察清單)
                                     ├── async show() (60fps UI 更新)
                                     └── 每 5 秒 CSV 輸出 (OHLCV + 內外盤分析)

cStocks.py (matplotlib) ────────────▶ K 線圖表 / MACD / KDJ / Bollinger / 支撐壓力
                                     │
                                     ├── 深色/亮色模式
                                     ├── 12 種繪圖工具 (線/通道/弧/斐波那契/測距)
                                     └── Whale 大戶偵測 (🐋↗ 吸收 / 🐋↘ 脫手)

claude_agent_setup.py ──────────────▶ Managed Agent 建立 (Opus 4.7 / Sonnet 4.6 / Haiku 4.5)
claude_agent_runtime.py ────────────▶ Managed Agent 運行 (4 種模式)
```

## 功能

| 模組 | 功能 | 狀態 |
| --- | --- | --- |
| **即時報價** | SubscribeFiveTick_out 五檔報價 (實測心跳正常) | ✅ |
| **統一行情狀態** | SUBSCRIPTION_STATE 字典 + StockQuoteState 類別 | ✅ |
| **技術指標** | MA5 / MA10 / 價格動量 / MACD / KDJ / Bollinger | ✅ |
| **買賣壓力** | 內外盤量 / 買賣不平衡 / 盤壓計算 | ✅ |
| **CSV 持久化** | 每 5 秒寫入 OHLCV + 內外盤數據 (非阻塞) | ✅ |
| **大戶偵測** | Whale 吸收/脫手/散戶盤整 自動標記 | ✅ |
| **K 線圖表** | 多週期切換 (1分K~月K) / 深色亮色主題 / 繪圖工具 | ✅ |
| **異步顯示** | async show() 每 1/60 秒更新 | ✅ |
| **Managed Agent** | Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 三模型 | ✅ |
| **收盤排程** | 13:30-14:30 盤後搓合暫停 CSV → 日匯總寫入 | ✅ |
| **日匯總 CSV** | @stockID.csv 每日一筆供隔日快速載入 | ✅ |
| **主力/散戶分類** | 5-factor scoring + 6 級標籤 (強力買進~強力賣出) | ✅ |
| **股票分類** | large_cap/mid_cap/small_cap/speculative 自動偵測 | ✅ |
| **自選股 JSON** | watchlist.json 可擴充自選股1/2/3…，dashboard 切換 | ✅ |
| **Web 監控面板** | Flask + SSE 即時多股監控, dark theme card layout | ✅ |
| **Put/Call 合理價** | Black-Scholes + IV + Parity + PCR 溢價避險分析 | ✅ |
## 環境需求

- **OS**: Windows (需要 .NET Framework / DLL)
- **Python**: 3.11+
- **依賴**:

  ```bash
  pip install pythonnet anthropic pandas numpy matplotlib pillow
  ```

## 快速開始

### 1. 即時報價

```python
# 啟動 Yuanta OneAPI 交易連線並訂閱五檔報價
python YuantaAPI_Pythonnet.py
```

### 2. K 線技術分析

```python
from cStocks import cStock

fox = cStock("2317", "鴻海", "D", "Dark")
fox.load_data("2317.csv", 90)
fox.plot_all()
```

### 3. AI Agent 分析 (需 ANTHROPIC_API_KEY)

```bash
# 一次性設定 (建立 Agent + Environment)
python claude_agent_setup.py

# 互動式對話
python claude_agent_runtime.py

# 排程分析
python claude_agent_runtime.py --cron

# 研究報告
python claude_agent_runtime.py --research "2330 台積電 DCF 估值"

# 切換模型
python claude_agent_runtime.py --model sonnet
```

## 專案結構

| 檔案 | 說明 |
| --- | --- |
| `YuantaAPI_Pythonnet.py` | 主程式 — pythonnet 橋接 YuantaOneAPI.dll，即時報價訂閱與 CSV 持久化 |
| `cStocks.py` | K 線圖表視覺化 — MACD/KDJ/Bollinger/Whale 偵測/繪圖工具 |
| `YuantaAPI_IronPython.py` | IronPython 版本的 API 橋接 |
| `claude_agent_setup.py` | Managed Agent 一次性建立 (3 個 Agent + 1 個 Sandbox) |
| `claude_agent_runtime.py` | Managed Agent 執行期 — 4 種運行模式 |
| `CHANGELOG.md` | 版本改動記錄 |
| `web_dashboard.py` | Flask + SSE 即時多股監控面板 |
| `option_pricing.py` | Black-Scholes + Put/Call Parity 合理價計算 |
| `watchlist.json` | 自選股設定檔，可自行編輯擴充 |
| `IO_Doc/` | Yuanta OneAPI 各項回應規格說明文件 |
| `*.dll` | 元大證券 API 原生元件 |

## 資料規格

每 5 秒 CSV 輸出欄位：

| 欄位 | 說明 |
| --- | --- |
| `timestamp` | 時間戳記 |
| `stock_id` | 股票代碼 |
| `deal_volume` | 成交股數 |
| `deal_amount` | 成交金額 |
| `open/high/low/close` | 開高低收 |
| `price_diff` | 漲跌價差 |
| `trade_count` | 成交筆數 |
| `estimated_day_volume` | 預估日成交量 |
| `pct_of_yesterday_avg` | 佔昨日均量% |
| `total_in_volume` | 累計內盤量 |
| `total_out_volume` | 累計外盤量 |
| `buy_sell_pressure` | 買賣壓力指標 |
| `ma5/ma10` | 移動平均線 |
| `price_momentum` | 價格動量 |

## 相關文件

- [元大證券OneAPI_Python使用說明.pdf](./元大證券OneAPI_Python使用說明.pdf)
- [元大證券API操作說明.pdf](./元大證券API操作說明.pdf)
- [IO_Doc/](./IO_Doc/) — 各項 API 回應規格

## 注意事項

- 本專案僅供學術研究與個人分析使用
- 交易功能需透過元大證券正式開戶取得 API 權限
- DLL 元件版權屬元大證券所有
