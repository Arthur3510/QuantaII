import os
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class DatabaseConfig:
    path: str = "data/stock_price.db"

@dataclass
class Config:
    # 資料目錄
    data_dir: Path = Path("data")
    signals_dir: Path = Path("signals")
    results_dir: Path = Path("results")
    reports_dir: Path = Path("reports")
    
    # 資料庫設定
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    # 下載設定
    date_chunk_size: int = 30  # 減少分段下載天數
    download_delay: float = 5.0  # 增加下載延遲（秒）
    max_retries: int = 10  # 增加最大重試次數
    save_to_db: bool = False  # 是否儲存至資料庫

    @classmethod
    def load(cls) -> 'Config':
        """載入配置"""
        config = cls()
        
        # 確保所有目錄存在
        for dir_path in [config.data_dir, config.signals_dir, 
                        config.results_dir, config.reports_dir]:
            os.makedirs(dir_path, exist_ok=True)
            
        return config 