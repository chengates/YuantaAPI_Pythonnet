# cStocks 技術規格（SPEC）

## 1. 系統架構

```
┌─────────────────────────────────────────────────────────┐
│  __main__ / 使用者腳本                                    │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  cStock(BasicUnit)                                       │
│  · load_data / refresh_period_data / calculate_indicators│
│  · update_view → _draw_*_panel                           │
│  · _setup_cursor / _setup_drawing_ui                     │
└──────┬───────────────────────────────┬──────────────────┘
       │                               │
┌──────▼──────┐                 ┌──────▼──────────────┐
│ StockPalette │                 │ {code}_drawings.json │
│ Light/Dark   │                 │ 繪圖物件持久化         │
└─────────────┘                 └─────────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│  df_raw → resample → df_all → slice → df (可視區)      │
└───────────────────────────────────────────────────────┘
```

### 1.1 主要模組

| 模組 | 檔案 | 職責 |
|------|------|------|
| 字型／Emoji | `cStocks.py` | `setup_chinese_font()`, `make_emoji_img()` |
| 配色 | `StockPalette` | 背景、K 線、均線、KDJ、網格 |
| 週期設定 | `BasicUnit` | `unit`, `units`, `unitIndex`, `TICK_INTERVAL` 等 |
| 股票邏輯 | `cStock` | 資料、指標、繪圖、事件 |
| Matplotlib 範例 | `basic_units.py` | **非本專案業務**，為 matplotlib 文件用，勿與 `BasicUnit` 混淆 |

---

## 2. CSV 資料格式

### 2.1 必要欄位

| 欄位名 | 型別 | 說明 |
|--------|------|------|
| 日期 | datetime 可解析字串 | 索引基礎 |
| 開盤價 | float | |
| 最高價 | float | |
| 最低價 | float | |
| 收盤價 | float | 不可全為 NaN |
| 成交股數 | float | 顯示成交量時 ÷1000 為「張」 |
| 成交金額 | float | |
| 成交筆數 | float | |

### 2.2 讀取流程

1. `pd.read_csv` → 欄位 `strip`
2. `日期` → `pd.to_datetime`
3. 數值欄 `to_numeric(..., errors="coerce")`
4. `dropna(subset=["收盤價"])`，依日期排序 → `df_raw`

### 2.3 週期重採樣

`refresh_period_data()` 對 `df_raw` 設 `日期` 為 index：

| `unit` | pandas 規則 | 聚合 |
|--------|-------------|------|
| `D` | 不重採樣 | — |
| `1T`…`60T`, `W-FRI`, `ME` | `resample(unit).apply(agg)` | 開:first, 高:max, 低:min, 收:last, 量/額/筆:sum |

---

## 3. 技術指標公式

### 3.1 移動平均

- `ma5` = `收盤價`.rolling(5).mean()
- `ma20` = `收盤價`.rolling(20).mean()

### 3.2 布林通道

- `std` = `收盤價`.rolling(20).std()
- `ub` = ma20 + 2×std
- `lb` = ma20 - 2×std

### 3.3 MACD（預設 12, 26, 9）

```
ema12 = EWM(收盤價, span=12)
ema26 = EWM(收盤價, span=26)
dif   = ema12 - ema26
dea   = EWM(dif, span=9)
macd  = (dif - dea) * 2
```

金叉：`dif > dea` 且前一日 `dif <= dea` → 紅色 `^` scatter。

### 3.4 KDJ（預設 9, 3, 3）

```
low9  = rolling_min(最低價, 9)
high9 = rolling_max(最高價, 9)
rsv   = (收盤價 - low9) / (high9 - low9) * 100
K     = EWM(rsv, com=2)
D     = EWM(K, com=2)
J     = 3*K - 2*D
```

### 3.5 籌碼衍生

| 欄位 | 公式 |
|------|------|
| 均價 | 成交金額 / 成交股數 |
| 每筆均量 | 成交股數 / 成交筆數 |
| 每筆均量_ma5 | rolling(5).mean(每筆均量) |
| vol_ma5 | rolling(5).mean(成交股數)，顯示時 ÷1000 為張 |

### 3.6 支撐／壓力（`_calc_support_resistance`）

以**最後一根收盤價**為基準，**同時**計算下方支撐、上方壓力（已移除「漲只畫撐、跌只畫壓」）。

1. **量能分布峰**：可視區 40–80 bins + `SR_PEAK_RADIUS` local peak → `(量, 價)`
2. **波段峰**：`SR_SWING_WINDOW`（預設 5）局部高低點 + 該 K 成交量
3. `_merge_sr_candidates` 合併同價位量能
4. `_pick_spaced_sr_levels`：支撐僅 `價 < 收盤×0.999`、壓力僅 `價 > 收盤×1.001`；同側最多 2 條、強制最小間距
5. 候選不足時 `_sr_fallback_levels` 補可視區／近 20 根極值
6. 最終再過濾，確保 S 在收盤下、R 在收盤上

### 3.7 PNG 匯出

- `export_png(fig, dpi=150)` → `{code}_{週期}_{時間戳}.png`
- 右側 **📷 PNG** 按鈕（`_setup_drawing_ui`）

---

## 4. 可視區與狀態

| 變數 | 預設 | 說明 |
|------|------|------|
| `n_days` | 60 | 可視 K 線根數 |
| `start_idx` | len(df_all)-n_days | 平移起點 |
| `df_all` | — | 當前週期全量 + 指標 |
| `df` | slice | `df_all[start_idx : start_idx+n_days]` |
| `TICK_INTERVAL` | 10 | 價格標籤間隔（K 線 panel） |
| `MA_VOL_PERIOD` | 5 | 均量週期 |
| `VOL_LARGE_RATIO` | 1.5 | 大量判定（預留） |
| `VOL_SMALL_RATIO` | 0.618 | 小量判定（預留） |

### 4.1 X 軸刻度（`_setup_xticks`）

- 刻度 index：`0, TICK_INTERVAL, 2*TICK_INTERVAL, …`
- 若最後一根不在列表中，追加 `len(df)-1`
- 標籤格式：`%y/%m/%d`

---

## 5. UI 佈局

### 5.1 圖表

- `plt.subplots(4, 1, sharex=True, height_ratios=[4, 1.5, 2, 2])`
- `figsize=(15, 11)`，`tight_layout(rect=[0.01, 0.03, 0.90, 0.97])`
- 右側 0.91–0.99 留給 Radio / Button

### 5.2 右側控制項

| 區域 | 元件 | 功能 |
|------|------|------|
| [0.91, 0.72, 0.08, 0.26] | RadioButtons | 繪圖工具 |
| [0.91, 0.60, 0.08, 0.11] | RadioButtons | 六色預設 |
| [0.91, 0.56, 0.08, 0.035] | Button | 儲存繪圖 JSON |
| [0.91, 0.10, 0.08, 0.30] | RadioButtons | 週期 1分～月K |

### 5.3 游標互動（`_setup_cursor`）

- **左鍵按下**（在四個 axes 內）：`is_dragging=True`，記錄 `press_x`, `press_start_idx`
- **拖曳**：僅當 `draw_tool == 'cursor'` 時左鍵啟動；`start_idx = press_start_idx - round(event.xdata - press_x)`，clamp 至 `[0, len(df_all)-n_days]`
- **非拖曳移動**：更新 `info_box`、emoji、`vlines` 垂直線

大戶邏輯（`_setup_cursor` → `on_mouse`，與程式一致）：

```
is_up = 收盤 >= 開盤
is_big = 每筆均量 > 每筆均量_ma5 * 1.2
若 is_big:
  whale = 🐋↗ if 收盤 >= 均價 else 🐋↘
  status = 依 is_up 與 whale 組合（大戶追價／吸收／高位調節／偷偷出貨）
否則: whale='👥', status='散戶盤整'
oi_vol emoji: 🔥 if 成交量(張) > vol_ma5 * 1.5 else 📊
```

**未使用**：`oi_kdj` 在 `_rebuild_overlays` 建立，但 `on_mouse` 未更新。

---

## 6. 繪圖物件 JSON 規格

**路徑**：`{self.code}_drawings.json`（陣列）

### 6.1 共通欄位

| 欄位 | 型別 | 說明 |
|------|------|------|
| type | string | 見下表 |
| x1,y1,x2,y2 | float | 畫面 index（執行期） |
| d1,d2(,d3) | string | `YYYY-MM-DD`，持久化用 |
| unit | string | `1T`…`ME`，與當前週期一致才顯示 |
| color | string | `#RRGGBB` |
| panel | `"k"` \| `"v"` | 價格或成交量軸 |

### 6.2 type 枚舉

| type | 點擊次數 | 備註 |
|------|----------|------|
| hline / vline | 1 | 單點 |
| line, arrow, arrow2, channel, rect, fib | 2 | channel 有 `channel_offset` |
| arc, measure | 3 | arc 含 x3,y3,d3 |
| — | select | 拖曳移動；右鍵刪除 |
| — | clear | 清除當前 `unit` 物件 |

載入時 `_obj_to_screen` 以 `d1`… 對應當前 `df` 的 index。

---

## 7. 設定檔（規劃，尚未實作）

建議 `settings.json` 結構：

```json
{
  "code": "2317",
  "unit": "D",
  "style": "Dark",
  "n_days": 90,
  "tick_interval": 10,
  "ma_short": 5,
  "ma_long": 20,
  "palette": {
    "ma5": {"r": 183, "g": 28, "b": 28, "a": 170},
    "ma20": {"r": 27, "g": 94, "b": 32, "a": 170}
  },
  "annotations": [
    {"date": "2024-01-15", "text": "財報", "fg": "#000", "bg": "#FFEB3B80"}
  ]
}
```

---

## 8. 盤中預估量（待實作規格草案）

台股連續交易 09:00–13:30（270 分鐘）。

```
預估量 = 盤中累計成交量(張) × 時間倍數
```

| 時點 | 參考倍數（待以歷史回測校準） |
|------|------------------------------|
| 09:05 | ~15（誤差大） |
| 09:15 | ~8 |
| 10:30 | ~3 |
| 12:30 | ~1.5 |
| 13:30 | 1 |

---

## 9. 相依套件

`requirements.txt` 所列：

- matplotlib >= 3.10
- numpy >= 2.4
- pandas >= 3.0
- mplfonts >= 2.4.2（需執行 `mplfonts init` 以支援中文）

- **Pillow** >= 10.0 — Emoji 圖片（`from PIL import Image, ImageDraw, ImageFont`）

---

## 10. 程式進入點（`__main__`）

| 區塊 | 行為 |
|------|------|
| `fox = cStock("2317", "鴻海", "D", "Dark")` | 載入 `2317.csv`，`n_days=90`，`plot_all(block=False)` |
| `tsmc = cStock("2330.TW", "台積電")` | 載入 `2330.csv`，預設亮色、`n_days=60`，`plot_all()` 阻塞 |
| Gemini 範例 | **註解區塊**：需 `pip install google-genai` 與 `GEMINI_API_KEY`，不影響圖表 |

繪圖存檔檔名依 `self.code`（例：`2317_drawings.json`、`2330.TW_drawings.json`）。

**PNG**：`export_png` / 右側 📷 按鈕，150 dpi，`bbox_inches='tight'`。

---

## 11. 已知限制與實作備註

| # | 項目 | 說明 |
|---|------|------|
| 1 | `basic_units.py` | Matplotlib 官方範例，與專案 `BasicUnit` 無關 |
| 2 | 事件 | 平移僅在 `draw_tool=='cursor'`；繪圖工具使用時不觸發水平拖曳 |
| 3 | Emoji 字型 | 硬編碼 `C:/Windows/Fonts/seguiemj.ttf`；失敗則 `ImageFont.load_default()` |
| 4 | 分 K 資料 | 僅日線 CSV 時，選 1 分 K 無法產生真實分鐘 K |
| 5 | `_draw_volume_panel` | 內部再次 slice `self.df`，繪製順序為 K 線 → 量 → MACD/KDJ |
| 6 | `VOL_LARGE_RATIO` / `VOL_SMALL_RATIO` | 類別上有定義；量能 🔥 判定實際用硬編碼 `1.5` |
| 7 | `calculate_indicators` | `self.allMax, self.allMin = df.max(), df.min()` 為整表 Series，非純價格極值（若後續使用需注意） |

---

## 12. 修訂紀錄

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0 | 2026-05-24 | 初版 |
| 1.1 | 2026-05-24 | 對齊 `cStocks.py` v989：PNG、S/R、Pillow、__main__、genai |
| 1.2 | 2026-05-24 | S/R 重繪、平移條件、Pillow 入 requirements |
