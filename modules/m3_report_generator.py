import os
import pandas as pd
from pathlib import Path

class ReportGenerator:
    """
    M3: 績效篩選與報告模組
    功能:
      - 根據 performance_master.csv 進行排序與篩選
      - 支援 Top N/Top %、條件式篩選
      - 輸出 CSV / XLSX / HTML
    """
    def __init__(self, reports_dir: Path):
        self.reports_dir = Path(reports_dir)
        os.makedirs(self.reports_dir, exist_ok=True)

    def load_summary(self, summary_path: str) -> pd.DataFrame:
        df = pd.read_csv(summary_path)
        # 確保顯示所有關鍵欄位
        show_cols = ['strategy', 'symbol', 'param_id', 'params', 'total_return', 'max_drawdown', 'run_id']
        show_cols = [c for c in show_cols if c in df.columns]
        return df[show_cols + [c for c in df.columns if c not in show_cols]]

    def get_available_symbols(self, df: pd.DataFrame) -> list:
        """獲取可用的股票代碼列表"""
        return sorted(df['symbol'].unique().tolist())

    def filter_by_symbol(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """根據股票代碼篩選資料"""
        return df[df['symbol'] == symbol]

    def filter_top(self, df: pd.DataFrame, metric: str, top_n: int = None, top_percent: float = None) -> pd.DataFrame:
        df_sorted = df.sort_values(metric, ascending=False)
        if top_n is not None:
            return df_sorted.head(top_n)
        elif top_percent is not None:
            n = max(1, int(len(df_sorted) * top_percent / 100))
            return df_sorted.head(n)
        else:
            return df_sorted

    def apply_conditions(self, df: pd.DataFrame, conditions: str) -> pd.DataFrame:
        if not conditions:
            return df
        for cond in conditions.split(','):
            cond = cond.strip()
            if not cond:
                continue
            # 例：sharpe>=1.2, max_dd<=0.15
            if '>=' in cond:
                col, val = cond.split('>=')
                df = df[df[col.strip()] >= float(val.strip())]
            elif '<=' in cond:
                col, val = cond.split('<=')
                df = df[df[col.strip()] <= float(val.strip())]
            elif '>' in cond:
                col, val = cond.split('>')
                df = df[df[col.strip()] > float(val.strip())]
            elif '<' in cond:
                col, val = cond.split('<')
                df = df[df[col.strip()] < float(val.strip())]
            elif '==' in cond:
                col, val = cond.split('==')
                df = df[df[col.strip()] == float(val.strip())]
        return df

    def save_reports(self, df: pd.DataFrame, prefix: str, metric: str, export_format: str, symbol: str):
        # 使用指定的股票代碼
        csv_path = self.reports_dir / f"{prefix}_{symbol}_{metric}.csv"
        xlsx_path = self.reports_dir / f"{prefix}_{symbol}_{metric}.xlsx"
        html_path = self.reports_dir / f"{prefix}_{symbol}_{metric}.html"
        if export_format == 'csv':
            df.to_csv(csv_path, index=False)
        elif export_format == 'xlsx':
            df.to_excel(xlsx_path, index=False)
        elif export_format == 'html':
            df.to_html(html_path, index=False)

    def run(self, summary_path: str, metric: str, top_n: int = None, top_percent: float = None, conditions: str = '', export_format: str = 'csv', symbol: str = None):
        # 載入資料
        df = self.load_summary(summary_path)
        
        # 如果沒有指定股票代碼，顯示可用的股票列表並讓使用者選擇
        if symbol is None:
            available_symbols = self.get_available_symbols(df)
            print("\n可用的股票代碼：")
            for i, sym in enumerate(available_symbols, 1):
                print(f"{i}. {sym}")
            print("0. 直接輸入股票代碼")
            
            while True:
                choice = input("\n請選擇股票代碼編號或直接輸入股票代碼：").strip()
                
                # 檢查是否為數字
                if choice.isdigit():
                    choice_num = int(choice)
                    if choice_num == 0:
                        # 顯示可用的股票代碼供參考
                        print("\n可用的股票代碼：", ", ".join(available_symbols))
                        symbol = input("請輸入股票代碼：").strip().upper()
                        if symbol in available_symbols:
                            break
                        else:
                            print(f"錯誤：{symbol} 不在可用的股票代碼列表中")
                    elif 1 <= choice_num <= len(available_symbols):
                        symbol = available_symbols[choice_num-1]
                        break
                    else:
                        print("無效的選擇，請重新輸入")
                else:
                    # 直接輸入股票代碼
                    symbol = choice.strip().upper()
                    if symbol in available_symbols:
                        break
                    else:
                        print(f"錯誤：{symbol} 不在可用的股票代碼列表中")
        
        # 篩選指定股票的資料
        df = self.filter_by_symbol(df, symbol)
        
        # 應用其他篩選條件
        df = self.apply_conditions(df, conditions)
        df_top = self.filter_top(df, metric, top_n, top_percent)
        
        # 生成報告
        prefix = f"top{top_n or int(top_percent)}"
        self.save_reports(df_top, prefix, metric, export_format, symbol)
        print(f"已輸出報告至 {self.reports_dir}") 