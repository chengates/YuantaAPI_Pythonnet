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
import collections

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

    def load_data(self, csv_file, n_days=60):
        full_df = pd.read_csv(csv_file)
        full_df.columns = [c.strip() for c in full_df.columns]
        full_df["日期"] = pd.to_datetime(full_df["日期"])
        cols = ["收盤價", "開盤價", "最高價", "最低價", "成交股數", "成交金額", "成交筆數"]
        for col in cols: full_df[col] = pd.to_numeric(full_df[col], errors="coerce")
        self.df_raw = full_df.dropna(subset=["收盤價"]).sort_values("日期").copy()
        self.n_days = n_days
        self.refresh_period_data()

    def refresh_period_data(self):
        df = self.df_raw.copy().set_index("日期")
        agg = {"開盤價":"first","最高價":"max","最低價":"min","收盤價":"last","成交股數":"sum","成交金額":"sum","成交筆數":"sum"}
        if self.unit != "D" and self.unit in ["1T","5T","15T","30T","60T","W-FRI","ME"]:
            df = df.resample(self.unit).apply(agg).dropna()
        self.df_all = df.reset_index()
        #如果self.unit被改變需要聚合焦集後從新計算不同層級的macd/kd/bolling/ma5,ma20均量及均線
        self.calculate_indicators()
        self.start_idx = max(0, len(self.df_all) - self.n_days)

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
        # MA5 &MA20 Bollinger & 籌碼 [360, Conversation History]
        df["ma5"], df["ma20"] = df["收盤價"].rolling(5).mean(), df["收盤價"].rolling(20).mean()
        std = df["收盤價"].rolling(20).std()
        #Bollinger
        df["ub"], df["lb"] = df["ma20"] + 2*std, df["ma20"] - 2*std
        df["均價"], df["每筆均量"] = df["成交金額"] / df["成交股數"], df["成交股數"] / df["成交筆數"]
        #ma5
        df["每筆均量_ma5"] = df["每筆均量"].rolling(5).mean()
        df["vol_ma5"] = (df["成交股數"]/1000).rolling(5).mean()

    def _calc_support_resistance(self):
        """
        結合「成交量加權」+「價格密集區」自動算出可視區的支撐/壓力線
        回傳 (supports, resistances) 各為 List[float] 最多 2 條
        演算法：
          1. 以可視區 df 計算價格範圍，切成 N 個 bin
          2. 每個 bin 累積「成交量加權」票數
          3. 找出量最大的 bin 中心價格 → 候選水平線
          4. 低於目前收盤價 → 支撐；高於 → 壓力
          5. 相鄰重複的線合併（距離 < 0.5%），各取前 2
        """
        df = self.df
        if df is None or len(df) < 5:
            return [], []

        price_min = df["最低價"].min()
        price_max = df["最高價"].max()
        price_range = price_max - price_min
        if price_range == 0:
            return [], []

        N_BINS = 60  # 把價格切成 60 格
        bin_size = price_range / N_BINS
        bins = np.zeros(N_BINS)

        for _, r in df.iterrows():
            vol = r["成交股數"]
            # 每根K棒的高低價範圍內所有 bin 加上成交量加權
            lo_bin = int((r["最低價"] - price_min) / bin_size)
            hi_bin = int((r["最高價"] - price_min) / bin_size)
            lo_bin = max(0, min(lo_bin, N_BINS - 1))
            hi_bin = max(0, min(hi_bin, N_BINS - 1))
            span = max(hi_bin - lo_bin + 1, 1)
            for b in range(lo_bin, hi_bin + 1):
                bins[b] += vol / span  # 按K棒價格範圍平均分配量

        # 找 local peak（鄰近 3 格都比它小）
        candidates = []
        for b in range(1, N_BINS - 1):
            if bins[b] >= bins[b-1] and bins[b] >= bins[b+1] and bins[b] > 0:
                price_level = price_min + (b + 0.5) * bin_size
                candidates.append((bins[b], price_level))
        candidates.sort(key=lambda x: -x[0])  # 由大量到小量排序

        current_close = df["收盤價"].iloc[-1]
        is_rising = current_close >= df["收盤價"].iloc[0]  # 可視區趨勢

        supports, resistances = [], []
        for _, price in candidates:
            if price < current_close * 0.9995:   # 支撐（低於收盤）
                # 合併相近的線（距離 < 0.5%）
                if not any(abs(p - price) / price < 0.005 for p in supports):
                    supports.append(price)
            elif price > current_close * 1.0005:  # 壓力（高於收盤）
                if not any(abs(p - price) / price < 0.005 for p in resistances):
                    resistances.append(price)
            if len(supports) >= 2 and len(resistances) >= 2:
                break

        # 漲時看撐不看壓，跌時看壓不看撐
        if is_rising:
            resistances = []   # 漲勢中壓力線不畫
        else:
            supports = []      # 跌勢中支撐線不畫

        # 支撐取最近（最高）2條，壓力取最近（最低）2條
        supports = sorted(supports, reverse=True)[:2]
        resistances = sorted(resistances)[:2]
        return supports, resistances

   
    def _draw_kline_panel(self,ax):
        ax.set_title(self.getName(), color=self.palette.fg)
        self.max =max(self.df['最高價'])
        self.min = min(self.df['最低價'])
        #print(f"max/min={self.max} {self.min} ")
        for i, r in self.df.iterrows():
            is_up = r['收盤價'] >= r['開盤價']
            c = self.palette.rise if is_up else self.palette.fall #bar 的color決定
            #在此改善if self.max 時將label位置標籤不論漲跌,都標示max & 收盤價:todo

            ax.plot([i, i], [r['最低價'], r['最高價']], color=c, lw=1)
            ax.add_patch(plt.Rectangle((i-0.3, min(r['開盤價'], r['收盤價'])), 0.6, abs(r['開盤價']-r['收盤價']), color=c))            
            # ── 根據 README 補足的高低價標籤邏輯 [1, 2] ,避免k棒與text重疊 good──
            if (i % self.TICK_INTERVAL == 0 or i == len(self.df)-1) or ((i <= (len(self.df)-3)) & self.getMaxMinDf(r) & (i % self.TICK_INTERVAL != 0) ):                                        #避免k棒MAX與TICK_INTERVAL重疊
                if is_up | (self.max == r['最高價']):
                    ax.text(i, r['最高價']*1.002, f"{r['最高價']}\n{r['收盤價']}", color=c, fontsize=7, ha='center', va='bottom')
                else:
                    ax.text(i, r['最低價']*0.998, f"{r['收盤價']}\n{r['最低價']}", color=c, fontsize=7, ha='center', va='top')
                    
        ax.plot(self.df["ma5"], color=self.palette.ma5, label="5MA")
        ax.plot(self.df["ma20"], color=self.palette.ma20, label="20MA")
        ax.fill_between(range(len(self.df)), self.df["ub"], self.df["lb"], color='skyblue', alpha=0.05)
        ax.yaxis.label.set_color(self.palette.grey)
        ax.set_ylabel("價格 (Price)", color=self.palette.grey)
        ax.grid(axis='both', linestyle='--', alpha=0.3)

        # ── 自動支撐/壓力線 ──────────────────────────────────────
        supports, resistances = self._calc_support_resistance()
        x_end = len(self.df) - 1  # 可視區右邊界
        legend_extra = []  # 收集 S/R proxy artist 加入 legend

        for i, price in enumerate(supports):
            alpha = 0.9 if i == 0 else 0.6
            lw = 1.5 if i == 0 else 1.0
            line, = ax.plot([], [], color='#00C853', linestyle='--', linewidth=lw,
                            alpha=alpha, label=f"S{i+1} {price:.1f}")
            ax.axhline(y=price, color='#00C853', linestyle='--', linewidth=lw, alpha=alpha)
            ax.text(x_end, price, f" S{i+1} {price:.1f}", color='#00C853',
                    fontsize=7, va='center', ha='left', alpha=alpha,
                    bbox=dict(boxstyle='round,pad=0.1', facecolor=self.palette.bg, alpha=0.6, edgecolor='none'))
            legend_extra.append(line)

        for i, price in enumerate(resistances):
            alpha = 0.9 if i == 0 else 0.6
            lw = 1.5 if i == 0 else 1.0
            line, = ax.plot([], [], color='#FF1744', linestyle='--', linewidth=lw,
                            alpha=alpha, label=f"R{i+1} {price:.1f}")
            ax.axhline(y=price, color='#FF1744', linestyle='--', linewidth=lw, alpha=alpha)
            ax.text(x_end, price, f" R{i+1} {price:.1f}", color='#FF1744',
                    fontsize=7, va='center', ha='left', alpha=alpha,
                    bbox=dict(boxstyle='round,pad=0.1', facecolor=self.palette.bg, alpha=0.6, edgecolor='none'))
            legend_extra.append(line)

        ax.legend(loc="best", fontsize="x-small")


    #self.dfs是擴充的dfs含kdj,成交筆數,漲跌價差,收盤價,macd,dea,dif,ma5,ma20,每筆均量,均價,bolling(lb,ub)vol_ma5每筆均量_ma5 ,self.dfs.iterrows()
    def getMaxMinDf(self,row):              
        result = False
        if( (self.max == row['最高價']) | (self.min == row['最低價'])):
            result = True
            
        return result
    
    def _draw_volume_panel(self, ax):
        self.df = self.df_all.iloc[self.start_idx-1 : self.start_idx + self.n_days].reset_index(drop=True) #已經改為第一筆是yesterday
        viewLength = len(self.df)-1 #-1才會是viewLengt 不含昨日        
        vol = self.df_all.iloc[self.start_idx-1:,1].reset_index(drop=True) #index 多一個下標0 & 原來的index &volumn 第一個view的yesterday [idx,成交股數]
        yesterdayVol = vol.loc[:'成交股數'] #去除index,yesterdayVol = only成交股數[]
        #print(f"1._draw_volume_panel vol len={len(vol)}:is 91? start_idx={self.start_idx}-1 成交股數viewLength={viewLength}應該=90 {len(yesterdayVol)}\n{yesterdayVol}")
        colors = []
        for i in range(viewLength): #viewLength90 -1為了避免overflow            
            if yesterdayVol[i] <= yesterdayVol[ (i+1) ]: #昨日成交數 <= 當日成交股數
                colors.append(self.palette.rise)        #當日成交數的顏色 if 量增
            else:
                colors.append(self.palette.fall)
            print(f"2... lenColors= {len(colors)}")
        
        #復原正確的view windows data & reset_index=0
        self.df = self.df_all.iloc[self.start_idx : self.start_idx + self.n_days].reset_index(drop=True)
        #vol = self.df['成交股數'] / 1000
        print(f"3.(Total df:colors:\n {vol}:{colors})")
        ax.bar(range(len(self.df)), vol, color=colors, alpha=0.6)        
        ax.plot(self.df["vol_ma5"], color=self.palette.ma5, lw=1, label="5MA均量")
                
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
        # ── Bug Fix: 每次 update 前先清空 vlines，避免累積舊的已失效 vline ──
        self.vlines.clear()
        for ax in axes:
            ax.clear()
            ax.set_facecolor(self.palette.bg)
            # 重建 vline，每次 clear 後必須重建，存入 self.vlines
            self.vlines.append(ax.axvline(x=0, color=self.palette.fg, linestyle='--', visible=False))
            ax.grid(True, color=self.palette.grid, ls='--', alpha=0.4)
            ax.yaxis.label.set_color(self.palette.grey)
            ax.tick_params(axis='y', colors=self.palette.grey)
            #設置邊框(spines)顏色為spines,&both XYticket color&label palette.grey
            for spine in ax.spines.values():
                spine.set_color(self.palette.fg)
            for l in ax.get_xticklabels(): #xaxis:                
                l.set_color(self.palette.grey)                
            for l in ax.get_yticklabels():  #yaxis:
                l.set_color(self.palette.grey)
        
        self._draw_kline_panel(axes[0])
        self._draw_volume_panel(axes[1])
        self._draw_macd_panel(axes[2])
        self._draw_kdj_panel(axes[3])
        self._setup_xticks(axes[3])
        self._rebuild_overlays(axes)   # ── 重建被 ax.clear() 清掉的 info_box / emoji overlay
        self._redraw_drawings(axes[0], axes[1])  # ── 重繪使用者繪圖物件
        fig.canvas.draw_idle()

    def _setup_xticks(self, ax):
        tick_idx = list(range(0, len(self.df), self.TICK_INTERVAL))
        if (len(self.df)-1) not in tick_idx: tick_idx.append(len(self.df)-1)
        #for ax in self.axes:
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
        try:
            target = pd.to_datetime(date_str).date()
            matches = self.df[self.df['日期'].dt.date == target].index
            if len(matches) > 0:
                return float(matches[0])
            # 找不到精確日期時，找最近的
            dates = self.df['日期'].dt.date.values
            diffs = [abs((d - target).days) for d in dates]
            return float(np.argmin(diffs))
        except:
            return None

    def _obj_to_screen(self, obj):
        """將物件的日期座標轉回當前畫面 index，回傳轉換後的 obj copy（不修改原始）"""
        o = obj.copy()
        for key in ('x1', 'x2', 'x3'):
            dkey = key.replace('x', 'd')  # d1, d2, d3
            if dkey in o:
                sx = self._date_to_x(o[dkey])
                if sx is not None:
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

    def _redraw_drawings(self, ax_k, ax_v):
        """update_view 後把當前週期的繪圖物件重新畫回去（不同週期的物件隱藏保留）"""
        self.draw_artists = []
        for obj in self.draw_objects:
            # 只畫出與當前週期相同的物件；沒有 unit 欄位的舊資料視為相容（全顯示）
            if obj.get('unit', self.unit) != self.unit:
                self.draw_artists.append([])  # 佔位，保持 index 對齊
                continue
            arts = self._draw_artist_from_obj(ax_k, ax_v, obj)
            self.draw_artists.append(arts)

    def _setup_drawing_ui(self, fig, axes):
        """右側新增工具選擇 RadioButtons + 顏色 RadioButtons + 清除 Button"""
        ax_k, ax_v = axes[0], axes[1]

        # ── 工具選擇（右側上方）
        ax_tool = plt.axes([0.91, 0.72, 0.08, 0.26], facecolor='#e8e8e8')
        tools =      ('cursor','hline','vline','line','arrow','arrow2','channel','rect','arc','fib','measure','select','clear')
        tool_labels = ('🖱 游標','─ 水平','| 垂直','╱ 切線','→ 箭頭','↔ 雙箭','⋀ 軌道','□ 矩形','⌢ 圓弧','φ 斐波','↕ 測距','✥ 選取','✕ 清除')
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
            if self.draw_tool == 'clear':
                # 只清除當前週期的物件，其他週期的保留
                self.draw_objects = [o for o in self.draw_objects
                                     if o.get('unit', self.unit) != self.unit]
                self.draw_artists.clear()
                self._draw_save()
                self.update_view(fig, axes)
        self.radio_tool.on_clicked(on_tool)

        # ── 顏色選擇（右側中間，週期按鈕上方）
        ax_color = plt.axes([0.91, 0.60, 0.08, 0.11], facecolor='#e8e8e8')
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
        self.radio_color.on_clicked(on_color)

        # ── 儲存 Button
        ax_save = plt.axes([0.91, 0.56, 0.08, 0.035], facecolor='#e8e8e8')
        self.btn_save = Button(ax_save, '💾 儲存', color='#b0bec5', hovercolor='#78909c')
        def on_save(event):
            self._draw_save()
        self.btn_save.on_clicked(on_save)

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

            # ── select 模式：找最近物件
            if tool == 'select' and event.button == 1:
                best, best_d = None, 1e9
                for i, obj in enumerate(self.draw_objects):
                    ox, oy = obj['x1'], obj['y1']
                    d = ((ox-x)**2 + (oy-y)**2)**0.5
                    if d < best_d:
                        best_d, best = d, i
                if best is not None and best_d < 5:
                    self.selected_obj = best
                    self.drag_offset = (self.draw_objects[best]['x1']-x,
                                        self.draw_objects[best]['y1']-y)
                return

            # ── 右鍵：刪除最近物件
            if event.button == 3 and tool in ('select','cursor'):
                best, best_d = None, 1e9
                for i, obj in enumerate(self.draw_objects):
                    ox, oy = obj['x1'], obj['y1']
                    d = ((ox-x)**2 + (oy-y)**2)**0.5
                    if d < best_d:
                        best_d, best = d, i
                if best is not None and best_d < 5:
                    self.draw_objects.pop(best)
                    self._draw_save()
                    self.update_view(fig, axes)
                return

            if event.button != 1: return
            if tool in ('cursor','select','clear'): return

            # ── 單點工具（水平線/垂直線）
            if tool in ('hline', 'vline'):
                obj = {'type': tool, 'x1': x, 'y1': y, 'x2': x, 'y2': y,
                       'd1': self._x_to_date(x),
                       'unit': self.unit,
                       'color': self.draw_color, 'panel': _panel(event.inaxes)}
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
            self.selected_obj = None

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
                if tool in ('cursor','select','clear','hline','vline','fib'): return
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

        def on_mouse(event):
            if event.inaxes is None: return
            if self.is_dragging and self.press_x is not None:   # 拖曳平移
                dx = int(round(event.xdata - self.press_x))     # 拖曳範圍距離
                self.start_idx = max(0, min(self.press_start_idx - dx, len(self.df_all) - self.n_days))     #視覺起點
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
                    txt = (f"{r['日期'].date()} | {status}  ma5:{r['ma5']:.1f} ma20:{r['ma20']:.1f}\n"
                           f"均價:{r['均價']:.1f} 高:{r['最高價']:.1f} 開:{r['開盤價']:.1f} 收:{r['收盤價']} 低:{r['最低價']} 量{(r['成交股數']/1000):.1f}\n"
                           f"MACD:{r['macd']:.1f}  K:{r['K']:.1f} D:{r['D']:.1f}  布林:U:{r['ub']:.1f} STD:{r['ma20']:.1f}  L:{r['lb']:.1f}")
                    # ── 關鍵修正：info_box/oi_vol 每次 update_view 後已重建為 instance 變數 ──
                    self.info_box.set_text(txt)
                    self.info_box.set_color(self.palette.rise if is_up else self.palette.fall)
                    self.oi_vol.set_data(make_emoji_img('🔥' if r['成交股數']/1000 > r['vol_ma5']*1.5 else '📊'))

                    x_pos = event.xdata
                    for vline in self.vlines:
                        vline.set_xdata([x_pos, x_pos])
                        vline.set_visible(True)

                    fig.canvas.draw_idle()

        fig.canvas.mpl_connect('button_press_event', lambda e: (
            setattr(self, 'is_dragging', True) or
            setattr(self, 'press_x', e.xdata) or
            setattr(self, 'press_start_idx', self.start_idx)
        ) if e.button == 1 and e.inaxes in axes and e.xdata is not None else None)
        fig.canvas.mpl_connect('button_release_event', lambda e: setattr(self, 'is_dragging', False))
        fig.canvas.mpl_connect('motion_notify_event', on_mouse)

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
            self.unit = m[label]; self.refresh_period_data(); self.update_view(fig, axes)
        self.radio.on_clicked(change_p)

        # ── 載入上次儲存的繪圖 + 建立繪圖工具 UI
        self._draw_load()
        self.update_view(fig, axes)
        self._setup_cursor(fig, axes)
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
    from google import genai

# The client gets the API key from the environment variable `GEMINI_API_KEY`.
#client = genai.Client()

# response = client.models.generate_content(
#     model="gemini-3-flash-preview", contents="Explain how AI works in a few words"
# )
# print(response.text)
tsmc.plot_all()

"""
整合後的主要改變與說明：
MACD 與 KDJ 完整回歸：在 calculate_indicators 與 _draw 面板方法中，完整實現了您最初要求的 EMA、RSV 計算，以及金叉 scatter 標註與 80/20 警戒線。
大戶 Whale 診斷系統：在 on_mouse 中，系統會自動比對 收盤價 與 均價。如果股價在跌但站穩均價且大單增加，系統會顯示 🟢 🐋↗ 大戶吸收 [Conversation History, 354]。
解決 Attribute 報錯：加入了 update_view 作為中央刷新方法，確保不管是手動滑動 X 軸還是點擊 Radio 按鈕切換週期，畫面都會同步重繪 [348, Conversation History]。
深色模式與視窗管理：StockPalette 會根據 style="Dark" 自動調整背景與 K 線顏色。且由於加入了 block 參數，您現在可以同時開啟多個股票視窗進行「評估與對比」 [348, Conversation History]。
您可以立刻驗證的目視項目：
K棒價格標籤：觀察 X 軸刻度處的 K 棒，若是紅K，上方應會出現「最高價」與「收盤價」；若是綠K，下方應會出現「收盤價」與「最低價」。
大戶吸收訊號：找到股價下跌但成交筆數不多、單筆量大的日子（綠 K 棒），資訊盒應顯示 🟢 🐋↗ 大戶持續吸收 [Conversation History]。
大戶脫手訊號：找到股價強拉但均價卻在下方的日子（紅 K 棒），資訊盒應顯示 🔴 🐋↘ 大戶拉高脫手 [Conversation History]。
MACD 標註：確認 DIF 線穿過 DEA 線時，是否有紅色的 ▲ (金叉) 符號出現在面板上
"""    
