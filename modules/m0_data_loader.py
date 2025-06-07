import os
import time
import random
import datetime
import sqlite3
import pandas as pd
import yfinance as yf
from utils.config import Config
from pathlib import Path
import logging

class DataLoader:
    """
    M0: 歷史資料下載模組

    功能:
      - 從 yfinance 下載股票歷史資料
      - 支援分段下載、指數退避與重試機制
      - 選擇性儲存至 SQLite 資料庫或 Parquet 檔
    """
    def __init__(self, config: Config):
        self.config = config
        self.setup_logging()
        # 確保資料夾存在
        self.data_dir = config.data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        # 資料庫位置
        self.db_path = config.database.path

    def setup_logging(self):
        """設置日誌"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def download_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """下載單一股票資料"""
        try:
            # 增加隨機延遲，避免同時請求
            time.sleep(self.config.download_delay + random.uniform(1, 3))
            
            # 使用更保守的設定
            data = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
                threads=False  # 禁用多執行緒以避免速率限制
            )
            
            if data.empty:
                self.logger.warning(f"{symbol} 無資料")
                return None
                
            return data
            
        except Exception as e:
            self.logger.error(f"下載 {symbol} 時發生錯誤: {str(e)}")
            return None
            
    def download_stock_data(self, symbols: list, start_date: str, end_date: str):
        """下載多個股票資料"""
        # 轉換日期字串為日期物件
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        
        # 計算需要下載的日期區間
        date_ranges = []
        current_start = start
        while current_start < end:
            current_end = min(
                current_start + datetime.timedelta(days=self.config.date_chunk_size),
                end
            )
            date_ranges.append((
                current_start.strftime("%Y-%m-%d"),
                current_end.strftime("%Y-%m-%d")
            ))
            current_start = current_end + datetime.timedelta(days=1)
            
        # 下載每個股票資料
        for symbol in symbols:
            symbol = symbol.strip().upper()
            self.logger.info(f"下載 {symbol} 資料: {start_date} ~ {end_date}")
            
            all_data = []
            for chunk_start, chunk_end in date_ranges:
                retry_count = 0
                while retry_count < self.config.max_retries:
                    try:
                        data = self.download_data(symbol, chunk_start, chunk_end)
                        if data is not None:
                            all_data.append(data)
                        break
                    except Exception as e:
                        retry_count += 1
                        if retry_count == self.config.max_retries:
                            self.logger.error(f"{symbol} 下載失敗，已達最大重試次數")
                            break
                        # 指數退避重試
                        wait_time = (2 ** retry_count) + random.uniform(1, 3)
                        self.logger.warning(f"重試 {symbol} ({retry_count}/{self.config.max_retries})，等待 {wait_time:.1f} 秒")
                        time.sleep(wait_time)
            
            if all_data:
                # 合併所有資料
                final_data = pd.concat(all_data)
                final_data = final_data[~final_data.index.duplicated(keep='first')]
                final_data.sort_index(inplace=True)
                
                # 儲存資料
                self.save_data(symbol, final_data)
            else:
                self.logger.warning(f"{symbol} 無資料，跳過儲存。")
                
    def save_data(self, symbol: str, data: pd.DataFrame):
        """儲存股票資料"""
        # 確保目錄存在
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 儲存為 CSV
        csv_path = self.config.data_dir / f"{symbol}.csv"
        data.to_csv(csv_path)
        self.logger.info(f"已儲存 {symbol} 資料至 {csv_path}")
        
        # 如果設定要儲存到資料庫
        if self.config.save_to_db:
            self.save_to_database(symbol, data)
            
    def save_to_database(self, symbol: str, data: pd.DataFrame):
        """儲存資料到 SQLite 資料庫"""
        try:
            # 確保資料庫目錄存在
            db_path = Path(self.config.database.path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 連接資料庫
            conn = sqlite3.connect(str(db_path))
            
            # 儲存資料
            data.to_sql(
                f"stock_{symbol}",
                conn,
                if_exists='replace',
                index=True
            )
            
            conn.close()
            self.logger.info(f"已儲存 {symbol} 資料至資料庫")
            
        except Exception as e:
            self.logger.error(f"儲存 {symbol} 資料到資料庫時發生錯誤: {str(e)}")

    def save_to_parquet(self, df: pd.DataFrame, symbol: str):
        """
        將 DataFrame 存成 Parquet 檔
        """
        filepath = os.path.join(self.data_dir, f"{symbol}.parquet")
        df.to_parquet(filepath)

    def run(self, symbols: list, start_date: str, end_date: str):
        """
        批次下載多個股票資料，並根據設定儲存
        symbols: List of ticker strings
        """
        self.download_stock_data(symbols, start_date, end_date) 