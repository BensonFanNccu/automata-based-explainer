# 更新版審查報告：作者修正後的重新驗證

日期：2026-09-09
審查對象：commit `2359c33`（作者在原審查版本 `79d7a04` 之後推出的 36 個 commit）
原始報告：[`../review_report.html`](../review_report.html)

---

## 這次做了什麼

原始報告針對 commit `79d7a04` 提出 41 條發現，分成 A（會影響論文結論）、B（會 crash 或產生錯誤資料）、C（待驗證的疑點）、R（照文件重現時會卡住）四組。作者後續推出 36 個 commit，其中大量直接對應這些發現，有些修正的註解甚至寫出了與原報告相同的成因分析。

這次做的事情有三項。第一是把作者最新的程式碼拉下來，照 `RUNNING.md` 第 2 節記載的兩條指令完整跑一次實驗。第二是把重跑結果與作者附在 repo 裡的參考結果逐項比對，確認可重現性。第三是回頭逐條檢視原始報告的 41 條發現，判斷每一條在新版的狀態，並且盡可能用實際執行或直接閱讀修正後的程式碼來佐證，而不是只看 commit 訊息。

執行環境是 Python 3.11、libmata 已編譯完成的乾淨 venv。實際執行的腳本保留在 [`run_all.sh`](run_all.sh)，完整輸出保留在 [`full_run.log`](full_run.log)。

---

## 執行結果

兩條指令都順利跑完，exit code 都是 0。regular 實驗花費 42 分鐘，real-world 實驗花費 88 分鐘。整份 log 裡沒有出現任何 traceback、`[ERROR]` 或警告，這一點與原始報告當時的情況有明顯差別：當時照 README 安裝完成後執行，會先看到 `ExplainLanguage not available` 的警告，接著兩條重現指令都會因為輸出資料夾已存在而直接失敗。

### 可重現性完全成立

把重跑結果和作者附帶的參考結果比對之後，六個任務、四個方法、共 24 列的 agreement 數值與 state 數**全部逐位元相同**。不只最終表格相同，beam search 每個 iteration 寫出的 MATA transition 數量（217、203、196、189……）也完全一致。兩份 log 之間的差異只有執行時間，以及作者機器路徑 `/home/yihua/anchor-llm/` 與本機路徑的不同。比對過程保留在 [`determinism_check.txt`](determinism_check.txt)。

達成這個結果的關鍵修正是 commit `9e56c0a`。作者在兩支實驗腳本開頭把 `PYTHONHASHSEED` 釘成 `0`，同時把 `get_alphabet()` 回傳的 set 明確排序後才使用。原始報告的 C 組曾經指出，regular 任務的 alphabet 順序來自 set，即使固定了 random seed 也無法跨行程重現，這條發現現在已經被正面解決。

順帶一提，`RUNNING.md` 第 5 節目前仍然寫著「本專案多浮點數運算，不同機器跑出來的數字不會逐位元相同，所以不要比對到小數點」。這句話在現在的版本已經不成立，實際上可以直接比對數值，建議更新。

### 論文宣稱的三個趨勢都成立

`RUNNING.md` 第 5 節列出三個應該觀察到的趨勢，這次重跑全部符合。

第一，beam 在全部六個任務都是執行時間最短的方法。第二，在最終 DFA 的 state 數上，beam 沒有輸給任何一個 baseline：在 DocumentReleaseWorkflow、MultiObligationOrder、SecureHandshake、mnist 四個任務上與最佳 baseline 並列，在 ECG（3 對 8）與 wafer（24 對 30）兩個任務上明顯勝出。第三，除了 wafer 之外的任務，beam 都達到 0.8 的 agreement 門檻，其中 mnist 的 0.8154 達標、wafer 的 0.7942 未達標，與文件描述一致。

需要注意的是，這些比較的基礎仍然是每個任務只有一個 test instance，詳見下方 A11。

---

## 原始報告發現的處理狀況

### 已修正，並且經過實際驗證

**A2：MERGE 的提案名額被必定會被拒絕的 initial state 配對佔滿。** 已修正。`src/learner/dfa_learner.py:1252` 起把 initial state 的過濾移到評分與 `max_pairs` 截斷之前，註解明確寫出這些配對「在觀察到的案例中會佔滿全部 top slots」。

**A3：MERGE 會無條件依路徑多數標籤改寫合併後狀態的 accepting 屬性。** 已修正。現在只有在 `s1` 與 `s2` 的 accepting 狀態不一致時才會查詢 `majority_labels`，兩者一致時直接沿用原本的屬性。

**A4：DELTA 在三個 regular 任務裡從未產生過候選。** 已修正，並且用實跑證實。這次執行中 DELTA 操作出現 166 次，平均每次產生 17.5 個候選。原始報告判斷成因是 `external_modules/Explaining-FA` 不在 repo 裡導致 CXp 分析靜默失效，作者把該模組實際用到的兩個檔案 force-add 進版控之後，DELTA 就正常運作了，這印證了當初的診斷。

**A5：PSO 每一回合都把 personal best 重設。** 已修正。`optimize()` 從「以 `iters=1` 反覆呼叫」改成單次呼叫，程式碼註解直接說明 pyswarms 每次呼叫都會把 `swarm.pbest_cost` 重設成無限大，使得 cognitive 項 `c1*(pbest_pos - position)` 在整個執行過程恆為零。

**A6：PSO 的 agreement cache 以 `id(dfa)` 為 key 卻不保留參照。** 已修正，補上了與 `AutomataBeamSearch` 相同的 `_id_reuse_guard`。

**A7：SA 的溫度從來沒有降下來。** 已修正。annealing schedule 的長度改成「評估預算實際允許的 `move()` 呼叫次數」，而不是原本的評估次數，因此預算用完時溫度確實已經降到接近 `T_min`。

**A8：GA 把 population 最佳個體的 fitness 指給評分失敗的 offspring。** 已修正，改成繼承該 offspring 自己的 parent 的 fitness；連 parent 的 fitness 都無效時，改用最差的 fitness，讓失敗的候選看起來就是差，而不是靜默地變好。

**A15：DFA teacher 在多執行緒下的 race 會產生錯誤標籤。** 已修正。`create_automata_dfa_predictor` 的走訪改用區域變數，不再呼叫會改動共享 `dfa.current_state` 的 `reset_to_initial()` 與 `step()`，註解也寫明了 `draw_automata_samples_parallel` 會同時從多個 thread 呼叫它。

**B1：平行抽樣的例外 fallback 會重複累計已完成的結果。** 已修正（commit `11f084e`）。

**B4：主實驗表格裡 Beam 的初始 training agreement 與其他三列不是同一個量。** 已修正。這次重跑的六張表格中，四個方法的初始值完全相同（例如 DocumentReleaseWorkflow 四列都是 0.8890），不再出現 beam 那一列與其他三列基準不同的情況。

**B6 與 C9：DOT 載入器把屬性宣告行與起點記號當成狀態，並且對帶額外屬性的 doublecircle 節點會靜默降級。** 已修正。`src/automaton/load_dfa.py` 現在會正確跳過 `node [shape=...]` 這類 Graphviz 預設屬性宣告與 `shape=point` 的起點錨點，屬性解析也改成能處理多個屬性的形式。

**B7：`make_plots.py` 只跑過 0.8 的實驗時整支腳本會 ValueError。** 已修正，並且用實跑確認。現在缺少 tau=0.9 的資料時會 graceful skip，輸出 `combo_tau09: skipped`，並回報 `2/3 figures written`，不會連完整的 tau=0.8 圖都產不出來。

**B9 與 R5：三支 teacher 訓練腳本都指向不存在的 datasets 目錄。** 已修正（commit `a774386`），路徑改為 `os.path.join(PROJECT_ROOT, 'dataset', 'ECG5000')` 這類正確形式，對應的資料目錄確實存在。

**C1：perturbation 對長度小於 edit_distance 的序列必定 crash。** 已修正。`replace` 操作現在與 `delete` 一起被 `len(new_instance) > 0` 保護，不會再發生 `random.randrange(0)`。作者同時加入了 `max_len` 參數來控制插入後的長度上限。

**C2：不帶 `--max_evaluations` 時 beam 沒有評估上限，baseline 卻有 500 次的上限。** 已修正，而且做得比原本建議的更好。`run_baseline` 移除了 500 這個預設值，並且新增了一段邏輯，把 baseline 的預算設成 beam 在該 instance 實際用掉的評估次數。這次重跑的每張表格上方都會列出 `Beam evaluations used: N (SA/GA/PSO max_evaluations budget)`，六個任務分別是 905、909、1317、1050、2354、1730。這讓四個方法的比較基準變得明確而且公平。

**C6：regular 任務的 alphabet 順序來自 set，固定 seed 也無法跨行程重現。** 已修正，見上方可重現性段落。

**C8：mnist 的 train 與 test 有大量重疊序列，teacher 的 test accuracy 偏樂觀。** 已修正。作者新增了 `_novel_test_accuracy()`，把出現在 training set 裡的測試序列排除後另外計算一個 `clf_test_novel`。這次重跑的數字證實了原始報告的判斷：mnist 的 `clf_test` 是 0.8973，排除重疊後的 `clf_test_novel` 降到 0.8676。ECG 與 wafer 的落差則很小。

**C11：`dfa_to_mata` 在沒有 accepting state 時會直接修改傳入的 DFA。** 已修正，註解明確寫出「避免改動呼叫端的 DFA，因為這是一個匯出函式」。

**R1：照 README 安裝完成後，DELTA 操作會靜默失效。** 已修正，見 A4。`external_modules/Explaining-FA/USAGE_NOTE.md` 也說明了為什麼只有 `language/explain.py` 與 `language/__init__.py` 兩個檔案進版控。

**R2：`RUNNING.md` 的兩條重現指令一啟動就失敗。** 已修正，輸出資料夾的 `FileExistsError` 防護被移除，改成 `os.makedirs(..., exist_ok=True)`。這次照文件的指令可以直接跑完。附帶說明見下方「新的注意事項」。

### 因為腳本被移除而不再適用

作者在這批 commit 裡刪除了 `examples/RPNI/run_kllucb_comparison.py` 與 `examples/RPNI/run_wafer_param_ablation.py` 兩支腳本。原始報告中針對這兩支腳本的五條發現因此不再適用，分別是 A12（KL-LUCB ablation 的 external holdout 與搜尋端重播同一條隨機流）、A13（ablation 的時間比較讓兩支變體使用不同的平行度）、A14（ablation 的門檻與評估預算都與主實驗不同，log 標題卻宣稱相同）、B2（prebuilt init 的防呆判斷永遠不會成立）、B3（`seed_details.csv` 的兩個欄位永遠是空的）。

需要提醒的是，這幾條發現指出的是那支 ablation 腳本量到的東西與它宣稱的不符。如果論文裡仍然要呈現 KL-LUCB 的 ablation 結果，那些數字是用有問題的腳本產生的，不會因為腳本從 repo 移除就變得可信。

### 仍然成立

**A1：表格中的 Validation 欄位量到的是與初始 DFA 的相似度，不是對 teacher 的忠實度。** 仍然成立。`src/explainer/automata_beam.py:801` 依然把建立初始 DFA 用的 init samples 直接當成 validation set，所以這次重跑的六個任務，validation 欄位的起始值全部都是 1.0000。作者的處理方式是在 `RUNNING.md` 第 4 節把這個欄位的語意寫明，標註為「與初始 DFA 的一致率」，而不是改變指標本身。以誠實揭露來說這個處理可以接受，但結論不變：這個欄位不能拿來當作模型泛化能力的證據，論文如果用它支持泛化相關的主張，需要重新表述。

**A10：調參腳本選出的 baseline 參數從未被主實驗讀取。** 仍然成立。`src/experiments/runner.py` 依然是用 `cfg.get("sa_candidate_pool_size", 10)`、`cfg.get("ga_population_size", 10)`、`cfg.get("pso_particles", 5)` 這樣的預設值，而 `DEFAULT_LANGUAGE_CONFIGS` 裡並沒有設定這些鍵。`tune_baseline_params.py` 產生的 `best_by_algo.csv` 沒有任何路徑會被主實驗讀回去。論文 5.3 節如果宣稱主實驗使用了調校過的 baseline 參數，這個宣稱與程式行為不符。

**A11：每個任務實際只跑一個 test instance。** 部分修正，但核心問題仍然存在。作者修好了 `--num_test_instances` 這個旗標本身：明確傳入時會清掉設定檔裡釘死的 `test_instance`，讓自動產生測試序列的路徑真的會被走到。但是 `RUNNING.md` 第 2 節記載的重現指令並沒有傳這個旗標，所以這次重跑的六個任務全部都是 `Selected test instances: 1`。這代表論文表格背後每一格都是單一 instance 的單次結果，沒有平均、沒有變異數，方法之間的勝負缺乏統計支撐。這是目前剩下的發現裡對論文結論影響最大的一條。

**B8 與 R3：`parse_results.py` 只掃描沒有任何程式會建立的目錄。** 仍然成立，並且用實跑確認。在完整跑完兩條實驗之後直接執行 `python analysis/parse_results.py`，仍然會得到 `FileNotFoundError: .../test_result/final_result`。實驗腳本寫出的是 `test_result/regular_0.8_1000/` 與 `test_result/realworld_0.8_1000/`，而 `final_result/` 這個目錄沒有任何程式會建立，文件也沒有說明需要手動搬移。我手動建立該目錄並把兩份結果複製進去之後，解析才成功產出 24 列的 `summary_table.csv`。從實驗到出圖的完整流程，目前仍然沒有辦法照文件走通。

**R4：`RUNNING.md` 的參數表裡有死參數，也沒有說明初始 DFA 的隱藏限制。** 部分修正。`--num_test_instances` 已經可以運作，但參數表仍然沒有說明初始 DFA 必須落在 25 到 65 個狀態這個範圍，而這個限制在 `init_num_samples` 調小的時候會直接讓實驗失敗（原始報告的 smoke run 記錄了這個情況）。

### 這次沒有逐條重新驗證

原始報告 C 組還有幾條疑點，這次因為重跑的執行路徑沒有觸發，或是需要更深入的程式碼追蹤才能判斷，沒有重新驗證，狀態維持原始報告的結論。這些是 C3（KL-LUCB 的非標準 early stop 把停止門檻放寬到 2ε）、C4（表格上的成功勾號用點估計判定，統計保證只到 τ 減 0.05）、C5（beam 的時間量測包含 RPNI 建構與繪圖，baseline 的不包含）、C7（`SequenceClassifier` 對超過 `max_len` 的序列靜默截斷）、C10（Explaining-FA 回傳的 CXp 位置被當成 0-based 的 path index）、C12（baseline 共用的 state 物件帶著全為零的標籤陣列），以及 B5（config 與 log 描述的 teacher 架構是死參數，而且與實際 checkpoint 不符）。

A9（baseline 的最終選擇在 history 為空時回報錯誤的量，PSO 的例外處理還會丟光 history）看起來已經被 commit `4f4a5e6` 處理，`_select_final` 現在會接收 `training_data` 參數。但這次重跑中四個方法都正常產生了候選，空 history 的路徑沒有被觸發，所以沒有實測佐證。

---

## 這次新發現的問題

`analysis/make_plots.py:238` 的 caption 直接寫入了 Unicode 字元 τ（U+03C4）。pdflatex 無法處理未經設定的 Unicode 字元，因此產生出來的 `combo_tau08.tex` 在編譯時會出現以下錯誤而中止：

```
! LaTeX Error: Unicode character τ (U+03C4)
               not set up for use with LaTeX.
!  ==> Fatal error occurred, no output PDF file produced!
```

同一支程式產生的 `comparison.tex` 則正確地使用 `$\tau=0.8$` 這種 LaTeX 數學模式寫法，所以問題只出在這一行的寫法不一致。實際影響是 `combo_tau08` 這張圖產不出 PDF 與 PNG，而且如果直接把這個 `.tex` 檔放進論文，論文本身也會編不過。腳本最後仍然回報 `combo_tau08: done`，只是少了 `comparison` 那一列有的 `(+ .png)` 後綴，差別很容易被忽略。

修正方式是把第 238 行的 `τ` 改成 `$\tau$`。

---

## 整體評價

作者對這份審查的回應相當紮實。原始報告 A 組的 15 條發現裡，有 8 條已經修正並且能用實跑或程式碼佐證，3 條因為相關腳本被移除而不再適用，剩下 4 條中有 1 條部分修正。B 組的 9 條裡有 5 條修正、3 條不再適用，只剩 1 條仍然成立。整體來看，會導致 crash 或產生錯誤資料的問題幾乎都被清掉了，這次完整重跑沒有出現任何錯誤或警告。

更重要的是可重現性從根本上改善了。原始審查時，照文件執行的兩條指令都會直接失敗；現在不只能跑完，而且結果與作者的參考結果逐位元相同，這在有平行處理與隨機取樣的研究程式碼裡並不常見，值得肯定。

剩下的問題集中在兩個地方。其一是實驗設計層面：每個任務只跑一個 test instance，讓所有方法比較都缺乏統計基礎；validation 欄位量的是與初始 DFA 的相似度而非泛化能力；調參腳本的產出沒有被主實驗使用。這三條都不是程式錯誤，而是實驗設計與論文論述需要對齊的問題。其二是從實驗結果到論文圖表的這段流程仍然沒有打通：`parse_results.py` 找不到目錄，`make_plots.py` 產出的 `.tex` 有一個字元會讓 LaTeX 編譯失敗。這段流程只要補上幾行就能修好，但目前照文件走確實走不通。
