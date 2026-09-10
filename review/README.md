# 程式碼審查資料夾

這個資料夾放的是對本 repo 所做的程式碼審查，以及作者兩批修正之後的複驗紀錄。審查期間 repo 的程式碼沒有被修改，只新增了這個資料夾。

資料夾依日期分成三個階段，每個階段各自包含當次的報告與佐證資料。

## 建議的閱讀順序

想知道每一條發現目前的狀態，從最新的一份開始讀：

1. [`2026-09-10_recheck/RECHECK_REPORT.md`](2026-09-10_recheck/RECHECK_REPORT.md) 是最新的複驗報告，逐條交代前一輪剩餘發現的處理狀況。
2. [`2026-09-09_rerun/UPDATE_REPORT.md`](2026-09-09_rerun/UPDATE_REPORT.md) 是第一次複驗報告，需要追溯前一輪的判定依據時再回頭讀。
3. [`2026-09-07_initial/review_report.md`](2026-09-07_initial/review_report.md) 是最初的完整報告，描述的是還沒有任何修正的版本，作為發現編號（A1、B3、R2 等）的定義來源。

## 各階段內容

### `2026-09-07_initial/` — 最初的完整審查

審查對象是 commit `79d7a04`，共提出 41 條發現，分成 A 組（會影響論文結論）、B 組（會 crash 或產生錯誤資料）、C 組（待驗證的疑點）、R 組（照文件重現時會卡住），另有 16 條經驗證後否決的候選。

- `review_report.md` 與 `review_report.html` 是同一份最終報告的兩種格式，HTML 版排版較完整，下載後用瀏覽器開啟即可。
- `review_local_findings.md` 是 9 月 2 日本機審查流程被停止前輸出的已驗證結果。
- `review_learner.md`、`review_beam.md`、`review_experiments.md` 是 9 月 7 日三條審查線各自的原始報告，每一條發現的實測數據與驗證方式都在裡面。
- `smoke_run/` 是在乾淨的 Python 3.11 環境裡照 README 與 RUNNING.md 實際執行的完整 log，包含兩次安裝嘗試與三次實驗執行。
- `verification/` 是三條審查線用來實測的 Python 腳本，執行時需要另外取得 aalpy 與 numpy 的原始碼，各腳本開頭有說明。

### `2026-09-09_rerun/` — 作者第一批修正後的複驗

審查對象是 commit `2359c33`（作者在 `79d7a04` 之後推出的 36 個 commit）。這一輪照 RUNNING.md 的指令完整重跑了兩條實驗，並逐條檢視 41 條發現在新版的狀態。

- `UPDATE_REPORT.md` 是這一輪的報告。
- `full_run.log` 是完整重跑的輸出，`run_all.sh` 是實際執行的腳本。
- `determinism_check.txt` 記錄重跑結果與作者附帶參考結果的比對，兩者的 agreement 與 state 數逐位元相同。

### `2026-09-10_recheck/` — 作者第二批修正後的複驗

審查對象是 commit `43bc43d`（作者在 `2359c33` 之後推出的 12 個 commit）。這一輪針對前一份報告列為「仍然成立」的發現逐一實測。

- `RECHECK_REPORT.md` 是這一輪的報告。
- `verification_log.txt` 是九項實測的完整記錄，報告裡每個結論都標了對應的段落編號。
- `recheck.sh` 是產生那份記錄的腳本，可以重跑。
