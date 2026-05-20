###程式名稱:YuantaAPI_IronPython.py
###程式用途說明:本程式為使用YuantaOneAPI.dll的範例程式
###程式使用版本:IronPython 3.4
###特別說明:透過IronPython 引用YuantaOneAPI.dll
###範例程式更新日期:2025.02.27
# os sys clr 將 DLL 所在目錄加入 Python 工作目錄
import os
import sys
import clr
import time
import datetime

import struct
import pathlib



##透過Clr引用系統標準函式 ,path加入C:\Windows\Microsoft.NET\Framework64\v4.0.30319
clr.AddReference('System.Collections')
##宣告增加DLL的引用路徑 取得當前路徑 Path = os.getcwd() 或 Path = pathlib.Path.cwd()
#sys.path.append(Path)
#strPath = str(Path)+str('\\YuantaOneAPI.dll')

## sys.path.append(Path(pathlib.Path(__file__).parent.resolve()).parent.absolute()) #NameError: name '__file__' is not defined. Did you mean: '__name__'?

#namespace 的 class
from datetime import datetime
from pathlib import Path
dll_dir = pathlib.Path.cwd() #取得當前路徑dll的引用路徑

# 將 DLL 所在目錄加入 Python 工作目錄 dll_dir = 'your_dll_directory'
if dll_dir not in sys.path:
    sys.path.append(dll_dir)

#透過Clr引用YuantaOneAPI.dll

clr.AddReference('YuantaOneAPI.dll')    #clr.AddReference("DLL路徑")這裡<[System.IO.FileNotFoundException: 無法載入檔案或組件 'YuantaOneAPI.dll' 或其相依性的其中之一。 系統找不到指定的檔案。案名稱: 'YuantaOneAPI.dll' >
##匯入YuataOneAPI物件
from YuantaOneAPI import (YuantaOneAPITrader,
                          enumEnvironmentMode,
                          OnResponseEventHandler,
                          YuantaDataHelper,
                          enumLangType,
                          StockOrder,
                          FutureOrder,
                          enumLogType,
                          OVFutureOrder,
                          Watchlist,
                          WatchlistAll,
                          FiveTickA,
			              StockTick,
                          DepositOptimum,
                          OrderStatus)

#List用來包裝RQ的struct
from System.Collections.Generic import List
import System

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

#WatchlistAll_response
#訂閱報價表 98.10.70.10
def SubscribeWatclistAll_Out(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    result += 'WatchlistALL報價表訂閱結果:\r\n';
    byTemp=''    
    
    try:
        #abyKey鍵值
        result += dataGetter.GetStr(22) + ','
        #byMarketNo市場代碼
        result +='{0}'.format(str(dataGetter.GetByte())) + ',' 
        #abyStkCode商品代碼
        result += dataGetter.GetStr(12) + ',' 
        #llSeqNo序號
        result += '{0}'.format(str(dataGetter.GetLong())) + ',' 
        #byIndexFlag索引值
        byTemp = str(dataGetter.GetByte())
        result += byTemp + ',' 
      
        if (str(byTemp) == '22'):
            #dwBuyVol第一買量
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #dwSellVol第一賣量
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
        elif (str(byTemp)  == '28'):
            #intBuyPrice買價
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #intSellPrice賣價
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
        elif (str(byTemp)  == '29'):
            #struTime交易時間  
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #dwTotalOutVol累計外盤量
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #dwTotalInVol累計內盤量
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #intDeal成交價
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #dwVol單量
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #dwTotalVol總成交量
            result += '{0}'.format(str(dataGetter.GetInt())) + ',' 
            #dwTotalAmt總成交金額
            result += '{0}'.format(str(dataGetter.GetInt()))
        result += '\r\n';
        
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#FiveTick_response
#訂閱五檔報價 210.10.60.10
def SubscribeFiveTick_out(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    result += 'FiveTick五檔訂閱結果:\r\n'
    
    try:
            # abyKey鍵值
            dataGetter.GetStr(22) + ',' 
            # byMarketNo市場代碼
            result +='{0}'.format(str(dataGetter.GetByte())) + ','
            # abyStkCode股票代碼
            result += dataGetter.GetStr(12) + ','
            #byIndexFlag索引值
            byTemp = str(dataGetter.GetByte())
            result += byTemp + ',' 
      
            if (str(byTemp) == '50'):
                #intPrice1第一買價  
                result += str(dataGetter.GetInt())+ ','  
                #intPrice2第二買價  
                result += str(dataGetter.GetInt())+ ','  
                #intPrice3第三買價  
                result += str(dataGetter.GetInt())+ ','  
                #intPrice4第四買價  
                result += str(dataGetter.GetInt())+ ','  
                #intPrice5第五買價  
                result += str(dataGetter.GetInt())+ ','
                #dwVol1第一買量  
                result += str(dataGetter.GetInt())+ ','            
                #dwVol2第二買量  
                result += str(dataGetter.GetInt())+ ','   
                #dwVol3第三買量  
                result += str(dataGetter.GetInt())+ ','               
                #dwVol4第四買量  
                result += str(dataGetter.GetInt())+ ','   
                #dwVol5第五買量  
                result += str(dataGetter.GetInt())+ ','   
                #intPrice1第一賣價  
                result += str(dataGetter.GetInt())+ ','  
                #intPrice1第二賣價  
                result += str(dataGetter.GetInt())+ ','  
                #intPrice1第三賣價  
                result += str(dataGetter.GetInt())+ ','  
                #intPrice1第四賣價  
                result += str(dataGetter.GetInt())+ ','  
                #intPrice1第五賣價  
                result += str(dataGetter.GetInt())+ ','  
                #dwVol1第一賣量  
                result += str(dataGetter.GetInt())+ ','    
                #dwVol2第二賣量  
                result += str(dataGetter.GetInt())+ ','  
                #dwVol3第三賣量  
                result += str(dataGetter.GetInt())+ ','  
                #dwVol4第四賣量  
                result += str(dataGetter.GetInt())+ ','  
                #dwVol5第五賣量  
                result += str(dataGetter.GetInt()) 
                result+='\r\n'
            
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#Watchlist_response
#訂閱報價表指定欄位 210.10.70.11
def SubscribeWatchlist_Out(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    result += 'WatchList指定欄位訂閱結果:\r\n'
    
    try:
        #abyKey鍵值
        dataGetter.GetStr(22) + ','
        #byMarketNo市場代碼
        result += '{0}'.format(dataGetter.GetByte()) + ',' 
        #abyStkCode股票代碼
        result += dataGetter.GetStr(12) + ','
        #byIndexFlag索引值
        result += '{0}'.format(dataGetter.GetByte()) + ',' 
        #intValue資料值  
        result += str(dataGetter.GetInt()) 
        result += '\r\n';        
        
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#StockTick_response
#訂閱個股分時明細結果 210.10.40.10
def SubscribeStocktick_out(abyData):
    dataGetter = YuantaDataHelper(enumLangType.NORMAL)
    dataGetter.OutMsgLoad(abyData)
    
    result = ''
    result += '分時明細訂閱結果:\r\n'    
    
    try:
            #abyKey鍵值
            dataGetter.GetStr(22)
            #byMarketNo市場代碼
            result +='{0}'.format(str(dataGetter.GetByte())) + ','
            #abyStkCode股票代碼
            result += dataGetter.GetStr(12) + ','
            #dwSerialNo序號
            result += str(dataGetter.GetInt()) + ','  
            #struTime交易時間  
            yuantaTime = dataGetter.GetTYuantaTime() 
            result += '{0}:{1}:{2}.{3}'.format(str(yuantaTime.bytHour), str(yuantaTime.bytMin), str(yuantaTime.bytSec), str(yuantaTime.ushtMSec)) + ',' 
            #intBuyPrice買價
            result += str(dataGetter.GetInt()) + ','  
            #intSellPrice賣價
            result += str(dataGetter.GetInt()) + ','  
            #intDealPrice成交價
            result += str(dataGetter.GetInt()) + ','
            #dwDealVol成交量
            result += str(dataGetter.GetInt()) + ','
            #byInOutFlag內外盤註記
            result +='{0}'.format(str(dataGetter.GetByte())) + ','
            #byType明細類別
            result +='{0}'.format(str(dataGetter.GetByte()))
            result += '\r\n';        
            
    except Exception as error:
        result = error
    #time.sleep(3)
    return result

#OnResponse
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
                result ='{0},{1}'.Format(strIndex, objValue)
    if result:
        print('##================================================##\n')
        print(result,'\n')

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
    LogOut(yuanta)
    objYuantaOneAPI.Close()
    objYuantaOneAPI.Dispose()

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
    stockorder.TradeDate = datetime.today().strftime('%Y/%m/%d') 
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
    futureOrder.TradeDate = datetime.today().strftime('%Y/%m/%d') 
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
        ovFutOrder.TradeDate = datetime.today().strftime('%Y/%m/%d') 

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
    watch = WatchlistAll()
    watch.MarketNo = 1
    watch.StockCode = '2330'
    lstWatchlistAll.Add(watch)
    yuanta.SubscribeWatchlistAll(lstWatchlistAll) 
    
#取消訂閱報價
#UnsubWatchlistAll 98.10.70.10
def UnsubWatchlistAll_api(yuanta):
    lstWatchlistAll = List[WatchlistAll]()
    watch = WatchlistAll()
    watch.MarketNo = 1
    watch.StockCode = '2330'
    lstWatchlistAll.Add(watch)
    yuanta.UnsubscribeWatchlistAll(lstWatchlistAll)    

#訂閱五檔報價
#FiveTick 210.10.60.10     
def SubscribeFiveTick_api(yuanta):
    lstFiveTick = List[FiveTickA]()    
    fiveTickA = FiveTickA() 
    fiveTickA.MarketNo =3
    fiveTickA.StockCode ='TXFPM1'
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
    watch = Watchlist()
    watch.IndexFlag = 7 #IndexFlag訂閱索引值
    watch.MarketNo = 3
    watch.StockCode ='TXFPM1'
    lstWatchlist.Add(watch)
    yuanta.SubscribeWatchlist(lstWatchlist) 

#取消訂閱報價表指定欄位 
#UnSubscribeWatchlist 210.10.70.11
def UnSubscribeWatchlist_api(yuanta):
    lstWatchlist = List[Watchlist]()
    watch = Watchlist()
    watch.IndexFlag = 7 #IndexFlag訂閱索引值
    watch.MarketNo = 3
    watch.StockCode ='TXFPM1'
    lstWatchlist.Add(watch)
    yuanta.UnsubscribeWatchlist(lstWatchlist) 

#訂閱分時明細
#StockTick 210.10.40.10
def SubscribeStocktick_api(yuanta):
    lstStocktick = List[StockTick]()    
    stocktick = StockTick()
    stocktick.MarketNo =  1
    stocktick.StockCode = '2330'
    lstStocktick.Add(stocktick)
    yuanta.SubscribeStockTick(lstStocktick)

#取消訂閱分時明細 
#UnSubscribeStocktick210.10.40.10
def UnSubscribeStocktick_api(yuanta):
    lstStocktick = List[StockTick]()    
    stocktick = StockTick()
    stocktick.MarketNo =  1
    stocktick.StockCode = '2330'
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
#SubscribeFiveTick_api(objYuantaOneAPI)

#訂閱指定欄位Watchlist
#SubscribeWatchlist_api(objYuantaOneAPI)

#訂閱分時明細Stocktick
#SubscribeStocktick_api(objYuantaOneAPI)

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
