# QUANTA 系統重構指南

以下內容匯總了與 ChatGPT 討論 M1 模組設計、資料串接、下載邏輯，以及 GitHub 操作相關的對話要點，並示範如何在本地 Jupyter 介面中使用 M1 拉取股票資料、分段下載、避免速率限制，最終將說明寫入 GitHub。請確認已將此檔案推送至你的遠端 Repo。

---

## 一、M1 模組整體架構

### 1.1 使用者操作流程
1. 在本地端 Jupyter Notebook 中執行 `fetch_stock_data` 函式（M1 模組）。
2. 使用者在介面上輸入：
   - Stock Name（可同時輸入多個股票代碼，例如 `"AAPL,TSLA,MSFT"`）
   - Start Date（例如 `"2020-01-01"`）
   - End Date（例如 `"2025-01-01"`）
   - Save to DB（`True` 或 `False`）
   - Auto Chunk（`True` 或 `False`，決定是否自動分段下載）
   - Source（預設 `"yfinance"`，可擴充到其他 API 平台）
   - Max Workers（限制平行下載數量，建議 2～3）
   - Download Delay（每支股票間暫停時間，建議 1～3 秒）

### 1.2 M1 後端處理步驟
1. **檢查本地資料庫**  
   - 連接至 SQLite（或其他 Cache 層，例如 CSV／Parquet）。  
   - 針對每個股票（`ticker`），查詢從 `start_date` 到 `end_date` 之間，資料庫是否已有完整紀錄。  
   - 將缺失的日期區段記錄下來，如 AAPL 缺少 2022-07-01 至 2025-01-01。

2. **分段 (Chunk) + 平行 (Max Workers) + 延遲 (Download Delay)**  
   - 若設定 `auto_chunk=True`，將每個缺失區段再拆成更小區段（建議半年或一年一段）。  
   - 使用 `ThreadPoolExecutor(max_workers=<max_workers>)` 平行下載多支股票各自的一段資料。  
   - 每段下載完成後立即睡眠 `random.uniform(<download_delay_range>)`，例如 1～3 秒，避免 yfinance API 被速率限制。 若非自動分段，也可以整段一次呼叫，但建議改為分段下載。

3. **將下載結果寫回本地 DB**  
   - 每次從 yfinance 獲得 DataFrame 後，用 `INSERT OR IGNORE` 將資料存回 SQLite 的 `stock_prices` 表格。  
   - 此步驟確保即使程式中途終止，已下載之區段仍保留，下次執行時可跳過。

4. **回傳完整資料給前端**  
   - 當所有缺失區段都已下載並存入庫中後，對每支股票做一次 `SELECT … WHERE date BETWEEN start_date AND end_date`。  
   - 將查到的完整歷史價格 DataFrame 放入字典並回傳給 Notebook。

5. **Notebook 顯示與後續分析**  
   - 使用者在 Jupyter Notebook 中呼叫 `fetch_stock_data(...)` 後，會拿到類似：
     ```python
     {
       "AAPL": df_AAPL_2020_2025,
       "TSLA": df_TSLA_2020_2025,
       ...
     }
     ```
   - Notebook 端可以直接 `display(df)` 或 `df["Close"].plot()` 做視覺化，或再匯出 CSV/Excel 做後續分析。

---

## 二、具體參數與需求整合

1. **Stock Name**  
   - 可同時輸入多支股票，格式以逗號分隔（例如：`"AAPL,TSLA,MSFT"`），後端會自動拆解成 List。

2. **Start Date / End Date**  
   - 範例：`"2020-01-01"`、`"2025-01-01"`，表示要拉取的歷史資料時間區間。

3. **Save to DB (True/False)**  
   - `True`：下載後寫回 SQLite 做快取，下次不必重複下載。  
   - `False`：僅在記憶體層面處理，不寫回本地庫。

4. **Auto Chunk (True/False)**  
   - `True`：若下載區段過長，自動將缺失的時間拆成多段，再依序呼叫 yfinance 下載。  
   - `False`：一次拉取完整區段，但若遇到 API 速率限制可能失敗。

5. **Source**  
   - 預設 `"yfinance"`，若未來要支援其他付費 API（IEX Cloud、Tiingo、Polygon.io、Alpha Vantage、Nasdaq Data Link），可在這欄輸入 `"iexcloud"`、`"tiingo"`、等，有對應的後端邏輯。

6. **Max Workers (預設 2～3)**  
   - 同一時間並行下載的最大支數。  
   - 建議值：2～3，可避免同時呼叫過多造成 API 拒絕。

7. **Download Delay**  
   - 每次下載一支（或一段）後，暫停 1～3 秒再繼續，以免 yfinance 被擋。  
   - 可設成常數，也可用隨機區間 `random.uniform(1, 3)`。

---

## 三、分段下載邏輯範例

以下示範如果 AAPL 缺失 2022-07-01 至 2025-01-01 時，自動切成 3 段下載：

```python
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import time, random

def get_missing_ranges(cursor, ticker, start_date, end_date):
    """
    查詢本地 DB，判斷該 ticker 在 start_date ~ end_date 有哪些缺資料區段，
    回傳 [(seg_start, seg_end), ...]
    """
    # 先查找已存在的最早 & 最晚日期
    cursor.execute("""
      SELECT MIN(date), MAX(date)
      FROM stock_prices
      WHERE ticker = ? AND date BETWEEN ? AND ?
    """, (ticker, start_date, end_date))
    row = cursor.fetchone()
    if row[0] is None:
        # 完全沒資料 → 整區段需要下載
        return [(start_date, end_date)]

    existing_min = datetime.strptime(row[0], "%Y-%m-%d")
    existing_max = datetime.strptime(row[1], "%Y-%m-%d")

    missing = []
    # 檢查 (start_date ~ existing_min - 1)
    if existing_min > datetime.strptime(start_date, "%Y-%m-%d"):
        missing.append((start_date, (existing_min - timedelta(days=1)).strftime("%Y-%m-%d")))
    # 檢查 (existing_max + 1 ~ end_date)
    if existing_max < datetime.strptime(end_date, "%Y-%m-%d"):
        missing.append(((existing_max + timedelta(days=1)).strftime("%Y-%m-%d"), end_date))
    return missing

def chunk_ranges(seg_start, seg_end, chunk_days=180):
    """
    把一個長區段切成多個 chunk_days（預設 180 天）的小區間
    """
    start_dt = datetime.strptime(seg_start, "%Y-%m-%d")
    end_dt   = datetime.strptime(seg_end, "%Y-%m-%d")
    chunks = []
    cur = start_dt
    while cur < end_dt:
        nxt = cur + timedelta(days=chunk_days)
        if nxt > end_dt:
            nxt = end_dt
        chunks.append((cur.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")))
        cur = nxt + timedelta(days=1)
    return chunks

def download_segment(ticker, seg_start, seg_end, download_delay):
    """
    用 yfinance 下載一段日期區間
    並自動暫停 download_delay 秒
    """
    df = yf.download(ticker, start=seg_start, end=seg_end, progress=False)
    df.reset_index(inplace=True)
    df["Ticker"] = ticker
    time.sleep(random.uniform(*download_delay))
    return df

def save_dataframe_to_db(df, conn):
    """
    把 DataFrame 的資料寫回本地 SQLite
    """
    records = []
    for idx, row in df.iterrows():
        records.append((
            row["Ticker"],
            row["Date"].strftime("%Y-%m-%d"),
            row["Open"], row["High"], row["Low"], row["Close"], int(row["Volume"])
        ))
    cursor = conn.cursor()
    cursor.executemany("""
      INSERT OR IGNORE INTO stock_prices
      (ticker, date, open, high, low, close, volume)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, records)
    conn.commit()

def fetch_stock_data(
    stock_list,
    start_date,
    end_date,
    save_to_db=True,
    auto_chunk=True,
    source="yfinance",
    max_workers=2,
    download_delay=(1,3)
):
    # 1. 連接本地 SQLite
    conn = sqlite3.connect("local_stock_data.db")
    cursor = conn.cursor()

    result_dict = {}
    for ticker in stock_list:
        # 2. 檢查缺失區段
        missing = get_missing_ranges(cursor, ticker, start_date, end_date)

        # 若不缺資料，直接拉出完整區段
        if not missing:
            cursor.execute("""
              SELECT date, open, high, low, close, volume
              FROM stock_prices
              WHERE ticker = ? AND date BETWEEN ? AND ?
              ORDER BY date ASC
            """, (ticker, start_date, end_date))
            rows = cursor.fetchall()
            df_full = pd.DataFrame(rows, columns=["date","open","high","low","close","volume"])
            df_full["date"] = pd.to_datetime(df_full["date"])
            result_dict[ticker] = df_full
            continue

        # 3. 針對缺失區段逐一下載
        to_download = []
        for (seg_start, seg_end) in missing:
            if auto_chunk:
                to_download += chunk_ranges(seg_start, seg_end)
            else:
                to_download.append((seg_start, seg_end))

        # 平行下載所有缺失小區段
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for (seg_start, seg_end) in to_download:
                futures.append(executor.submit(
                    download_segment,
                    ticker, seg_start, seg_end, download_delay
                ))
            for f in futures:
                seg_df = f.result()  # DataFrame
                if save_to_db:
                    save_dataframe_to_db(seg_df, conn)

        # 4. 重新查詢並組成完整 DataFrame
        cursor.execute("""
          SELECT date, open, high, low, close, volume
          FROM stock_prices
          WHERE ticker = ? AND date BETWEEN ? AND ?
          ORDER BY date ASC
        """, (ticker, start_date, end_date))
        rows = cursor.fetchall()
        df_full = pd.DataFrame(rows, columns=["date","open","high","low","close","volume"])
        df_full["date"] = pd.to_datetime(df_full["date"])
        result_dict[ticker] = df_full

    conn.close()
    return result_dict
