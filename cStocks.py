import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.offsetbox as offsetbox
import matplotlib.patches as mpatches
from matplotlib.widgets import RadioButtons, Button
from matplotlib.lines import Line2D
from PIL import Image, ImageDraw, ImageFont
import os
import json
# ── 1. Emoji 渲染與字體設定 ──────────────────────────────────────
def make_emoji_img(text: str, size: int = 48) -> np.ndarray:
    w = size * max(len(text), 1)
    img = Image.new('RGBA', (w, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", size - 6)
    except:
        font = ImageFont.load_default()
    draw.text((0, 0), text, font=font, fill=(255, 255, 255, 255), embedded_color=True)
    return np.array(img)

def setup_chinese_font():
    font_list = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
    available = {f.name for f in fm.fontManager.ttflist}
    selected = [f for f in font_list if f in available] + ['sans-serif']
    plt.rcParams['font.sans-serif'] = selected
    plt.rcParams['axes.unicode_minus'] = False

# ── 2. 視覺配色管理器 ──────────────────────────────────────────
class StockPalette:
    def __init__(self, mode="Light"):
        if mode == "Dark":
            self.bg, self.fg, self.grid,self.spines = "#121212", "#E0E0E0", "#55555555", "#E0E0E0"
            self.rise, self.fall, self.box = "#FF3333", "#00E676", "#66666633"            
            self.k,self.d,self.j,self.kd80,self.kd20 = "blue","orange","purple","red","green"
            self.label="white"
            
        else:
            self.bg, self.fg, self.grid,self.spines = "white", "black", "#C0C0C0C0","#10101010"
            self.rise, self.fall, self.box = "red", "green", "white"
            self.k,self.d,self.j,self.kd80,self.kd20 = "blue","orange","purple","red","green"
            self.label = 'black'
        #灰色: #57606a 
        self.gray, self.grey = "#57606a88" ,"#57606a"
        self.ma5, self.ma20 = "#B71C1CAA", "#1B5E20AA"
        if mode == "Dark":
            self.bb_line, self.bb_fill = "#64B5F6", "#1976D2"
            self.bb_fill_alpha = 0.18
        else:
            self.bb_line, self.bb_fill = "#1565C0", "#42A5F5"
            self.bb_fill_alpha = 0.14

# ── 3. 基礎類別 (BasicUnit) ──────────────────────────────────────
class BasicUnit:
    """整合週期與樣式設定 (解決 ToBe 4)"""
    def __init__(self, code, name, unit, style):
        self.code = code
        self.name = name
        #可視區的單位unit:最小=1分k~"ME"最大月:下標=self.units[5],["1T","5T","15T","30T","60T","D","W-FRI","ME"]
        self.unit = unit 
        #print("unit=",unit)
        # 初始化配色方案
        self.palette = StockPalette(mode=style)
        self.TICK_INTERVAL = 10
        self.MA_VOL_PERIOD = 5
        self.VOL_LARGE_RATIO = 1.5
        self.VOL_SMALL_RATIO = 0.618
        self.SR_MIN_GAP_RATIO = 0.04   # 同側兩條 S 或 R 的最小價格間距（× 可視區高低差）
        self.SR_PEAK_RADIUS = 2        # 量能峰鄰域半徑（格數）
        self.SR_SWING_WINDOW = 5       # 波段高低點視窗（根 K）
        self.show_bollinger = True     # 布林通道預設開啟
        self.ma_short_period = 5       # 短均線週期（最長 240）
        self.ma_long_period = 20       # 長均線／布林基準週期
        self.vol_ma_short = 5
        self.vol_ma_long = 20
        self.TICK_INTERVAL_AUTO = True # True 時依 n_days 自動密度
        self.N_DAYS_MIN = 10           # X 縮放最少顯示 K 線根數
        self.N_DAYS_ZOOM_RATIO = 0.12  # 每次縮放步進（佔目前 n_days 比例）
        self.unitIndex = 5  #可視區的預設單位=5,這部分要配合csv資料輸入單位加以調整,ex:想辦法轉成min:code1分K.csv
        self.units = ["1分K","5分K","15分K","30分K","60分K","日K","周K","月K"]

    def getName(self):
        return f"{self.code} {self.name} {self.getUnit()}"
        #return f"{self.code} {self.name}"
    
    def getUnit(self):
        #可視區的單位unit:最小=1分k~"ME"最大月,
        datas = ["1T","5T","15T","30T","60T","D","W-FRI","ME"]
        i=0
        for idx in datas:            
            #print(f'datas={idx} int({i})') 
            if idx == self.unit:
               return self.units[i]
            else:
                i+=1



class cStock(BasicUnit):
    def __init__(self, code, name, unit="D",style="Light"):
        # 修正：將 style 傳遞給父類別
        super().__init__(code, name, unit, style)
        self.df_raw = None  # 1分K原始數據緩衝
        self.df_all = None  # 當前週期全量緩衝
        self.df = None      # 顯示窗口
        self.n_days = 60    #可視區的長度,預設60天(單位unit:最小=1分k~最大可擴充暫定"ME"=mounth)
        self.start_idx = 0  #可視區的start_idx
        self.is_dragging = False
        self.press_x = 0
        self.press_start_idx = 0    #mouse move 顯示窗口按下左鍵df的位置 ,default 0
        self.allMax=0
        self.allMin=0x7ffffff
        self.max=0
        self.min=0x7ffffff
        self.vlines = []   #初始化直線物件
        self.info_box = None
        self.oi_vol = None
        self.oi_kdj = None
        # ── 支撐/壓力線快取 ──
        self._sr_cache = ([], [])
        self._sr_dirty = True
        # ── 繪圖工具狀態 ──────────────────────────────────────────
        self.draw_tool    = 'cursor'   # 目前選擇的工具
        self.draw_color   = '#FFFF00'  # 目前選擇的顏色（預設黃色）
        self.draw_step    = 0          # 0=等待第一點, 1=等待第二點, 2=等待第三點(measure)
        self.draw_p1      = None       # 第一個點 (x, y, panel)
        self.draw_p2      = None       # 第二個點，measure 工具用
        self.draw_preview = None       # 預覽用暫時物件
        self.draw_objects = []         # 所有已完成的繪圖物件 dict
        self.draw_artists = []         # 對應的 matplotlib artist
        self.selected_obj = None       # 被選中要移動的物件 index
        self.drag_offset  = (0, 0)     # 拖曳偏移量
        self.k_y_zoom = 1.0            # 價格 Y 縮放（1=自動貼合可視區）
        self.k_y_center = None         # 手動 Y 縮放時的中心價

    def _settings_path(self):
        return f"{self.code}_settings.json"

    def load_settings(self):
        path = self._settings_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        unit_map = {"1T": 0, "5T": 1, "15T": 2, "30T": 3, "60T": 4, "D": 5, "W-FRI": 6, "ME": 7}
        if "unit" in cfg:
            self.unit = cfg["unit"]
            self.unitIndex = unit_map.get(self.unit, self.unitIndex)
        for key in ("n_days", "TICK_INTERVAL", "show_bollinger", "ma_short_period",
                    "ma_long_period", "vol_ma_short", "vol_ma_long"):
            if key in cfg:
                setattr(self, key, cfg[key])
        if "TICK_INTERVAL_AUTO" in cfg:
            self.TICK_INTERVAL_AUTO = bool(cfg["TICK_INTERVAL_AUTO"])
        if "style" in cfg:
            self.palette = StockPalette(mode=cfg["style"])
        self.ma_short_period = max(2, min(240, int(self.ma_short_period)))
        self.ma_long_period = max(self.ma_short_period + 1, min(240, int(self.ma_long_period)))
        if "start_idx" in cfg:
            self._pending_start_idx = int(cfg["start_idx"])
        # RGBA 調色覆蓋
        for key in ("ma_s_color", "ma_l_color", "bb_color", "rise_color", "fall_color"):
            if key in cfg:
                setattr(self.palette, key, cfg[key])

    def save_settings(self):
        cfg = {
            "unit": self.unit,
            "n_days": self.n_days,
            "start_idx": self.start_idx,
            "TICK_INTERVAL": self.TICK_INTERVAL,
            "TICK_INTERVAL_AUTO": self.TICK_INTERVAL_AUTO,
            "show_bollinger": self.show_bollinger,
            "ma_short_period": self.ma_short_period,
            "ma_long_period": self.ma_long_period,
            "vol_ma_short": self.vol_ma_short,
            "vol_ma_long": self.vol_ma_long,
            "style": "Dark" if self.palette.bg == "#121212" else "Light",
            "ma_s_color": getattr(self.palette, 'ma_s_color', self.palette.ma5),
            "ma_l_color": getattr(self.palette, 'ma_l_color', self.palette.ma20),
            "bb_color": getattr(self.palette, 'bb_color', self.palette.bb_line),
            "rise_color": getattr(self.palette, 'rise_color', self.palette.rise),
            "fall_color": getattr(self.palette, 'fall_color', self.palette.fall),
        }
        with open(self._settings_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"[cStocks] 設定已儲存: {os.path.abspath(self._settings_path())}")

    def load_data(self, csv_file, n_days=60):
        full_df = pd.read_csv(csv_file)
        full_df.columns = [c.strip() for c in full_df.columns]
        full_df["日期"] = pd.to_datetime(full_df["日期"])
        cols = ["收盤價", "開盤價", "最高價", "最低價", "成交股數", "成交金額", "成交筆數"]
        for col in cols: full_df[col] = pd.to_numeric(full_df[col], errors="coerce")
        self.df_raw = full_df.dropna(subset=["收盤價"]).sort_values("日期").copy()
        self.n_days = n_days
        self.load_settings()
        self.refresh_period_data()

    def refresh_period_data(self):
        df = self.df_raw.copy().set_index("日期")
        agg = {"開盤價":"first","最高價":"max","最低價":"min","收盤價":"last","成交股數":"sum","成交金額":"sum","成交筆數":"sum"}
        if self.unit != "D" and self.unit in ["1T","5T","15T","30T","60T","W-FRI","ME"]:
            df = df.resample(self.unit).apply(agg).dropna()
        self.df_all = df.reset_index()
        self.calculate_indicators()
        max_n = len(self.df_all)
        pending = getattr(self, "_pending_start_idx", None)
        if pending is not None:
            self.start_idx = max(0, min(pending, max(0, max_n - self.n_days)))
            self._pending_start_idx = None
        else:
            self.start_idx = max(0, max_n - self.n_days)
        self._sr_dirty = True

    def calculate_indicators(self):
        df = self.df_all
        # 原有的 MACD [1]
        ema12, ema26 ,self.allMax,self.allMin = df["收盤價"].ewm(span=12).mean(), df["收盤價"].ewm(span=26).mean(), df.max(),df.min()        
        df["dif"] = ema12 - ema26
        df["dea"] = df["dif"].ewm(span=9).mean()
        df["macd"] = (df["dif"] - df["dea"]) * 2
        # 原有的 KDJ [5]
        low9, high9 = df["最低價"].rolling(9).min(), df["最高價"].rolling(9).max()
        rsv = (df["收盤價"] - low9) / (high9 - low9) * 100
        df["K"], df["D"] = rsv.ewm(com=2).mean(), rsv.ewm(com=2).mean().ewm(com=2).mean()
        df["J"] = 3 * df["K"] - 2 * df["D"]
        s, l = self.ma_short_period, self.ma_long_period
        close = df["收盤價"]
        df["ma_s"] = close.rolling(s).mean()
        df["ma_l"] = close.rolling(l).mean()
        df["ma5"], df["ma20"] = df["ma_s"], df["ma_l"]
        std = close.rolling(l).std()
        df["ub"], df["lb"] = df["ma_l"] + 2 * std, df["ma_l"] - 2 * std
        df["均價"], df["每筆均量"] = df["成交金額"] / df["成交股數"], df["成交股數"] / df["成交筆數"]
        df["每筆均量_ma5"] = df["每筆均量"].rolling(self.vol_ma_short).mean()
        vol_k = df["成交股數"]
        df["vol_ma5"] = vol_k.rolling(self.vol_ma_short).mean()
        df["vol_ma20"] = vol_k.rolling(self.vol_ma_long).mean()
        self._est_vol = self._estimate_today_volume()

    def _estimate_today_volume(self):
        """估算今日全市場成交量（僅最新一筆為今日時有效，台股 09:00–13:30）"""
        if self.df_all is None or len(self.df_all) == 0:
            return None
        last_date = self.df_all.iloc[-1]['日期']
        now = pd.Timestamp.now()
        if last_date.date() != now.date():
            return None
        market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
        market_close = now.replace(hour=13, minute=30, second=0, microsecond=0)
        if now < market_open:
            return None
        if now >= market_close:
            return float(self.df_all.iloc[-1]['成交股數'])
        elapsed = max((now - market_open).total_seconds() / 60, 1)
        ratio = 270.0 / elapsed
        return float(self.df_all.iloc[-1]['成交股數']) * ratio

    def _merge_sr_candidates(self, *pools):
        """合併多來源候選，同價位加總量能。"""
        merged = {}
        for pool in pools:
            for vol, price in pool:
                key = round(float(price), 4)
                merged[key] = merged.get(key, 0.0) + float(vol)
        return sorted(((v, p) for p, v in merged.items()), key=lambda x: -x[0])

    def _volume_profile_candidates(self, df, price_min, price_max):
        """可視區成交量分布的 local peak。"""
        price_range = price_max - price_min
        if price_range <= 0:
            return []
        n_bins = max(40, min(80, len(df) * 2))
        bin_size = price_range / n_bins
        bins = np.zeros(n_bins)
        r = self.SR_PEAK_RADIUS
        for _, row in df.iterrows():
            vol = row["成交股數"]
            lo = int((row["最低價"] - price_min) / bin_size)
            hi = int((row["最高價"] - price_min) / bin_size)
            lo, hi = max(0, min(lo, n_bins - 1)), max(0, min(hi, n_bins - 1))
            span = max(hi - lo + 1, 1)
            for b in range(lo, hi + 1):
                bins[b] += vol / span
        out = []
        for b in range(r, n_bins - r):
            if bins[b] <= 0:
                continue
            if all(bins[b] >= bins[b + d] for d in range(-r, r + 1) if d != 0):
                out.append((bins[b], price_min + (b + 0.5) * bin_size))
        return out

    def _swing_sr_candidates(self, df, current_close):
        """波段低點→支撐候選、波段高點→壓力候選（附該根 K 成交量）。"""
        w = self.SR_SWING_WINDOW
        lows, highs = [], []
        if len(df) < w * 2 + 1:
            return lows, highs
        lo_vals = df["最低價"].values
        hi_vals = df["最高價"].values
        vols = df["成交股數"].values
        for i in range(w, len(df) - w):
            seg_lo = lo_vals[i - w : i + w + 1]
            seg_hi = hi_vals[i - w : i + w + 1]
            v = float(vols[i])
            p_lo, p_hi = float(lo_vals[i]), float(hi_vals[i])
            if p_lo == seg_lo.min() and p_lo < current_close * 0.999:
                lows.append((v, p_lo))
            if p_hi == seg_hi.max() and p_hi > current_close * 1.001:
                highs.append((v, p_hi))
        return lows, highs

    def _pick_spaced_sr_levels(self, candidates, current_close, side, price_range, max_lines=2):
        """收盤下方只出支撐、上方只出壓力；同側最多 max_lines 條且強制間距。"""
        min_gap = max(price_range * self.SR_MIN_GAP_RATIO, current_close * 0.012)
        if side == "support":
            pool = [(v, p) for v, p in candidates if p < current_close * 0.999]
            pool.sort(key=lambda x: (-x[0], -x[1]))
        else:
            pool = [(v, p) for v, p in candidates if p > current_close * 1.001]
            pool.sort(key=lambda x: (-x[0], x[1]))
        selected = []
        for _, price in pool:
            if any(abs(price - s) < min_gap for s in selected):
                continue
            selected.append(price)
            if len(selected) >= max_lines:
                break
        return sorted(selected, reverse=True) if side == "support" else sorted(selected)

    def _sr_fallback_levels(self, df, current_close, price_min, price_max, side, price_range):
        """量能峰不足時，以可視區極值／近期波段補一條。"""
        recent = df.tail(min(20, len(df)))
        if side == "support":
            below = df[df["最低價"] < current_close * 0.999]
            if below.empty:
                return []
            p = float(below["最低價"].min())
            if recent["最低價"].min() < current_close:
                p = min(p, float(recent["最低價"].min()))
            return [p] if p < current_close * 0.999 else []
        above = df[df["最高價"] > current_close * 1.001]
        if above.empty:
            return []
        p = float(above["最高價"].max())
        if recent["最高價"].max() > current_close:
            p = max(p, float(recent["最高價"].max()))
        return [p] if p > current_close * 1.001 else []

    def _calc_support_resistance(self):
        """支撐＝最後收盤下方量能／波段密集區；壓力＝上方。兩側同時計算，不做漲跌單邊過濾。"""
        if not self._sr_dirty:
            return self._sr_cache

        df = self.df
        if df is None or len(df) < 5:
            self._sr_cache = ([], [])
            self._sr_dirty = False
            return self._sr_cache

        price_min = float(df["最低價"].min())
        price_max = float(df["最高價"].max())
        price_range = price_max - price_min
        if price_range == 0:
            self._sr_cache = ([], [])
            self._sr_dirty = False
            return self._sr_cache

        current_close = float(df["收盤價"].iloc[-1])
        vol_cands = self._volume_profile_candidates(df, price_min, price_max)
        swing_lows, swing_highs = self._swing_sr_candidates(df, current_close)

        support_pool = self._merge_sr_candidates(vol_cands, swing_lows)
        resist_pool = self._merge_sr_candidates(vol_cands, swing_highs)

        supports = self._pick_spaced_sr_levels(
            support_pool, current_close, "support", price_range)
        resistances = self._pick_spaced_sr_levels(
            resist_pool, current_close, "resistance", price_range)

        if not supports:
            lb = df.iloc[-1].get("lb")
            if lb is not None and not pd.isna(lb) and float(lb) < current_close * 0.999:
                supports = [float(lb)]
            else:
                supports = self._sr_fallback_levels(
                    df, current_close, price_min, price_max, "support", price_range)[:1]
        if not resistances:
            ub = df.iloc[-1].get("ub")
            if ub is not None and not pd.isna(ub) and float(ub) > current_close * 1.001:
                resistances = [float(ub)]
            else:
                resistances = self._sr_fallback_levels(
                    df, current_close, price_min, price_max, "resistance", price_range)[:1]

        supports = [p for p in supports if p < current_close * 0.999]
        resistances = [p for p in resistances if p > current_close * 1.001]

        self._sr_cache = (supports, resistances)
        self._sr_dirty = False
        return self._sr_cache

    def _apply_x_zoom(self, fig, axes, zoom_in):
        """X 軸縮放：只改 n_days／start_idx，不改週期 unit。右緣（最新 K）盡量固定。"""
        if self.df_all is None or len(self.df_all) < 2:
            return
        max_n = len(self.df_all)
        step = max(3, int(self.n_days * self.N_DAYS_ZOOM_RATIO))
        end = self.start_idx + self.n_days
        if zoom_in:
            self.n_days = max(self.N_DAYS_MIN, self.n_days - step)
        else:
            self.n_days = min(max_n, self.n_days + step)
        self.start_idx = max(0, min(end - self.n_days, max_n - self.n_days))
        self.update_view(fig, axes)

    def _effective_tick_interval(self, n):
        if not self.TICK_INTERVAL_AUTO or n < 2:
            return max(1, self.TICK_INTERVAL)
        if n <= 18:
            return max(1, n // 5)
        if n <= 35:
            return 4
        if n <= 70:
            return 7
        if n <= 120:
            return 10
        return 14

    def _kline_auto_ylim(self, df):
        lo = float(df["最低價"].min())
        hi = float(df["最高價"].max())
        for col in ("ma_s", "ma_l", "ub", "lb"):
            if col in df.columns:
                ser = df[col].dropna()
                if len(ser):
                    lo, hi = min(lo, float(ser.min())), max(hi, float(ser.max()))
        for p in self._sr_cache[0] + self._sr_cache[1]:
            lo, hi = min(lo, p), max(hi, p)
        pad = max((hi - lo) * 0.06, hi * 0.002)
        return lo - pad, hi + pad

    def _apply_k_ylim(self, ax, auto_lo, auto_hi):
        if self.k_y_zoom <= 1.01 and self.k_y_center is None:
            ax.set_ylim(auto_lo, auto_hi)
            return
        mid = self.k_y_center if self.k_y_center is not None else (auto_lo + auto_hi) / 2
        half = (auto_hi - auto_lo) / 2 / max(self.k_y_zoom, 0.25)
        ax.set_ylim(mid - half, mid + half)

    def _apply_y_zoom(self, fig, axes, zoom_in):
        if zoom_in:
            self.k_y_zoom = min(self.k_y_zoom * 1.18, 25.0)
        else:
            self.k_y_zoom = max(self.k_y_zoom / 1.18, 0.35)
        if self.df is not None and len(self.df):
            self.k_y_center = float(self.df["收盤價"].iloc[-1])
        self.update_view(fig, axes)

    def reset_y_view(self, fig, axes):
        self.k_y_zoom = 1.0
        self.k_y_center = None
        self.update_view(fig, axes)

    def export_png(self, fig, dpi=150):
        """匯出目前四聯圖為 PNG。"""
        unit_tag = self.getUnit().replace("/", "")
        ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        path = f"{self.code}_{unit_tag}_{ts}.png"
        fig.savefig(
            path, dpi=dpi, facecolor=fig.get_facecolor(),
            edgecolor="none", bbox_inches="tight",
        )
        print(f"[cStocks] 圖表已儲存: {os.path.abspath(path)}")
        return path

   
    def _draw_kline_panel(self, ax):
        ax.set_title(self.getName(), color=self.palette.fg)
        df = self.df.reset_index(drop=True)
        n = len(df)
        x = np.arange(n)

        # RGBA 調色覆蓋（取自 settings.json）
        _rise = getattr(self.palette, 'rise_color', self.palette.rise)
        _fall = getattr(self.palette, 'fall_color', self.palette.fall)
        _ma_s = getattr(self.palette, 'ma_s_color', self.palette.ma5)
        _ma_l = getattr(self.palette, 'ma_l_color', self.palette.ma20)
        _bb   = getattr(self.palette, 'bb_color', self.palette.bb_line)

        # ── 向量化 K 線繪製 (單次 vlines + bar，取代逐根 Rectangle) ──
        is_up = df['收盤價'].values >= df['開盤價'].values
        wick_colors = np.where(is_up, _rise, _fall)
        self.max = float(df['最高價'].max())
        self.min = float(df['最低價'].min())

        ax.vlines(x, df['最低價'].values, df['最高價'].values,
                  colors=wick_colors, lw=1)

        body_bottom = np.minimum(df['開盤價'].values, df['收盤價'].values)
        body_height = np.abs(df['收盤價'].values - df['開盤價'].values)
        up_mask = is_up
        down_mask = ~is_up
        if up_mask.any():
            ax.bar(x[up_mask], body_height[up_mask], 0.6,
                   bottom=body_bottom[up_mask], color=_rise)
        if down_mask.any():
            ax.bar(x[down_mask], body_height[down_mask], 0.6,
                   bottom=body_bottom[down_mask], color=_fall)

        # ── 價格標籤 (刻度 + 極值) ──
        label_step = self._effective_tick_interval(n)
        tick_mask = np.zeros(n, dtype=bool)
        tick_mask[::label_step] = True
        tick_mask[-1] = True
        is_extreme = (df['最高價'].values == self.max) | (df['最低價'].values == self.min)
        extreme_mask = is_extreme & ~tick_mask
        if n >= 3:
            extreme_mask[n-2:] = False
        label_indices = np.where(tick_mask | extreme_mask)[0]

        for i in label_indices:
            r = df.iloc[i]
            if is_up[i] or (self.max == r['最高價']):
                ax.text(i, float(r['最高價']) * 1.002,
                        f"{r['最高價']}\n{r['收盤價']}",
                        color=wick_colors[i], fontsize=7, ha='center', va='bottom')
            else:
                ax.text(i, float(r['最低價']) * 0.998,
                        f"{r['收盤價']}\n{r['最低價']}",
                        color=wick_colors[i], fontsize=7, ha='center', va='top')

        # ── 均線與 Bollinger（預設開啟）──
        ax.plot(x, df["ma_s"], color=_ma_s,
                label=f"{self.ma_short_period}MA")
        ax.plot(x, df["ma_l"], color=_ma_l,
                label=f"{self.ma_long_period}MA")
        if self.show_bollinger:
            ax.fill_between(
                x, df["ub"], df["lb"],
                color=self.palette.bb_fill, alpha=self.palette.bb_fill_alpha,
                label="Boll帶",
            )
            ax.plot(x, df["ub"], color=_bb, lw=1, ls="--",
                    alpha=0.9, label="Boll上")
            ax.plot(x, df["lb"], color=_bb, lw=1, ls="--",
                    alpha=0.9, label="Boll下")
        ax.yaxis.label.set_color(self.palette.grey)
        ax.set_ylabel("價格 (Price)", color=self.palette.grey)
        ax.grid(axis='both', linestyle='--', alpha=0.3)
        self._apply_k_ylim(ax, *self._kline_auto_ylim(df))

        # ── 支撐/壓力線 (快取) ──
        supports, resistances = self._sr_cache
        x_end = n - 1
        legend_extra = []
        for i, price in enumerate(supports):
            a = 0.9 if i == 0 else 0.6
            lw = 1.5 if i == 0 else 1.0
            line, = ax.plot([], [], color='#00C853', linestyle='--', linewidth=lw,
                            alpha=a, label=f"S{i+1} {price:.1f}")
            ax.axhline(y=price, color='#00C853', linestyle='--', linewidth=lw, alpha=a)
            ax.text(x_end, price, f" S{i+1} {price:.1f}", color='#00C853',
                    fontsize=7, va='center', ha='left', alpha=a,
                    bbox=dict(boxstyle='round,pad=0.1', facecolor=self.palette.bg, alpha=0.6, edgecolor='none'))
            legend_extra.append(line)
        for i, price in enumerate(resistances):
            a = 0.9 if i == 0 else 0.6
            lw = 1.5 if i == 0 else 1.0
            line, = ax.plot([], [], color='#FF1744', linestyle='--', linewidth=lw,
                            alpha=a, label=f"R{i+1} {price:.1f}")
            ax.axhline(y=price, color='#FF1744', linestyle='--', linewidth=lw, alpha=a)
            ax.text(x_end, price, f" R{i+1} {price:.1f}", color='#FF1744',
                    fontsize=7, va='center', ha='left', alpha=a,
                    bbox=dict(boxstyle='round,pad=0.1', facecolor=self.palette.bg, alpha=0.6, edgecolor='none'))
            legend_extra.append(line)
        ax.legend(loc="best", fontsize="x-small")

    def _draw_volume_panel(self, ax):
        vol = self.df['成交股數'] / 1000
        n = len(vol)
        _rise = getattr(self.palette, 'rise_color', self.palette.rise)
        _fall = getattr(self.palette, 'fall_color', self.palette.fall)
        _ma_s = getattr(self.palette, 'ma_s_color', self.palette.ma5)
        _ma_l = getattr(self.palette, 'ma_l_color', self.palette.ma20)

        # ── 向量化色彩：量增紅、量縮綠 ──
        if n >= 2:
            vol_arr = vol.values
            colors = np.where(vol_arr[1:] >= vol_arr[:-1], _rise, _fall)
            colors = np.append(colors, colors[-1] if len(colors) else _rise)
        else:
            colors = [_rise] * n

        ax.bar(range(n), vol, color=colors, alpha=0.6)
        ax.plot(self.df["vol_ma5"] / 1000, color=_ma_s, lw=1,
                label=f"{self.vol_ma_short}MA均量")
        ax.plot(self.df["vol_ma20"] / 1000, color=_ma_l, lw=1, alpha=0.85,
                label=f"{self.vol_ma_long}MA均量")
                
        # ── 智慧 Y 軸：上限取 95 百分位 * 1.2，避免單根大量壓扁全圖
        vol_95 = np.percentile(vol.dropna(), 95)
        vol_max = vol.max()
        y_top = vol_95 * 1.25
        ax.set_ylim(0, y_top)
        # 若有超出上限的極端量，加標籤提示
        for i, v in enumerate(vol):
            if v > y_top:
                ax.text(i, y_top * 0.97, f'{v:.0f}↑', color=colors[i],
                        fontsize=6, ha='center', va='top', rotation=90)

        ax.yaxis.label.set_color(self.palette.label)
        ax.set_ylabel("成交量 (Volume)", color=self.palette.grey)
        ax.grid(axis='both', linestyle='--', alpha=0.35)
        ax.legend(loc="upper left", fontsize="x-small")


    def _draw_macd_panel(self, ax):
        ax.bar(range(len(self.df)), self.df["macd"],
               color=np.where(self.df["macd"] >= 0, 'r', 'g'), alpha=0.5)
        ax.plot(self.df["dif"], label="DIF", lw=1)
        ax.plot(self.df["dea"], label="DEA", lw=1)
        ax.yaxis.label.set_color(self.palette.grey)

        # ── 智慧 Y 軸：取可視區內 DIF/DEA/MACD 三者的 95 百分位極值，對稱縮放
        all_vals = pd.concat([self.df["macd"], self.df["dif"], self.df["dea"]]).dropna()
        abs_95 = np.percentile(np.abs(all_vals), 95)
        y_rng = max(abs_95 * 1.4, 0.001)   # 至少保留最小範圍避免除零
        ax.set_ylim(-y_rng, y_rng)
        ax.axhline(0, color=self.palette.grey, lw=0.5, alpha=0.5)  # 零軸參考線

        # 金叉死叉標記
        gold = (self.df['dif'] > self.df['dea']) & \
               (self.df['dif'].shift(1) <= self.df['dea'].shift(1))
        ax.scatter(np.where(gold), self.df.loc[gold, 'dif'],
                   color='red', marker='^', s=30)
        ax.set_ylabel("MACD 指標", color=self.palette.grey)
        ax.legend(loc="upper left", fontsize="x-small")

   
    def _draw_kdj_panel(self,ax):
        kdColor=self.palette
        ax.plot(self.df["K"], label="K", color=kdColor.k, lw=1)
        ax.plot(self.df["D"], label="D", color=kdColor.d, lw=1)
        ax.plot(self.df["J"], label="J", color=kdColor.j, lw=1)
        ax.axhline(80, color=kdColor.kd80, ls=':', alpha=0.5); ax.axhline(20, color=kdColor.kd20, ls=':', alpha=0.5)
        # 4. 設置坐標軸標籤(label)顏色為白色ax.yaxis.label.set_color('white'),ax.xaxis.label.set_color('white')        
        ax.yaxis.label.set_color(self.palette.grey)
        # 外部專業刻度調整
        ax.set_yticks([0, 20, 40, 60, 80, 100, 120])
        ax.set_ylim(-15, 125)
        ax.set_ylabel("KDJ 指標",color = self.palette.grey)  # 子圖外部的label
        ax.grid(axis='both', linestyle='--', alpha=0.3)
        ax.legend(loc="best", fontsize=7)   # Removed explicit labels, will use plotted labels


    def update_view(self, fig, axes):
        self.df = self.df_all.iloc[self.start_idx : self.start_idx + self.n_days].reset_index(drop=True)

        # ── 可視區變更時重算支撐／壓力 ──
        self._sr_dirty = True
        self._calc_support_resistance()

        self.vlines.clear()
        for ax in axes:
            ax.clear()
            ax.set_facecolor(self.palette.bg)
            self.vlines.append(ax.axvline(x=0, color=self.palette.fg, linestyle='--', visible=False))
            ax.grid(True, color=self.palette.grid, ls='--', alpha=0.4)
            ax.yaxis.label.set_color(self.palette.grey)
            ax.tick_params(axis='y', colors=self.palette.grey)
            for spine in ax.spines.values():
                spine.set_color(self.palette.fg)
            for lab in ax.get_xticklabels():
                lab.set_color(self.palette.grey)
            for lab in ax.get_yticklabels():
                lab.set_color(self.palette.grey)

        self._draw_kline_panel(axes[0])
        self._draw_volume_panel(axes[1])
        self._draw_macd_panel(axes[2])
        self._draw_kdj_panel(axes[3])
        self._setup_xticks(axes[3])
        self._rebuild_overlays(axes)
        self._redraw_drawings(axes[0], axes[1])
        fig.canvas.draw_idle()

    def _setup_xticks(self, ax):
        n = len(self.df)
        step = self._effective_tick_interval(n)
        tick_idx = list(range(0, n, step))
        last = n - 1
        if tick_idx and last - tick_idx[-1] <= max(2, step // 2):
            tick_idx[-1] = last
        elif last not in tick_idx:
            tick_idx.append(last)
        ax.set_xticks(tick_idx)
        ax.set_xticklabels([self.df.iloc[i]['日期'].strftime('%y/%m/%d') for i in tick_idx], rotation=45, fontsize=8, color=self.palette.fg)
        # 3. 設置刻度(ticks)和刻度標籤(labels)顏色為白色colors='white'
        ax.tick_params(axis='x', colors=self.palette.grey)
        ax.tick_params(axis='y', colors=self.palette.grey)

    def _rebuild_overlays(self, axes):
        """每次 update_view 後重建被 ax.clear() 清掉的 info_box 與 emoji overlay"""
        _blank = make_emoji_img(' ', 48)

        # info_box 文字區（純文字，左上角，留出右邊給 emoji）
        self.info_box = axes[0].text(
            0.02, 0.97, "", transform=axes[0].transAxes, va='top', fontsize=9,
            color=self.palette.fg,
            bbox=dict(boxstyle='round', facecolor=self.palette.box, alpha=0.8)
        )
        # emoji 圖片放在 info_box 文字框「右邊外側」，不蓋住文字
        # x=0.30 對應文字框右緣右方，y=0.97 與文字框頂部對齊
        oi_emoji = offsetbox.OffsetImage(_blank, zoom=0.55)
        ab_emoji = offsetbox.AnnotationBbox(
            oi_emoji, (0.30, 0.97), frameon=False,
            xycoords='axes fraction', box_alignment=(0, 1)
        )
        axes[0].add_artist(ab_emoji)
        self.oi_emoji = oi_emoji   # 鯨魚/人群 emoji（🐋↗/🐋↘/👥）

        def _make_emoji(ax, xy=(0.97, 0.85)):
            oi = offsetbox.OffsetImage(_blank, zoom=0.5)
            ab = offsetbox.AnnotationBbox(oi, xy, frameon=False, xycoords='axes fraction')
            ax.add_artist(ab)
            return oi
        self.oi_vol = _make_emoji(axes[1])   # 成交量 emoji（🔥/📊）
        self.oi_kdj = _make_emoji(axes[3])

    # ══════════════════════════════════════════════════════════════
    # 繪圖工具系統
    # ══════════════════════════════════════════════════════════════

    def _draw_save(self):
        """儲存繪圖物件到 JSON（同股票代碼）"""
        path = f"{self.code}_drawings.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.draw_objects, f, ensure_ascii=False, indent=2)

    def _draw_load(self):
        """從 JSON 載入繪圖物件"""
        path = f"{self.code}_drawings.json"
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.draw_objects = json.load(f)

    def _x_to_date(self, x):
        """畫面 index → 日期字串（用於儲存，不受 start_idx 影響）"""
        idx = int(round(x))
        idx = max(0, min(idx, len(self.df) - 1))
        return str(self.df.iloc[idx]['日期'].date())

    def _date_to_x(self, date_str):
        """日期字串 → 當前可視區畫面 index（找不到回傳 None）"""
        if self.df is None or len(self.df) == 0:
            return None
        try:
            target = pd.to_datetime(date_str).date()
            matches = self.df[self.df['日期'].dt.date == target].index
            if len(matches) > 0:
                result = float(matches[0])
                return result if 0 <= result < len(self.df) else None
            # 找不到精確日期時，找最近的
            dates = self.df['日期'].dt.date.values
            diffs = [abs((d - target).days) for d in dates]
            result = float(np.argmin(diffs))
            return result if 0 <= result < len(self.df) else None
        except:
            return None

    def _obj_to_screen(self, obj):
        """將物件的日期座標轉回當前畫面 index，回傳轉換後的 obj copy（不修改原始）"""
        o = obj.copy()
        n = len(self.df) if self.df is not None else 0
        for key in ('x1', 'x2', 'x3'):
            dkey = key.replace('x', 'd')  # d1, d2, d3
            if dkey in o:
                sx = self._date_to_x(o[dkey])
                if sx is not None and 0 <= sx < max(n, 1):
                    o[key] = sx
        return o

    def _draw_artist_from_obj(self, ax_k, ax_v, obj):
        """根據 draw_objects 中的一筆 dict 重建 matplotlib artist，回傳 artist list"""
        # 日期→畫面座標轉換
        o = self._obj_to_screen(obj)
        t    = o['type']
        c    = o.get('color', '#FFFF00')
        x1,y1 = o['x1'], o['y1']
        x2,y2 = o.get('x2', x1), o.get('y2', y1)
        panel = o.get('panel', 'k')   # 'k' 或 'v'
        ax = ax_k if panel == 'k' else ax_v
        artists = []

        if t == 'hline':
            line = ax.axhline(y=y1, color=c, lw=1.5, linestyle='-', alpha=0.85, picker=5)
            artists.append(line)
        elif t == 'vline':
            line = ax.axvline(x=x1, color=c, lw=1.5, linestyle='-', alpha=0.85, picker=5)
            artists.append(line)
        elif t == 'note':
            txt = o.get('text', '')
            bg = o.get('bg', '#00000088')
            ann = ax.text(x1, y1, f' {txt}', color=c, fontsize=8, va='center', ha='left',
                          bbox=dict(boxstyle='round,pad=0.3', facecolor=bg, edgecolor=c, alpha=0.85),
                          picker=5)
            artists.append(ann)
        elif t in ('line', 'arrow', 'arrow2'):
            arrowstyle = None
            if t == 'arrow':
                arrowstyle = '->'
            elif t == 'arrow2':
                arrowstyle = '<->'
            if arrowstyle:
                ann = ax.annotate('', xy=(x2,y2), xytext=(x1,y1),
                    arrowprops=dict(arrowstyle=arrowstyle, color=c, lw=1.5),
                    picker=5)
                artists.append(ann)
            else:
                line, = ax.plot([x1,x2],[y1,y2], color=c, lw=1.5, alpha=0.85, picker=5)
                artists.append(line)
        elif t == 'channel':
            dy = y2 - y1
            offset = o.get('channel_offset', abs(dy)*0.3)
            norm = offset
            l1, = ax.plot([x1,x2],[y1,y2], color=c, lw=1.5, alpha=0.9, picker=5)
            l2, = ax.plot([x1,x2],[y1+norm, y2+norm], color=c, lw=1, alpha=0.5, linestyle='--', picker=5)
            l3, = ax.plot([x1,x2],[y1-norm, y2-norm], color=c, lw=1, alpha=0.5, linestyle='--', picker=5)
            ax.fill_between([x1,x2],[y1-norm,y2-norm],[y1+norm,y2+norm], color=c, alpha=0.05)
            artists.extend([l1,l2,l3])
        elif t == 'rect':
            rect = mpatches.Rectangle(
                (min(x1,x2), min(y1,y2)), abs(x2-x1), abs(y2-y1),
                linewidth=1.5, edgecolor=c, facecolor=c, alpha=0.12, picker=5)
            ax.add_patch(rect)
            artists.append(rect)
        elif t == 'arc':
            # ── 三點貝茲曲線弧：P1=起, P2=終, P3=弧頂控制點
            from matplotlib.path import Path
            import matplotlib.patches as mpatches_local
            x3, y3 = o.get('x3', (x1+x2)/2), o.get('y3', max(y1,y2) + abs(y2-y1)*0.5)
            # 二次貝茲：P1 → ctrl → P2，ctrl 由 P3 反推（令貝茲中點 = P3）
            cx_ctrl = 2*x3 - (x1+x2)/2
            cy_ctrl = 2*y3 - (y1+y2)/2
            # 細分貝茲曲線成 50 段折線
            pts = np.array([
                (1-t_)**2 * np.array([x1,y1]) +
                2*(1-t_)*t_ * np.array([cx_ctrl, cy_ctrl]) +
                t_**2 * np.array([x2, y2])
                for t_ in np.linspace(0, 1, 50)
            ])
            line, = ax.plot(pts[:,0], pts[:,1], color=c, lw=1.5, alpha=0.9, picker=5)
            # 弧頂虛線輔助點（小叉）
            ax.plot(x3, y3, '+', color=c, ms=6, alpha=0.5)
            artists.append(line)
        elif t == 'fib':
            levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
            dy = y2 - y1
            for lv in levels:
                py = y1 + dy * lv
                lc = '#FFD700' if abs(lv - 0.618) < 0.001 else c
                lw = 2.0 if abs(lv - 0.618) < 0.001 else 1.0
                line = ax.axhline(y=py, color=lc, lw=lw, linestyle='--', alpha=0.75, picker=5)
                ax.text(x2, py, f' {lv:.3f}  {py:.2f}',
                        color=lc, fontsize=7, va='bottom', alpha=0.9)
                artists.append(line)
        elif t == 'measure':
            x3, y3 = o.get('x3', x2), o.get('y3', y2)
            dx = x2 - x1
            dy = y2 - y1
            x4, y4 = x3 + dx, y3 + dy
            l_ref, = ax.plot([x1, x2], [y1, y2], color=c, lw=1.5,
                             linestyle='--', alpha=0.7, picker=5)
            ann = ax.annotate('', xy=(x4, y4), xytext=(x3, y3),
                arrowprops=dict(arrowstyle='->', color=c, lw=2.0))
            rect = mpatches.Rectangle(
                (min(x3, x4), min(y3, y4)), abs(dx), abs(dy),
                linewidth=0, facecolor=c, alpha=0.08)
            ax.add_patch(rect)
            mid_x, mid_y = (x3 + x4) / 2, (y3 + y4) / 2
            pct = (dy / y1 * 100) if y1 != 0 else 0
            ax.text(mid_x, mid_y,
                    f' Δ{abs(dx):.0f}K  {dy:+.2f}({pct:+.1f}%)',
                    color=c, fontsize=8, va='bottom',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#00000088',
                              edgecolor='none', alpha=0.7))
            artists.extend([l_ref, ann, rect])
        return artists

    @staticmethod
    def _point_segment_dist(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        qx, qy = x1 + t * dx, y1 + t * dy
        return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5

    def _dist_to_draw_obj(self, obj, x, y):
        x1, y1 = obj['x1'], obj['y1']
        x2, y2 = obj.get('x2', x1), obj.get('y2', y1)
        t = obj['type']
        if t == 'hline':
            return abs(y - y1)
        if t == 'vline':
            return abs(x - x1)
        if t == 'note':
            return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        if t in ('line', 'arrow', 'arrow2', 'channel', 'rect', 'fib', 'measure'):
            return self._point_segment_dist(x, y, x1, y1, x2, y2)
        if t == 'arc' and 'x3' in obj:
            return min(
                self._point_segment_dist(x, y, x1, y1, x2, y2),
                ((x - obj['x3']) ** 2 + (y - obj['y3']) ** 2) ** 0.5,
            )
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5

    def _find_nearest_draw_index(self, x, y):
        n_vis = len(self.df) if self.df is not None else self.n_days
        thresh = max(5.0, n_vis * 0.07)
        best, best_d = None, 1e9
        for i, obj in enumerate(self.draw_objects):
            if obj.get('unit', self.unit) != self.unit:
                continue
            d = self._dist_to_draw_obj(obj, x, y)
            if d < best_d:
                best_d, best = d, i
        return best if best is not None and best_d < thresh else None

    def _redraw_drawings(self, ax_k, ax_v):
        """update_view 後把當前週期的繪圖物件重新畫回去（不同週期的物件隱藏保留）"""
        self.draw_artists = []
        for obj in self.draw_objects:
            # 只畫出與當前週期相同的物件；沒有 unit 欄位的舊資料視為相容（全顯示）
            if obj.get('unit', self.unit) != self.unit:
                self.draw_artists.append([])  # 佔位，保持 index 對齊
                continue
            # 將日期座標轉為當前畫面座標，同步回 obj 供 _find_nearest_draw_index 選取使用
            so = self._obj_to_screen(obj)
            for key in ('x1', 'x2', 'x3'):
                if key in so:
                    obj[key] = so[key]
            arts = self._draw_artist_from_obj(ax_k, ax_v, obj)
            self.draw_artists.append(arts)

    def _setup_drawing_ui(self, fig, axes):
        """右側新增工具選擇 RadioButtons + 顏色 RadioButtons + 清除 Button"""
        ax_k, ax_v = axes[0], axes[1]

        # ── 工具選擇（右側上方；按鈕區下移避免遮住色盤）
        ax_tool = plt.axes([0.91, 0.735, 0.08, 0.235], facecolor='#e8e8e8')
        tools =      ('cursor','hline','vline','line','arrow','arrow2','channel','rect','arc','fib','measure','note','select','clear')
        tool_labels = ('[+] 游標','-- 水平','|  垂直','/  切線','-> 箭頭','<-> 雙箭','=  軌道','[] 矩形','~  圓弧','F  斐波','^  測距','[N] 備註','[*]選取','[X]清除')
        self.radio_tool = RadioButtons(ax_tool, tool_labels, active=0)
        tool_map = dict(zip(tool_labels, tools))
        def on_tool(label):
            self.draw_tool = tool_map[label]
            self.draw_step = 0
            self.draw_p1 = None
            self.draw_p2 = None
            if self.draw_preview:
                try: self.draw_preview.remove()
                except: pass
                self.draw_preview = None
            if self.draw_tool != 'select':
                self.selected_obj = None
            if self.draw_tool == 'clear':
                # 只清除當前週期的物件，其他週期的保留
                self.draw_objects = [o for o in self.draw_objects
                                     if o.get('unit', self.unit) != self.unit]
                self.draw_artists.clear()
                self.selected_obj = None
                self._draw_save()
                self.update_view(fig, axes)
        self.radio_tool.on_clicked(on_tool)

        # ── 顏色選擇（與下方按鈕錯開，避免被遮住）
        ax_color = plt.axes([0.91, 0.618, 0.08, 0.11], facecolor='#e8e8e8')
        colors_label = ('黃','白','紅','綠','青','紫')
        colors_val   = ('#FFFF00','#FFFFFF','#FF4444','#00E676','#00BCD4','#CE93D8')
        self.radio_color = RadioButtons(ax_color, colors_label, active=0)
        color_map = dict(zip(colors_label, colors_val))
        # 把 radio 按鈕本身也設成對應顏色（相容新舊版 matplotlib）
        circles = getattr(self.radio_color, 'circles', None) or self.radio_color.ax.patches
        for circle, lbl in zip(circles, colors_label):
            circle.set_facecolor(color_map[lbl])
        def on_color(label):
            self.draw_color = color_map[label]
            if self.selected_obj is not None:
                idx = self.selected_obj
                if 0 <= idx < len(self.draw_objects):
                    self.draw_objects[idx]['color'] = self.draw_color
                    self._draw_save()
                    self.update_view(fig, axes)
                    fig.canvas.draw()
        self.radio_color.on_clicked(on_color)

        # ── 儲存 / PNG 按鈕（2026-05-26 已改用純文字標籤取代 emoji）
        ax_save = plt.axes([0.91, 0.575, 0.08, 0.030], facecolor='#e8e8e8')
        self.btn_save = Button(ax_save, '[Save] 繪圖', color='#b0bec5', hovercolor='#78909c')
        def on_save(event):
            self._draw_save()
        self.btn_save.on_clicked(on_save)

        ax_png = plt.axes([0.91, 0.537, 0.08, 0.030], facecolor='#e8e8e8')
        self.btn_png = Button(ax_png, '[PNG] 匯出', color='#90caf9', hovercolor='#42a5f5')
        def on_png(event):
            self.export_png(fig)
        self.btn_png.on_clicked(on_png)

        ax_zoom_in = plt.axes([0.91, 0.500, 0.038, 0.028], facecolor='#e8e8e8')
        ax_zoom_out = plt.axes([0.952, 0.500, 0.038, 0.028], facecolor='#e8e8e8')
        self.btn_zoom_in = Button(ax_zoom_in, '＋', color='#c5e1a5', hovercolor='#9ccc65')
        self.btn_zoom_out = Button(ax_zoom_out, '－', color='#ffe082', hovercolor='#ffca28')
        self.btn_zoom_in.on_clicked(lambda e: self._apply_x_zoom(fig, axes, True))
        self.btn_zoom_out.on_clicked(lambda e: self._apply_x_zoom(fig, axes, False))

        ax_cfg = plt.axes([0.91, 0.463, 0.08, 0.028], facecolor='#e8e8e8')
        self.btn_cfg = Button(ax_cfg, '儲存設定', color='#d1c4e9', hovercolor='#b39ddb')
        self.btn_cfg.on_clicked(lambda e: self.save_settings())

        ax_yreset = plt.axes([0.91, 0.428, 0.08, 0.028], facecolor='#e8e8e8')
        self.btn_yreset = Button(ax_yreset, 'Y軸還原', color='#e0e0e0', hovercolor='#bdbdbd')
        self.btn_yreset.on_clicked(lambda e: self.reset_y_view(fig, axes))

        # ── 綁定繪圖滑鼠事件
        self._bind_drawing_events(fig, axes)

    def _bind_drawing_events(self, fig, axes):
        ax_k, ax_v = axes[0], axes[1]
        DRAW_AXES = [ax_k, ax_v]

        def _panel(ax):
            return 'k' if ax is ax_k else 'v'

        def _remove_preview():
            if self.draw_preview is not None:
                arts = self.draw_preview if isinstance(self.draw_preview, list) else [self.draw_preview]
                for a in arts:
                    try: a.remove()
                    except: pass
                self.draw_preview = None

        def on_press(event):
            if event.inaxes not in DRAW_AXES: return
            if event.xdata is None or event.ydata is None: return
            tool = self.draw_tool
            x, y = event.xdata, event.ydata

            # ── select 模式：找最近物件（僅當前週期）
            if tool == 'select' and event.button == 1:
                best = self._find_nearest_draw_index(x, y)
                if best is not None:
                    self.selected_obj = best
                    obj = self.draw_objects[best]
                    self.drag_offset = (obj['x1'] - x, obj['y1'] - y)
                else:
                    self.selected_obj = None
                return

            # ── 右鍵：刪除最近物件
            if event.button == 3 and tool in ('select', 'cursor'):
                best = self._find_nearest_draw_index(x, y)
                if best is not None:
                    if best == self.selected_obj:
                        self.selected_obj = None
                    self.draw_objects.pop(best)
                    self._draw_save()
                    self.update_view(fig, axes)
                return

            if event.button != 1: return
            if tool in ('cursor','select','clear'): return

            # ── 單點工具（水平線/垂直線/備註）
            if tool in ('hline', 'vline', 'note'):
                obj = {'type': tool, 'x1': x, 'y1': y, 'x2': x, 'y2': y,
                       'd1': self._x_to_date(x),
                       'unit': self.unit,
                       'color': self.draw_color, 'panel': _panel(event.inaxes)}
                if tool == 'note':
                    obj['text'] = self._x_to_date(x)
                    obj['bg'] = '#00000088'
                self.draw_objects.append(obj)
                arts = self._draw_artist_from_obj(ax_k, ax_v, obj)
                self.draw_artists.append(arts)
                self._draw_save()
                fig.canvas.draw_idle()
                return

            # ── 兩點工具 / 三點工具(measure)
            if self.draw_step == 0:
                self.draw_step = 1
                self.draw_p1 = (x, y, _panel(event.inaxes))
            elif self.draw_step == 1:
                if self.draw_tool in ('measure', 'arc'):
                    # 第二點：記錄終點，繼續等第三點（measure=平移起點, arc=弧頂控制）
                    self.draw_step = 2
                    self.draw_p2 = (x, y)
                    _remove_preview()
                else:
                    x1, y1, panel = self.draw_p1
                    _remove_preview()
                    obj = {'type': self.draw_tool,
                           'x1': x1, 'y1': y1, 'x2': x, 'y2': y,
                           'd1': self._x_to_date(x1), 'd2': self._x_to_date(x),
                           'unit': self.unit,
                           'color': self.draw_color, 'panel': panel}
                    if self.draw_tool == 'channel':
                        obj['channel_offset'] = abs(y - y1) * 0.4
                    self.draw_objects.append(obj)
                    arts = self._draw_artist_from_obj(ax_k, ax_v, obj)
                    self.draw_artists.append(arts)
                    self._draw_save()
                    self.draw_step = 0
                    self.draw_p1 = None
                    fig.canvas.draw_idle()
            elif self.draw_step == 2:
                x1, y1, panel = self.draw_p1
                x2m, y2m = self.draw_p2
                _remove_preview()
                if self.draw_tool == 'arc':
                    obj = {'type': 'arc',
                           'x1': x1, 'y1': y1, 'x2': x2m, 'y2': y2m,
                           'x3': x,  'y3': y,
                           'd1': self._x_to_date(x1), 'd2': self._x_to_date(x2m),
                           'd3': self._x_to_date(x),
                           'unit': self.unit,
                           'color': self.draw_color, 'panel': panel}
                else:  # measure
                    obj = {'type': 'measure',
                           'x1': x1, 'y1': y1, 'x2': x2m, 'y2': y2m,
                           'x3': x,  'y3': y,
                           'd1': self._x_to_date(x1), 'd2': self._x_to_date(x2m),
                           'd3': self._x_to_date(x),
                           'unit': self.unit,
                           'color': self.draw_color, 'panel': panel}
                self.draw_objects.append(obj)
                arts = self._draw_artist_from_obj(ax_k, ax_v, obj)
                self.draw_artists.append(arts)
                self._draw_save()
                self.draw_step = 0
                self.draw_p1 = None
                self.draw_p2 = None
                fig.canvas.draw_idle()

        def on_release(event):
            # 保留 selected_obj，才能放開滑鼠後用色盤改色
            pass

        def on_motion(event):
            if event.inaxes not in DRAW_AXES: return
            if event.xdata is None: return
            x, y = event.xdata, event.ydata

            # 拖曳移動選取物件
            if self.selected_obj is not None and event.button == 1:
                i = self.selected_obj
                obj = self.draw_objects[i]
                dx_obj = obj.get('x2', obj['x1']) - obj['x1']
                dy_obj = obj.get('y2', obj['y1']) - obj['y1']
                nx = x + self.drag_offset[0]
                ny = y + self.drag_offset[1]
                obj['x1'], obj['y1'] = nx, ny
                obj['x2'], obj['y2'] = nx + dx_obj, ny + dy_obj
                # ── 同步更新日期座標，讓拖曳後的位置跟著K線跑
                obj['d1'] = self._x_to_date(nx)
                obj['d2'] = self._x_to_date(nx + dx_obj)
                if 'x3' in obj:
                    dx3 = obj['x3'] - (obj['x1'] - (x + self.drag_offset[0]))
                    obj['d3'] = self._x_to_date(obj['x3'])
                self.update_view(fig, axes)
                return

            # 預覽線（兩點工具第一點已點下）
            if self.draw_step >= 1 and self.draw_p1 is not None:
                tool = self.draw_tool
                if tool in ('cursor','select','clear','hline','vline','fib','note'): return
                ax_target = ax_k if self.draw_p1[2] == 'k' else ax_v
                _remove_preview()
                x1, y1 = self.draw_p1[0], self.draw_p1[1]
                c = self.draw_color

                if tool == 'measure':
                    if self.draw_step == 1:
                        prev, = ax_target.plot([x1, x], [y1, y], color=c,
                                               lw=1.5, alpha=0.6, linestyle='--')
                        self.draw_preview = prev
                    elif self.draw_step == 2 and self.draw_p2 is not None:
                        x2m, y2m = self.draw_p2
                        dx, dy = x2m - x1, y2m - y1
                        x4, y4 = x + dx, y + dy
                        l1, = ax_target.plot([x1, x2m], [y1, y2m], color=c,
                                             lw=1.5, linestyle='--', alpha=0.5)
                        l2, = ax_target.plot([x, x4], [y, y4], color=c,
                                             lw=2.0, alpha=0.8, linestyle='-')
                        pct = (dy / y1 * 100) if y1 != 0 else 0
                        txt = ax_target.text(
                            (x + x4) / 2, (y + y4) / 2,
                            f' Δ{abs(dx):.0f}K  {dy:+.2f}({pct:+.1f}%)',
                            color=c, fontsize=8,
                            bbox=dict(boxstyle='round,pad=0.2',
                                      facecolor='#00000088', edgecolor='none'))
                        self.draw_preview = [l1, l2, txt]
                elif tool == 'arc':
                    if self.draw_step == 1:
                        # 步驟1：P1已定，預覽弦線 + 輔助矩形框
                        l_chord, = ax_target.plot([x1, x], [y1, y], color=c,
                                                  lw=1, alpha=0.4, linestyle='--')
                        rect_prev = mpatches.Rectangle(
                            (min(x1,x), min(y1,y)), abs(x-x1), abs(y-y1),
                            linewidth=1, edgecolor=c, facecolor=c, alpha=0.05,
                            linestyle=':')
                        ax_target.add_patch(rect_prev)
                        self.draw_preview = [l_chord, rect_prev]
                    elif self.draw_step == 2 and self.draw_p2 is not None:
                        # 步驟2：P1+P2已定，預覽貝茲弧（P3=滑鼠位置）
                        x2m, y2m = self.draw_p2
                        cx_ctrl = 2*x - (x1+x2m)/2
                        cy_ctrl = 2*y - (y1+y2m)/2
                        pts = np.array([
                            (1-t_)**2 * np.array([x1,y1]) +
                            2*(1-t_)*t_ * np.array([cx_ctrl, cy_ctrl]) +
                            t_**2 * np.array([x2m, y2m])
                            for t_ in np.linspace(0, 1, 50)
                        ])
                        l_arc, = ax_target.plot(pts[:,0], pts[:,1], color=c, lw=1.5, alpha=0.7)
                        # 弦線 + 控制點輔助線（虛線）
                        l_chord, = ax_target.plot([x1, x2m], [y1, y2m], color=c,
                                                  lw=0.8, alpha=0.3, linestyle='--')
                        l_ctrl1, = ax_target.plot([x1, x], [y1, y], color=c,
                                                  lw=0.8, alpha=0.3, linestyle=':')
                        l_ctrl2, = ax_target.plot([x2m, x], [y2m, y], color=c,
                                                  lw=0.8, alpha=0.3, linestyle=':')
                        self.draw_preview = [l_arc, l_chord, l_ctrl1, l_ctrl2]
                elif tool in ('line','arrow','arrow2','channel'):
                    prev, = ax_target.plot([x1,x],[y1,y], color=c, lw=1, alpha=0.5, linestyle=':')
                    self.draw_preview = prev
                elif tool == 'rect':
                    prev = mpatches.Rectangle(
                        (min(x1,x), min(y1,y)), abs(x-x1), abs(y-y1),
                        linewidth=1, edgecolor=c, facecolor='none', alpha=0.5)
                    ax_target.add_patch(prev)
                    self.draw_preview = prev
                fig.canvas.draw_idle()

        fig.canvas.mpl_connect('button_press_event', on_press)
        fig.canvas.mpl_connect('button_release_event', on_release)
        fig.canvas.mpl_connect('motion_notify_event', on_motion)

    def _setup_cursor(self, fig, axes):
        self._ctrl_held = False

        def on_key_press(event):
            if event.key == 'control':
                self._ctrl_held = True

        def on_key_release(event):
            if event.key == 'control':
                self._ctrl_held = False

        def on_press(event):
            if event.button != 1: return
            if event.inaxes not in axes: return
            if event.xdata is None: return
            if self.draw_tool != 'cursor': return
            self.is_dragging = True
            self.press_x = event.xdata
            self.press_start_idx = self.start_idx
            if event.ydata is not None:
                self._press_y = event.ydata
                self._press_k_y_zoom = self.k_y_zoom
                if self.k_y_center is not None:
                    self._press_k_y_center = self.k_y_center
                elif self.df is not None and len(self.df) > 0:
                    self._press_k_y_center = (float(self.df['最低價'].min()) + float(self.df['最高價'].max())) / 2
                else:
                    self._press_k_y_center = event.ydata

        def on_release(event):
            self.is_dragging = False

        def on_mouse(event):
            if event.inaxes is None: return
            if self.is_dragging and self.press_x is not None:
                if self._ctrl_held and event.inaxes == axes[0] and hasattr(self, '_press_y'):
                    # Ctrl + 垂直拖曳於價格圖 = Y 軸縮放
                    dy = self._press_y - event.ydata
                    if self._press_k_y_center and abs(self._press_k_y_center) > 0.001:
                        factor = 1.0 + dy / abs(self._press_k_y_center) * 8.0
                        self.k_y_zoom = max(0.35, min(25.0, self._press_k_y_zoom * max(0.4, factor)))
                        self.k_y_center = self._press_k_y_center
                    self.update_view(fig, axes)
                else:
                    # 水平平移
                    dx = int(round(event.xdata - self.press_x))
                    self.start_idx = max(0, min(self.press_start_idx - dx, len(self.df_all) - self.n_days))
                    self.update_view(fig, axes)
            elif not self.is_dragging:   # 純移動，顯示資訊
                idx = int(round(event.xdata))
                if 0 <= idx < len(self.df):
                    r = self.df.iloc[idx]; is_up = r['收盤價'] >= r['開盤價']
                    is_big = r['每筆均量'] > r['每筆均量_ma5'] * 1.2
                    if is_big:
                        whale = '🐋↗' if r['收盤價'] >= r['均價'] else '🐋↘'
                        status = ("大戶追價" if is_up else "大戶吸收") if whale=='🐋↗' else ("高位調節" if is_up else "偷偷出貨")
                    else:
                        whale, status = '👥', '散戶盤整'
                    # emoji 獨立渲染（matplotlib text 無法顯示 emoji，需用 PIL 圖片）
                    self.oi_emoji.set_data(make_emoji_img(whale, 48))
                    # info_box 只放純文字（去掉 whale emoji）
                    est_line = ""
                    if getattr(self, '_est_vol', None) is not None:
                        est_line = f"預估量:{self._est_vol/1000:.0f}張 | "
                    txt = (f"{r['日期'].date()} | {status}  "
                           f"{self.ma_short_period}MA:{r['ma_s']:.1f} {self.ma_long_period}MA:{r['ma_l']:.1f}\n"
                           f"{est_line}均價:{r['均價']:.1f} 高:{r['最高價']:.1f} 開:{r['開盤價']:.1f} 收:{r['收盤價']} 低:{r['最低價']} 量{(r['成交股數']/1000):.1f}\n"
                           f"MACD:{r['macd']:.1f}  K:{r['K']:.1f} D:{r['D']:.1f}  布林:U:{r['ub']:.1f} STD:{r['ma20']:.1f}  L:{r['lb']:.1f}")
                    self.info_box.set_text(txt)
                    self.info_box.set_color(
                        getattr(self.palette, 'rise_color', self.palette.rise) if is_up
                        else getattr(self.palette, 'fall_color', self.palette.fall))
                    self.oi_vol.set_data(make_emoji_img('🔥' if r['成交股數'] > r['vol_ma5']*1.5 else '📊'))

                    x_pos = event.xdata
                    for vline in self.vlines:
                        vline.set_xdata([x_pos, x_pos])
                        vline.set_visible(True)

                    fig.canvas.draw_idle()

        fig.canvas.mpl_connect('key_press_event', on_key_press)
        fig.canvas.mpl_connect('key_release_event', on_key_release)
        fig.canvas.mpl_connect('button_press_event', on_press)
        fig.canvas.mpl_connect('button_release_event', on_release)
        fig.canvas.mpl_connect('motion_notify_event', on_mouse)

    def _setup_x_zoom(self, fig, axes):
        """滾輪：一般=X 縮放；Shift+滾輪於價格圖=Y 縮放。週期 unit 不變。"""

        def on_scroll(event):
            if event.inaxes not in axes:
                return
            if self.draw_tool != 'cursor':
                return
            if getattr(event, 'step', 0) == 0:
                return
            if event.key == 'shift' and event.inaxes is axes[0]:
                self._apply_y_zoom(fig, axes, zoom_in=(event.step > 0))
            else:
                self._apply_x_zoom(fig, axes, zoom_in=(event.step > 0))

        fig.canvas.mpl_connect('scroll_event', on_scroll)

    def plot_all(self, block=True):
        setup_chinese_font()
        fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=True,
            gridspec_kw={'height_ratios': [4, 1.5, 2, 2]}, facecolor=self.palette.bg)
        fig.canvas.manager.set_window_title(f"量價高手系統 - {self.code}")

        # ── 週期選擇 RadioButtons（右側中下）
        ax_radio = plt.axes([0.91, 0.10, 0.08, 0.30], facecolor='#f0f0f0')
        self.radio = RadioButtons(ax_radio, ('1分','5分','15分','30分','60分','日K','週K','月K'), active=self.unitIndex)
        def change_p(label):
            m = {'1分':'1T','5分':'5T','15分':'15T','30分':'30T','60分':'60T','日K':'D','週K':'W-FRI','月K':'ME'}
            self.unit = m[label]
            self.unitIndex = list(m.keys()).index(label)
            self.refresh_period_data()
            self.update_view(fig, axes)
            self.save_settings()
        self.radio.on_clicked(change_p)

        self._fig = fig
        # ── 載入上次儲存的繪圖 + 建立繪圖工具 UI
        self._draw_load()
        self.update_view(fig, axes)
        self._setup_cursor(fig, axes)
        self._setup_x_zoom(fig, axes)
        self._setup_drawing_ui(fig, axes)

        plt.tight_layout(rect=[0.01, 0.03, 0.90, 0.97])
        plt.show(block=block)
       

if __name__ == "__main__":
    # 測試：鴻海使用深色模式，台積電使用亮色模式 [348, Conversation History] "D"表示日K = {'1分':'1T','5分':'5T','15分':'15T','30分':'30T','60分':'60T','日K':'D','週K':'W-FRI','月K':'ME'}
    fox = cStock("2317", "鴻海","D", "Dark")
    #fox = cStock("2317.TW", "鴻海")
    fox.load_data("2317.csv",90)
    fox.plot_all(block=False) #False = 未鎖定,程式不會卡住，可以繼續執行

    tsmc = cStock("2330.TW", "台積電")
    tsmc.load_data("2330.csv")

 

    tsmc.plot_all()

"""
整合後的主要改變與說明：
MACD 與 KDJ 完整回歸：在 calculate_indicators 與 _draw 面板方法中，完整實現 EMA、RSV 計算，以及金叉 scatter 標註與 80/20 警戒線。
大戶 Whale 診斷系統：在 on_mouse 中，系統會自動比對 收盤價 與 均價。如果股價在跌但站穩均價且大單增加，系統會顯示 🟢 🐋↗ 大戶吸收 [Conversation History, 354]。
解決 Attribute 報錯：加入了 update_view 作為中央刷新方法，確保不管是手動滑動 X 軸還是點擊 Radio 按鈕切換週期，畫面都會同步重繪 [348, Conversation History]。
深色模式與視窗管理：StockPalette 會根據 style="Dark" 自動調整背景與 K 線顏色。且由於加入了 block 參數，可以同時開啟多個股票視窗進行「評估與對比」 [348, Conversation History]。
目視驗證：
K棒價格標籤：觀察 X 軸刻度處的 K 棒，若是紅K，上方應會出現「最高價」與「收盤價」；若是綠K，下方應會出現「收盤價」與「最低價」。
大戶吸收訊號：找到股價下跌但成交筆數不多、單筆量大的日子（綠 K 棒），資訊盒應顯示 🟢 🐋↗ 大戶持續吸收 [Conversation History]。
大戶脫手訊號：找到股價強拉但均價卻在下方的日子（紅 K 棒），資訊盒應顯示 🔴 🐋↘ 大戶拉高脫手 [Conversation History]。
MACD 標註：確認 DIF 線穿過 DEA 線時，是否有紅色的 ▲ (金叉) 符號出現在面板上
KDJ 標註：確認 K 值超過 80 時，是否有紅色的 ▲ 符號出現在面板上
布林通道：確認價格是否在布林通道內，且是否在布林通道上方或下方
均線：確認價格是否在均線上方或下方
均量：確認成交股數是否在均量上方或下方
成交量：確認成交量是否在均量上方或下方
成交量均量：確認成交量是否在均量上方或下方
修改支撐壓力算法：暫時以視覺驗證，未進行量化驗證.偏向短線評估,長線改看月線或季線
todo:
    ✥ 選取改色功能尚未完成
 右側選 ✥ 的圖示..等,幾乎都只看到一個方塊,似乎Emoji 渲染有問題
 目前右側設定工具區,無法完全顯示,需要調整,建議可以將設定工具區移動到左側,或右側下方.因為Emoji 渲染有問題,導致無法完全顯示
    
"""    
