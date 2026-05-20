###程式名稱:YuantaAPI_Pythonnet.py
###程式用途說明:本程式為使用YuantaOneAPI.dll的範例程式
###特別說明:透過Pythonnet引用YuantaOneAPI.dll
###範例程式更新日期:2025.02.27

### 修改摘要 (2026.05.20 更新)
### 1. 新增 StockQuoteState 類別封裝股票報價狀態管理
###    - 支援五檔報價、成交明細、觀察清單等數據更新
###    - 自動計算開高低收、漲跌價差、估計日成交量
###    - 內外盤成交量分析，用於主力/散戶占比評估
### 2. 統一訂閱數據存儲到全局 SUBSCRIPTION_STATE 字典
###    - stocks: 各股票報價狀態 (StockQuoteState 實例)
###    - system: 系統訊息
###    - rq_rp: 查詢回應
### 3. 實現異步 show() 方法 (含市場排程控制)
###    - 每 1/60 秒更新 UI 顯示所有訂閱股票資訊
###    - 交易時段(09:00-13:30): 每 5 秒保存完整報價到 CSV
###    - 盤後搓合(13:30-14:30): 暫停 CSV 輸出
###    - 收盤後(14:30+): 寫入日總結 @stockID.csv 後停止
### 4. 優化訂閱回應處理函數
###    - SubscribeFiveTick_out: 處理五檔報價 (實測心跳訊號)
###    - SubscribeWatclistAll_Out: 處理觀察清單報價
###    - SubscribeStocktick_out: 處理分時成交明細
###    - SubscribeWatchlist_Out: 處理指定欄位報價
### 5. 新增異步 CSV 保存功能
###    - _save_to_csv_async: 非阻塞式數據持久化，支援多股票並發保存
### 6. 修復 pct_of_yesterday_avg 缺失問題
###    - StockQuoteState._load_yesterday_data(): 從 yesterday/ 載入昨量
### 7. 新增日總結寫入 _write_daily_summary()
###    - @stockID.csv: 每交易日一筆 OHLCV 供隔日快速載入
###    - 同步更新 yesterday/{stockID}.csv 為最新日資料
### 8. 修復 _display_quote_info() 重複顯示程式碼
### 9. 市場排程輔助函數 _market_phase(): pre_open/trading/matching/closed

import os
import clr
import time
import signal
import datetime as dt
import struct
import pathlib
import sys
import csv
from pathlib import Path
import asyncio
import pandas as pd

## 全局訂閱資料存儲狀態
SUBSCRIPTION_STATE = {
    'stocks': {},
    'system': [],
    'rq_rp': {},
    'login_status': False,  # 登入狀態
    'event_counts': {},
}

class StockQuoteState:
    def __init__(self, stock_id: str, market_no=None):
        self.stock_id = stock_id
        self.market_no = market_no
        self.latest_timestamp = None
        self.byIndexFlag = None
        self.buy_prices = []
        self.buy_volumes = []
        self.sell_prices = []
        self.sell_volumes = []
        self.last_deal_price = None
        self.last_deal_volume = None
        self.total_in_volume = 0
        self.total_out_volume = 0
        self.total_volume = 0
        self.trade_count = 0
        self.open_price = None
        self.high_price = None
        self.low_price = None
        self.close_price = None
        self.price_diff = None
        self.prev_average_volume = None
        self.estimated_day_volume = None
        self.pct_of_yesterday_avg = None
        self.last_update = None
        self.extra_data = {}
        self.price_history = []
        self.max_price_history = 20
        self.ma5 = None
        self.ma10 = None
        self.price_momentum = None
        self.last_saved_timestamp = None
        self.yesterday_volume = None
        self.yesterday_close = None
        try:
            self._load_yesterday_data()
        except Exception as e:
            print(f"[StockQuoteState] 載入昨日數據失敗 {stock_id}: {e}")

    def update_five_tick(self, byIndexFlag, buy_prices, buy_volumes, sell_prices, sell_volumes, timestamp=None):
        self.byIndexFlag = byIndexFlag
        self.buy_prices = buy_prices
        self.buy_volumes = buy_volumes
        self.sell_prices = sell_prices
        self.sell_volumes = sell_volumes
        self.last_update = timestamp or time.time()
        self.latest_timestamp = self.last_update
        self._infer_prices_from_depth()

    def has_trade_activity(self):
        return any(
            [
                self.last_deal_price is not None,
                self.last_deal_volume is not None,
                self.total_in_volume > 0,
                self.total_out_volume > 0,
                self.trade_count > 0,
            ]
        )

    def update_watchlist_all(self, byIndexFlag, timestamp=None, total_out=None, total_in=None, deal_price=None, deal_volume=None):
        self.byIndexFlag = byIndexFlag
        self.last_update = timestamp or time.time()
        self.latest_timestamp = self.last_update

        if total_out is not None:
            self.total_out_volume = total_out
        if total_in is not None:
            self.total_in_volume = total_in
        if deal_price is not None:
            self.last_deal_price = deal_price
        if deal_volume is not None:
            self.last_deal_volume = deal_volume
            self.total_volume += deal_volume
            self.trade_count += 1

        if self.open_price is None and self.last_deal_price is not None:
            self.open_price = self.last_deal_price

        if self.last_deal_price is not None:
            if self.high_price is None or self.last_deal_price > self.high_price:
                self.high_price = self.last_deal_price
            if self.low_price is None or self.last_deal_price < self.low_price:
                self.low_price = self.last_deal_price
            self.close_price = self.last_deal_price
            self._append_price_history(self.last_deal_price)

        self._update_estimates()

    def update_stocktick(self, deal_price=None, deal_volume=None, in_out_flag=None, timestamp=None):
        self.last_update = timestamp or time.time()
        self.latest_timestamp = self.last_update

        if deal_price is not None:
            self.last_deal_price = deal_price
        if deal_volume is not None:
            self.last_deal_volume = deal_volume
            self.total_volume += deal_volume
            self.trade_count += 1
        if in_out_flag == '1':
            self.total_out_volume += deal_volume or 0
        elif in_out_flag == '2':
            self.total_in_volume += deal_volume or 0

        if self.open_price is None and self.last_deal_price is not None:
            self.open_price = self.last_deal_price

        if self.last_deal_price is not None:
            if self.high_price is None or self.last_deal_price > self.high_price:
                self.high_price = self.last_deal_price
            if self.low_price is None or self.last_deal_price < self.low_price:
                self.low_price = self.last_deal_price
            self.close_price = self.last_deal_price
            self._append_price_history(self.last_deal_price)

        self._update_estimates()

    def update_watchlist_field(self, byIndexFlag, int_value, timestamp=None):
        self.byIndexFlag = byIndexFlag
        self.last_update = timestamp or time.time()
        self.latest_timestamp = self.last_update
        self.extra_data[byIndexFlag] = int_value

    def _update_estimates(self):
        if self.total_volume and self.latest_timestamp:
            now = dt.datetime.fromtimestamp(self.latest_timestamp)
            elapsed = now.hour * 3600 + now.minute * 60 + now.second - 9 * 3600
            elapsed = max(elapsed, 1)
            trading_seconds = 4 * 60 * 60
            self.estimated_day_volume = int(self.total_volume * trading_seconds / elapsed)
        else:
            self.estimated_day_volume = None

        if self.prev_average_volume and self.estimated_day_volume is not None:
            self.pct_of_yesterday_avg = round(self.estimated_day_volume / self.prev_average_volume * 100, 2)
        else:
            self.pct_of_yesterday_avg = None

        if self.open_price is not None and self.close_price is not None:
            self.price_diff = self.close_price - self.open_price

        self._update_technical_indicators()

    def _load_yesterday_data(self):
        """從 yesterday/{stock_id}.csv 載入昨日收盤量作為 prev_average_volume。"""
        yesterday_path = os.path.join("yesterday", f"{self.stock_id}.csv")
        if not os.path.exists(yesterday_path):
            return
        try:
            df = pd.read_csv(yesterday_path)
            if "成交股數" in df.columns and len(df) > 0:
                self.yesterday_volume = int(df["成交股數"].sum())
                self.prev_average_volume = self.yesterday_volume
            if "收盤價" in df.columns and len(df) > 0:
                self.yesterday_close = float(df["收盤價"].iloc[-1])
        except Exception:
            pass

    def _infer_prices_from_depth(self):
        if self.last_deal_price is not None:
            return

        best_bid = self.buy_prices[0] if self.buy_prices else None
        best_ask = self.sell_prices[0] if self.sell_prices else None
        if best_bid is None and best_ask is None:
            return

        if best_bid is None:
            inferred_price = best_ask
        elif best_ask is None:
            inferred_price = best_bid
        else:
            inferred_price = round((best_bid + best_ask) / 2, 2)

        if inferred_price is None:
            return

        if self.open_price is None:
            self.open_price = inferred_price
        if self.high_price is None or inferred_price > self.high_price:
            self.high_price = inferred_price
        if self.low_price is None or inferred_price < self.low_price:
            self.low_price = inferred_price
        self.close_price = inferred_price

        if self.open_price is not None and self.close_price is not None:
            self.price_diff = self.close_price - self.open_price

    def _append_price_history(self, price):
        if price is None:
            return
        self.price_history.append(price)
        if len(self.price_history) > self.max_price_history:
            self.price_history.pop(0)

    def _update_technical_indicators(self):
        if self.price_history:
            if len(self.price_history) >= 5:
                self.ma5 = round(sum(self.price_history[-5:]) / 5, 2)
            else:
                self.ma5 = None
            if len(self.price_history) >= 10:
                self.ma10 = round(sum(self.price_history[-10:]) / 10, 2)
            else:
                self.ma10 = None
            if len(self.price_history) >= 2:
                self.price_momentum = round(self.price_history[-1] - self.price_history[-2], 2)
            else:
                self.price_momentum = None
        else:
            self.ma5 = None
            self.ma10 = None
            self.price_momentum = None

    def has_data(self):
        return any(
            [
                self.last_deal_price is not None,
                self.last_deal_volume is not None,
                self.total_volume > 0,
                self.total_in_volume > 0,
                self.total_out_volume > 0,
                bool(self.buy_prices),
                bool(self.buy_volumes),
                bool(self.sell_prices),
                bool(self.sell_volumes),
                bool(self.extra_data),
            ]
        )

    def build_save_record(self):
        if self.latest_timestamp is None or not self.has_data():
            return None

        self._infer_prices_from_depth()
        deal_amount = None
        if self.last_deal_price is not None and self.last_deal_volume is not None:
            deal_amount = self.last_deal_price * self.last_deal_volume

        buy_sell_total = self.total_in_volume + self.total_out_volume
        buy_sell_ratio = None
        buy_total_volume = sum(self.buy_volumes) if self.buy_volumes else 0
        sell_total_volume = sum(self.sell_volumes) if self.sell_volumes else 0
        buy_sell_imbalance = None
        buy_sell_pressure = None
        if buy_sell_total > 0:
            buy_sell_ratio = {
                'in_pct': round(self.total_in_volume / buy_sell_total * 100, 2),
                'out_pct': round(self.total_out_volume / buy_sell_total * 100, 2)
            }
        if buy_total_volume + sell_total_volume > 0:
            buy_sell_imbalance = buy_total_volume - sell_total_volume
            buy_sell_pressure = round(buy_sell_imbalance / (buy_total_volume + sell_total_volume) * 100, 2)

        return {
            'timestamp': dt.datetime.fromtimestamp(self.latest_timestamp).strftime('%Y%m%d %H:%M:%S'),
            'stock_id': self.stock_id,
            'deal_volume': self.last_deal_volume,
            'deal_amount': deal_amount,
            'open_price': self.open_price,
            'high_price': self.high_price,
            'low_price': self.low_price,
            'close_price': self.close_price,
            'price_diff': self.price_diff,
            'trade_count': self.trade_count,
            'estimated_day_volume': self.estimated_day_volume,
            'pct_of_yesterday_avg': self.pct_of_yesterday_avg,
            'total_in_volume': self.total_in_volume,
            'total_out_volume': self.total_out_volume,
            'buy_total_volume': buy_total_volume,
            'sell_total_volume': sell_total_volume,
            'buy_sell_imbalance': buy_sell_imbalance,
            'buy_sell_pressure': buy_sell_pressure,
            'buy_sell_ratio': buy_sell_ratio,
            'buy_prices': self.buy_prices,
            'buy_volumes': self.buy_volumes,
            'sell_prices': self.sell_prices,
            'sell_volumes': self.sell_volumes,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'price_momentum': self.price_momentum,
            'byIndexFlag': self.byIndexFlag,
            'extra_data': self.extra_data,
        }

    def to_display_dict(self):
        return self.build_save_record()


def get_quote_state(stock_id: str, market_no=None) -> StockQuoteState:
    state = SUBSCRIPTION_STATE['stocks'].get(stock_id)
    if state is None:
        state = StockQuoteState(stock_id, market_no)
        SUBSCRIPTION_STATE['stocks'][stock_id] = state
    return state

##透過Clr引用系統標準函式
clr.AddReference('System.Collections')
##宣告增加DLL的引用路徑
sys.path.append(Path(pathlib.Path(__file__).parent.resolve()).absolute())
##透過Clr引用YuantaOneAPI.dll
clr.AddReference('YuantaOneAPI')


##匯入YuataOneAPI物件
from YuantaOneAPI import (YuantaOneAPITrader, # pyright: ignore[reportMissingImports]
                          enumEnvironmentMode,
                          OnResponseEventHandler,
                          YuantaDataHelper,
                          enumLangType,
                          enumLogType,
                          StockOrder,
                          FutureOrder,
                          OVFutureOrder,
                          Watchlist,
                          WatchlistAll,
                          FiveTickA,
			              StockTick,
                          DepositOptimum,
                          OrderStatus)

from System.Collections.Generic import List # pyright: ignore[reportMissingImports]

import System # type: ignore

#login_in
#登入
def login_out_response(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)

    result = ''
    
    try:
        #abyMsgCode訊息代碼
        strMsgCode = dataGetter.GetStr(5) 
        #abyMsgContent中文訊息
        strMsgContent = dataGetter.GetStr(50) 
        #uintCount筆數
        intCount = dataGetter.GetUInt() 

        if strMsgCode == '0001' or strMsgCode == '00001':
            SUBSCRIPTION_STATE['login_status'] = True
            result += '帳號筆數: ' + str(intCount) + '\r\n'

            for _ in range(intCount):
                #abyAccount帳號
                result += dataGetter.GetStr(22) + ',' 
                #abyName客戶姓名
                result += dataGetter.GetStr(12) + ',' 
                #abyInvestorID身分證字號
                result += dataGetter.GetStr(14) + ',' 
                #shtSellerNo營業員代碼
                shtSellNo = dataGetter.GetShort() 
                result += str(shtSellNo)
                print('login_out_response:',result)
                result += '\r\n'
                

    except Exception as error:
        result = error

    return result

#即時回報彙總(回補) 10.0.0.16
def get_real_report_merge_response(abyData):

    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    nRowCount = 0

    result = ''
    
    try:
        #筆數
        nRowCount = dataGetter.GetUInt()
        #訊息添加即時回報筆數
        result += '即時回報彙總(查詢結果) 筆數:'+str(nRowCount)+'\r\n'
        
        #循環處理回應資料
        for _ in range(nRowCount):
            #abyAccount帳號 
            result += dataGetter.GetStr(22) + ',' 
            #bytRptFlag回報標記  
            result += '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyOrderNo委託單號  
            result += dataGetter.GetStr(20)+ ',' 
            #byMarketNo市場代碼  
            result += '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyCompanyNo商品代碼  
            result += dataGetter.GetStr(20) + ',' 
            #struOrderDate交易日	
            yuantaDate = dataGetter.GetTYuantaDate() 
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #struOrderTime委託時間  
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #abyOrderType委託種類  
            result += (dataGetter.GetStr(3))+ ',' 
            #abyBS買賣別  S:賣；B:買
            result += (dataGetter.GetStr(1)) + ',' 
            #abyOrderPrice委託價  
            result += dataGetter.GetStr(14)+ ',' 
            #abyTouchPrice停損執行價  
            result += dataGetter.GetStr(14)+','
            #abyLastDealPrice最新成交價  
            result += dataGetter.GetStr(14)+','
            #abyAvgDealPrice成交均價  
            result += dataGetter.GetStr(14)+','
            #intBeforeQty改量前數量  
            result += str(dataGetter.GetInt())+ ','  
            #intOrderQty委託股數  
            result += str(dataGetter.GetInt())+',' 
            #intOkQty成交股數  
            result += str(dataGetter.GetInt())+',' 
            #abyOpenOffsetKind新增/沖銷別  
            result += dataGetter.GetStr(1) + ',' 
            #abyDayTrade當沖記號
            result += dataGetter.GetStr(1)+ ',' 
            #abyOrderCond委託條件
            result += dataGetter.GetStr(1) + ',' 
            #abyOrderErrorNo錯誤碼
            result += dataGetter.GetStr(4) + ',' 
            #byAPCode委託類別
            result += '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #shtOrderStatus狀態碼
            result += '{0}'.format(str(dataGetter.GetShort())) + ',' 
            #byLastOrderStatus最新一筆即回資料狀態
            result += '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyStkCName商品名稱
            result += dataGetter.GetStr(20) + ',' 
            #abyTradeCode實體交易代號
            result += dataGetter.GetStr(20) + ','
            #uintStrikePrice履約價
            result += '{0}'.format(str(dataGetter.GetUInt())) + ',' 
            #abyBasketNo一籃子下單編號
            result += dataGetter.GetStr(32) + ','
            #byStkType1屬性1
            result += '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #byStkType2屬性2
            result += '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #byBelongMarketNo所屬市場代碼
            result += '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyBelongStkCode所屬股票代碼
            result += dataGetter.GetStr(12) + ','
            #abyStkOrderType委託價格種類
            result += dataGetter.GetStr(1) + ','
            #abyStkOrderErrorNo證券回報錯誤碼
            result += dataGetter.GetStr(5) 
            result += '\r\n'
        
    except Exception as error:
        result = error

    return result

#即時回報(回補) 10.0.0.20
def get_real_report_response(abyData):

    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    nRowCount = 0
    result = ''
    
    try:
        #筆數
        nRowCount = dataGetter.GetUInt()
        #訊息添加即時回報筆數
        result += '即時回報(查詢結果) 筆數:'+str(nRowCount)+'\r\n'

        #循環處理回應資料
        for _ in range(nRowCount):
            #abyAccount帳號 
            result += dataGetter.GetStr(22) + ',' 
            #bytRptType回報類別  
            result += '{0}'.format(dataGetter.GetByte()) + ',' 
            #abyOrderNo委託單號  
            result += dataGetter.GetStr(20)+ ',' 
            #byMarketNo市場代碼  
            result += '{0}'.format(dataGetter.GetByte()) + ',' 
            #abyCompanyNo商品代碼  
            result += dataGetter.GetStr(20) + ','
            #abyStkCName股票名稱  
            result += dataGetter.GetStr(20) + ','  
            #struOrderDate交易日		
            yuantaDate = dataGetter.GetTYuantaDate() 
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #struOrderTime交易時間  
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #abyOrderType委託種類  
            result += dataGetter.GetStr(3) + ','  
            #abyBS買賣別  
            result += dataGetter.GetStr(1) + ','  
            #abyPrice價位  
            result += dataGetter.GetStr(14) + ','  
            #abyTouchPrice停損執行價  
            result += dataGetter.GetStr(14) + ',' 
            #intBeforeQty改量前數量  
            result += str(dataGetter.GetInt()) + ',' 
            #intOrderQty數量  
            result +=  str(dataGetter.GetInt()) + ',' 
            #abyOpenOffsetKind新增/沖銷別  
            result += dataGetter.GetStr(1) + ',' 
            #abyDayTrade當沖記號
            result += dataGetter.GetStr(1) + ',' 
            #abyOrderCond委託條件
            result += dataGetter.GetStr(1) + ',' 
            #abyOrderErrorNo錯誤碼
            result += dataGetter.GetStr(4) + ',' 
            #bytTradeKind交易性質
            result += '{0}'.format(dataGetter.GetByte()) + ','
            #byAPCode委託類別
            result += '{0}'.format(dataGetter.GetByte()) + ','
            #abyBasketNo一籃子下單編號
            result += dataGetter.GetStr(32) + ',' 
            #byOrderStatus即回資料狀態
            result += '{0}'.format(dataGetter.GetByte()) + ','
            #byStkType1屬性1
            result += '{0}'.format(dataGetter.GetByte()) + ','
            #byStkType2屬性2
            result += '{0}'.format(dataGetter.GetByte()) + ','
            #byBelongMarketNo所屬市場代碼
            result += '{0}'.format(dataGetter.GetByte()) + ','
            #abyBelongStkCode所屬股票代碼
            result +=  dataGetter.GetStr(12) + ',' 
            #uintSeqNo成交序號
            result +=  dataGetter.GetStr(4) + ',' 
            #abyPriceType價格型態
            result +=  dataGetter.GetStr(1) + ',' 
            #abyStkErrCode證券回報錯誤碼
            result +=  dataGetter.GetStr(5)
            result += '\r\n'

    except Exception as error:
        result = error

    return result

#GetQuoteList
#取得己訂閱報價商品列表
def GetQuoteList_Out(abyData):
    
    result = ''
    
    try:
        dataGetter = YuantaDataHelper(enumLangType.NORMAL)
        dataGetter.OutMsgLoad(abyData)
        nRowCount = dataGetter.GetUInt()
        result +='己訂閱報價商品列表 筆數{0}: \r\n'.format(nRowCount)
        for i in range(nRowCount):
            result += '{0} \r\n'.format(dataGetter.GetStr(50))
            
    except Exception as error:
        result = error
        
    return result

#stk_order_out_response	
#現貨下單回應 30.100.10.31
def stk_order_out_response(abyData):

    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)

    result = ''
    
    try:
        result += '現貨下單結果:\r\n'
		#abyMsgCode訊息代碼 0001代表執行成功，其他則為失敗
        result += dataGetter.GetStr(4) + ',' 
		#abyMsgContent訊息內容
        result += dataGetter.GetStr(75) + ',' 
		#uintCount筆數
        Rcount = dataGetter.GetUInt() 
        
        #訊息添加下單筆數  
        result += '下單筆數:' + str(Rcount) + '\r\n'

		#循環處理回應資料
        for _ in range(Rcount):
		    #intIdentify識別碼 
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
			#shtReplyCode委託結果代碼 0代表委託成功，其他則為委託失敗
            result += '{0}'.format(str(dataGetter.GetShort())) + ',' 
			#abyOrderNO委託書編號
            result += dataGetter.GetStr(5) + ',' 
			#struTradeDate交易日期
            yuantaDate = dataGetter.GetTYuantaDate() 
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #abyErrType錯誤類別
            result += dataGetter.GetStr(1) + ',' 
			#abyErrNO錯誤代號
            result += dataGetter.GetStr(3) + ',' 
			#abyAdvisory錯誤說明
            result += dataGetter.GetStr(120)
            result += '\r\n'
            
    except Exception as error:
        result = error

    return result

#future_order_out_response	
#期貨下單回應 30.100.20.24
def future_order_out_response(abyData):

    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = '' 
    
    try:
        result += '期貨下單結果: \r\n'
		#abyMsgCode訊息代碼 0001代表執行成功，其他則為失敗
        result += dataGetter.GetStr(4) + ',' 
		#abyMsgContent訊息內容
        result += dataGetter.GetStr(50) + ',' 
		#uintCount筆數
        Rcount = dataGetter.GetUInt() 
        
        #訊息添加下單筆數  
        result += '下單筆數:' + str(Rcount) + '\r\n'

		#循環處理回應資料
        for _ in range(Rcount):
		    #intIdentify識別碼 
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
			#shtReplyCode委託結果代碼 0代表委託成功，其他則為委託失敗
            result += '{0}'.format(str(dataGetter.GetShort())) + ',' 
			#abyOrderNO委託書編號
            result += dataGetter.GetStr(5) + ',' 
			#struTradeDate交易日期
            yuantaDate = dataGetter.GetTYuantaDate() 
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #abyErrKind錯誤類別
            result += dataGetter.GetStr(1) + ',' 
			#abyErrNO錯誤代號
            result += dataGetter.GetStr(3) + ',' 
			#abyAdvisory錯誤說明
            result += dataGetter.GetStr(74) 
            result += '\r\n'
            
    except Exception as error:
        result = error

    return result

#OVFuture_order_out_response
#海外期貨下單回應 30.100.40.12
def OVFuture_order_out_response(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)

    result = '' 

    try:
        result += '國外期貨下單結果: \r\n'
        #abyMsgCode訊息代碼 0001代表執行成功，其他則為失敗
        result += dataGetter.GetStr(4) + ',' 
        #abyMsgContent訊息內容
        result += dataGetter.GetStr(50) + ',' 
        #uintCount筆數
        Rcount = dataGetter.GetUInt()  
        
        #訊息添加下單筆數  
        result += '下單筆數:' + str(Rcount) + '\r\n'
        
        #循環處理回應資料
        for _ in range(Rcount):
            #intIdentify識別碼 
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #shtReplyCode委託結果代碼 
            result += '{0}'.format(str(dataGetter.GetShort())) + ',' 
            #abyOrderNO委託書編號 
            result += str(dataGetter.GetStr(5)) + ',' 
            #struTradeDate交易日期 
            yuantaDate = dataGetter.GetTYuantaDate() 
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #abyErrType錯誤類別 
            result += str(dataGetter.GetStr(1)) + ',' 
            #abyErrNO錯誤代號 
            result += str(dataGetter.GetStr(3)) + ',' 
            #abyAdvisory錯誤說明 
            result += str(dataGetter.GetStr(74))  
            result +='\r\n'
        
    except Exception as error:
        result = error

    return result

#ReadWatchlistAll_response
#讀取行情報價 50.0.0.16
def ReadWatchListAll_Out(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    #筆數
    nRowCount = dataGetter.GetUInt()
    result = ''
    result = '讀取報價表結果:\r\n'
    
    try:
        for i in range(nRowCount):
            result +='\r\n市場別:{0} 商品代碼:{1} 商品名稱:{2}\r\n昨收價:{3}\r\n開盤參考價:{4}\r\n漲停價:{5}\r\n跌停價:{6}\r\n昨量:{7}\r\n擴充名:{8}\r\n小數位數:{9}\r\n融資成數:{10}\r\n融券成數:{11}'.format(
                #byMarketNo市場代碼
                str(dataGetter.GetByte()),
                #abyStkCode股票代碼
                dataGetter.GetStr(12),
                #abyStkName股票名稱
                dataGetter.GetStr(20),
                #intYstPrice昨收價
                str(dataGetter.GetInt()),
                #intOpenRefPrice開盤參考價
                str(dataGetter.GetInt()),
                #intUpStopPrice漲停價
                str(dataGetter.GetInt()),
                #intDownStopPrice跌停價
                str(dataGetter.GetInt()),
                #uintYstVol昨量
                str(dataGetter.GetInt()),
                #abyExtName擴充名
                dataGetter.GetStr(20),  
                 #shtDecimal小數位數 
                str(dataGetter.GetShort()),    
                #byCreditPercent融資成數
                str(dataGetter.GetByte()),
                #byLenBondPercent融券成數
                str(dataGetter.GetByte()),)

            #dataGetter.GetStr(24); #中間24bytes沒要用不解開

            result+='\r\n開盤價:{0}\r\n最高價:{1}\r\n最低價:{2}\r\n買價:{3}\r\n累計外盤量:{4}\r\n賣價:{5}\r\n累計內盤量:{6}\r\n成交價:{7}\r\n總成交金額:{8}\r\n單量內外盤標記:{9}\r\n單量:{10}\r\n總成交量:{11}\r\n'.format(
                #intOpenPrice開盤
                str(dataGetter.GetInt()),
                #intHighPrice最高
                str(dataGetter.GetInt()),
                #intLowPrice最低
                str(dataGetter.GetInt()),
                #intBuyPrice買價
                str(dataGetter.GetInt()),
                #uintTotalOutVol累計外盤量
                str(dataGetter.GetInt()),
                #intSellPrice賣價
                str(dataGetter.GetInt()),
                #uintTotalInVol累計內盤量
                str(dataGetter.GetInt()),
                #intDealPrice成交價
                str(dataGetter.GetInt()),
                #uintTotalDealAmt總成交金額
                str(dataGetter.GetInt()),
                #bytVolFlag單量內外盤標記
                str(dataGetter.GetByte()),
                #uintVol單量
                str(dataGetter.GetInt()),
                #uintTotalVol總成交量
                str(dataGetter.GetInt()))

            dataGetter.GetStr(105); #後面資料沒用到就不解析 需要請自行參考文件調整

    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#stk_OrderTradeReport
#委託成交綜合回報 20.101.0.18
def stk_OrderTradeReport(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    
    try:
        #uintCount1現貨委託筆數
        count=dataGetter.GetInt()
        result += '現貨委託筆數:'+ str(count) +'\r\n'
        
        for _ in range(count):
            #struStkAccountInfo帳號
            result += dataGetter.GetStr(22) + ','
            #struTradeYMD交易日
            yuantaDate = dataGetter.GetTYuantaDate() 
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ',' 
            #byMarketNo市場代碼
            result += str(dataGetter.GetByte()) + ','
            #abyMarketName市場名稱 
            result += dataGetter.GetStr(30) + ',' 
            #abyCompanyNo股票代號
            result += dataGetter.GetStr(12) + ',' 
            #abyStkName股票名稱
            result += dataGetter.GetStr(30) + ',' 
            #shtOrderType委託種類
            result += str(dataGetter.GetShort()) + ',' 
            #abyBS買賣別
            result += dataGetter.GetStr(1)+ ',' 
            #lngPrice價位
            result += str(dataGetter.GetLong()) + ',' 
            #abyPriceFlag價格種類
            result += dataGetter.GetStr(1)+ ',' 
            #intBeforeQty前一次委託量
            result += str(dataGetter.GetInt()) + ',' 
            #intAfterQty目前委託量  
            result += str(dataGetter.GetInt()) + ','   
            #intOkQty成交量    
            result += str(dataGetter.GetInt()) + ','    
            #shtOrderStatus委託狀態
            result += str(dataGetter.GetShort()) + ',' 
            #struAcceptDate委託日期
            yuantaDate = dataGetter.GetTYuantaDate() 
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','     
            #struAcceptTime委託時間 
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #abyOrderNo委託單號 
            result += dataGetter.GetStr(5) + ',' 
            #abyOrderErrorNo錯誤碼
            result += dataGetter.GetStr(5) + ','  
            #abyEmError錯誤原因
            result += dataGetter.GetStr(120) + ',' 
            #shtSeller營業員代碼 
            result += str(dataGetter.GetShort()) + ','    
            #abyChannel  
            result += dataGetter.GetStr(3) + ',' 
            #shtAPCode  
            result += str(dataGetter.GetShort()) + ','   
            #intOTax證交稅
            result += str(dataGetter.GetInt()) + ',' 
            #intOCharge手續費
            result += str(dataGetter.GetInt()) + ',' 
            #intODueAmt應收付
            result += str(dataGetter.GetInt()) + ',' 
            #abyCancelFlag可取消Flag
            result += dataGetter.GetStr(1)+ ',' 
            #abyReduceFlag可減量Flag
            result += dataGetter.GetStr(1)+ ',' 
            #abyTraditionFlag傳統單Flag 
            result += dataGetter.GetStr(1)+ ','    
            #abyBasketNo 
            result += dataGetter.GetStr(10)+ ','    
            #abyTradeCurrency報價幣別 
            result += dataGetter.GetStr(3)+ ','     
            #abyTime_in_Force委託效期 
            result += dataGetter.GetStr(1)+ ','     
            #abyOrder_Success委託成功旗標
            result += dataGetter.GetStr(1)+ ','     
            #abyReduce_Flag本委託下單是否被減量
            result += dataGetter.GetStr(1)+ ','    
            #abyChg_Prz_Flag本委託下單是否進行改價
            result += dataGetter.GetStr(1)+ ','      
            #abyTSE_Cancel本委託下單是否被交易所主動刪單
            result += dataGetter.GetStr(1)+ ','       
            #intCancelQty取消數量
            result += str(dataGetter.GetInt()) + ',' 
            #intOR_QTY原委託量
            result += str(dataGetter.GetInt()) + ','     
            #struUpdateDate更新日期
            yuantaDate = dataGetter.GetTYuantaDate() 
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','   
            #struUpdateTime更新時間  
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}/{1}/{2}'.format(yuantaTime.bytHour, yuantaTime.bytMin, yuantaTime.bytSec, yuantaTime.ushtMSec) + ','      
            result += '\r\n'
        
        #uintCount2現貨成交筆數
        count=dataGetter.GetInt()
        result += '現貨成交筆數:'+ str(count) +'\r\n'
        
        for _ in range(count):
            #abyAccount帳號
            result += dataGetter.GetStr(22) + ',' 
            #byMarketNo市場代碼
            result += str(dataGetter.GetByte()) + ',' 
            #abyMarketName市場名稱 
            result += dataGetter.GetStr(30) + ',' 
            #abyCompanyNo股票代號
            result += dataGetter.GetStr(12) + ',' 
            #abyStkName股票名稱
            result += dataGetter.GetStr(30) + ',' 
            #shtOrderType委託種類
            result += str(dataGetter.GetShort()) + ',' 
            #abyBS買賣別 
            result += dataGetter.GetStr(1)+ ',' 
            #intOkStockNos成交量
            result += str(dataGetter.GetInt()) + ','
            #lngOPrice委託價
            result += str(dataGetter.GetLong()) + ',' 
            #lngSPrice成交價 
            result += str(dataGetter.GetLong()) + ','
            #struDateTime交易日(年月日時分秒毫秒)
            yuantaDateTime = dataGetter.GetTYunataDateTime() 
            result += '{0}/{1}/{2} {3}:{4}:{5}.{6}'.format(yuantaDateTime.struDate.ushtYear, yuantaDateTime.struDate.bytMon, yuantaDateTime.struDate.bytDay, yuantaDateTime.struTime.bytHour, yuantaDateTime.struTime.bytMin, yuantaDateTime.struTime.bytSec, yuantaDateTime.struTime.ushtMSec) + ','           
            #abyOrderNo委託單號 
            result += dataGetter.GetStr(5) + ',' 
            #abyTradeCurrency報價幣別 
            result += dataGetter.GetStr(3) + ',' 
            #abyPrice_Flag價位Flag  
            result += dataGetter.GetStr(1) + ','   
            #shtExchange_Code委託別
            result += str(dataGetter.GetShort()) + ','             
            result += '\r\n'

        #uintCount3期貨委託筆數
        uintFutOrderCount = dataGetter.GetUInt()
        result += '期貨委託筆數: ' + str(uintFutOrderCount) + '\r\n'
        
        for _ in range(uintFutOrderCount):
            #abyAccount期貨帳號
            result += dataGetter.GetStr(22) +','
            #struTradeDate交易日期
            yuantaDate = dataGetter.GetTYuantaDate()
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #byMarketNo市場代碼
            result += '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyMarketName市場名稱
            result += dataGetter.GetStr(30) +',' 
            #abyCommodityID1商品名稱1
            result += dataGetter.GetStr(7) +',' 
            #intSettlementMonth1商品月份1
            result += '{0}'.format(str(dataGetter.GetInt())) + ','
            #intStrikePrice1履約價1
            result += '{0}'.format(str(dataGetter.GetInt())) + ','
            #abyBuySellKind1買賣別1
            result += dataGetter.GetStr(1) +',' 
            #abyCommodityID2商品名稱2
            result += dataGetter.GetStr(7) +',' 
            #intSettlementMonth2商品月份2
            result += '{0}'.format(str(dataGetter.GetInt())) + ','
            #intStrikePrice2履約價2
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #abyBuySellKind2買賣別2
            result += dataGetter.GetStr(1) +',' 
            #abyOpenOffsetKind新/平倉 0:新倉,1:平倉,2系統
            result += dataGetter.GetStr(1) +',' 
            #abyOrderCondition委託條件 
            result += dataGetter.GetStr(1) +',' 
            #abyOrderPrice委託價 
            result += dataGetter.GetStr(10) +',' 
            #intBeforeQty前一次委託量 
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #intAferQty目前委託量 
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #intOKQty成交口數 
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #shtStatus委託狀態 
            result += '{0}'.format(str(dataGetter.GetShort())) + ',' 
            #struAcceptDate委託日期
            yuantaDate = dataGetter.GetTYuantaDate()
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #struAcceptTime委託時間
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #abyErrorNo錯誤代碼 
            result += dataGetter.GetStr(10) +',' 
            #abyErrorMessage錯誤訊息 
            result += dataGetter.GetStr(120) +',' 
            #abyOrderNO委託單號 
            result += dataGetter.GetStr(5) +',' 
            #abyProductType商品種類 
            result += dataGetter.GetStr(1) +',' 
            #ushtSeller營業員代碼 
            result += '{0}'.format(str(dataGetter.GetUShort())) + ','
            #lngTotalMatFee手續費總和 
            result += '{0}'.format(str(dataGetter.GetLong())) + ','
            #lngTotalMatExchTax交易稅總和 
            result += '{0}'.format(str(dataGetter.GetLong())) + ','
            #lngTotalMatPremium應收付 
            result += '{0}'.format(str(dataGetter.GetLong())) + ','
            #abyDayTradeID當沖註記 
            result += dataGetter.GetStr(1) +',' 
            #abyCancelFlag可取消Flag 
            result += dataGetter.GetStr(1) +',' 
            #abyReduceFlag可減量Flag 
            result += dataGetter.GetStr(1) +','
            #abyStkName1商品名稱1 
            result += dataGetter.GetStr(30) +','
            #abyStkName2商品名稱2 
            result += dataGetter.GetStr(30) +','
            #abyTraditionFlag傳統單Flag 
            result += dataGetter.GetStr(1) +','
            #abyTRID商品代碼 
            result += dataGetter.GetStr(20) +','
            #abyCurrencyType交易幣別 
            result += dataGetter.GetStr(3) +','
            #abyCurrencyType2交割幣別 
            result += dataGetter.GetStr(3) +','
            #abyBasketNo 
            result += dataGetter.GetStr(10) +','
            #byMarketNo1市場代碼1 
            result += '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyStkCode1行情股票代碼1 
            result += dataGetter.GetStr(12) +','
            #byMarketNo2市場代碼2 
            result +=  '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyStkCode2行情股票代碼2 
            result +=  dataGetter.GetStr(12) 
            result+='\r\n'
        
        #uintCount4期貨成交筆數
        uintFuTradeCount = dataGetter.GetUInt()
        result += '期貨成交筆數: ' + str(uintFuTradeCount) + '\r\n'
        
        for _ in range(uintFuTradeCount):
            #abyAccount期貨帳號
            result +=  dataGetter.GetStr(22) +','
            #byMarketNo市場代碼
            result +=  '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyMarketName市場名稱
            result +=  dataGetter.GetStr(30) +','
            #abyCommodityID1商品名稱1
            result +=  dataGetter.GetStr(7) +','
            #intSettlementMonth1商品月份1
            result +=   '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #abyBuySellKind1買賣別1
            result +=  dataGetter.GetStr(1) +','
            #intMatchQty成交口數
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ','
            #lngMatchPrice1成交價1
            result +=  '{0}'.format(str(dataGetter.GetLong())) + ','
            #lngMatchPrice2成交價2
            result +=  '{0}'.format(str(dataGetter.GetLong())) + ','
            #struMatchTime成交時間
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #struMatchDate成交日期
            yuantaDate = dataGetter.GetTYuantaDate()
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #abyOrderNO委託單號
            result +=   dataGetter.GetStr(5) +','
            #intStrikePrice1履約價1
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ','
            #abyCommodityID2商品名稱2
            result +=  dataGetter.GetStr(7) +','
            #intSettlementMonth2商品月份2
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ','
            #abyBuySellKind2買賣別2
            result += dataGetter.GetStr(1) +','
            #intStrikePrice2履約價2
            result += '{0}'.format(str(dataGetter.GetInt())) + ','
            #abyRecType單式單/複式單 “1”:單式 “2”:複式
            result += dataGetter.GetStr(1) +','
            #abyProductType商品種類
            result += dataGetter.GetStr(1) +','
            #lngOrderPrice委託價
            result += '{0}'.format(str(dataGetter.GetLong())) + ','
            #abyStkName1商品名稱1
            result += dataGetter.GetStr(30) +','
            #abyStkName2商品名稱2
            result += dataGetter.GetStr(30) +','
            #abyDayTradeID當沖註記
            result += dataGetter.GetStr(1) +','
            #lng SprMatchPrice複式單成交價
            result +=  '{0}'.format(str(dataGetter.GetLong())) + ','
            #abyTRID商品代碼
            result += dataGetter.GetStr(20) +','
            #abyCurrencyType交易幣別
            result += dataGetter.GetStr(3) +','
            #abyCurrencyType2交割幣別
            result += dataGetter.GetStr(3) +','
            #abySubNo子成交序號 0(單式)1(複式腳1)2(複式腳2)
            result += dataGetter.GetStr(1) 
            result +='\r\n'

        #uintCount5國外股票委託筆數
        uintOVOrderCount = dataGetter.GetUInt()
        result += '國外股票委託筆數: ' + str(uintOVOrderCount) + '\r\n'
        
        for _ in range(uintOVOrderCount):
            #abyAccount證券帳號
            result +=  dataGetter.GetStr(22) +','
            #struTradeYMD交易日
            yuantaDate = dataGetter.GetTYuantaDate()
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #byMarketNo市場代碼
            result +=  '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyMarketName市場名稱
            result +=  dataGetter.GetStr(30) +','
            #abyCompanyNo股票代碼
            result +=  dataGetter.GetStr(12) +','
            #abyStkName股票名稱
            result +=  dataGetter.GetStr(30) +','
            #abyBS買賣別
            result +=  dataGetter.GetStr(1) +','
            #abyCurrencyType交易幣別
            result +=  dataGetter.GetStr(3) +','
            #lngPrice委託價
            result +=  '{0}'.format(str(dataGetter.GetLong())) + ',' 
            #abyPriceType價格型態
            result +=  dataGetter.GetStr(3) +','
            #intOrderQty委託量
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #intMatchQty成交量
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #shtOrderStatus狀態碼
            result +=  '{0}'.format(str(dataGetter.GetShort())) + ',' 
            #struOrderTime委託時間
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #abyOrderType委託單型態
            result +=  dataGetter.GetStr(3) +','
            #abyOrderNo委託書編號
            result +=  dataGetter.GetStr(7) +','
            #intFee手續費
            result +=   '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #lngPolarisAMT應收付金額
            result +=  '{0}'.format(str(dataGetter.GetLong())) + ',' 
            #abyOrderErrorNo錯誤碼
            result +=  dataGetter.GetStr(8) +','
            #abyEmError錯誤原因
            result +=  dataGetter.GetStr(180) +','
            #abyCurrencyType2交割幣別
            result +=  dataGetter.GetStr(3) +','
            #abyCancelFlag可取消Flag
            result +=  dataGetter.GetStr(1) +','
            #abyReduceFlag可減量Flag
            result +=  dataGetter.GetStr(1) +','
            #abyTraditionFlag傳統單Flag
            result +=  dataGetter.GetStr(1) +','
            #abySettleType交割方式
            result +=  dataGetter.GetStr(1) +','
            #abyBasketNo
            result +=  dataGetter.GetStr(10) 

        #uintCount6國外股票成交筆數
        uintOVTradeCount = dataGetter.GetUInt()
        result += '國外股票成交筆數: ' + str(uintOVTradeCount) + '\r\n'
        
        for _ in range(uintOVTradeCount):
            #abyAccount現貨帳號
            result +=  dataGetter.GetStr(22) +','
            #byMarketNo市場代碼
            result +=  '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyMarketName市場名稱
            result +=  dataGetter.GetStr(30) +','
            #abyCompanyNo股票代碼
            result +=  dataGetter.GetStr(12) +','
            #abyStkName股票名稱
            result +=  dataGetter.GetStr(30) +','
            #abyBS買賣別
            result +=  dataGetter.GetStr(1) +','
            #abyCurrencyType交易幣別
            result +=  dataGetter.GetStr(3) +','
            #intMatchQty成交量
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ','
            #lngOrderPrice委託價
            result +=  '{0}'.format(str(dataGetter.GetLong())) + ','
            #lngMatchPrice成交價
            result +=  '{0}'.format(str(dataGetter.GetLong())) + ','
            #struDateTime成交時間
            yuantaDateTime = dataGetter.GetTYunataDateTime()
            result += '{0}/{1}/{2} {3}:{4}:{5}'.format(yuantaDateTime.struDate.ushtYear, yuantaDateTime.struDate.bytMon, yuantaDateTime.struDate.bytDay, yuantaDateTime.struTime.bytHour, yuantaDateTime.struTime.bytMin, yuantaDateTime.struTime.bytSec) + ',' 
            #intFee手續費
            result += '{0}'.format(str(dataGetter.GetInt())) + ','
            #abyOrderNo委託單號
            result +=  dataGetter.GetStr(7)  +','
            #lngSettlementAMT成交金額
            result +=  '{0}'.format(str(dataGetter.GetLong())) + ','
            #abyCurrencyType2交割幣別
            result +=  dataGetter.GetStr(3)  
            result +='\r\n'

        #uintCount7國際期貨委託筆數
        uintOFOrderCount = dataGetter.GetUInt()
        result += '國外期貨委託筆數:' + str(uintOFOrderCount) + '\r\n' 
        
        for _ in range(uintOFOrderCount):
            #abyAccount期貨帳號
            result +=  dataGetter.GetStr(22) +','
            #struTradeYMD交易日
            yuantaDate = dataGetter.GetTYuantaDate()
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #byMarketNo市場代碼
            result +=  '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyMarketName市場名稱
            result +=  dataGetter.GetStr(30) +','
            #abyCommodityID商品代碼
            result +=  dataGetter.GetStr(7) +','
            #intSettlementMonth商品年月
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #abyStkName商品名稱
            result +=  dataGetter.GetStr(30) +','
            #abyBuySell買賣別
            result +=  dataGetter.GetStr(1) +','
            #abyOrderType委託方式
            result +=  dataGetter.GetStr(3) +','
            #abyOdrPrice委託價
            result +=  dataGetter.GetStr(14) +','
            #abyTouchPrice停損執行價
            result +=  dataGetter.GetStr(14) +','
            #intOrderQty委託口數
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #intMatchQty成交口數
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #shtOrderStatus狀態碼
            result +=  '{0}'.format(str(dataGetter.GetShort())) + ',' 
            #struAcceptDate委託日期
            yuantaDate = dataGetter.GetTYuantaDate()
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #struAcceptTime委託時間
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #abyErrorNo錯誤代碼
            result +=  dataGetter.GetStr(10) +','
            #abyErrorMessage錯誤訊息
            result +=  dataGetter.GetStr(120) +','
            #abyOrderNo委託書編號
            result +=  dataGetter.GetStr(8) +','
            #abyDayTradeID當沖註記
            result +=  dataGetter.GetStr(1) +','
            #abyCancelFlag可取消Flag
            result +=  dataGetter.GetStr(1) +','
            #abyReduceFlag可減量Flag
            result +=  dataGetter.GetStr(1) +','
            #lngUtPrice委託價格整數位
            result +=  '{0}'.format(str(dataGetter.GetLong())) + ',' 
            #intUtPrice2委託價格分子
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #intMinPrice2委託價格分母
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #lngUtPrice4停損執行價整數位
            resultt +=  '{0}'.format(str(dataGetter.GetLong())) + ',' 
            #intUtPrice5停損執行價格分子
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #intUtPrice6停損執行價格分母
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #abyTraditionFlag傳統單Flag
            result +=  dataGetter.GetStr(1) +','
            #abyBasketNo
            result +=  dataGetter.GetStr(10) +','
            #byMarketNo1市場代碼1
            result +=  '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyStkCode1行情股票代碼1
            result +=   dataGetter.GetStr(12) +','
            #abyCurrencyType交易幣別
            result +=   dataGetter.GetStr(3) +','
            #abyCurrencyType2交割幣別
            result +=   dataGetter.GetStr(3) 
            result +='\r\n'

        #uintCount8國際期貨成交筆數
        uintOFTradeCount = dataGetter.GetUInt()
        result += '國外期貨成交筆數:' + str(uintOFTradeCount) + '\r\n'
        
        for _ in range(uintFutOrderCount):
            #abyAccount期貨帳號
            result +=  dataGetter.GetStr(22) +','
            #byMarketNo市場代碼
            result +=  '{0}'.format(str(dataGetter.GetByte())) + ',' 
            #abyMarketName市場名稱
            result +=  dataGetter.GetStr(30) +','
            #abyCommodityID商品代碼
            result +=  dataGetter.GetStr(7) +','
            #intSettlementMonth商品年月
            result +=  '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #abyStkName商品名稱
            result +=  dataGetter.GetStr(30) +','
            #abyBuySell買賣別
            result +=  dataGetter.GetStr(1) +','
            #shtMatchQty成交口數
            result +=   '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #abyOdrPrice委託價
            result +=  dataGetter.GetStr(14) +','
            #abyMatchPrice成交價
            result +=  dataGetter.GetStr(14) +','
            #struMatchDate成交日期
            yuantaDate = dataGetter.GetTYuantaDate()
            result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
            #struMatchTime成交時間
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #abyOrderNo委託書編號
            result +=  dataGetter.GetStr(8) +','
            #abyCurrencyType交易幣別
            result +=  dataGetter.GetStr(3) +','
            #abyCurrencyType2交割幣別
            result +=  dataGetter.GetStr(3) 
            result +='\r\n'

        dataGetter.ClearOutputData()

    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#stk_SummaryReport
#庫存綜合總表 20.103.0.22
def stk_SummaryReport(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    
    try:   
        #uintCount1現貨庫存筆數
        count=dataGetter.GetInt()
        result += '庫存綜合總表筆數:'+ str(count) +',\r\n'
        
        for _ in range(count):               
            #abyAccount帳號
            result += dataGetter.GetStr(22) + ',' 
            #shtTradeKind交易種類
            result += str(dataGetter.GetShort()) + ',' 
            #byMarketNo市場代碼
            result += str(dataGetter.GetByte()) + ',' 
            #abyMarketName市場名稱 
            result += dataGetter.GetStr(30) + ',' 
            #abyStkCode股票代號
            result += dataGetter.GetStr(12) + ',' 
            #abyStkName股票名稱
            result += dataGetter.GetStr(30) + ',' 
            #lngStockNos股數
            result += str(dataGetter.GetLong()) + ',' 
            #lngPrice成交均價
            result += str(dataGetter.GetLong()) + ',' 
            #lngCost持有成本
            result += str(dataGetter.GetLong()) + ',' 
            #lngInterest預估利息
            result += str(dataGetter.GetLong()) + ',' 
            #intBuyNotInNos買進未入帳股數
            result += str(dataGetter.GetInt()) + ',' 
            #intSellNotInNos賣出未入帳股數
            result += str(dataGetter.GetInt()) + ',' 
            #lngCanOrderQty今日可下單股數
            result += str(dataGetter.GetLong()) + ',' 
            #lngLoan資保證金/券擔保價品
            result += str(dataGetter.GetLong()) + ',' 
            #intTaxRate交易稅率
            result += str(dataGetter.GetInt()) + ',' 
            #uintLotSize交易單位 
            result += str(dataGetter.GetUInt()) + ','   
            #intMarketPrice市價 
            result += str(dataGetter.GetInt()) + ','    
            #shtDecimal小數位數
            result += str(dataGetter.GetShort()) + ','    
            #byStkType1屬性1 
            result += str(dataGetter.GetByte()) + ','   
            #byStkType2屬性2 
            result += str(dataGetter.GetByte()) + ','   
            #intBuyPrice買價  
            result += str(dataGetter.GetInt()) + ',' 
            #intSellPrice賣價 
            result += str(dataGetter.GetInt()) + ','  
            #intUpStopPrice漲停價
            result += str(dataGetter.GetInt()) + ','   
            #intDownStopPrice跌停價 
            result += str(dataGetter.GetInt()) + ','  
            #uintPriceMultiplier計價倍數 
            result += str(dataGetter.GetUInt()) + ','  
            #abyTradeCurrency報價幣別
            result += dataGetter.GetStr(3) + ','  
            #lngCDQTY借貸股數 
            result += str(dataGetter.GetLong()) + ',' 
            #lngCanOrderOddQty零股可下單股數 
            result += str(dataGetter.GetLong())           		
            result += '\r\n'
        
        #uintCount2國外股票庫存筆數
        #未提供複委託交易故國外股票庫存皆回傳0
        count=dataGetter.GetInt()
        result += '國外股票庫存筆數:'+ str(count) +',\r\n'
        
        for _ in range(count):               
            #abyAccount帳號
            result += dataGetter.GetStr(22) + ',' 
            #abyCurrencyType幣別
            result += dataGetter.GetStr(3) + ',' 
            #byMarketNo市場代碼
            result += dataGetter.GetStr(1) + ',' 
            #abyMarketName市場名稱
            result += dataGetter.GetStr(30) + ','  
            #abyStkCode股票代號
            result += dataGetter.GetStr(12) + ',' 
            #abyStkName股票名稱
            result += dataGetter.GetStr(30) + ',' 
            #abyStkFullName股票全名
            result += dataGetter.GetStr(60) + ',' 
            #lngStockQty庫存股數
            result += str(dataGetter.GetLong()) + ',' 
            #lngTradingQty可交易股數
            result += str(dataGetter.GetLong()) + ',' 
            #lngPrice成交均價
            result += str(dataGetter.GetLong()) + ',' 
            #lngCost持有成本
            result += str(dataGetter.GetLong()) + ',' 
            #intCloseRate匯率
            result += str(dataGetter.GetInt()) + ',' 
            #byRateKind匯率運算模式
            result += dataGetter.GetStr(1) + ',' 
            #uintLotSize交易單位
            result += str(dataGetter.GetUInt()) + ',' 
            #intMarketPrice市價   
            result += str(dataGetter.GetInt()) + ','    
            #shtDecimal小數位數
            result += str(dataGetter.GetShort()) + ','    
            #intBuyPrice買價
            result += str(dataGetter.GetInt()) + ','   
            #intSellPrice賣價
            result += str(dataGetter.GetInt())             		
            result += '\r\n'
            
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#fut_SummaryReport
#期貨庫存總表 20.103.20.13
def fut_SummaryReport(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    
    try:   
        #uintCount筆數
        count=dataGetter.GetInt()
        result += '期貨庫存總表筆數:'+ str(count) +',\r\n'
        
        for _ in range(count):               
            #struFutAccountInfo帳號
            result += dataGetter.GetStr(22) + ',' 
            #abyKind委託種類
            result += dataGetter.GetStr(1) + ',' 
            #abyTrid商品代碼
            result += dataGetter.GetStr(21) + ',' 
            #abyBS買賣別
            result += dataGetter.GetStr(1) + ',' 
            #intQty未平倉口數
            result += str(dataGetter.GetInt()) + ',' 
            #lngAmt總成交點數
            result += str(dataGetter.GetLong()) + ',' 
            #intFee手續費
            result += str(dataGetter.GetInt()) + ',' 
            #intTax交易稅
            result += str(dataGetter.GetInt()) + ','             
            #abyCurrencyType幣別
            result += dataGetter.GetStr(3) + ','  
            #abyDayTradeID當沖註記
            result += dataGetter.GetStr(1) + ','         
            #abyCommodityID1商品名稱1
            result += dataGetter.GetStr(6) + ','  
            #abyCallPut1買賣權1
            result += dataGetter.GetStr(1) + ',' 
            #intSettlementMonth1交易月份1
            result += str(dataGetter.GetInt()) + ',' 
            #intStrikePrice1履約價1
            result += str(dataGetter.GetInt()) + ',' 
            #abyBS1買賣別1
            result += dataGetter.GetStr(1) + ','
            #abyStkName1股票名稱1
            result += dataGetter.GetStr(20) + ','             
            #byMarketNo1市場代碼1
            result += str(dataGetter.GetByte()) + ','             
            #abyStkCode1行情報價代碼1
            result += dataGetter.GetStr(12) + ','             
            #abyCommodityID2商品名稱2
            result += dataGetter.GetStr(6) + ','              
            #abyCallPut2買賣權2
            result += dataGetter.GetStr(1) + ','         
            #intSettlementMonth2交易月份2
            result += str(dataGetter.GetInt()) + ',' 
            #intStrikePrice2履約價2
            result += str(dataGetter.GetInt()) + ',' 
            #abyBS2買賣別2
            result += dataGetter.GetStr(1) + ','
            #abyStkName2股票名稱2
            result += dataGetter.GetStr(20) + ','             
            #byMarketNo2市場代碼2
            result += str(dataGetter.GetByte()) + ','             
            #abyStkCode2行情報價代碼2
            result += dataGetter.GetStr(12) + ','              
            #intBuyPrice1買入價1
            result += str(dataGetter.GetInt()) + ',' 
            #intSellPrice1賣出價1
            result += str(dataGetter.GetInt()) + ',' 
            #intMarketPrice1市價1
            result += str(dataGetter.GetInt()) + ',' 
            #intBuyPrice2買入價2
            result += str(dataGetter.GetInt()) + ',' 
            #intSellPrice2賣出價2
            result += str(dataGetter.GetInt()) + ',' 
            #intMarketPrice2市價2
            result += str(dataGetter.GetInt()) + ',' 
            #shtDecimal小數位數
            result += str(dataGetter.GetShort()) + ',' 
            #abyProductType1商品類別1
            result += dataGetter.GetStr(1) + ','
            #abyProductKind1商品屬性1
            result += dataGetter.GetStr(1) + ','
            #abyProductType2商品類別2
            result += dataGetter.GetStr(1) + ',' 
            #abyProductKind2商品屬性2
            result += dataGetter.GetStr(1) + ','
            #intUpStopPrice1漲停價1
            result += str(dataGetter.GetInt()) + ',' 
            #intDownStopPrice1跌停價1
            result += str(dataGetter.GetInt()) + ',' 
            #intUpStopPrice2漲停價2
            result += str(dataGetter.GetInt()) + ',' 
            #intDownStopPrice2跌停價2
            result += str(dataGetter.GetInt()) + ',' 
            #abyStkCode1opp行情股票代碼1反向
            result += dataGetter.GetStr(12) + ','             
            #abyStkCode2opp行情股票代碼2反向
            result += dataGetter.GetStr(12)                       		
            result += '\r\n'
            
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#OVfut_SummaryReport
#國際期貨庫存總表 20.103.40.18
def OVfut_SummaryReport(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    
    try:   
        #uintCount筆數
        count=dataGetter.GetInt()
        result += '國際期貨庫存總表筆數:'+ str(count) +',\r\n'
        
        for _ in range(count):               
            #struFutAccountInfo帳號
            result += dataGetter.GetStr(22) + ',' 
            #abyKind委託種類
            result += dataGetter.GetStr(1) + ','
            #abyTrid商品代碼
            result += dataGetter.GetStr(20) + ',' 
            #abyBS買賣別
            result += dataGetter.GetStr(1) + ',' 
            #intQty未平倉口數
            result += str(dataGetter.GetInt()) + ',' 
            #lngAmt總成交點數
            result += str(dataGetter.GetLong()) + ',' 
            #abyCommodityID1商品名稱1
            result += dataGetter.GetStr(6) + ','              
            #abyCallPut1買賣權1
            result += dataGetter.GetStr(1) + ','   
            #intSettlementMonth1交易月份1
            result += str(dataGetter.GetInt()) + ',' 
            #abyProductCName1商品中文名稱1
            result += dataGetter.GetStr(18) + ','                
            #intStrikePrice1履約價1
            result += str(dataGetter.GetInt()) + ',' 
            #abyCommodityID2商品名稱2
            result += dataGetter.GetStr(6) + ','              
            #abyCallPut2買賣權2
            result += dataGetter.GetStr(1) + ','                 
            #intSettlementMonth2交易月份2
            result += str(dataGetter.GetInt()) + ',' 
            #abyProductCName2商品中文名稱2
            result += dataGetter.GetStr(18) + ','  
            #intStrikePrice2履約價2
            result += str(dataGetter.GetInt()) + ',' 
            #intFee手續費
            result += str(dataGetter.GetInt()) + ',' 
            #abyCurrencyType幣別
            result += dataGetter.GetStr(3) + ','  
            #abyDayTradeID當沖註記
            result += dataGetter.GetStr(1) + ','             
            #abyBS1買賣別1
            result += dataGetter.GetStr(1) + ',' 
            #abyBS2買賣別2
            result += dataGetter.GetStr(1) + ',' 
            #abyOptProdKind1選擇權商品種類1
            result += dataGetter.GetStr(1) + ','
            #abyOptProdKind2選擇權商品種類2
            result += dataGetter.GetStr(1) + ','           
            #byMarketNo1市場代碼1
            result += str(dataGetter.GetByte()) + ','             
            #abyStkCode1行情股票代碼1
            result += dataGetter.GetStr(12) + ','    
            #byMarketNo2市場代碼2
            result += str(dataGetter.GetByte()) + ','             
            #abyStkCode2行情股票代碼2
            result += dataGetter.GetStr(12) + ','                       
            #intBuyPrice1買入價1
            result += str(dataGetter.GetInt()) + ',' 
            #intSellPrice1賣出價1
            result += str(dataGetter.GetInt()) + ',' 
            #intMarketPrice1市價1
            result += str(dataGetter.GetInt()) + ',' 
            #intBuyPrice2買入價2
            result += str(dataGetter.GetInt()) + ',' 
            #intSellPrice2賣出價2
            result += str(dataGetter.GetInt()) + ',' 
            #intMarketPrice2市價2
            result += str(dataGetter.GetInt()) + ',' 
            #shtDecimal小數位數
            result += str(dataGetter.GetShort()) + ',' 
            #uintTickDiff檔差
            result += str(dataGetter.GetInt())
            result += '\r\n'
            
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#FutInterestStoreReport
#簡易權益數庫存 20.104.20.20
def FutInterestStoreReport(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''

    try:
        result += '簡易權益數:\r\n'
        #shtReplyCode委託結果代碼
        result += str(dataGetter.GetShort()) + ','
        #abyAdvisory錯誤說明
        result += dataGetter.GetStr(78) + ','    
        #abyType型態
        result += dataGetter.GetStr(1) + ','  
        #abyCurrency幣別
        result += dataGetter.GetStr(3) + ','  
        #lngEquity權益數
        result += str(dataGetter.GetLong()) + ',' 
        #lngAllFullIm全額原始保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngCanuseMargin可運用保證金
        result += str(dataGetter.GetLong()) + ',' 
        #abyRiskRate權益比率
        result += dataGetter.GetStr(9) + ','  
        #abyDaytradeRisk當沖風險指標
        result += dataGetter.GetStr(9) + ','
        #abyAllRiskRate風險指標
        result += dataGetter.GetStr(9) + ','  
        #lngCashForward前日餘額
        result += str(dataGetter.GetLong()) + ',' 
        #lngOpenGlYes昨日未平倉損益
        result += str(dataGetter.GetLong()) + ',' 
        #strucUpdateTime風險更新時間
        yuantaDateTime = dataGetter.GetTYunataDateTime() 
        result += '{0}/{1}/{2} {3}:{4}:{5}.{6}'.format(yuantaDateTime.struDate.ushtYear, yuantaDateTime.struDate.bytMon, yuantaDateTime.struDate.bytDay, yuantaDateTime.struTime.bytHour, yuantaDateTime.struTime.bytMin, yuantaDateTime.struTime.bytSec, yuantaDateTime.struTime.ushtMSec) + ','           
        #lngAccounting存/提
        result += str(dataGetter.GetLong()) + ',' 
        #lngFloatMargin未沖銷期貨浮動損益
        result += str(dataGetter.GetLong()) + ',' 
        #lngFloatPremium未沖銷買方選擇權市值 + 未沖銷賣方選擇權市值
        result += str(dataGetter.GetLong()) + ',' 
        #lngCommissionAll手續費    
        result += str(dataGetter.GetLong()) + ',' 
        #lngTotalValue權益總值 
        result += str(dataGetter.GetLong()) + ',' 
        #lngTaxRate期交稅
        result += str(dataGetter.GetLong()) + ',' 
        #lngAllIm原始保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngCallMargin追繳保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngGrantal本日期貨平倉損益淨額 + 到期履約損益
        result += str(dataGetter.GetLong()) + ',' 
        #lngAllMm維持保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngOrderIm委託保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngPremium權利金收入與支出
        result += str(dataGetter.GetLong()) + ',' 
        #lngOrderPremium委託權利金
        result += str(dataGetter.GetLong()) + ',' 
        #lngBalance本日餘額
        result += str(dataGetter.GetLong()) + ',' 
        #lngCanusePremium可動用(出金)保證金(含抵委)
        result += str(dataGetter.GetLong()) + ',' 
        #lngCoveredOim委託抵繳保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngBondAmt債券實物交割款
        result += str(dataGetter.GetLong()) + ',' 
        #lngNobondAmt債券實物不足交割款
        result += str(dataGetter.GetLong()) + ',' 
        #lngBondMargin債券待交割保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngCoveredIm有價證券抵繳總額
        result += str(dataGetter.GetLong()) + ',' 
        #lngReduceIm期貨多空減收保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngIncreaseIm加收保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngYTotalValue昨日權益總值
        result += str(dataGetter.GetLong()) + ',' 
        #lngRate匯率
        result += str(dataGetter.GetLong()) + ',' 
        #abyBestFlag客戶保證金計收方式
        result += str(dataGetter.GetByte()) + ','
        #lngGlToday本日損益
        result += str(dataGetter.GetLong()) + ',' 
        #lngDspEquity風險權益總值
        result += str(dataGetter.GetLong()) + ',' 
        #lngDspFloatmargin未沖銷期貨風險浮動損益
        result += str(dataGetter.GetLong()) + ',' 
        #lngDspFloatpremium未沖銷買方選擇權風險市值+未沖銷賣方選擇權風險市值
        result += str(dataGetter.GetLong()) + ',' 
        #lngDspIM風險原始保證金
        result += str(dataGetter.GetLong()) + ',' 
        #lngDspRiskRate盤後風險指標
        result += str(dataGetter.GetLong())
        result += '\r\n'

        #uintCount筆數
        count=dataGetter.GetInt()
        result += '簡易庫存筆數:'+ str(count) +',\r\n'

        for _ in range(count):               
            #struFutAccountInfo帳號
            result += dataGetter.GetStr(22) + ',' 
            #abyKind期權別
            result += dataGetter.GetStr(3) + ',' 
            #abyTrid商品代碼
            result += dataGetter.GetStr(21) + ',' 
            #abyID1商品組合代碼-單腳1
            result += dataGetter.GetStr(12) + ','                
            #abyCommodityID1商品名稱1
            result += dataGetter.GetStr(6) + ','              
            #intSettlementMonth1商品月份1
            result += str(dataGetter.GetInt()) + ',' 
            #abyCP1買賣權
            result += dataGetter.GetStr(1) + ','   
            #intStrikePrice1履約價1
            result += str(dataGetter.GetInt()) + ',' 
            #intNetLotsB1留倉總買1
            result += str(dataGetter.GetInt()) + ',' 
            #intNetLotsS1留倉總賣1
            result += str(dataGetter.GetInt()) + ',' 
            #byMarketNo1市場代碼1
            result += str(dataGetter.GetByte()) + ','             
            #abyStkCode1行情報價代碼1
            result += dataGetter.GetStr(12) + ','    
            #abyStkName1股票名稱1
            result += dataGetter.GetStr(20) + ','                
            #shtDecimal1小數位數1
            result += str(dataGetter.GetShort()) + ',' 
            #intBuyPrice1買入價1
            result += str(dataGetter.GetInt()) + ',' 
            #intSellPrice1賣出價1
            result += str(dataGetter.GetInt()) + ',' 
            #intMarketPrice1市價1
            result += str(dataGetter.GetInt()) + ',' 
            #abyID2商品組合代碼-單腳2
            result += dataGetter.GetStr(12) + ','                
            #abyCommodityID2商品代碼2
            result += dataGetter.GetStr(6) + ','              
            #intSettlementMonth2商品月份2
            result += str(dataGetter.GetInt()) + ',' 
            #abyCP2買賣權2
            result += dataGetter.GetStr(1) + ','     
            #intStrikePrice2履約價2
            result += str(dataGetter.GetInt()) + ',' 
            #intNetLotsB2留倉總買2
            result += str(dataGetter.GetInt()) + ',' 
            #intNetLotsS2留倉總賣2
            result += str(dataGetter.GetInt()) + ',' 
            #byMarketNo2市場代碼2
            result += str(dataGetter.GetByte()) + ','             
            #abyStkCode2行情報價代碼2
            result += dataGetter.GetStr(12) + ','    
            #abyStkName2股票名稱2
            result += dataGetter.GetStr(20) + ','                
            #shtDecimal2小數位數2
            result += str(dataGetter.GetShort()) + ',' 
            #intBuyPrice2買入價2
            result += str(dataGetter.GetInt()) + ',' 
            #intSellPrice2賣出價2
            result += str(dataGetter.GetInt()) + ',' 
            #intMarketPrice2市價2
            result += str(dataGetter.GetInt())
            result += '\r\n'

    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#FutDepositOptimumReport
#期貨保證金最佳化查詢20.104.20.17
def FutDepositOptimumReport(abyData):
    result = ''
    
    try:
        global DOLList
        DOLList = abyData    
        count=len(DOLList)
        result += '期貨保證金最佳化筆數:'+ str(count) +'\r\n'
        for i in range(count):
            depositOptimum=DOLList[i]
            #策略ID
            result +=str(depositOptimum.byStrategyID)+ ','
            #期貨帳號
            result +=depositOptimum.struFutAccountInfo+ ','
            #口數
            result +=str(depositOptimum.shtQty)+ ','
            #買賣別1
            result +=depositOptimum.abyBuySell1+ ','
            #買賣別2
            result +=depositOptimum.abyBuySell2+ ','
            #成交價1
            result +=str(depositOptimum.intDealPrice1)+ ','
            #成交價2
            result +=str(depositOptimum.intDealPrice2)+ ','
            #小數位數1
            result +=str(depositOptimum.shtDecimal1)+ ','
            #商品一保證金
            result +=str(depositOptimum.intCurrentIM1)+ ','
            #商品二保證金
            result +=str(depositOptimum.intCurrentIM2)+ ','
            #可節省保證金
            result +=str(depositOptimum.intSaveIM)+ ','
            #商品ID1
            result +=depositOptimum.abyCommodityID1+ ','
            #買賣權1
            result +=depositOptimum.abyCallPut1+ ','
            #商品年月1
            result +=str(depositOptimum.intSettlementMonth1)+ ','
            #履約價1
            result +=str(depositOptimum.intStrikePrice1)+ ','
            #股票名稱1
            result +=depositOptimum.abyStkName1+ ','
            #商品ID2
            result +=depositOptimum.abyCommodityID2+ ','
            #買賣權2
            result +=depositOptimum.abyCallPut2+ ','
            #商品年月2
            result +=str(depositOptimum.intSettlementMonth2)+ ','
            #履約價2
            result +=str(depositOptimum.intStrikePrice2)+ ','
            #股票名稱2
            result +=depositOptimum.abyStkName2
            result += '\r\n'
        
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#FutCombined_order_out_response
#期貨複式單組合30.100.20.14
def FutCombined_order_out_response(abyData):
    result = ''
    
    try:
        orderStatus=OrderStatus()
        orderStatus=abyData
        result += '期貨複式單組合:'
        #訊息代碼
        result +=orderStatus.ResultCount.MsgCode+ ','
        #訊息內容
        result +=orderStatus.ResultCount.MsgContent+ ','
        #筆數
        count=orderStatus.ResultCount.Count
        result +=str(count)+'筆\r\n'
        
        for i in range(count):
            OrderResultMesg=orderStatus.orderResult[i]
            #識別碼
            result +=str(OrderResultMesg.Identify)+ ','
            #委託結果代碼
            result +=str(OrderResultMesg.ReplyCode)+ ','
            #錯誤類別
            result +=OrderResultMesg.ErrType+ ','
            #錯誤代號
            result +=OrderResultMesg.ErrNO+ ','
            #錯誤說明
            result +=OrderResultMesg.Advisory+ ','
            result += '\r\n'
        
    except Exception as error:
        result = error
    #time.sleep(3)
    return result


#stk_order_real_report
#即時回報 200.10.10.26
def stk_order_real_report(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    
    try:
        result += '即時回報:\r\n'
		#abyAccount帳號
        result += dataGetter.GetStr(22) + ',' 
		#bytRptType回報類別50/51
        result += '回報類別:' + dataGetter.GetStr(1) + ',' 
		#abyOrderNo委託單號
        result += '委託單號:' + dataGetter.GetStr(20) + ','
        #byMarketNo市場代碼		
        result += '市場代碼:' + dataGetter.GetStr(1) + ',' 
		#abyCompanyNo商品代碼
        result += '商品代碼:' + dataGetter.GetStr(20) + ',' 
		#abyStkCName股票名稱
        result += '股票名稱:' + dataGetter.GetStr(20) + ','
        #struOrderDate交易日
        yuantaDate = dataGetter.GetTYuantaDate() 
        result += '{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
		#struOrderTime交易時間
        yuantaTime = dataGetter.GetTYuantaTime() 
        result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
		#abyOrderType委託種類 0:現貨
        result += '現貨:' + dataGetter.GetStr(3) + ',' 
		#abyBS買賣別
        buySell = dataGetter.GetStr(1) 
        result += '買賣別:' + buySell + ',' 
		#abyPrice價格
        result += 'price:' + dataGetter.GetStr(14) + ',' 
		#abyTouchPrice停損執行價(未使用欄位)
        dataGetter.GetStr(14) + ',' 
		#intBeforeQty改量前數量
        result += ' 改量前:{0}'.format(str(dataGetter.GetInt())) + ','
        #intOrderQty數量		
        result += '數量:{0}'.format(str(dataGetter.GetInt())) + '股,' 
		#abyOpenOffsetKind期權沖(未使用欄位)
        dataGetter.GetStr(1) + ',' 
		#abyDayTrade當沖記號 '' or X:現股當沖註記 
        result += '當沖記號:' + dataGetter.GetStr(1) + ',' 
		#abyOrderCond委託效期 0:ROD (預設) 3:IOC  4:FOK
        result += '委託效期:' + dataGetter.GetStr(1) + ',' 
		#abyOrderErrorNo錯誤碼
        result += '錯誤碼:' + dataGetter.GetStr(4) + ','  
		#bytTradeKind交易性質 1:買 2: 賣 3:改量  4:取消 5:查詢 6:改價 9:交易所主動刪單
        result += '交易性質:' + dataGetter.GetStr(1) + ','  
		#byAPCode委託類別 0:現股,2:零股,4:盤中零股,7:盤後,99:興櫃
        result += '委託類別:' + dataGetter.GetStr(1) + ',' 
		# YuantaOneAPI未使用欄位(52)
        #(abyBasketNo32/byOrderStatus/byStkType1/byStkType2/byBelongMarketNo/abyBelongStkCode/uintSeqNo)
        dataGetter.GetStr(52) 
		#abyPriceType價格型態 
        result += '價格型態:' + dataGetter.GetStr(1) + ',' 
		#abyStkErrCode證券回報錯誤碼
        result_ErrCode = dataGetter.GetStr(5)
        result +=  '證券回報錯誤碼:' + result_ErrCode
        result += '\r\n'
        
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#stk_order_real_reportMerge
#即時回報彙總 200.10.10.27 
def stk_order_real_reportMerge(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    
    try:
        result += '即時回報彙總:\r\n'
		#abyAccount帳號
        result += dataGetter.GetStr(22) + ',' 
		#bytRptFlag回報標記
        result += '回報標記:'+'{0}'.format(str(dataGetter.GetByte()))  + ',' 
		#abyOrderNo委託單號
        result += '委託單號:'+dataGetter.GetStr(20) + ','
        #byMarketNo市場代碼		
        result += '市場代碼:'+'{0}'.format(str(dataGetter.GetByte()))   + ',' 
		#abyCompanyNo商品代碼
        result += '商品代碼:'+dataGetter.GetStr(20) + ',' 
        #struOrderDate交易日期		
        yuantaDate = dataGetter.GetTYuantaDate() 
        result += '交易日期:'+'{0}/{1}/{2}'.format(yuantaDate.ushtYear, yuantaDate.bytMon, yuantaDate.bytDay) + ','
		#struOrderTime交易時間
        yuantaTime = dataGetter.GetTYuantaTime() 
        result += '交易時間:'+'{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ','
		#abyOrderType委託種類 0:現貨
        result += '委託種類:'+ dataGetter.GetStr(3) + ',' 
		#abyBS買賣別
        result += '買賣別:'+ dataGetter.GetStr(1)  + ',' 
		#abyOrderPrice委託價
        result +=  '委託價:'+ dataGetter.GetStr(14) + ',' 
		#abyTouchPrice停損執行價
        result +=  '停損執行價:'+ dataGetter.GetStr(14) + ',' 
		#abyLastDealPrice最後成交價
        result +=  '最後成交價:'+ dataGetter.GetStr(14) + ',' 
        #abyAvgDealPrice平均成交價
        result +=  '平均成交價:'+ dataGetter.GetStr(14) + ',' 
        #intBeforeQty改量前數量
        result += '改量前數量:'+'{0}'.format(str(dataGetter.GetInt()))   + ',' 
        #intOrderQty委託股數
        result += '委託股數:'+'{0}'.format(str(dataGetter.GetInt()))   + ',' 
        #intOkQty成交股數
        result += '成交股數:'+'{0}'.format(str(dataGetter.GetInt()))   + ',' 
		#abyOpenOffsetKind新增/沖銷別
        result +=  '新增/沖銷別:'+ dataGetter.GetStr(1) + ',' 
		#abyDayTrade當沖記號 '' or X:現股當沖註記 
        result +=  '當沖記號:'+ dataGetter.GetStr(1) + ',' 
		#abyOrderCond委託條件 
        result +=  '委託條件:'+ dataGetter.GetStr(1) + ',' 
		#abyOrderErrorNo錯誤碼
        result +=  '錯誤碼:'+ dataGetter.GetStr(4) + ','  
		#byAPCode委託類別 0:現股,2:零股,4:盤中零股,7:盤後,99:興櫃
        result += '委託類別:'+'{0}'.format(str(dataGetter.GetByte()))   + ',' 
		#shtOrderStatus狀態碼
        result += '狀態碼:'+'{0}'.format(str(dataGetter.GetShort()))   + ','
        #byLastOrderStatus最新一筆即回資料狀態
        result += '資料狀態:'+'{0}'.format(str(dataGetter.GetByte()))   + ',' 
        #abyCompanyName股票名稱
        result += '股票名稱:'+ dataGetter.GetStr(20) + ','  
        #abyTradeCode實體交易代碼
        result += '實體交易代碼:'+ dataGetter.GetStr(20) + ','  
        #dwStrikePrice履約價
        result += '履約價:'+'{0}'.format(str(dataGetter.GetUInt()))   + ','
        #abyBasketNo32一籃子下單編號
        result +=  '一籃子下單編號:'+ dataGetter.GetStr(32) + ','  
        #byStkType1屬性1
        result += '屬性1:'+'{0}'.format(str(dataGetter.GetByte()))   + ',' 
        #byStkType2屬性2
        result += '屬性2:'+'{0}'.format(str(dataGetter.GetByte()))   + ',' 
        #byBelongMarketNo所屬市場代碼
        result += '所屬市場代碼:'+'{0}'.format(str(dataGetter.GetByte()))   + ',' 
        #abyBelongStkCode所屬股票代碼
        result += '所屬股票代碼:'+ dataGetter.GetStr(12) + ','  
		#PriceType價格型態 
        result += '價格型態:'+ dataGetter.GetStr(1) + ',' 
		#abyStkErrCode證券回報錯誤碼
        result +=  '證券回報錯誤碼'+ dataGetter.GetStr(5) 
        result += '\r\n'
        
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

# WatchlistAll_response - 已按 readme.md 實現字典格式保存和異步 CSV 寫入
# 每 5 秒完整保存一筆資料：時間、成交股數、成交金額、開盤價、最高價、最低價、收盤價、漲跌價差、成交筆數
#WatchlistAll_response
#訂閱報價表 98.10.70.10
def SubscribeWatclistAll_Out(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    result += 'WatchlistALL報價表訂閱結果:\r\n';
    byTemp=''    
    
    try:
        abyKey = dataGetter.GetStr(22)
        market_no = dataGetter.GetByte()
        stock_id = dataGetter.GetStr(12)
        seq_no = dataGetter.GetLong()
        byTemp = str(dataGetter.GetByte())
        state = get_quote_state(stock_id, market_no)
        state.byIndexFlag = byTemp

        if byTemp == '22':
            buy_vol = dataGetter.GetInt()
            sell_vol = dataGetter.GetInt()
            state.buy_volumes = [buy_vol]
            state.sell_volumes = [sell_vol]
            state.last_update = time.time()
            state.latest_timestamp = state.last_update
            result += f"WatchlistAll {stock_id} 22: buy_vol={buy_vol}, sell_vol={sell_vol}\r\n"
        elif byTemp == '28':
            buy_price = dataGetter.GetInt()
            sell_price = dataGetter.GetInt()
            state.buy_prices = [buy_price]
            state.sell_prices = [sell_price]
            state.last_update = time.time()
            state.latest_timestamp = state.last_update
            result += f"WatchlistAll {stock_id} 28: buy_price={buy_price}, sell_price={sell_price}\r\n"
        elif byTemp == '29':
            yuantaTime = dataGetter.GetTYuantaTime()
            timestamp = dt.now().replace(
                hour=yuantaTime.bytHour,
                minute=yuantaTime.bytMin,
                second=yuantaTime.bytSec,
                microsecond=yuantaTime.ushtMSec * 1000
            ).timestamp()
            total_out = dataGetter.GetInt()
            total_in = dataGetter.GetInt()
            deal_price = dataGetter.GetInt()
            deal_vol = dataGetter.GetInt()
            total_vol = dataGetter.GetInt()
            total_amt = dataGetter.GetInt()
            state.update_watchlist_all(byTemp, timestamp=timestamp, total_out=total_out, total_in=total_in, deal_price=deal_price, deal_volume=deal_vol)
            result += f"WatchlistAll {stock_id} 29: out={total_out}, in={total_in}, deal={deal_price}@{deal_vol}, total_vol={total_vol}, total_amt={total_amt}\r\n"
        else:
            result += f"WatchlistAll {stock_id} unknown index {byTemp}\r\n"
    except Exception as error:
        result = error
    #time.sleep(3)
    display_data = state.to_display_dict() if 'state' in locals() else {}
    if display_data:
        print(f"\nWatchlistAll {stock_id} 解析結果: {display_data}")
    return display_data


dtsFiveTickOrder ={
    'abyKey':1, 
    'byMarketNo':50,       
    'stock_id':2317,
    'FiveTickOrder': [2265000,2260000,2255000,2250000,2245000,347,214,108,103,324,2270000,2275000,2280000,2285000,2290000,302,240,632,340,564],
    'ticket': time.time() #当前时间戳time.asctime(time.localtime(ticket)), time.strftime("%Y%m%d %H:%M:%S", time.localtime())
    }
#讀取key已知key的values like dts.get(key)
#print(dtsFiveTickOrde)

#FiveTick_response - 已按 readme.md 實現統一字典格式保存
#訂閱五檔報價 210.10.60.10
def SubscribeFiveTick_out(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    try:
        #abyKey訂閱識別碼
        abyKey = dataGetter.GetStr(22)
        #byMarketNo市場代碼
        market_no = dataGetter.GetByte()
        stock_id = dataGetter.GetStr(12)
        
        byIndexFlag = str(dataGetter.GetByte())
        state = get_quote_state(stock_id, market_no)
        state.byIndexFlag = byIndexFlag

        buy_prices = []
        buy_volumes = []
        sell_prices = []
        sell_volumes = []

        if byIndexFlag in ('50', '51'):
            for _ in range(5):
                buy_prices.append(dataGetter.GetInt())
            for _ in range(5):
                buy_volumes.append(dataGetter.GetInt())
            for _ in range(5):
                sell_prices.append(dataGetter.GetInt())
            for _ in range(5):
                sell_volumes.append(dataGetter.GetInt())

            state.update_five_tick(byIndexFlag, buy_prices, buy_volumes, sell_prices, sell_volumes)
        else:
            # 未知的五檔索引，仍保存基本欄位
            state.last_update = time.time()
            state.latest_timestamp = state.last_update

        raw_length = len(abyData) if hasattr(abyData, '__len__') else None
        print(f"[{dt.datetime.now()}] SubscribeFiveTick_out stock_id={stock_id} raw_len={raw_length} byIndexFlag={byIndexFlag} buy_prices={buy_prices} buy_volumes={buy_volumes} sell_prices={sell_prices} sell_volumes={sell_volumes}")
        display_data = state.to_display_dict()
        if display_data:
            print(f"\nFiveTick {stock_id} 解析結果: {display_data}")
        else:
            print(f"[{dt.datetime.now()}] SubscribeFiveTick_out {stock_id} 無有效 display_data")
        return display_data

    except Exception as error:
        print(f'SubscribeFiveTick_out error: {error}')
        return {}

#Watchlist_response
#訂閱報價表指定欄位 210.10.70.11
def SubscribeWatchlist_Out(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    result += 'WatchList指定欄位訂閱結果:\r\n'
    
    try:
        dataGetter.GetStr(22)
        market_no = dataGetter.GetByte()
        stock_id = dataGetter.GetStr(12)
        byIndexFlag = '{0}'.format(dataGetter.GetByte())
        int_value = dataGetter.GetInt()

        state = get_quote_state(stock_id, market_no)
        state.update_watchlist_field(byIndexFlag, int_value)

        display_data = state.to_display_dict()
        if display_data:
            print(f"\nWatchList {stock_id} 指定欄位訂閱結果: {display_data}")
        return display_data
    except Exception as error:
        print(f'SubscribeWatchlist_Out error: {error}')
        return {}

#StockTick_response
#訂閱個股分時明細結果 210.10.40.10
def SubscribeStocktick_out(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    result += '分時明細訂閱結果:\r\n'    
    
    try:
            raw_length = len(abyData) if hasattr(abyData, '__len__') else None
            dataGetter.GetStr(22)
            market_no = dataGetter.GetByte()
            stock_id = dataGetter.GetStr(12)
            seq_no = dataGetter.GetInt()
            yuantaTime = dataGetter.GetTYuantaTime()
            deal_time = dt.datetime.now().replace(
                hour=yuantaTime.bytHour,
                minute=yuantaTime.bytMin,
                second=yuantaTime.bytSec,
                microsecond=yuantaTime.ushtMSec * 1000
            ).timestamp()
            buy_price = dataGetter.GetInt()
            sell_price = dataGetter.GetInt()
            deal_price = dataGetter.GetInt()
            deal_volume = dataGetter.GetInt()
            in_out_flag = str(dataGetter.GetByte())
            detail_type = str(dataGetter.GetByte())
            state = get_quote_state(stock_id, market_no)
            state.update_stocktick(deal_price=deal_price, deal_volume=deal_volume, in_out_flag=in_out_flag, timestamp=deal_time)
            result += f"StockTick {stock_id}: raw_len={raw_length} deal={deal_price}@{deal_volume}, in_out={in_out_flag}, type={detail_type}\r\n"
    except Exception as error:
        result = error
    display_data = state.to_display_dict() if 'state' in locals() else {}
    if display_data:
        print(f"\nStockTick {stock_id} 解析結果: {display_data}")
    return display_data
# 訂閱回應資訊統一字典格式 - 已按 readme.md 實現
# 所有 intMark == 2 訂閱回應現在統一更新到 SUBSCRIPTION_STATE['stocks']，
# 由 show() 異步顯示並每 5 秒寫入 CSV。
# OnResponse
def objApi_OnResponse(intMark, dwIndex, strIndex, objHandle, objValue):
    result = ''
	# 系統回應資訊
    if intMark == 0: 
        result = str(objValue)
	# 查詢(RQ/RP)回應資訊
    elif intMark == 1: 
	    #Login登入
        if strIndex == 'Login':
            result = login_out_response(objValue)
        #取得己訂閱報價商品列表    
        elif strIndex == 'GetQuoteList':
            result = GetQuoteList_Out(objValue)       
        #逐筆即時回報彙總
        elif strIndex == '10.0.0.16':  
            result = get_real_report_merge_response(objValue)
        #逐筆即時回報
        elif strIndex == '10.0.0.20': 
            result = get_real_report_response(objValue)            
		#Order現貨下單	
        elif strIndex == '30.100.10.31':
            result = stk_order_out_response(objValue)
        #futureorder期貨下單
        elif strIndex == '30.100.20.24': 
            result = future_order_out_response(objValue)
        #OVFutureorder國際期貨下單
        elif strIndex == '30.100.40.12':
            result = OVFuture_order_out_response(objValue)
        #OrderTradeReport委託成交綜合回報	
        elif strIndex == '20.101.0.18':
            result = stk_OrderTradeReport(objValue)
		#SummaryReport現貨庫存綜合總表	
        elif strIndex == '20.103.0.22':
            result = stk_SummaryReport(objValue)
		#FutStoreSummaryReport期貨庫存總表	
        elif strIndex == '20.103.20.13':
            result = fut_SummaryReport(objValue)
		#OVFutStoreSummaryReport國際期貨庫存總表	
        elif strIndex == '20.103.40.18':
            result = OVfut_SummaryReport(objValue)            
        #ReadWatchListAll讀取報價表
        elif strIndex == '50.0.0.16':
            result = ReadWatchListAll_Out(objValue)
        #FutInterestStore期貨簡易權益數庫存查詢
        elif strIndex == '20.104.20.20':
            result = FutInterestStoreReport(objValue)
        #FutDepositOptimum期貨保證金最佳化查詢
        elif strIndex == '20.104.20.17':
            result = FutDepositOptimumReport(objValue)
        #OrderFutCombined期貨複式單組合
        elif strIndex == '30.100.20.14':
            result = FutCombined_order_out_response(objValue)
        else:
            if (strIndex == ''):
                result = str(objValue)
            else:
                result ='{0},{1}'.Format(strIndex, objValue)
	# 訂閱回應資訊		
    elif intMark == 2:
        print(f"[{dt.datetime.now()}] OnResponse intMark=2 strIndex={strIndex}")
        SUBSCRIPTION_STATE['event_counts'][strIndex] = SUBSCRIPTION_STATE['event_counts'].get(strIndex, 0) + 1
        #RealReport即時回報資料
        if strIndex == '200.10.10.26': 	
            result = stk_order_real_report(objValue)
        #RealReportMerge逐筆即時回報彙總    
        elif strIndex == '200.10.10.27': 	
            result = stk_order_real_reportMerge(objValue)
        #Watchlist報價表(指定欄位)        
        elif strIndex == '210.10.70.11':  
            result = SubscribeWatchlist_Out(objValue) 
        #WatchlistAll報價表
        elif strIndex == '98.10.70.10':  
            result = SubscribeWatclistAll_Out(objValue) 
        #StockTick分時明細        
        elif strIndex == '210.10.40.10':  
            result = SubscribeStocktick_out(objValue) 
        #FiveTick五檔報價
        elif strIndex == '210.10.60.10':  
            result = SubscribeFiveTick_out(objValue) 
        else:
            if (strIndex == ''):
                result = str(objValue)
            else:
                print(f"[{dt.datetime.now()}] 未知訂閱回應 strIndex={strIndex} objValue={objValue}")
                result = '{0},{1}'.format(strIndex, objValue)
    if result:
        print('##================================================##\n')
        print(result,'\n')
    elif intMark == 2:
        print(f"[{dt.datetime.now()}] intMark=2 回應沒有 result，strIndex={strIndex}")

# Open		
def open_api(yuanta):
    yuanta.Open(enumEnvironmentMode.UAT)
    time.sleep(3)

# Login
def login_api(yuanta):
    #現貨
    yuanta.Login('S98875005091', '1234')
    #期貨
    #yuanta.Login('FF021005P051234567', '1234')
    time.sleep(3)

# LogOut
def LogOut_api(yuanta): 
    yuanta.LogOut()

#close
def Close_api(yuanta):
    #LogOut(yuanta)
    LogOut_api(yuanta)
    objYuantaOneAPI.Close()
    objYuantaOneAPI.Dispose()


def cleanup_and_logout():
    """Gracefully logout and close YuantaOneAPI on shutdown."""
    if 'objYuantaOneAPI' not in globals():
        return

    try:
        print(f"[{dt.datetime.now()}] 執行登出清理...")
        if SUBSCRIPTION_STATE.get('login_status', False):
            LogOut_api(objYuantaOneAPI)
            SUBSCRIPTION_STATE['login_status'] = False
        objYuantaOneAPI.Close()
        objYuantaOneAPI.Dispose()
        print(f"[{dt.datetime.now()}] 已完成登出及關閉 YuantaOneAPI")
    except Exception as e:
        print(f"[{dt.datetime.now()}] 登出清理失敗: {e}")


def _handle_exit_signal(signum, frame):
    print(f"[{dt.datetime.now()}] 接收到結束信號 {signum}，準備登出...")
    cleanup_and_logout()
    raise KeyboardInterrupt


def register_exit_signal_handlers():
    signal.signal(signal.SIGINT, _handle_exit_signal)
    try:
        signal.signal(signal.SIGTERM, _handle_exit_signal)
    except AttributeError:
        # Windows may not support SIGTERM in all environments
        pass

#即時回報(回補) 
#GetRealport 10.0.0.20
def GetRealReport(yuanta):
        dataSetter = YuantaDataHelper(enumLangType.NORMAL)
        dataSetter.SetFunctionID(10, 0, 0, 20)
        dataSetter.SetUInt(1)
        dataSetter.SetTByte('S98875005091',22)
        yuanta.RQ('S98875005091', dataSetter)

#即時回報彙總(回補)
#GetRealReportMerge 10.0.0.16
def GetRealReportMerge(yuanta):
    dataSetter = YuantaDataHelper(enumLangType.NORMAL)
    dataSetter.SetFunctionID(10, 0, 0, 16)
    dataSetter.SetByte(0)
    dataSetter.SetByte(0)
    dataSetter.SetTByte(' ',20)
    dataSetter.SetUInt(1)
    dataSetter.SetTByte('S98875005091',22)
    yuanta.RQ('S98875005091', dataSetter)

#取得己訂閱報價商品
#GetQuoteList
def GetQuoteList_api(yuanta):
    yuanta.GetQuoteList()

#現貨下單
#SendStockOrder 30.100.10.31     
def send_stock_order(yuanta):
    stockorder = StockOrder()
    
	#Identify識別碼
    stockorder.Identify = int('00001') 
	#Account現貨帳號
    stockorder.Account = 'S98875005091'
	#APCode市場交易別 0:一般 2:盤後零股 4:盤中零股 7:盤後
    stockorder.APCode = int('0') 
	#TradeKind交易性質 00:委託單 03:改量 04:取消 07:改價
    stockorder.TradeKind = int('0')
	#OrderType委託種類 0:現貨 3:融資 4:融券 5策略借券(賣出) 6:避險借券(賣出) 9:現股當沖
    stockorder.OrderType = '0' 
	#StkCode股票代號
    stockorder.StkCode = '2885'
	#PriceFlag價格種類 H:漲停 -:平盤  L:跌停 ' ':限價  M:市價單    
    stockorder.PriceFlag = ''
	#Price委託價格 X 10000
    stockorder.Price = int(35.55*10000) 
	#OrderQty委託單位數
    stockorder.OrderQty = int('1')
	#BuySell買賣別 B:買  S:賣
    stockorder.BuySell = 'B' 
	#SellerNo營業員代碼
    stockorder.SellerNo = int('0') 
	#OrderNo委託書編號 (刪改單用)
    stockorder.OrderNo = ''
	#TradeDate交易日期 yyyy/MM/dd
    stockorder.TradeDate = dt.datetime.now().strftime('%Y/%m/%d') 
	#BasketNo自訂欄位 (英數字 長度 32 byte)
    stockorder.BasketNo = '' 
	#Time_in_force委託效期 0:ROD (預設) 3:IOC  4:FOK
    stockorder.Time_in_force = '0'
	
    lstStockOrder = List[StockOrder]()
    lstStockOrder.Add(stockorder)

	#傳送下單
    yuanta.SendStockOrder('S98875005091', lstStockOrder)
	#測試環境傳送後要休息一下
    time.sleep(2)

#期貨下單
#SendFutureOrder 30.100.20.24   
def send_future_order(yuanta):
    futureOrder = FutureOrder()
    
	#Identify識別碼
    futureOrder.Identify = int('1') 
	#Account下單帳號
    futureOrder.Account = 'FF021005P051234567'
	#FunctionCode功能別
    futureOrder.FunctionCode = int('0') 
	#CommodityID1商品名稱1
    futureOrder.CommodityID1 = 'FIZF'    
    #CallPut1買賣權1
    futureOrder.CallPut1 = ''
    #SettlementMonth1商品月份1
    futureOrder.SettlementMonth1 = int('202409')
    #StrikePrice1履約價1
    futureOrder.StrikePrice1 = 0
    #Price委託價格 X 10000
    futureOrder.Price = 1600*10000
    #OrderQty1委託口數1
    futureOrder.OrderQty1 = 1
    #BuySell1買賣別1
    futureOrder.BuySell1 = 'B'
    #CommodityID2商品名稱2
    futureOrder.CommodityID2 = ''
    #CallPut2買賣權2
    futureOrder.CallPut2 = ''
    #SettlementMonth2商品月份2
    futureOrder.SettlementMonth2 = 0
    #StrikePrice2履約價2
    futureOrder.StrikePrice2 = 0
    #OrderQty2委託口數2
    futureOrder.OrderQty2 = 0
    #BuySell2買賣別2
    futureOrder.BuySell2 = ''
    #OpenOffsetKind新平倉
    futureOrder.OpenOffsetKind = '2'
    #DayTradeID當沖註記
    futureOrder.DayTradeID = ' '
    #OrderType委託方式
    futureOrder.OrderType = '2'
    #OrderCond委託條件
    futureOrder.OrderCond = ' '
    #SellerNo營業員代碼
    futureOrder.SellerNo = 0
    #OrderNo委託書編號
    futureOrder.OrderNo=''
    #TradeDate交易日期
    futureOrder.TradeDate = dt.today().strftime('%Y/%m/%d') 
    #BasketNo(目前無作用)
    futureOrder.BasketNo = ''
    #Session盤別
    futureOrder.Session = ' '
	
    lstFutureOrder = List[FutureOrder]()
    lstFutureOrder.Add(futureOrder)

	#傳送下單
    yuanta.SendFutureOrder('FF021005P051234567', lstFutureOrder)
	#測試環境傳送後要休息一下
    time.sleep(2)

#海外期貨下單 
#SendOVFutureOrder 30.100.40.12
def send_OvFuture_order(yuanta):
        ovFutOrder = OVFutureOrder()
        
        # Identify識別碼
        ovFutOrder.Identify = int('1') 
        # Account下單帳號
        ovFutOrder.Account = 'FF021005P051234567'
        # FunctionCode功能別
        ovFutOrder.FunctionCode = int('0') 
        # ExhCode交易所簡碼
        ovFutOrder.ExhCode = 'CME'
        # MarketNo市場代碼
        ovFutOrder.MarketNo = int('203') 
        # CommodityID商品代碼
        ovFutOrder.CommodityID = 'JY'
        # SettlementMonth商品年月
        ovFutOrder.SettlementMonth = int('202412')
        # StrikePrice屐約價格 X 10000
        ovFutOrder.StrikePrice = 0
        # UtPrice委託價格整數位 X 10000 (市價或市價停損單填 0)
        ovFutOrder.UtPrice = 6970*10000
        # BuySell買賣別 'B':買 'S':賣
        ovFutOrder.BuySell = 'B'
        # UtPrice2委託價格分子 X 10000
        ovFutOrder.UtPrice2 = 0
        # MinPrice2委託價格分母
        ovFutOrder.MinPrice2 = 1
        # UtPrice4停損執行價整數位 X 10000 (非停損單填0)
        ovFutOrder.UtPrice4 = 0
        # UtPrice5停損執行價格分子 X 10000 (非停損單填0)
        ovFutOrder.UtPrice5 = 0
        # UtPrice6停損執行價格分母 (非停損單填1)
        ovFutOrder.UtPrice6 = 1
        # OrderQty委託口數
        ovFutOrder.OrderQty = 1
        # Dtover是否當沖 Y/N
        ovFutOrder.Dtover = 'N'
        # OrderType委託種類 LMT:限價單, MKT:市價單,STP:停損單, SWL:停損限價單
        ovFutOrder.OrderType = 'LMT'
        # OrderNo委託書編號 
        ovFutOrder.OrderNo = ''
        # TradeDate交易日期 
        ovFutOrder.TradeDate = dt.today().strftime('%Y/%m/%d') 

        lstOVFutureOrder = List[OVFutureOrder]()
        lstOVFutureOrder.Add(ovFutOrder)

        #傳送下單
        yuanta.SendOVFutureOrder('FF021005P051234567', lstOVFutureOrder)
        #測試環境傳送後要休息一下
        time.sleep(2)

#訂閱報價    
#WatchlistAll 98.10.70.10
def SubscribeWatchlistAll_api(yuanta):
    lstWatchlistAll = List[WatchlistAll]()   
    for code in ['2330', '2317', '2344']:
        watch = WatchlistAll()
        watch.MarketNo = 1
        watch.StockCode = code
        lstWatchlistAll.Add(watch)
    yuanta.SubscribeWatchlistAll(lstWatchlistAll) 
    
#取消訂閱報價
#UnsubWatchlistAll 98.10.70.10
def UnsubWatchlistAll_api(yuanta):
    lstWatchlistAll = List[WatchlistAll]()
    for code in ['2330', '2317', '2344']:
        watch = WatchlistAll()
        watch.MarketNo = 1  #個股
        watch.StockCode = code
        lstWatchlistAll.Add(watch)
    yuanta.UnsubscribeWatchlistAll(lstWatchlistAll)    

'''
市場別
public enum enumMarketType : byte
    {
        TWSE = 1, 台灣期貨交易所,上市股,含上市權證,市基金,水泥類(各類)報酬指數,市電子
        TWOTC = 2, 上櫃,含上櫃權證
        TAIFEX = 3, 台指選,微台,小電子,電指,金指,台指期,個股期,個股選
        TWEMERGING = 4, 興櫃
        TWSEODD = 5,  台灣證券交易所零股交易,上市治理評鑑,元大台灣50,0051,etf,2317倆者1/5
        TWOTCODD = 6    上櫃,含上櫃權證零股交易
        SGX = 202,
        CME = 203,
        CBOT = 204,
        TCE = 205,
        OSE = 207,
        HKFE = 208,
        NYBOT = 209,
        LIFFE = 210,
        XEUREX = 211,
        ASX = 212,
        CBOE = 215
    }
'''
#訂閱五檔報價
#FiveTick 210.10.60.10     
def SubscribeFiveTick_api(yuanta):
    lstFiveTick = List[FiveTickA]()    
    fiveTickA = FiveTickA() 
    fiveTickA.MarketNo = 3           #期貨
    fiveTickA.StockCode = 'TXFPM1'   #台指PM近
    lstFiveTick.Add(fiveTickA)

    fiveTickA = FiveTickA()
    fiveTickA.MarketNo = 1           #個股
    fiveTickA.StockCode = '2330'     #個股商品代碼
    lstFiveTick.Add(fiveTickA)

    fiveTickA = FiveTickA()
    fiveTickA.MarketNo = 1           #個股
    fiveTickA.StockCode = '2317'     #個股商品代碼
    lstFiveTick.Add(fiveTickA)

    fiveTickA = FiveTickA()
    fiveTickA.MarketNo = 1           #個股
    fiveTickA.StockCode = '2344'     #個股商品代碼
    lstFiveTick.Add(fiveTickA)

    yuanta.SubscribeFiveTickA(lstFiveTick)

#取消訂閱五檔報價
#UnSubscribeFiveTick 210.10.60.10
def UnSubscribeFiveTick_api(yuanta):
    lstFiveTick = List[FiveTickA]()    
    fiveTickA = FiveTickA() 
    fiveTickA.MarketNo =3
    fiveTickA.StockCode ='TXFPM1'
    lstFiveTick.Add(fiveTickA)                    
    yuanta.UnsubscribeFivetickA(lstFiveTick)

#訂閱報價表指定欄位
#Watchlist 210.10.70.11
def SubscribeWatchlist_api(yuanta):
    lstWatchlist = List[Watchlist]()
    for code in ['2330', '2317', '2344']:
        watch = Watchlist()
        watch.IndexFlag = 7 #IndexFlag訂閱索引值
        watch.MarketNo = 1
        watch.StockCode = code
        lstWatchlist.Add(watch)
    yuanta.SubscribeWatchlist(lstWatchlist) 

#取消訂閱報價表指定欄位 
#UnSubscribeWatchlist 210.10.70.11
def UnSubscribeWatchlist_api(yuanta):
    lstWatchlist = List[Watchlist]()
    for code in ['2330', '2317', '2344']:
        watch = Watchlist()
        watch.IndexFlag = 7 #IndexFlag訂閱索引值
        watch.MarketNo = 1
        watch.StockCode = code
        lstWatchlist.Add(watch)
    yuanta.UnsubscribeWatchlist(lstWatchlist) 

#訂閱分時明細
#StockTick 210.10.40.10
def SubscribeStocktick_api(yuanta):
    lstStocktick = List[StockTick]()    
    for code in ['2330', '2317', '2344']:
        stocktick = StockTick()
        stocktick.MarketNo =  1
        stocktick.StockCode = code
        lstStocktick.Add(stocktick)
    yuanta.SubscribeStockTick(lstStocktick)

#取消訂閱分時明細 
#UnSubscribeStocktick210.10.40.10
def UnSubscribeStocktick_api(yuanta):
    lstStocktick = List[StockTick]()    
    for code in ['2330', '2317', '2344']:
        stocktick = StockTick()
        stocktick.MarketNo =  1
        stocktick.StockCode = code
        lstStocktick.Add(stocktick)
    yuanta.UnsubscribeStocktick(lstStocktick) 
    
#讀取報價
#ReadWatchListAll 50.0.0.16
def ReadWatchListAll_api(yuanta):
    dataSetter =  YuantaDataHelper(enumLangType.NORMAL)
    dataSetter.SetFunctionID(50, 0, 0, 16);
    dataSetter.SetUInt(1);
    dataSetter.SetByte(1)
    dataSetter.SetTByte('2330',12)
    yuanta.RQ('S98875005091',dataSetter) 

#查詢委託成交
# OrderTradeReport 20.101.0.18
def OrderTradeReport_api(yuanta):
    dataSetter = YuantaDataHelper(enumLangType.NORMAL)
    dataSetter.SetFunctionID(20, 101, 0, 18)
    dataSetter.SetTByte('Y',1) #Y不列取消單 Cancel not show
    dataSetter.SetUInt(1)
    dataSetter.SetTByte('S98875005091',22)
    yuanta.RQ('S98875005091',dataSetter)

#查詢現貨庫存
# SummaryReport 20.103.0.22
#未提供複委託交易故國外股票庫存皆回傳0
def SummaryReport_api(yuanta):
    dataSetter = YuantaDataHelper(enumLangType.NORMAL)
    dataSetter.SetFunctionID(20, 103,0,22)
    dataSetter.SetUInt(1)
    dataSetter.SetTByte('S98875005091',22)
    yuanta.RQ('S98875005091',dataSetter)

#查詢期貨庫存
# FutStoreSummaryReport 20.103.20.13
def FutStoreSummaryReport_api(yuanta):
    dataSetter = YuantaDataHelper(enumLangType.NORMAL)
    dataSetter.SetFunctionID(20, 103,20,13)
    dataSetter.SetUInt(1)
    dataSetter.SetTByte('FF021005P051234567',22)
    yuanta.RQ('FF021005P051234567',dataSetter)

#查詢國際期貨庫存
# OVFutStoreSummaryReport 20.103.40.18
def OVFutStoreSummaryReport_api(yuanta):
    dataSetter = YuantaDataHelper(enumLangType.NORMAL)
    dataSetter.SetFunctionID(20, 103,40,18)
    dataSetter.SetUInt(1)
    dataSetter.SetTByte('FF021005P051234567',22)
    yuanta.RQ('FF021005P051234567',dataSetter)

#查詢簡易權益數庫存
#FutInterestStore 20.104.20.20
def FutInterestStore_api(yuanta):
    dataSetter = YuantaDataHelper(enumLangType.NORMAL)
    dataSetter.SetFunctionID(20,104,20,20)
    dataSetter.SetTByte('FF021005P051234567',22)
    dataSetter.SetTByte('1',1)
    dataSetter.SetTByte('TWD',3)
    yuanta.RQ('FF021005P051234567',dataSetter)
    
#查詢保證金最佳化
def FutDepositOptimum_api(yuanta):
    yuanta.GetFutDepositOptimum('FF021005P051234567')

#期貨複式單組合
def SendFutureCombined_api(yuanta,depositOptimumLList):
    yuanta.SendFutureCombined('FF021005P051234567',depositOptimumLList)

##########################################################################
objYuantaOneAPI = YuantaOneAPITrader()
objYuantaOneAPI.OnResponse += OnResponseEventHandler(objApi_OnResponse)
objYuantaOneAPI.SetLogType(enumLogType.COMMON) 
DOLList = List[DepositOptimum]()
###########################################################################

open_api(objYuantaOneAPI)
login_api(objYuantaOneAPI)
#登入後需休息3秒，主機端會控制快速重複登入
time.sleep(3)

#登出
#LogOut_api(objYuantaOneAPI)

#關閉
#Close_api(objYuantaOneAPI)

#即時回報(回補)GetRealport
#GetRealReport(objYuantaOneAPI)

#即時回報彙總(回補)GetRealReportMerge
#GetRealReportMerge(objYuantaOneAPI)

#取得己訂閱報價商品GetQuoteList
#GetQuoteList_api(objYuantaOneAPI)

#現貨下單
send_stock_order(objYuantaOneAPI)

#期貨下單
#send_future_order(objYuantaOneAPI)

#海外期貨下單 
#send_OvFuture_order(objYuantaOneAPI)

#訂閱報價WatchlistAll
#SubscribeWatchlistAll_api(objYuantaOneAPI)

#訂閱五檔FiveTick
SubscribeFiveTick_api(objYuantaOneAPI)

#訂閱指定欄位Watchlist
SubscribeWatchlist_api(objYuantaOneAPI)

#訂閱報價表WatchlistAll
SubscribeWatchlistAll_api(objYuantaOneAPI)

#訂閱分時明細Stocktick
SubscribeStocktick_api(objYuantaOneAPI)

#讀取報價ReadWatchListAll
#ReadWatchListAll_api(objYuantaOneAPI)

#查詢委託成交OrderTradeReport
#OrderTradeReport_api(objYuantaOneAPI)

#查詢現貨庫存SummaryReport
#SummaryReport_api(objYuantaOneAPI)

#查詢期貨庫存FutStoreSummaryReport
#FutStoreSummaryReport_api(objYuantaOneAPI)

#查詢國際期貨庫存OVFutStoreSummaryReport
#OVFutStoreSummaryReport_api(objYuantaOneAPI)

#查詢簡易權益數庫存FutInterestStore
#FutInterestStore_api(objYuantaOneAPI)

#查詢期貨保證金最佳化FutDepositOptimum
#FutDepositOptimum_api(objYuantaOneAPI)
#time.sleep(3)

#期貨複式單組合SendFutureCombined
#SendFutureCombined_api(objYuantaOneAPI,DOLList)
############################################################################
    
'''
 已實現功能:
 * 所有訂閱回應統一使用字典格式保存
 * UI 每 1/60 秒更新一次顯示所有收到的信息
 * 每 5 秒完整保存一筆包含時間、成交股數、成交金額、開盤價等資料
 * 使用 asyncio 異步方法避免阻塞
 * 支持多檔股票管理和內外盤成交量分析
'''
def _market_phase() -> str:
    """判斷目前市場階段: 'pre_open'(09:00前), 'trading'(09:00-13:30),
    'matching'(13:30-14:30), 'closed'(14:30後)。"""
    now = dt.datetime.now()
    t = now.hour * 60 + now.minute
    if t < 9 * 60:
        return 'pre_open'
    if t < 13 * 60 + 30:
        return 'trading'
    if t < 14 * 60 + 30:
        return 'matching'
    return 'closed'


def _write_daily_summary(stock_id: str, state):
    """寫入每日總結 CSV (@stock_id.csv)，每個交易日一筆。"""
    filename = f"@{stock_id}.csv"
    record = state.build_save_record() if isinstance(state, StockQuoteState) else state
    if not record:
        return

    now = dt.datetime.now()
    file_exists = os.path.exists(filename)

    fieldnames = ["date", "stock_id", "open_price", "high_price", "low_price",
                  "close_price", "total_volume", "total_in_volume", "total_out_volume",
                  "estimated_day_volume", "trade_count"]
    try:
        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "date": f"{now.year}{now.month:02d}{now.day:02d}",
                "stock_id": stock_id,
                "open_price": record.get("open_price"),
                "high_price": record.get("high_price"),
                "low_price": record.get("low_price"),
                "close_price": record.get("close_price"),
                "total_volume": record.get("deal_volume") or 0,
                "total_in_volume": record.get("total_in_volume"),
                "total_out_volume": record.get("total_out_volume"),
                "estimated_day_volume": record.get("estimated_day_volume"),
                "trade_count": record.get("trade_count"),
            })
        # 同步更新到 yesterday/ 供隔日載入
        yesterday_dir = "yesterday"
        os.makedirs(yesterday_dir, exist_ok=True)
        yesterday_path = os.path.join(yesterday_dir, f"{stock_id}.csv")
        with open(yesterday_path, "w", newline="", encoding="utf-8") as yf:
            yf.write("日期,成交股數,成交金額,開盤價,最高價,最低價,收盤價,漲跌價差,成交筆數\n")
            yf.write(f"{now.strftime('%Y-%m-%d')},{record.get('deal_volume') or 0},{record.get('deal_amount') or 0},{record.get('open_price')},{record.get('high_price')},{record.get('low_price')},{record.get('close_price')},{record.get('price_diff') or 0},{record.get('trade_count')}\n")
        print(f"[{dt.datetime.now()}] 日總結寫入: {filename}, yesterday/{stock_id}.csv")
    except Exception as e:
        print(f"[{dt.datetime.now()}] 寫入日總結失敗 {stock_id}: {e}")


_daily_summary_written = set()


async def show(update_interval: float = 1/60, save_interval: float = 5, subscribe_interval: float = 5):
    """
    異步顯示訂閱回應資訊，含市場排程控制。
    09:00-13:25: 正常每 5 秒保存
    13:25-13:30: 最後一次 CSV 保存
    13:30-14:30: 盤後搓合，暫停 CSV 輸出
    14:30 後:   寫入日總結 @stock_id.csv 後停止
    """
    if not SUBSCRIPTION_STATE.get('login_status', False):
        print(f"[{dt.datetime.now()}] show() 登入狀態未確認，跳過執行")
        return []

    saved_records = []
    last_save_time = time.time()
    last_subscribe_time = time.time()
    global _daily_summary_written

    try:
        if 'objYuantaOneAPI' in globals():
            print(f"[{dt.datetime.now()}] show() 啟動時呼叫 SubscribeFiveTick_api()")
            SubscribeFiveTick_api(objYuantaOneAPI)
            last_subscribe_time = time.time()
        else:
            print(f"[{dt.datetime.now()}] show() 無法呼叫 SubscribeFiveTick_api(): objYuantaOneAPI 未初始化")

        while True:
            current_time = time.time()
            phase = _market_phase()

            # ---- 盤後搓合結束 → 寫日總結並停止 ----
            if phase == 'closed':
                for stock_id, state in SUBSCRIPTION_STATE['stocks'].items():
                    if stock_id not in _daily_summary_written:
                        _write_daily_summary(stock_id, state)
                        _daily_summary_written.add(stock_id)
                print(f"[{dt.datetime.now()}] 收盤完成，CSV 輸出停止")
                break

            subscribe_triggered = False
            if current_time - last_subscribe_time >= subscribe_interval and phase in ('trading', 'matching'):
                if 'objYuantaOneAPI' in globals():
                    SubscribeFiveTick_api(objYuantaOneAPI)
                    last_subscribe_time = current_time
                    subscribe_triggered = True
                    print(f"[{dt.datetime.now()}] 週期性重新呼叫 SubscribeFiveTick_api()")
                else:
                    print(f"[{dt.datetime.now()}] 無法重新訂閱，objYuantaOneAPI 未初始化")

            # ---- 交易時段才保存 CSV (13:30 前) ----
            if not subscribe_triggered and current_time - last_save_time >= save_interval:
                print(f"[{dt.datetime.now()}] 開始保存數據... (phase={phase})")
                saved_count = 0
                for stock_id, state in SUBSCRIPTION_STATE['stocks'].items():
                    record = state.build_save_record() if isinstance(state, StockQuoteState) else state
                    if not record or not record.get('stock_id'):
                        continue
                    if state.last_saved_timestamp == state.latest_timestamp and phase == 'trading':
                        continue
                    if not state.has_trade_activity():
                        continue
                    now = dt.datetime.now()
                    record['timestamp'] = f"{now.year}{now.month:02d}{now.day:02d} {now.hour:02d}:{now.minute:02d}:{now.second:02d}"
                    saved_records.append(record)
                    await _save_to_csv_async(stock_id, record)
                    saved_count += 1
                    state.last_saved_timestamp = state.latest_timestamp
                if saved_count > 0:
                    print(f"[{dt.datetime.now()}] 已保存 {saved_count} 筆數據記錄 (phase={phase})")
                else:
                    print(f"[{dt.datetime.now()}] 沒有數據可保存 (phase={phase})")
                print(f"[{dt.datetime.now()}] subscription event counts: {SUBSCRIPTION_STATE['event_counts']}")
                last_save_time = current_time

            # 每 1/60 秒顯示所有已訂閱股票的最新信息
            for state in SUBSCRIPTION_STATE['stocks'].values():
                _display_quote_info(state)

            await asyncio.sleep(update_interval)

    except KeyboardInterrupt:
        print("\n訂閱監控已停止")
    except Exception as e:
        print(f"show 方法出現錯誤: {e}")

    return saved_records


async def _save_to_csv_async(stock_id, record):
    """
    異步保存數據到 CSV 文件
    
    Args:
        stock_id: 股票代碼
        record: 要保存的記錄
    """
    try:
        filename = f"{stock_id}.csv"
        
        file_exists = os.path.exists(filename)
        
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            fieldnames = [
                'timestamp', 'stock_id', 'deal_volume', 'deal_amount', 'open_price', 'high_price', 'low_price',
                'close_price', 'price_diff', 'trade_count', 'estimated_day_volume', 'pct_of_yesterday_avg',
                'total_in_volume', 'total_out_volume', 'buy_total_volume', 'sell_total_volume', 'buy_sell_imbalance',
                'buy_sell_pressure', 'buy_prices', 'buy_volumes', 'sell_prices', 'sell_volumes',
                'ma5', 'ma10', 'price_momentum', 'byIndexFlag', 'extra_data'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            row = {
                'timestamp': record.get('timestamp'),
                'stock_id': record.get('stock_id'),
                'deal_volume': record.get('deal_volume'),
                'deal_amount': record.get('deal_amount'),
                'open_price': record.get('open_price'),
                'high_price': record.get('high_price'),
                'low_price': record.get('low_price'),
                'close_price': record.get('close_price'),
                'price_diff': record.get('price_diff'),
                'trade_count': record.get('trade_count'),
                'estimated_day_volume': record.get('estimated_day_volume'),
                'pct_of_yesterday_avg': record.get('pct_of_yesterday_avg'),
                'total_in_volume': record.get('total_in_volume'),
                'total_out_volume': record.get('total_out_volume'),
                'buy_total_volume': record.get('buy_total_volume'),
                'sell_total_volume': record.get('sell_total_volume'),
                'buy_sell_imbalance': record.get('buy_sell_imbalance'),
                'buy_sell_pressure': record.get('buy_sell_pressure'),
                'buy_prices': str(record.get('buy_prices', [])),
                'buy_volumes': str(record.get('buy_volumes', [])),
                'sell_prices': str(record.get('sell_prices', [])),
                'sell_volumes': str(record.get('sell_volumes', [])),
                'ma5': record.get('ma5'),
                'ma10': record.get('ma10'),
                'price_momentum': record.get('price_momentum'),
                'byIndexFlag': record.get('byIndexFlag'),
                'extra_data': str(record.get('extra_data', {}))
            }
            writer.writerow(row)
            print(f"已保存 {stock_id} 的報價數據到 {filename}")
            
    except Exception as e:
        print(f"保存 CSV 文件出現錯誤: {e}")


def _display_quote_info(state):
    """
    顯示訂閱的報價信息
    
    Args:
        state: StockQuoteState 或包含報價信息的字典
    """
    try:
        if isinstance(state, StockQuoteState):
            record = state.build_save_record()
        else:
            record = state

        if not record:
            return

        stock_id = record.get('stock_id', 'N/A')
        byIndexFlag = record.get('byIndexFlag', 'N/A')
        buy_prices = record.get('buy_prices', [])
        buy_volumes = record.get('buy_volumes', [])
        sell_prices = record.get('sell_prices', [])
        sell_volumes = record.get('sell_volumes', [])
        extra_data = record.get('extra_data', {})

        print(f"\n===== {stock_id} 報價 (索引: {byIndexFlag}) =====")
        close_price = record.get('close_price')
        deal_volume = record.get('deal_volume')
        deal_amount = record.get('deal_amount')
        open_price = record.get('open_price')
        high_price = record.get('high_price')
        low_price = record.get('low_price')
        price_diff = record.get('price_diff')
        trade_count = record.get('trade_count')
        total_in_volume = record.get('total_in_volume')
        total_out_volume = record.get('total_out_volume')
        estimated_day_volume = record.get('estimated_day_volume')
        pct_of_yesterday_avg = record.get('pct_of_yesterday_avg')

        print(f"最新成交: {close_price if close_price is not None else 'N/A'} 量: {deal_volume if deal_volume is not None else 'N/A'} 成交額: {deal_amount if deal_amount is not None else 'N/A'}")
        print(f"開: {open_price if open_price is not None else 'N/A'}  高: {high_price if high_price is not None else 'N/A'}  低: {low_price if low_price is not None else 'N/A'}  收: {close_price if close_price is not None else 'N/A'}  漲跌: {price_diff if price_diff is not None else 'N/A'}")
        print(f"成交筆數: {trade_count} 內盤: {total_in_volume} 外盤: {total_out_volume} 估日量: {estimated_day_volume if estimated_day_volume is not None else 'N/A'} 昨日均量%: {pct_of_yesterday_avg if pct_of_yesterday_avg is not None else 'N/A'}")

        if extra_data:
            print(f"额外訂閱欄位: {extra_data}")

        if record.get('ma5') is not None or record.get('ma10') is not None:
            print(f"MA5: {record.get('ma5')}  MA10: {record.get('ma10')}  動量: {record.get('price_momentum')}")

        if record.get('buy_total_volume') is not None or record.get('sell_total_volume') is not None:
            print(f"買總量: {record.get('buy_total_volume')} 賣總量: {record.get('sell_total_volume')} 盤差: {record.get('buy_sell_imbalance')} 盤壓: {record.get('buy_sell_pressure')}%")

        if buy_volumes and sell_volumes:
            total_buy = sum(buy_volumes)
            total_sell = sum(sell_volumes)
            print(f"買盤累計量: {total_buy}, 賣盤累計量: {total_sell}")
            if total_buy + total_sell > 0:
                buy_ratio = total_buy / (total_buy + total_sell) * 100
                sell_ratio = total_sell / (total_buy + total_sell) * 100
                print(f"買盤佔比: {buy_ratio:.2f}%, 賣盤佔比: {sell_ratio:.2f}%")
            print(f"\n===== {stock_id} 五檔報價 (索引: {byIndexFlag}) =====")
            for i in range(min(5, len(buy_prices), len(buy_volumes), len(sell_prices), len(sell_volumes))):
                print(f"買 {i+1}: {buy_prices[i]:>8} x {buy_volumes[i]:>6} | 賣 {i+1}: {sell_prices[i]:>8} x {sell_volumes[i]:>6}")
    
    except Exception as e:
        print(f"顯示報價信息出現錯誤: {e}")


# 程式最後執行 show，並保存返回的數據記錄
register_exit_signal_handlers()
print(f"[{dt.datetime.now()}] 即將呼叫 asyncio.run(show())")
try:
    saved_data = asyncio.run(show())  # 等待回應並顯示 UI，返回保存的數據記錄
    print(f"[{dt.datetime.now()}] asyncio.run(show()) 已結束")
except KeyboardInterrupt:
    print(f"[{dt.datetime.now()}] 收到 Ctrl+C，已觸發登出流程")
    saved_data = []
except Exception as e:
    print(f"[{dt.datetime.now()}] 執行 show() 時發生錯誤: {e}")
    saved_data = []
finally:
    cleanup_and_logout()

# 處理保存的數據（如果需要）
if saved_data:
    print(f"總共保存了 {len(saved_data)} 筆數據記錄")
    # 可以在這裡添加進一步的數據處理邏輯
