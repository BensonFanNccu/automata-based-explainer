# 第二次複驗報告：作者第二批修正後的檢查

日期：2026-09-10
審查對象：commit `43bc43d`（作者在第一次複驗版本 `2359c33` 之後推出的 12 個 commit）
前一份報告：[`../2026-09-09_rerun/UPDATE_REPORT.md`](../2026-09-09_rerun/UPDATE_REPORT.md)
最初的完整報告：[`../2026-09-07_initial/review_report.md`](../2026-09-07_initial/review_report.md)

---

## 這次做了什麼

第一次複驗（2026-09-09）確認作者修掉了大部分問題，但也列出四條仍然成立的發現，以及一條當時新發現的問題。作者接著推出 12 個 commit，內容幾乎全部針對這些項目。

這次的工作是把新版程式碼拉下來，對前一份報告列出的每一條剩餘發現逐一實測，確認修正是否真的生效，並且檢查這批新增的程式碼有沒有帶進新的問題。所有實測的完整輸出保留在 [`verification_log.txt`](verification_log.txt)，共九項驗證，每一項在下文都會標出對應的段落編號。

---

## 前一輪剩餘發現的處理狀況

### 已修正，並且經過實測

**上一輪新發現的 Unicode τ 問題（`make_plots.py:238`）已修正。** caption 從原本直接寫入的 τ 字元改成 `$\tau = {threshold}$`。實測執行 `make_plots.py` 之後，`combo_tau08` 成功產出 `(+ .png)`，不再出現 pdflatex 的 fatal error（驗證記錄第 2 段）。作者同時修掉了另一個相關問題：`comparison_figure` 的 caption 原本把 batch size 寫死成 1000，現在改成動態帶入實際的 `batch_size`。

**B8 與 R3：`parse_results.py` 只掃描沒有任何程式會建立的目錄。** 已修正。新的 `find_experiment_logs()` 會遞迴走訪 `test_result/` 底下所有目錄名符合 `CONFIG_RE` 的資料夾，找到就不再往下深入，不需要手動把結果搬到 `final_result/`。同一組 (domain, threshold, batch_size) 如果出現在多個位置，會取修改時間最新的那一份並印出提示。實測在完整跑完實驗之後直接執行 `python analysis/parse_results.py`，順利產出 24 列的 `summary_table.csv`（驗證記錄第 1 段）。從實驗結果到論文圖表的整段流程，現在照文件走是通的。

**R4：`RUNNING.md` 沒有說明初始 DFA 的隱藏限制。** 已修正。文件新增了一整節「實驗中限制初始 DFA 狀態數」，說明搜尋方法本身不要求特定狀態數，這道篩選是為了讓各任務都能看出狀態數下降的趨勢而刻意加的；同時寫出 `init_state_range=(25, 65)` 是 `automata_beam()` 裡的固定值、目前沒有開放 CLI 覆蓋、重試上限是 `max_init_attempts=40`、40 次都不落在範圍內就整筆跳過並印出 `[ERROR] Initial DFA construction failed`，最後也說明了 `--init_num_samples` 與初始狀態數的關係。

**A1：Validation 欄位的語意描述。** 描述改得更精確，從「與初始 DFA 的一致率」改成「與初始 DFA 建構樣本的一致率」，這個說法與程式行為完全相符。指標本身沒有改變，所以這一欄仍然不是 held-out 的泛化指標，六個任務的起始值仍然都是 1.0000；差別在於現在文件把它講清楚了。

**先前文件描述的 `results.csv` 並不存在。** 已修正。`RUNNING.md` 第 4 節改成正確描述純文字 log 的實際格式，並說明需要機器可讀的 CSV 時要透過 `analysis/parse_results.py` 產生 `summary_table.csv`，欄位也逐一列出。

### 機制已打通，但實質問題尚未解決

**A10：調參腳本選出的 baseline 參數從未被主實驗讀取。** 機制上已經打通。`src/experiments/runner.py` 新增了 `_find_latest_tuned_params_csv()` 與 `_load_tuned_baseline_params()`，會自動尋找 `test_result/tune_*/best_by_algo_cross_task.csv` 裡最新的一份並套用；找不到時退回原本寫死的預設值。我造了一份探測用的 CSV（刻意把 SA candidate pool 設成 7、GA population 設成 13、PSO 設成 9/11/3），實測確認這些值真的會走到執行路徑上，log 印出 `[SA] Running 15 steps ... candidate_pool=7` 與 `[GA-Gen] Generation 1, evals: 14/100`（驗證記錄第 3 與第 4 段）。

實質問題仍然存在。我檢查作者附在 repo 裡的兩份參考結果 log，`[Tuned params]` 出現次數都是 0（驗證記錄第 8 段），代表這批參考結果是用寫死的預設值（SA pool=10、GA population=10、PSO particles=5/pool=5）產生的，並沒有套用任何調參結果。因此如果論文 5.3 節宣稱主實驗使用了調校過的 baseline 參數，而論文表格用的是這批參考結果，那個宣稱與數字仍然對不上。要讓兩者一致，需要在跑過調參之後重新產生一次主實驗結果。

### 部分修正，並且在文件中誠實揭露

**A11：每個任務實際只跑一個 test instance。** 這一輪的處理分成三個部分。

第一，`RUNNING.md` 現在直接寫明：「上面兩個指令都只跑每個任務固定的單一 test instance，不會取平均、沒有變異數」，並且明確說出「論文表格裡每一格因此是單一 instance 的單次數字，不是多次重複的平均」。這是把問題正面講清楚，不再需要讀者自己從程式碼推斷。

第二，`--num_test_instances N` 確實可以運作。實測傳入 3 之後，程式印出 `Selected test instances: 3`，並依序跑完 instance_00、instance_01、instance_02（驗證記錄第 4 段）。

第三，新增了 `print_averaged_summary()`，會依任務分組印出跨 instance 的 mean 與標準差，並且標示有效 instance 數（例如 `n=3/3 valid instances`），失敗的 instance 會被排除且如實顯示。函式本身的計算正確，實測輸入 states = 3, 4, 5 得到 mean 4.00（驗證記錄第 6 段）。

要注意的是預設指令仍然是單一 instance，而平均表格也不會自動印出。`RUNNING.md` 對後者有明確說明：「`experiment_log.txt` 預設只印出每個 instance 各自的表格，不會自動平均」，需要平均時自行 `from experiments.runner import print_averaged_summary` 後呼叫即可。

---

## 這次新發現的問題

### 調參結果自動載入形成隱藏的全域狀態，反而傷害可重現性

`_find_latest_tuned_params_csv()` 用 `glob` 搜尋 `test_result/tune_*/best_by_algo_cross_task.csv`，只要 `test_result/` 底下存在任何以 `tune_` 開頭的目錄，主實驗就會自動套用裡面的 baseline 參數。我實測用的目錄叫 `tune_probe_test`，並不是調參腳本預設的 `tune_fairflow_baselines_<timestamp>`，一樣被撿到並套用（驗證記錄第 3 與第 4 段），可見比對條件相當寬鬆。

同時有三個條件疊在一起，使這件事變成可重現性問題。第一，兩支實驗腳本都沒有提供任何可以停用自動載入的 CLI 旗標（驗證記錄第 9 段）。第二，`.gitignore` 排除了 `test_result/**`，只有兩份 `experiment_log.txt` 被 force-add 進版控，所以調參結果永遠不會隨 repo 散布，使用者拿不到作者的那一份。第三，作者附的參考結果是用預設值產生的。

實際會發生的情況是這樣：使用者照 `README.md` 第 5.3 節跑過一次調參，之後再跑主實驗，baseline 參數就被靜默換掉了，結果自然與參考結果不同；而 `RUNNING.md` 第 5 節仍然要求使用者拿新結果去對照參考結果的三個趨勢。使用者只會看到一行 `[Tuned params] Using ...`，不容易聯想到這正是數字對不上的原因。

建議的處理方式有幾種，可以擇一。最直接的是加一個 `--no_tuned_params` 旗標，讓使用者能明確關掉。更保守的做法是把自動搜尋改成必須明確傳入 CSV 路徑才套用，也就是讓「使用調參結果」成為一個明示的選擇。若要保留現在的行為，至少應該在參考結果的說明裡註明它是用預設參數產生的，並提醒使用者跑過調參之後不能再直接與參考結果比對。

---

## 可重現性驗證：為什麼不需要再完整重跑一次

這次沒有再花兩小時做完整重跑，判斷依據有兩層，兩層都有實測支持。

第一層，核心演算法的五個檔案在這批 commit 裡完全沒有變動，包括 `src/learner/dfa_learner.py`、`src/explainer/automata_beam.py`、`src/baselines/search_baselines.py`、`src/automaton/load_dfa.py` 與 `src/automaton/dfa_utils.py`（驗證記錄第 7 段）。這批改動集中在分析腳本、文件，以及 `runner.py` 的 baseline 參數載入。

第二層，`runner.py` 確實改動了 `run_baseline()` 傳遞參數的路徑，所以我用與 2026-09-08 完全相同的參數重跑了一次小規模實驗來檢查這條路徑。在沒有任何 `tune_*` 目錄的情況下，結果與當時逐項相同：初始 DFA 31 個狀態、初始 training agreement 0.8700、BeamSearch 0.8980 搭配 30 個狀態、SA 0.8250 搭配 16 個狀態、GA 0.8350 搭配 20 個狀態、PSO 0.8750 搭配 25 個狀態（驗證記錄第 5 段）。log 中也沒有出現 `[Tuned params]`，確認預設路徑的行為沒有被這批改動影響。

兩層合起來可以推論：在沒有調參結果的乾淨環境下，完整重跑會得到與 2026-09-09 那次一致的結果。如果需要一份專門針對 `43bc43d` 的完整 log 留檔，另外再跑一次即可，預期結果不變。

另外，全部 Python 檔通過語法檢查，`tune_baseline_params.py` 這次移除的兩個函式（`write_summary_text()` 與 `write_best_by_algo_table()`）沒有留下任何殘留呼叫，該模組可以正常載入。

---

## 整體評價

作者對這份審查的回應，在兩輪之後已經相當完整。最初報告的 41 條發現裡，會導致程式崩潰或產生錯誤資料的問題基本上都清掉了；影響論文結論的 A 組問題，也只剩下實驗設計層面的部分尚未變動。從實驗執行到論文圖表的整段流程，現在照文件走是通的，這是這一輪最實際的進展：`parse_results.py` 不再需要手動搬移資料，`make_plots.py` 產生的 `.tex` 也能正常編譯。

可重現性的表現值得特別肯定。在有平行處理與隨機取樣的研究程式碼裡，能做到跨機器逐位元相同並不常見，作者透過固定 `PYTHONHASHSEED` 與排序 alphabet 達成了這件事。

剩下的問題可以分成兩類。第一類是需要作者做決定、而不是修程式的，主要是兩件事：預設指令仍然只跑單一 test instance，所以論文表格每一格都是單次結果，方法之間的勝負沒有統計基礎（文件已經誠實揭露這一點，但要不要改成多 instance 並報平均，是論文層面的取捨）；以及參考結果並沒有套用調參參數，如果論文宣稱使用了調校後的 baseline，需要重新產生一次結果讓兩者對齊。

第二類是這次唯一的新發現，也是小範圍修改就能處理的：把調參結果的自動載入改成可以關閉，或改成必須明確指定才套用。這一條不影響現有結果的正確性，但如果不處理，跑過調參的使用者會拿到與參考結果不同的數字，卻難以判斷原因出在哪裡。
