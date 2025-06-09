import sys
import os
import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.config import Config
from modules.m0_data_loader import DataLoader
from modules.m1_signal_generator import SignalGenerator
from modules.m2_backtester import Backtester
from modules.m3_report_generator import ReportGenerator
# 預留未來模組
# from modules.m3_report_generator import ReportGenerator

def main():
    config = Config.load()

    while True:
        print("\n============================")
        print(" Quanta II 主選單")
        print("============================")
        print("1. 下載歷史資料 (M0)")
        print("2. 產生策略信號 (M1)")
        print("3. 策略回測 (M2)")
        print("4. 績效篩選與報告 (M3)")
        print("5. 離開系統")

        choice = input("請選擇功能編號：").strip()

        if choice == '1':
            run_m0(config)
        elif choice == '2':
            run_m1(config)
        elif choice == '3':
            run_m2(config)
        elif choice == '4':
            print("\n[M3: 績效篩選與報告模組]")
            summary_path = input("1. 請輸入 summary 檔案路徑（如 results/performance_master.csv）：")
            metric = input("2. 請輸入排序依據（如 total_return, max_drawdown）：")
            
            top_mode = input("3. 請選擇 Top 模式（n=Top N, p=Top %，預設 n）：").lower()
            if top_mode == 'p':
                top_percent = float(input("請輸入 Top % 百分比（如 10）："))
                top_n = None
            else:
                top_n = int(input("請輸入 Top N 數量（如 10）："))
                top_percent = None
            
            conditions = input("4. 請輸入篩選條件（如 total_return>=0.05, max_drawdown<=0.1，可留空）：")
            export_format = input("5. 請選擇輸出格式（csv/xlsx/html，預設 csv）：").lower() or 'csv'
            
            reporter = ReportGenerator(config.reports_dir)
            reporter.run(summary_path, metric, top_n, top_percent, conditions, export_format)
        elif choice == '5':
            print("已離開系統。")
            break
        else:
            print("請輸入正確選項。")

def run_m0(config):
    print("\n[M0: 資料下載模組]")
    symbols = input("1. 請輸入股票代碼（逗號分隔）：").strip().upper().split(',')
    start_date = input("2. 請輸入開始日期 (YYYY-MM-DD)：").strip()
    end_date = input("3. 請輸入結束日期 (YYYY-MM-DD)：").strip()
    save_to_db = input("4. 是否存到 SQLite 資料庫？(True/False, 預設 False)：").strip() or 'False'
    auto_fill = input("5. 是否自動補齊資料？(True/False, 預設 True)：").strip() or 'True'
    source = input("6. 資料來源？(預設 yfinance)：").strip() or 'yfinance'
    max_workers = input("7. 同時下載股票數量？(預設 3)：").strip() or '3'
    download_delay = input("8. 每支股票下載間隔（秒）？(預設 2)：").strip() or '2'
    date_chunk_size = input("9. 分段下載天數上限？(預設 180)：").strip() or '180'

    symbols = [s.strip() for s in symbols if s.strip()]
    save_to_db = save_to_db.lower() == 'true'
    auto_fill = auto_fill.lower() == 'true'
    max_workers = int(max_workers)
    download_delay = float(download_delay)
    date_chunk_size = int(date_chunk_size)

    loader = DataLoader(config)
    loader.run(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        save_to_db=save_to_db,
        auto_fill=auto_fill,
        source=source,
        max_workers=max_workers,
        download_delay=download_delay,
        date_chunk_size=date_chunk_size
    )

def run_m1(config):
    print("\n[M1: 策略產生模組]")
    strategy = input("1. 請輸入策略名稱（如 SMA_CROSS, RSI）：").strip().upper()
    symbols = input("2. 請輸入股票代碼（逗號分隔）：").strip().upper().split(',')
    start_date = input("3. 請輸入資料起始日 (YYYY-MM-DD)：").strip()
    end_date = input("4. 請輸入資料結束日 (YYYY-MM-DD)：").strip()
    param_mode = input("5. 參數輸入方式？(Auto/Manual, 預設 Auto)：").strip() or 'Auto'
    save_format = input("6. signals 輸出格式？(csv/parquet, 預設 csv)：").strip() or 'csv'
    export_param_log = input("7. 是否匯出 param_log.json？(True/False, 預設 True)：").strip() or 'True'

    symbols = [s.strip() for s in symbols if s.strip()]
    param_mode = param_mode.capitalize()
    save_format = save_format.lower()
    export_param_log = export_param_log.lower() == 'true'

    # 新增：讓使用者自訂產生策略組數與參數範圍
    if strategy == 'SMA_CROSS':
        if param_mode == 'Auto':
            print("請輸入 short_period 範圍（如 5,50）：")
            short_min, short_max = map(int, input().strip().split(','))
            print("請輸入 long_period 範圍（如 20,200）：")
            long_min, long_max = map(int, input().strip().split(','))
            print("請輸入 short_period 與 long_period 的步進（如 1,5）：")
            short_step, long_step = map(int, input().strip().split(','))
            print("請輸入要產生幾組策略（如 100）：")
            n_combinations = int(input().strip())
            param_space = []
            for s in range(short_min, short_max+1, short_step):
                for l in range(long_min, long_max+1, long_step):
                    if l > s:
                        param_space.append({'short_period': s, 'long_period': l})
            # 隨機抽取 n 組（如超過）
            import random
            if len(param_space) > n_combinations:
                param_space = random.sample(param_space, n_combinations)
        else:
            short_period = int(input("請輸入 short_period：").strip())
            long_period = int(input("請輸入 long_period：").strip())
            param_space = [{'short_period': short_period, 'long_period': long_period}]
    elif strategy == 'RSI':
        if param_mode == 'Auto':
            print("請輸入 period 範圍（如 7,30）：")
            period_min, period_max = map(int, input().strip().split(','))
            print("請輸入 overbought 範圍（如 65,85）：")
            ob_min, ob_max = map(float, input().strip().split(','))
            print("請輸入 oversold 範圍（如 15,35）：")
            os_min, os_max = map(float, input().strip().split(','))
            print("請輸入 period/overbought/oversold 步進（如 1,5,5）：")
            period_step, ob_step, os_step = map(int, input().strip().split(','))
            print("請輸入要產生幾組策略（如 100）：")
            n_combinations = int(input().strip())
            param_space = []
            for p in range(period_min, period_max+1, int(period_step)):
                for obv in range(int(ob_min), int(ob_max+1), int(ob_step)):
                    for osv in range(int(os_min), int(os_max+1), int(os_step)):
                        if osv < obv:  # oversold 必須小於 overbought
                            param_space.append({'period': p, 'overbought': obv, 'oversold': osv})
            import random
            if len(param_space) > n_combinations:
                param_space = random.sample(param_space, n_combinations)
        else:
            period = int(input("請輸入 period：").strip())
            overbought = float(input("請輸入 overbought：").strip())
            oversold = float(input("請輸入 oversold：").strip())
            param_space = [{'period': period, 'overbought': overbought, 'oversold': oversold}]
    else:
        print("不支援的策略名稱。")
        return

    # 新增：自動建立子資料夾存放本次所有 signal 檔案
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for symbol in symbols:
        subdir = config.signals_dir / f"{strategy}_{symbol}_{timestamp}"
        os.makedirs(subdir, exist_ok=True)
        generator = SignalGenerator(config)
        generator.signals_dir = subdir  # 指定本次 signal 子資料夾
        generator.run(
            symbol=symbol,
            strategy=strategy,
            param_space=param_space,
            start_date=start_date,
            end_date=end_date,
            save_format=save_format,
            export_param_log=export_param_log
        )
    print(f"本次所有信號檔案已儲存於 {subdir}")

def run_m2(config):
    print("\n[M2: 策略回測模組]")
    signal_files = input("1. 請輸入 signal 檔案路徑（可逗號分隔多個或資料夾，如 signals/SMA_CROSS_AAPL_0001.csv,signals/SMA_CROSS_TSLA_0001.csv 或 signals/SMA_CROSS_AAPL_20240608_001）：").strip()
    symbol = input("2. 請輸入股票代碼（如 AAPL）：").strip().upper()
    initial_cash = float(input("3. 請輸入初始資金（預設 100000）：").strip() or 100000)
    fee = float(input("4. 請輸入手續費率（預設 0.001425）：").strip() or 0.001425)
    slippage = float(input("5. 請輸入滑點（預設 0.0005）：").strip() or 0.0005)
    position = input("6. 請輸入倉位配置（fixed=100 或 percent=0.1，預設 fixed=100）：").strip() or 'fixed=100'
    trade_time = input("7. 請輸入交易時機（預設 next_open）：").strip() or 'next_open'
    export_perf = input("8. 是否匯出績效結果（True/False，預設 True）：").strip() or 'True'
    export_nav = input("9. 是否匯出 NAV 序列（True/False，預設 True）：").strip() or 'True'

    export_perf = export_perf.lower() == 'true'
    export_nav = export_nav.lower() == 'true'

    backtester = Backtester(config)
    # 支援 signal 檔案路徑為資料夾
    all_files = []
    for f in [f.strip() for f in signal_files.split(',') if f.strip()]:
        if os.path.isdir(f):
            all_files.extend([os.path.join(f, x) for x in os.listdir(f) if x.endswith('.csv')])
        else:
            all_files.append(f)
    for signal_file in all_files:
        backtester.run(
            signal_file=signal_file,
            symbol=symbol,
            initial_cash=initial_cash,
            fee=fee,
            slippage=slippage,
            position=position,
            trade_time=trade_time,
            export_perf=export_perf,
            export_nav=export_nav
        )

if __name__ == '__main__':
    main() 