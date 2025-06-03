# QUANTA II 系統重構說明文件

## 🔧 專案目標

重新設計量化交易系統「QUANTA II」，以解決舊版模組優化與再回測階段的除錯與維護困難，並建立模組化、穩定、可擴充的開發架構。

## 📦 系統模組設計（V1.0）

| 模組代號 | 模組名稱             | 功能說明 |
|----------|----------------------|----------|
| M1       | 資料載入模組         | 載入股票歷史資料（Yahoo/CSV） |
| M2       | 策略定義模組         | 策略邏輯封裝為可重複調用函式 |
| M3       | 回測模組             | 回測單一策略並產出績效與交易紀錄 |
| M4       | 參數優化模組         | 對策略進行參數掃描與貝葉斯最佳化 |
| M5       | 再回測（樣本外驗證） | 使用最佳參數進行樣本外測試 |
| M6       | 結果資料庫模組       | 儲存回測與優化結果（SQLite）並匯出報表 |

## 📁 預設目錄結構

```
Quanta II/
├── DATA/
├── STRATEGY/
├── BACKTEST/
├── OPTIMIZATION/
├── DATABASE/
├── DOC/
├── CONFIG/
└── utils/
```

## 📌 技術選型

- 語言：Python 3.11+
- 儲存：SQLite
- 優化：Grid + Bayesian
- 視覺化：matplotlib + Streamlit
- 支援：MCP plugin / GitHub CI

## 🔄 建議開發順序

1. 策略模板（ex. 雙均線）
2. 回測模組（產出交易紀錄）
3. 績效寫入 DB（含 Sharpe, return…）
4. 優化與參數規則設計
5. 樣本外驗證
6. 匯出報告（HTML/Excel）

## ✅ 範例指令

```bash
python main.py --mode backtest --strategy sma_cross.yaml
```

---

完成後，我可以馬上幫你建立第一個模組的範本，例如：
- `strategy_template.py`
- `run_backtest.py`
- `config.yaml`

你希望先從哪一塊開始？（例如策略定義、資料匯入或回測模組）
