from utils.config import Config
from modules.m0_data_loader import DataLoader
# 預留未來模組
# from modules.m1_signal_generator import SignalGenerator
# from modules.m2_backtester import Backtester
# from modules.m3_report_generator import ReportGenerator

def main():
    config = Config.load()

    while True:
        print("\n============================")
        print(" Quanta II 主選單")
        print("============================")
        print("1. 下載歷史資料 (M0)")
        print("2. 離開系統")

        choice = input("請選擇功能編號：").strip()

        if choice == '1':
            run_m0(config)
        elif choice == '2':
            print("已離開系統。")
            break
        else:
            print("請輸入正確選項。")

def run_m0(config):
    print("\n[下載歷史資料]")
    symbols = input("請輸入股票代碼（以逗號分隔）：").strip().upper().split(',')
    start_date = input("請輸入開始日期 (YYYY-MM-DD)：").strip()
    end_date = input("請輸入結束日期 (YYYY-MM-DD)：").strip()

    symbols = [s.strip() for s in symbols if s.strip()]

    loader = DataLoader(config)
    loader.run(symbols, start_date, end_date)

if __name__ == '__main__':
    main() 