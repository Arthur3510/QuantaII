import os
import json
import pandas as pd
from pathlib import Path
import logging
from utils.config import Config

class Backtester:
    """
    M2: 策略回測與績效分析模組
    功能:
      - 載入 signal CSV
      - 根據信號進行模擬交易
      - 計算績效指標與 NAV
      - 自動 append 至 performance_master.csv
    """
    def __init__(self, config: Config):
        self.config = config
        self.results_dir = config.results_dir
        os.makedirs(self.results_dir, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def load_signals(self, signal_path: str) -> pd.DataFrame:
        return pd.read_csv(signal_path, index_col=0, parse_dates=True)

    def load_price(self, symbol: str) -> pd.DataFrame:
        price_path = self.config.data_dir / f"{symbol}.csv"
        return pd.read_csv(price_path, index_col=0, parse_dates=True)

    def run_backtest(self, price: pd.DataFrame, signals: pd.DataFrame, initial_cash: float, fee: float, slippage: float, position: str, trade_time: str) -> (pd.DataFrame, dict):
        nav = []
        cash = initial_cash
        position_size = 0
        last_signal = 0
        nav_series = []
        trade_log = []
        for date, row in signals.iterrows():
            if date not in price.index:
                continue
            close = price.loc[date, 'close']
            signal = row['signal']
            # 只在信號變化時交易
            if signal != last_signal:
                if signal == 1:  # 買入
                    if position.startswith('fixed='):
                        qty = int(position.split('=')[1])
                        cost = close * qty * (1 + fee + slippage)
                        if cash >= cost:
                            cash -= cost
                            position_size += qty
                            trade_log.append({'date': date, 'action': 'buy', 'price': close, 'qty': qty, 'cash': cash})
                    elif position.startswith('percent='):
                        pct = float(position.split('=')[1])
                        invest = cash * pct
                        qty = int(invest // (close * (1 + fee + slippage)))
                        cost = close * qty * (1 + fee + slippage)
                        if cash >= cost and qty > 0:
                            cash -= cost
                            position_size += qty
                            trade_log.append({'date': date, 'action': 'buy', 'price': close, 'qty': qty, 'cash': cash})
                elif signal == -1 and position_size > 0:  # 賣出
                    revenue = close * position_size * (1 - fee - slippage)
                    cash += revenue
                    trade_log.append({'date': date, 'action': 'sell', 'price': close, 'qty': position_size, 'cash': cash})
                    position_size = 0
            nav_series.append({'date': date, 'nav': cash + position_size * close})
            last_signal = signal
        nav_df = pd.DataFrame(nav_series).set_index('date')
        perf = self.calc_performance(nav_df)
        return nav_df, perf

    def calc_performance(self, nav: pd.DataFrame) -> dict:
        perf = {}
        nav_series = nav['nav']
        perf['total_return'] = float(nav_series.iloc[-1] / nav_series.iloc[0] - 1)
        perf['max_drawdown'] = float((nav_series.cummax() - nav_series).max() / nav_series.cummax().max())
        perf['run_id'] = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        return perf

    def get_param_info(self, signal_file: str):
        # 解析 <策略名稱>_<股票代碼>_<參數編號>.csv，允許策略名稱有多個 _
        basename = os.path.basename(signal_file).replace('.csv', '')
        parts = basename.split('_')
        if len(parts) >= 3:
            strategy = '_'.join(parts[:-2])
            symbol = parts[-2]
            param_id = parts[-1].zfill(4)  # 統一四位數
        else:
            strategy = parts[0]
            symbol = 'UNKNOWN'
            param_id = '0001'
        # 先找信號檔案同資料夾下的 param_log
        signal_dir = Path(signal_file).parent
        param_log_path = signal_dir / f"param_log_{strategy}_{symbol}.json"
        if not param_log_path.exists():
            # 再找 signals 根目錄
            param_log_path = self.config.signals_dir / f"param_log_{strategy}_{symbol}.json"
        if param_log_path.exists():
            with open(param_log_path, 'r', encoding='utf-8') as f:
                param_log = json.load(f)
            param_info = param_log.get(param_id, {})
            params = param_info.get('params', {})
        else:
            params = {}
        return strategy, symbol, param_id, params

    def save(self, perf: dict, nav: pd.DataFrame, strategy: str, run_id: str, export_perf: bool, export_nav: bool, symbol: str, param_id: str, params: dict):
        # 直接用信號檔案上層資料夾名稱作為 results 子資料夾
        signal_dir = Path(self.current_signal_file).parent
        subdir_name = signal_dir.name
        subdir = self.results_dir / subdir_name
        os.makedirs(subdir, exist_ok=True)
        
        # 增加策略、股票、參數資訊
        perf_full = perf.copy()
        perf_full['strategy'] = strategy
        perf_full['symbol'] = symbol
        perf_full['param_id'] = param_id
        perf_full['params'] = json.dumps(params, ensure_ascii=False)
        
        if export_perf:
            perf_path = subdir / f"performance_{strategy}_{symbol}_{param_id}.csv"
            pd.DataFrame([perf_full]).to_csv(perf_path, index=False)
        
        if export_nav:
            nav_path = subdir / f"nav_{strategy}_{symbol}_{param_id}.parquet"
            nav.to_parquet(nav_path)
        
        # 在子資料夾中維護獨立的 performance_master.csv
        master_path = subdir / "performance_master.csv"
        if master_path.exists():
            master = pd.read_csv(master_path)
        else:
            master = pd.DataFrame()
        master = pd.concat([master, pd.DataFrame([perf_full])], ignore_index=True)
        master.to_csv(master_path, index=False)
        
        # 同時更新根目錄的 performance_master.csv
        root_master_path = self.results_dir / "performance_master.csv"
        if root_master_path.exists():
            root_master = pd.read_csv(root_master_path)
        else:
            root_master = pd.DataFrame()
        root_master = pd.concat([root_master, pd.DataFrame([perf_full])], ignore_index=True)
        root_master.to_csv(root_master_path, index=False)

    def run(self, signal_file: str, symbol: str, initial_cash: float = 100000, fee: float = 0.001425, slippage: float = 0.0005, position: str = 'fixed=100', trade_time: str = 'next_open', export_perf: bool = True, export_nav: bool = True):
        # 儲存當前信號檔案路徑
        self.current_signal_file = signal_file
        
        signals = self.load_signals(signal_file)
        price = self.load_price(symbol)
        nav, perf = self.run_backtest(price, signals, initial_cash, fee, slippage, position, trade_time)
        strategy, symbol_from_file, param_id, params = self.get_param_info(signal_file)
        run_id = perf['run_id']
        self.save(perf, nav, strategy, run_id, export_perf, export_nav, symbol_from_file, param_id, params)
        self.logger.info(f"完成回測：{signal_file}，績效：{perf}") 