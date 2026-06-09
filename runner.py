import datetime
import subprocess
import sys
"""
#### 步驟 ：設定工作排程器
1.  開啟 `taskschd.msc`，建立「建立基本工作」。
2.  **觸發程序**：選擇「每日」，時間設為 `08:30 AM`。
3.  **動作**：選擇「啟動程式」。
    *   **程式或指令碼**：輸入 `python.exe` 的完整路徑。
    *   **新增引數**：輸入上面 `runner.py` 的路徑。
4.  其餘設定（描述、權限）照常設定。

這樣系統每天 8:30 都會醒來一次，跑去執行 `runner.py`，`runner.py` 會判斷：
*   如果是週六日 -> 結束 (不執行)。
*   如果是你列表中的假日 -> 結束 (不執行)。
*   如果是平日且非假日 -> 執行 `run.py`。
"""
# ==========================================
# 在這裡設定你的主要股票腳本路徑
MAIN_SCRIPT_PATH = r"D:\workCS\TEST\2026\YuantaOneAPI_Python\YuantaOneAPI_Python\run.py"
# ==========================================

def is_trading_day():
    """
    檢查今天是否為股市開盤日
    """
    today = datetime.date.today()

    # 1. 檢查是否為週末 (0=Mon, 6=Sun)
    if today.weekday() >= 5:
        return False

    # 2. 檢查是否為假日 (你需要手動維護這個清單)
    # 格式範例: (2024, 1, 1) 代表 2024/1/1
    holidays = [
        (2027, 1, 1),  # 元旦
        (2027, 2, 28), # 和平紀念日
        (2026, 4, 4),  # 清明節
        (2026, 5, 1),  # 勞動節
        (2026, 6, 19),  # 端午節
        (2026, 9, 25), #中秋節與教師節
        (2026, 9, 28), #中秋節與教師節
        (2026, 10, 9),  #國慶日
        (2026,10,26),   #台灣光復節
        (2026,12,25)   #行憲紀念日        
        # ... 請依序新增今年的國定假日
    ]

    # 轉換成 date 物件比對
    today_tuple = (today.year, today.month, today.day)

    if today_tuple in holidays:
        return False

    return True

if __name__ == "__main__":
    if is_trading_day():
        print(f"今天是股市開盤日，執行腳本: {MAIN_SCRIPT_PATH}")
        try:
            # 使用 subprocess 執行你的主腳本
            # 如果不希望開命令提示字元，可以加上 creationflags=subprocess.CREATE_NO_WINDOW
            subprocess.run([sys.executable, MAIN_SCRIPT_PATH], check=True)
        except Exception as e:
            print(f"執行錯誤: {e}")
    else:
        print("今天不是股市開盤日（週末或假日），不執行。")