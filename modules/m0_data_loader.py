import os
import time
import random
import datetime
import sqlite3
import pandas as pd
import yfinance as yf
from utils.config import Config

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
        # 確保資料夾存在
        self.data_dir = config.data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        # 資料庫位置
        self.db_path = config.database.path

    def download(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        下載單一股票在指定區間的歷史資料，包含分段與重試機制
        返回:
            pd.DataFrame: 以日期為索引，包含 OHLCV 欄位
        """
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        chunk_days = self.config.date_chunk_size
        max_retries = getattr(self.config, 'max_retries', 5)
        delay_base = self.config.download_delay

        all_chunks = []
        current_start = start_dt
        while current_start < end_dt:
            current_end = min(current_start + pd.Timedelta(days=chunk_days), end_dt)
            # yfinance 的 end 參數為不含當日，因此加一天
            yf_start = current_start.strftime('%Y-%m-%d')
            yf_end   = (current_end + pd.Timedelta(days=1)).strftime('%Y-%m-%d')

            attempt = 0
            while True:
                try:
                    df_chunk = yf.download(
                        symbol,
                        start=yf_start,
                        end=yf_end,
                        progress=False,
                        threads=False
                    )
                    if not df_chunk.empty:
                        all_chunks.append(df_chunk)
                    break
                except Exception as e:
                    if attempt >= max_retries:
                        print(f"[ERROR] {symbol} {yf_start}~{yf_end} 超過重試次數，跳過。錯誤: {e}")
                        break
                    wait = (2 ** attempt) * delay_base * random.uniform(0.5, 1.5)
                    print(f"[WARN] {symbol} 下載失敗，重試 {attempt+1}/{max_retries}，等待 {wait:.1f}s")
                    time.sleep(wait)
                    attempt += 1
            current_start = current_end

        if not all_chunks:
            return pd.DataFrame()

        # 合併、去重、排序
        df = pd.concat(all_chunks)
        df = df[~df.index.duplicated(keep='first')]
        df.sort_index(inplace=True)
        return df

    def save_to_db(self, df: pd.DataFrame, symbol: str):
        """
        將 DataFrame 存入 SQLite 資料庫
        """
        conn = sqlite3.connect(self.db_path)
        df.to_sql(symbol, conn, if_exists='append', index=True, index_label='date')
        conn.close()

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
        for symbol in symbols:
            print(f"[INFO] 下載 {symbol} 資料: {start_date} ~ {end_date}")
            df = self.download(symbol, start_date, end_date)
            if df.empty:
                print(f"[WARN] {symbol} 無資料，跳過儲存。")
                continue

            if getattr(self.config, 'save_to_db', False):
                try:
                    self.save_to_db(df, symbol)
                    print(f"[OK] {symbol} 資料已儲存至資料庫。")
                except Exception as e:
                    print(f"[ERROR] {symbol} 儲存至 DB 失敗: {e}")
            else:
                try:
                    self.save_to_parquet(df, symbol)
                    print(f"[OK] {symbol} 資料已儲存至 Parquet。")
                except Exception as e:
                    print(f"[ERROR] {symbol} 儲存 Parquet 失敗: {e}") 