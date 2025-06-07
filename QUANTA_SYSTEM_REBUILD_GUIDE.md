# QUANTA II 系統開發說明文件：M0 ~ M3 架構與檔案規劃

## 「開發目標」

建立一套模組化、資料儲存清晰、互動性佳的量化交易回測系統。整體流程分為四大模組：

* M0：歷史資料下載模組
* M1：策略信號產生模組
* M2：策略回測與績效分析模組
* M3：績效篩選與報告產出模組

每個模組的程式執行後會產出獨立檔案，並更新對應的 Master Summary 作為全局彙整表。

---

## M0：歷史資料下載模組

### 使用者輸入選項

| 選項名稱              | 說明              | 範例                 |
| ----------------- | --------------- | ------------------ |
| Stock Name        | 股票代碼清單          | "AAPL, TSLA, MSFT" |
| Start Date        | 開始日期            | "2020-01-01"       |
| End Date          | 結束日期            | "2023-12-31"       |
| Save to DB        | 是否儲存至 SQLite DB | True / False       |
| 自動補資料             | 是否只補缺漏部份        | True / False       |
| Source            | 資料來源平台          | "yfinance"（預設）     |
| max_workers      | 同時下載股票數上限       | 2~3（建議）           |
| download_delay   | 每支股票下載延遲（秒）     | 1~3               |
| date_chunk_size | 長時間段自動分段大小      | 180（建議）            |

### 檔案儲存路徑

* `/data/*.parquet`（或寫入資料庫 `stock_price.db`）

---

## M1：策略信號產生模組

### 使用者輸入選項

| 選項名稱            | 說明                    | 範例                     |
| --------------- | --------------------- | ---------------------- |
| Strategy Name   | 策略邏輯類型                | "SMA_CROSS"、"RSI_BB" |
| Stock Name      | 股票清單                  | "AAPL, TSLA"           |
| Start Date      | 起始日期                  | "2020-01-01"           |
| End Date        | 結束日期                  | "2023-12-31"           |
| 參數輸入方式          | 自動產生 / 手動指定           | "Auto" / "Manual"      |
| 輸出格式            | signal 檔案格式           | "csv" / "parquet"      |
| 是否匯出 param_log | 是否輸出 param_id 與參數對照表 | True（建議）               |

### 輸出檔案

* `signals/<strategy>_<param_id>.csv`
* `signals/param_log_<strategy>_<timestamp>.json`
* `signals/signal_param_map.json`（signal → param_log 對應表）

### 可選

* `signals_master.csv`（所有 signal 合併紀錄）

---

## M2：策略回測與績效分析模組

### 使用者輸入選項

| 選項名稱        | 說明                 | 範例                             |
| ----------- | ------------------ | ------------------------------ |
| Signal 檔案路徑 | signal CSV 檔或資料夾路徑 | "signals/SMA_CROSS_0001.csv" |
| 初始資金        | 回測起始資本             | 100000                         |
| 手續費率        | 每筆交易手續費            | 0.001425                       |
| 滑點          | 成交價格偏移模擬           | 0.0005                         |
| 交易時機        | 下單時點               | "next_open"（預設）               |
| 倉位配置        | 固定下單股數或資金比例        | "fixed=100" / "percent=0.1"    |
| 匯出績效結果      | 是否輸出 performance 檔 | True（預設）                       |
| 匯出 NAV 序列   | 是否輸出每日資產變化         | True（預設）                       |

### 系統自動行為

* 根據 signal_param_map 自動找 param_log
* 自動 append 至 `performance_master.csv`

### 輸出檔案

* `results/performance_<strategy>_<run_id>.csv`
* `results/nav_<strategy>_<run_id>.parquet`
* `results/performance_master.csv`

---

## M3：績效篩選與報告模組

### 使用者輸入選項

| 選項名稱         | 說明               | 範例                                |
| ------------ | ---------------- | --------------------------------- |
| Summary 檔案路徑 | M2 輸出的 summary 表 | "results/performance_master.csv" |
| 排序依據         | 指標欄位名稱           | "sharpe_ratio"、"total_return"   |
| Top 組合數量     | 前 N 策略或前 N%      | "top_n=10"、"top_percent=5"      |
| 篩選條件         | 條件式篩選邏輯          | "sharpe>=1.2, max_dd<=0.15"      |
| 輸出格式         | 匯出報表格式           | "csv"、"xlsx"、"html"               |
| 圖表類型         | 選擇是否含圖表          | "equity, radar, drawdown"         |

### 輸出檔案

* `reports/top10_sharpe.html`
* `reports/top10_sharpe.xlsx`
* `reports/top10_sharpe.csv`

---

## 📁 資料夾與檔案總覽

```
Quanta II/
├── data/                        # M0 輸出歷史價格
├── signals/                    # M1 輸出 signals 檔與參數對照表
│   ├── SMA_CROSS_0001.csv
│   ├── param_log_SMA_CROSS_0001.json
│   └── signal_param_map.json
├── results/                    # M2 輸出回測績效與每日 NAV
│   ├── performance_SMA_CROSS_0001_20250610.csv
│   ├── nav_SMA_CROSS_0001_20250610.parquet
│   └── performance_master.csv
├── reports/                    # M3 輸出篩選後報告
│   ├── top10_sharpe.xlsx
│   └── top10_sharpe.html
```

---

## ✅ 小結

* 每個模組皆產出獨立檔案，不相互耦合
* M2 執行時自動對應 param_log，不需人工輸入
* 所有歷史回測結果統一儲存於 performance_master.csv
* 使用者只需記住 signal 檔案，系統可自動追溯參數與策略類型
