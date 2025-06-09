import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from utils.config import Config

class SignalGenerator:
    """
    M1: 策略信號產生模組
    
    功能:
      - 載入歷史資料
      - 計算技術指標
      - 產生交易信號
      - 輸出信號檔案與參數對照表
    """
    def __init__(self, config: Config):
        self.config = config
        self.setup_logging()
        # 確保目錄存在
        self.signals_dir = config.signals_dir
        os.makedirs(self.signals_dir, exist_ok=True)
        # 參數對照表
        self.param_log = {}
        self.signal_param_map = {}

    def setup_logging(self):
        """設置日誌"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def load_data(self, symbol: str) -> pd.DataFrame:
        """載入股票歷史資料"""
        try:
            # 嘗試從 CSV 讀取
            csv_path = self.config.data_dir / f"{symbol}.csv"
            if csv_path.exists():
                df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
                self.logger.info(f"從 {csv_path} 載入 {symbol} 資料")
                return df
            else:
                self.logger.error(f"找不到 {symbol} 的歷史資料檔案")
                return None
        except Exception as e:
            self.logger.error(f"載入 {symbol} 資料時發生錯誤: {str(e)}")
            return None

    def calculate_sma(self, df: pd.DataFrame, short_period: int, long_period: int) -> pd.DataFrame:
        """計算 SMA 交叉策略"""
        df = df.copy()
        # 計算移動平均
        df['sma_short'] = df['close'].rolling(window=short_period).mean()
        df['sma_long'] = df['close'].rolling(window=long_period).mean()
        # 產生信號
        df['signal'] = 0
        # 黃金交叉：短期均線向上穿越長期均線
        df.loc[(df['sma_short'] > df['sma_long']) & 
               (df['sma_short'].shift(1) <= df['sma_long'].shift(1)), 'signal'] = 1
        # 死亡交叉：短期均線向下穿越長期均線
        df.loc[(df['sma_short'] < df['sma_long']) & 
               (df['sma_short'].shift(1) >= df['sma_long'].shift(1)), 'signal'] = -1
        return df[['signal']]

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14, 
                     overbought: float = 70, oversold: float = 30) -> pd.DataFrame:
        """計算 RSI 策略"""
        df = df.copy()
        # 計算價格變化
        delta = df['close'].diff()
        # 分離上漲和下跌
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        # 計算 RS 和 RSI
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        # 產生信號
        df['signal'] = 0
        df.loc[df['rsi'] < oversold, 'signal'] = 1  # 超賣買入
        df.loc[df['rsi'] > overbought, 'signal'] = -1  # 超買賣出
        return df[['signal']]

    def generate_signals(self, df: pd.DataFrame, strategy: str, params: dict) -> pd.DataFrame:
        """根據策略類型產生信號"""
        if strategy == 'SMA_CROSS':
            return self.calculate_sma(df, params['short_period'], params['long_period'])
        elif strategy == 'RSI':
            return self.calculate_rsi(df, params['period'], params['overbought'], params['oversold'])
        else:
            self.logger.error(f"不支援的策略類型: {strategy}")
            return None

    def save_signals(self, df: pd.DataFrame, strategy: str, symbol: str, param_id: str):
        """儲存信號檔案，檔名包含股票代碼"""
        try:
            signal_path = self.signals_dir / f"{strategy}_{symbol}_{param_id}.csv"
            df.to_csv(signal_path)
            self.logger.info(f"已儲存信號檔案: {signal_path}")
            self.param_log[param_id] = {
                'strategy': strategy,
                'symbol': symbol,
                'params': self.signal_param_map[param_id]
            }
        except Exception as e:
            self.logger.error(f"儲存信號檔案時發生錯誤: {str(e)}")

    def save_param_log(self, strategy: str):
        """儲存參數對照表"""
        try:
            # 儲存參數對照表
            param_log_path = self.signals_dir / f"param_log_{strategy}.json"
            with open(param_log_path, 'w') as f:
                json.dump(self.param_log, f, indent=2)
            self.logger.info(f"已儲存參數對照表: {param_log_path}")
            
            # 儲存信號-參數對應表
            signal_param_path = self.signals_dir / "signal_param_map.json"
            with open(signal_param_path, 'w') as f:
                json.dump(self.signal_param_map, f, indent=2)
            self.logger.info(f"已儲存信號-參數對應表: {signal_param_path}")
            
        except Exception as e:
            self.logger.error(f"儲存參數對照表時發生錯誤: {str(e)}")

    def run(self, symbol: str, strategy: str, param_space: list, start_date=None, end_date=None, save_format='csv', export_param_log=True):
        """
        執行信號產生流程
        
        Args:
            symbol: 股票代碼
            strategy: 策略名稱
            param_space: 參數組合列表
            start_date: 資料起始日 (YYYY-MM-DD)
            end_date: 資料結束日 (YYYY-MM-DD)
            save_format: signals 輸出格式 ('csv' 或 'parquet')
            export_param_log: 是否匯出 param_log.json
        """
        self.logger.info(f"開始產生 {symbol} 的 {strategy} 策略信號")
        
        # 載入歷史資料
        df = self.load_data(symbol)
        if df is None:
            return
        
        # 根據日期範圍篩選
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]
        if df.empty:
            self.logger.error(f"{symbol} 在指定日期範圍內無資料")
            return
        
        # 產生每組參數的信號
        for i, params in enumerate(param_space, start=1):
            param_id = f"{i:04d}"
            self.signal_param_map[param_id] = params
            
            # 產生信號
            signals = self.generate_signals(df, strategy, params)
            if signals is not None:
                # 儲存信號
                signal_path = self.signals_dir / f"{strategy}_{symbol}_{param_id}.{save_format}"
                try:
                    if save_format == 'csv':
                        signals.to_csv(signal_path)
                    elif save_format == 'parquet':
                        signals.to_parquet(signal_path)
                    else:
                        self.logger.error(f"不支援的儲存格式: {save_format}")
                        continue
                    self.logger.info(f"已儲存信號檔案: {signal_path}")
                except Exception as e:
                    self.logger.error(f"儲存信號檔案時發生錯誤: {str(e)}")
                # 更新參數對照表
                self.param_log[param_id] = {
                    'strategy': strategy,
                    'symbol': symbol,
                    'params': self.signal_param_map[param_id]
                }
        # 儲存參數對照表
        if export_param_log:
            try:
                param_log_path = self.signals_dir / f"param_log_{strategy}_{symbol}.json"
                with open(param_log_path, 'w', encoding='utf-8') as f:
                    json.dump(self.param_log, f, indent=2, ensure_ascii=False)
                self.logger.info(f"已儲存參數對照表: {param_log_path}")
                signal_param_path = self.signals_dir / f"signal_param_map_{strategy}_{symbol}.json"
                with open(signal_param_path, 'w', encoding='utf-8') as f:
                    json.dump(self.signal_param_map, f, indent=2, ensure_ascii=False)
                self.logger.info(f"已儲存信號-參數對應表: {signal_param_path}")
            except Exception as e:
                self.logger.error(f"儲存參數對照表時發生錯誤: {str(e)}")
        self.logger.info(f"完成 {symbol} 的 {strategy} 策略信號產生") 