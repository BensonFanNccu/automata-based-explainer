# 程式碼審查資料夾

這個資料夾放的是對本 repo（commit 79d7a04）所做的程式碼審查，包含最終報告與所有佐證資料。審查期間 repo 的程式碼沒有被修改，只新增了這個資料夾。

- 這份 README 的下半部就是最終的合併報告，內容與 `review_report.html` 相同；HTML 版有較完整的排版，下載後用瀏覽器開啟即可。
- `review_local_findings.md` 是 9 月 2 日本機 code-review 流程被停止前輸出的已驗證結果。
- `review_learner.md`、`review_beam.md`、`review_experiments.md` 是 9 月 7 日三條審查線各自的原始報告，每一條 finding 的實測數據與驗證方式都在裡面。
- `smoke_run/` 是在乾淨的 Python 3.11 環境裡照 README 與 RUNNING.md 實際執行的完整 log，包含兩次安裝嘗試與三次實驗執行。
- `verification/` 是三條審查線用來實測的 Python 腳本，執行時需要另外取得 aalpy 與 numpy 的原始碼，各腳本開頭有說明。
- `rerun_2026-09-09/` 是作者針對本報告做出第一批修正之後（commit `2359c33`）的重新驗證，包含 `UPDATE_REPORT.md`、完整重跑的 log、決定性驗證結果與實際執行的腳本。
- `recheck_2026-09-10/` 是作者第二批修正之後（commit `43bc43d`）的複驗，包含 `RECHECK_REPORT.md`、九項實測的完整記錄 `verification_log.txt` 與驗證腳本。**想知道每一條發現目前的狀態，請看這份最新的複驗報告**；閱讀順序是先看 `recheck_2026-09-10/RECHECK_REPORT.md`，需要追溯前一輪的判定再回頭看 `rerun_2026-09-09/UPDATE_REPORT.md`，本 README 下半部的原始報告描述的是最初未修正的 commit `79d7a04`。

---

# automata-based-explainer 程式碼審查報告

這份報告審查的是碩士論文《Local Explanation for Black-Box Sequential Models》的公開實作。審查範圍是全部 Python 程式碼，重點放在會導致錯誤實驗結果的正確性 bug，以及照著作者文件操作之後仍然會出問題的可重現性缺陷。

- **審查對象** **github.com/Chen-Yihua/automata-based-explainer**，commit `79d7a04`，共 26 個 Python 檔、11,308 行。 
- **審查日期** **2026 年 9 月 2 日至 9 月 7 日**。靜態審查分四條線進行，另外在乾淨的 Python 3.11 環境裡照 README 與 RUNNING.md 實際跑過一遍。 
- **判定標準** 每一條 CONFIRMED 都追完了從實驗入口到問題點的實際呼叫路徑，多數另外用小型腳本實測；追不完或需要特殊輸入的列為 PLAUSIBLE；不成立的列在已否決清單。 

## 總覽

程式碼可以跑，也沒有語法或載入層級的錯誤，但實驗結果與論文宣稱之間有四類實質落差。第一，實作出來的演算法與論文描述的方法不同：MERGE 操作的提案名額大多被必定會被拒絕的配對佔走，MERGE 還會偷偷改寫狀態的 accepting 屬性，而 DELTA 操作在三個 regular 任務的實驗裡從頭到尾沒有產生過任何候選。第二，表格裡的 Validation 欄位量到的不是 DFA 對 teacher 的忠實度，而是精簡後的 DFA 與初始 DFA 的相似度，所以所有依據這一欄下的結論都要重新解讀。第三，三個 baseline 都有讓它們失真的 bug：PSO 每一回合都會把 personal best 歸零，SA 的溫度從來沒有降下來，GA 會把未評分的個體當成菁英保留；因此 beam 與 baseline 的比較並不是與正常運作的 SA、GA、PSO 比較。第四，每個任務實際上只跑了一個 test instance，而 KL-LUCB ablation 用來評估的 external holdout 與搜尋本身重播同一條隨機流，實質上是 in-sample 評估。

可重現性方面，照 RUNNING.md 的指令原封不動執行會在啟動時直接失敗，分析腳本照文件執行也會失敗；照 README 安裝完成後，DELTA 操作會因為缺少一個未被納入 repo 的外部模組而靜默失效，使用者不會知道自己跑的是少了一種操作的演算法。

- **15** A 組。已確認且會影響論文結論解讀的正確性問題。 
- **9** B 組。已確認會 crash 或產生錯誤資料，但不直接改變主表格結論的問題。 
- **12** C 組。機制成立但預設實驗不會觸發，或無法完整追蹤的疑點。 

另有 5 項照文件重現時會卡住的問題（R 組），以及 16 項經驗證後否決的候選。四條審查線各自的原始報告與驗證腳本都保留在 review 目錄，見文末說明。

| 編號 | 一句話摘要 | 影響 |
|---|---|---|
| A1 | 表格中的 Validation 欄位是在建初始 DFA 的那批樣本上量的，量到的是與初始 DFA 的相似度，不是對 teacher 的忠實度。 | [論文結論] |
| A2 | MERGE 的提案名額會被含 initial state 的配對佔滿，三十次初始化裡有五次 MERGE 完全沒有候選。 | [論文結論] |
| A3 | MERGE 會無條件依路徑多數標籤改寫合併後狀態的 accepting 屬性，與 docstring 宣稱的語意不符。 | [論文結論] |
| A4 | DELTA 在三個 regular 任務的附帶 log 裡 157 個回合全部只有父代一個候選；沒有 Explaining-FA 時 DELTA 對所有任務都是 no-op。 | [論文結論] |
| A5 | PSO 在迴圈裡反覆呼叫 pyswarms 的 optimize(iters=1)，每次呼叫都會把 personal best 重設，量到的不是 PSO。 | [論文結論] |
| A6 | PSO 的 agreement cache 以 id(dfa) 為 key 卻不保留參照，位址重用會讓新的 DFA 繼承別人的分數。 | [論文結論] |
| A7 | SA 的溫度排程按評估預算計算，但每個 move 消耗十次評估，退火在整個搜尋裡從未發生。 | [論文結論] |
| A8 | GA 在 offspring 評分失敗時把 population 最佳個體的 fitness 指給它，讓未評分的 DFA 以菁英分數存活。 | [論文結論] |
| A9 | baseline 的最終選擇在 history 為空時會把 validation 值當 training agreement 回報，PSO 的 catch-all except 還會丟光 history。 | [論文結論] |
| A10 | 調參腳本選出的 baseline 參數從來沒有被主實驗讀取，主比較永遠使用寫死的預設值。 | [論文結論] |
| A11 | 每個任務實際只跑一個 test instance，文件與 log 裡的 num_test_instances 是死參數。 | [論文結論] |
| A12 | KL-LUCB ablation 的 external holdout 與搜尋端從同一個 seed 重播同一條隨機流，validation set 是 holdout 的嚴格子集。 | [論文結論] |
| A13 | ablation 的時間比較讓有 KL-LUCB 的那一支走多執行緒與 process pool，沒有 KL-LUCB 的那一支永遠單執行緒。 | [論文結論] |
| A14 | ablation 的三個 regular 任務用 0.9 的門檻判定成功，資料夾名稱與 summary 標題卻寫 0.8，而且沒有評估次數上限。 | [論文結論] |
| A15 | DFA teacher 的 predictor 在多執行緒下共享 current_state，race 產生的錯誤標籤會被 prediction cache 固定到整個搜尋。 | [論文結論] |
| B1 | 平行抽樣的例外 fallback 會重複累計前面已完成的結果，之後在合併統計時 shape mismatch。 | [crash 或錯誤資料] |
| B2 | KL-LUCB 比較腳本的 prebuilt init 防呆判斷永遠不會成立，初始化失敗時會 AttributeError。 | [crash 或錯誤資料] |
| B3 | seed_details.csv 的兩個 teacher agreement 欄位永遠是空的，holdout_size 欄位寫的是要求值而非實際抽到的數量。 | [crash 或錯誤資料] |
| B4 | 主實驗表格裡 Beam 那一列的初始 training agreement 與其他三列不是同一個量。 | [crash 或錯誤資料] |
| B5 | real-world config 與 log 描述的 teacher 架構參數是死參數，而且與實際 checkpoint 的架構不符。 | [crash 或錯誤資料] |
| B6 | DOT 載入器把屬性宣告行與起點記號當成狀態，MultiObligationOrder 的 teacher 被算成 39 個狀態而不是 37 個。 | [crash 或錯誤資料] |
| B7 | make_plots.py 會急切建構 threshold 0.9 的圖，只跑過 0.8 時整支腳本 ValueError。 | [crash 或錯誤資料] |
| B8 | parse_results.py 只掃描沒有任何程式會建立的目錄，並且會略過帶 output_suffix 的結果資料夾。 | [crash 或錯誤資料] |
| B9 | 三支 teacher 訓練腳本都指向不存在的 datasets 目錄，重新訓練 mnist 的 teacher 會直接 crash。 | [crash 或錯誤資料] |

C 組與 R 組的項目數量較多，摘要直接放在各自的章節裡。

## A 會影響論文結論的正確性問題

這一組的每一條都已經追到實際的實驗入口與預設參數，確認在作者發表的實驗設定下會發生。排序依據是對論文結論的影響程度。前四條關於評估欄位與三種操作本身，接下來六條關於三個 baseline，最後五條關於實驗設計與統計。

---

**A1  [論文結論]** 

### 表格中的 Validation 欄位量到的是與初始 DFA 的相似度，不是對 teacher 的忠實度

- **位置：** `src/explainer/automata_beam.py:750, 794-795`、`src/experiments/runner.py:140-141`、`src/baselines/search_baselines.py:685-686, 764, 789` 
- **來源：** beam 線追蹤資料流，實驗線與本機實跑各自從 log 印證。 

建初始 DFA 時，程式先用 sampler 抽出 init_num_samples 筆擾動序列並向 teacher 取得標籤，把它們切成正負例交給 RPNI，然後在第 794 至 795 行直接把同一批樣本指派為 validation_data 與 validation_labels。這組資料經由 build_shared_init 原樣轉交給 SA、GA 與 PSO，所以四個方法用的 validation set 都是初始 DFA 的建構樣本。RPNI 的輸出保證與輸入樣本一致，因此六個任務的 Initial validation 全部是 1.0000，這是建構上的恆真式，不是量測結果。

Final validation 因此量到的是「精簡後的 DFA 在初始 DFA 的建構樣本上，與初始 DFA 一致的比例」，本質上是與初始 DFA 的相似度。附帶的 real-world log 裡 wafer 那一列是最清楚的例子：SA 與 GA 回傳的是未經修改的 36 個狀態的初始 DFA，它們的 training agreement 只有 0.748，Validation 欄位卻拿到 1.0000；PSO 回傳 34 個狀態拿到 0.942；beam 精簡到 5 個狀態只拿到 0.716。這一欄實際上獎勵「不去動初始 DFA」，越積極精簡的方法越吃虧。beam 線另外用蒙地卡羅量了 validation set 與每一批 training batch 的重疊比例，regular 三個任務是 7% 到 15%，real-world 三個任務是 37% 到 48%，所以即使把它當成同分布的另一組樣本，也不是乾淨的 held-out。

四個方法都沒有用 validation 做候選選擇，beam 看 all_history 的 training_agreement，baseline 看固定 batch 上的 training_agreement，所以不存在選擇性洩漏。附帶結果裡 wafer_ablation_grid/summary.txt 把 validation 下降歸因於「壓縮過度」，這個解讀沒有考慮 validation set 本身就是初始 DFA 的建構集。

> **對論文的影響：**凡是依據 Validation 欄位對 beam 或任何 baseline 所下的結論，無論是「在 validation 上也維持得不錯」或「在 validation 上輸給某個方法」，都不能成立。Train 欄位與 States 欄位不受這個問題影響。 

---

**A2  [論文結論]** 

### MERGE 的提案名額被必定會被拒絕的 initial state 配對佔滿

- **位置：** `src/learner/dfa_learner.py:1190-1247`（collect_merge_pairs_simple）、`:1281-1296`（_propose_merge） 
- **來源：** 本機 code-review 流程列為未驗證疑點，learner 線用 aalpy 1.5.3 與 repo 程式碼實測後確認。 

collect_merge_pairs_simple 已經把「跳過含 initial state 的配對」那兩行註解掉，而 _propose_merge 是在截取前 max_pairs 個配對之後才過濾掉含 initial state 的配對，所以必定被拒絕的配對會佔掉有限的提案名額。三個環節疊在一起讓情況變得嚴重：initial state 永遠是 states[0]，所以它的配對在 combinations 的列舉裡排在最前面；主標籤相同的配對一律給 1.0 分且排序是穩定的，所以這些配對在最高分群組裡仍然排在最前面；initial state 出現在每一條路徑上，它的主標籤就是全體樣本的多數標籤，因此任何 non-accepting 且主標籤相同的狀態都會和它組成滿分配對。beam_size 預設為 1，max_pairs 因此是 20，只要這種狀態有 20 個，前 20 名全部是含 initial state 的配對，過濾後一個都不剩。

learner 線用三個 regular teacher 的預設 test instance 與 edit_distance 各跑 10 個 sampler seed。SecureHandshake 十次初始化的可用配對數依序是 16、3、0、0、0、6、7、9、5、6；DocumentReleaseWorkflow 是 5、9、9、11、5、4、0、6、15、5；MultiObligationOrder 是 15、6、3、0、6、13、10、7、14、15。三十次初始化裡有五次 MERGE 完全沒有候選，其餘多數只剩不到一半的名額。以 DocumentReleaseWorkflow 的 seed 7 為例，模擬四個 DELETE 加 MERGE 回合，每一回合 DELETE 產生 31 到 34 個候選，MERGE 都是 0 個。初始 DFA 越大越容易被完全餓死。

> **對論文的影響：**論文描述的方法有 Delete、Merge、Delta 三種操作，實作裡 MERGE 在相當比例的實例上被削弱甚至完全關閉，所以 beam 的最終狀態數與 agreement 是在與描述不同的操作集合下跑出來的。影響方向無法確定，但「實作的演算法不等於論文的演算法」這一點是確定的。 

---

**A3  [論文結論]** 

### MERGE 會無條件依路徑多數標籤改寫合併後狀態的 accepting 屬性

- **位置：** `src/learner/dfa_learner.py:217-220`（_merge_candidate_from_pair）、`:983-995`（_propose_merge_single） 
- **來源：** learner 線實測。 

docstring 說「若兩個狀態的 accepting 屬性不一致，才由 majority_labels 決定」，但程式碼無條件執行 `s1_new.is_accepting = (merged_majority == 1)`。在 beam 的路徑上，collect_merge_pairs_simple 已經把 accepting 屬性不同的配對全部過濾掉，所以「不一致」的前提永遠不成立，改寫卻照樣發生。而且 majority_labels 統計的是「經過該狀態的樣本」的標籤，不是「結束於該狀態的樣本」，一個位於通往 accepting state 路上的中繼狀態很容易被判成多數標籤 1。

learner 線以 SecureHandshake 的初始 DFA 對所有非 initial 的可合併配對呼叫 _merge_candidate_from_pair，195 個合法候選裡有 70 個合併後的 accepting 屬性與兩個輸入狀態都不同，例如 s8 與 s9 都是 non-accepting，合併後變成 accepting。

> **對論文的影響：**不確定。候選仍會經過 KL-LUCB 評估，回報的 agreement 數值本身沒有錯，但實作的 MERGE 是「合併加改標籤」，搜尋軌跡與論文描述的 Merge 操作不同。 

---

**A4  [論文結論]** 

### DELTA 在三個 regular 任務的實驗裡從未產生過候選；沒有 Explaining-FA 時對所有任務都是 no-op

- **位置：** `src/learner/dfa_learner.py:34-40, 106-107`（Explaining-FA 缺失時的退化）、`:251-252`（缺失 transition 分支）、`:1616, 1654-1655`（_propose_delta） 
- **來源：** 可重現性線發現退化，learner 線實測缺失分支是死路，beam 線從附帶 log 發現 regular 任務的現象，本機實跑印證 warning。 

附帶的 regular log 裡，SecureHandshake、DocumentReleaseWorkflow 與 MultiObligationOrder 三個任務總共 157 個 DELTA 回合，每一個都印出 candidates=1，也就是只有父代自己被放回候選清單。同一份實驗的 real-world log 裡，DELTA 回合有 2 到 42 個候選。這代表作者的實驗環境確實有 Explaining-FA，但對以 DFA 當 teacher 的 regular 任務，CXp 分析從來沒有產生過任何 rewire 候選；根因在 _aggregate_cxp_analysis 或外部的 ExplainLanguage，因為該模組不在 repo 內，無法再往下追。

另一個情境是照 README 安裝之後的狀態。external_modules/Explaining-FA 被 .gitignore 排除，沒有 submodule，README 也沒有任何取得方式的說明，所以照文件安裝完成後這個模組一定不存在。此時 dfa_learner.py 在 import 階段只印一行 warning，_collect_cxp_records_for_path 直接回傳空的 CXP 記錄，只剩「缺失 transition」的記錄；而 _delta_candidate_from_edge 一開始就以 `if symbol not in src_new.transitions: return None` 拒絕所有缺失 symbol 的任務，docstring 宣稱的「add missing transitions」在任何情況下都不會發生。learner 線把 SecureHandshake 初始 DFA 的一條 transition 刪掉後呼叫這個函式，非 None 的候選數是 0。因此沒有 Explaining-FA 時，DELTA 在每個奇數回合只會回傳父代，是完整的 no-op，比先前「退化成只剩 missing transition 修補」的描述更嚴重。

> **對論文的影響：**論文若宣稱三種操作都參與了 regular 實驗的精簡，與附帶 log 不符，regular 實驗實際上只用了 Delete 與 Merge。任何照文件重現的人，在六個任務上跑的都是只有兩種操作的演算法，而且不會收到任何錯誤。 

---

**A5  [論文結論]** 

### PSO 每一回合都把 personal best 重設，量到的不是 PSO

- **位置：** `src/baselines/search_baselines.py:567`；pyswarms 1.3.0 的 `single/global_best.py:204` 
- **來源：** 本機 code-review 流程 CONFIRMED，beam 線與先前的雲端審查各自從 pyswarms 原始碼再確認。 

PSO baseline 在自己的迴圈裡反覆呼叫 pyswarms 的 `GlobalBestPSO.optimize(iters=1)`。requirements.txt 釘的是 pyswarms 1.3.0，這個版本在每次 optimize 開始時執行 `self.swarm.pbest_cost = np.full(..., np.inf)`，把所有粒子的 personal best 歸零。結果是每一回合 pbest_pos 都塌縮成當前位置，速度更新退化成慣性項加上 social 項，cognitive 項（c1）完全失效。

> **對論文的影響：**Beam 對 PSO 的比較表，以及 tune_baseline_params 產出的 PSO 調參表，量到的都不是真正的 PSO。 

---

**A6  [論文結論]** 

### PSO 的 agreement cache 以 id(dfa) 為 key 卻不保留參照，新的 DFA 會繼承別人的分數

- **位置：** `src/baselines/search_baselines.py:276`；對照 `src/explainer/automata_beam.py:197` 的 _id_reuse_guard 
- **來源：** 本機 code-review 流程 CONFIRMED。 

被拒絕或重複的候選在 _add_to_history 之後就被釋放，但它們的 id() 仍留在 state_metrics 裡當 key。之後 deepcopy 出來的新候選有機會配置到同一個位址，`dfa_id in self.state_metrics` 因此命中，一個結構不同的 DFA 會用別的自動機的 true_pos 與 true_neg 被評分，並且可能因此贏得 _update_gbest、被當成 PSO 的最佳結果回傳。beam 的實作有 _id_reuse_guard 專門防這件事，PSO 沒有。

> **對論文的影響：**PSO 回報的 agreement 與狀態數可能屬於另一個自動機，方向不定。 

---

**A7  [論文結論]** 

### SA 的溫度從來沒有降下來，退火在整個搜尋裡從未發生

- **位置：** `src/baselines/search_baselines.py:1056-1057`（effective_steps）、`:900-931`（每個 move 評估 pool_size 個候選）、`:985-1000`（early stopping 與 energy）；simanneal 0.5.0 的 `anneal.py:182-199` 
- **來源：** beam 線讀 simanneal 原始碼並計算溫度排程，附帶 log 印證。 

第 1056 行把 effective_steps 設成 max(steps, max_evaluations + 1)，註解寫著這是為了「確保有足夠的 move 用完評估預算」，它假設每個 step 只消耗一次評估。但 move() 每次會評估 pool_size 等於 10 個鄰居，所以 3000 次的預算只夠 300 個 move，而 simanneal 是按 step 除以 effective_steps 做指數降溫的。附帶 log 裡 SecureHandshake 的 SA 只做了 34 個 move 就因為連續 10 輪沒有新的 best 而停止，此時溫度約為 9.0，就算 agreement 掉整整 1.0 的 move 也有 0.90 的機率被接受。換句話說 Metropolis 幾乎接受一切，SA 退化成「每輪從 10 個鄰居挑 energy 最低的那一個然後無條件移動過去」的貪婪隨機下降，從頭到尾沒有低溫階段。log 同時顯示 SA 在 SecureHandshake 只用掉 3000 之中的 340 次評估就 early stop。

附帶的問題是 move() 回傳 None，所以 simanneal 在每個 step 之後會呼叫 energy() 在 1000 筆 training 資料上重算一次 agreement，這些評估沒有計入 evaluations_count，SA 實際做的評估次數比報告的多約 10%，Time 欄位也包含這些工作。

> **對論文的影響：**表格裡的 SA 列不是 simulated annealing 的結果，而是一個退化演算法的結果。「beam 優於 SA」的幅度可能被高估，實際幅度無法從程式碼判定。 

---

**A8  [論文結論]** 

### GA 把 population 最佳個體的 fitness 指給評分失敗的 offspring

- **位置：** `src/baselines/search_baselines.py:1302` 
- **來源：** 本機 code-review 流程 CONFIRMED。 

GA 的 sequential fallback 在 offspring 評分失敗時，把「population 裡最佳個體」的 fitness 指給它，註解卻寫著是指派 parent 的 fitness。一個從未被評分的 DFA 因此以菁英分數長期存活，扭曲 selection 與 early stopping。

> **對論文的影響：**GA 的搜尋軌跡與最終結果可能被未評分的個體帶偏，方向不定。 

---

**A9  [論文結論]** 

### baseline 的最終選擇在 history 為空時回報錯誤的量，PSO 的例外處理還會丟光 history

- **位置：** `src/baselines/search_baselines.py:789`（_select_final）、`:1506`（pso_dfa_search） 
- **來源：** 本機 code-review 流程 CONFIRMED。 

all_history 為空時，_select_final 把初始 DFA 在 validation 資料上算出的值當成 training_agreement 回報。pso_dfa_search 用一個 catch-all except 同時包住 optimize() 與收集 history 的迴圈，中途任何錯誤都會讓已收集的 history 全部丟失，然後回報「No candidates generated」。這兩件事疊起來，PSO 只要在搜尋中途出錯，表格上就會出現一個看起來合理但其實是 validation 值的數字。

> **對論文的影響：**PSO 或其他 baseline 的某些列可能是錯誤路徑產生的數字，而 log 不會明顯標示。 

---

**A10  [論文結論]** 

### 調參腳本選出的 baseline 參數從未被主實驗讀取

- **位置：** `src/baselines/tune_baseline_params.py:57-58, 313-343`；讀取端 `src/experiments/runner.py:231-245` 
- **來源：** 實驗線。 

調參腳本只把結果寫到 tune_results.csv、best_by_algo.csv 與 summary_top20.txt。主實驗的 run_baseline 用 cfg.get 讀 sa_candidate_pool_size、ga_population_size、pso_particles 與 pso_candidate_pool_size，預設值是 10、10、5、5；兩支主實驗腳本的 DEFAULT_LANGUAGE_CONFIGS 都沒有這些鍵，命令列也沒有對應旗標，整個 repo 沒有任何程式讀 best_by_algo.csv。所以無論調參結果如何，Beam 對 SA、GA、PSO 的主比較永遠使用寫死的預設值。另外調參腳本把 AGREEMENT_THRESHOLD 寫死為 0.8，整支腳本沒有設定任何 seed，每個網格點只跑一次，排名建立在單次無 seed 的結果上。

> **對論文的影響：**如果論文只是獨立呈現調參表，主結果沒有錯；如果論文宣稱主比較使用了調參後的最佳 baseline 設定，這個宣稱不成立。 

---

**A11  [論文結論]** 

### 每個任務實際只跑一個 test instance，num_test_instances 是死參數

- **位置：** `examples/RPNI/run_regular_experiment.py:205`、`examples/RPNI/run_realworld_experiment.py:138` 
- **來源：** 本機 code-review 流程 CONFIRMED，實驗線與本機實跑從 log 印證。 

DEFAULT_LANGUAGE_CONFIGS 的每一組設定都固定了 test_instance，而選取邏輯永遠優先使用它，所以 --num_test_instances 與 regular 任務的 --max_length 實際上都沒有作用。附帶的兩份 log 在參數區塊印出 num_test_instances 為 5 或 10，但每個任務都只印「Selected test instances: 1」，結果目錄也只有 instance_00。本機重跑得到相同結果。

> **對論文的影響：**論文若把結果描述成多個 instance 的平均，實際上每個任務只有一條序列的結果，所有表格數字都沒有跨 instance 的變異估計。 

---

**A12  [論文結論]** 

### KL-LUCB ablation 的 external holdout 與搜尋端重播同一條隨機流

- **位置：** `examples/RPNI/run_kllucb_comparison.py:686-687, 703, 752`；觸發點 `src/learner/dfa_learner.py:307-309, 441` 
- **來源：** 本機 code-review 流程列為未驗證疑點，實驗線用純 Python 重製 perturbation 後確認。 

create_explainer 每次都建立新的 DFASampler 並傳入同一個 seed，而 DFASampler 的建構式會呼叫 random.seed 與 np.random.seed 重設全域亂數；perturbation 沒有收到 rng 參數時直接用全域 random。因此第 686 行建立 holdout 用的 sampler 時全域亂數被設成 seed，第 687 行抽出 holdout；第 703 行為「有 KL-LUCB」那一支再建一個 sampler，全域亂數被設回同一個 seed，接下來的初始抽樣與所有循序抽樣都從同一個起點重播同一串亂數；第 752 行為「沒有 KL-LUCB」那一支又重設一次。perturbation 每一次 trial 消耗的亂數只取決於 instance 與亂數流，所以第 k 次 trial 在兩邊產生完全相同的序列。

實驗線把 perturbation 逐行搬到純 Python，用六個任務的預設設定對 seed 0 到 2 各做一次，結果全部一致：validation set 是 holdout 的嚴格子集；搜尋端前一到四個 1000 筆的循序 batch 百分之百落在 holdout 內；「沒有 KL-LUCB」那一支的第一個 batch 完整包含 validation set；作為對照，用不同 seed 抽出的獨立 batch 落在 holdout 內的比例只有 18% 到 53%。另外 perturbation 的 max_trials 是 10000，而 --holdout_size 預設也是 10000，所以 holdout 實際只有 2083 到 7128 個不重複樣本。

> **對論文的影響：**summarize_language_results 的 success_ratio、win rate、tie rate 全部以 external_holdout_agreement 為依據，而這個量不是獨立估計。兩支變體都被同樣的機制汙染，勝負方向不必然偏向某一邊，但 success_ratio 對兩支都偏樂觀，腳本宣稱的「external hold-out」在方法學上不成立。 

---

**A13  [論文結論]** 

### ablation 的時間比較讓兩支變體使用不同的平行度

- **位置：** `examples/RPNI/run_kllucb_comparison.py:579-585`；分歧點 `src/explainer/automata_beam.py:489, 510, 938, 964` 
- **來源：** 實驗線。 

兩支變體用相同的 cfg 建立 AutomataBeamSearch，預設 parallel 為 True、n_jobs 為 4。有 KL-LUCB 的那一支在候選數大於 1 時走 draw_automata_samples_parallel，抽樣用 ThreadPoolExecutor、評分用 ProcessPoolExecutor；沒有 KL-LUCB 的那一支在第 938 行直接呼叫循序版本的 draw_automata_samples，cfg 的 parallel 對它完全無效。因此 beam_time 的平均與標準差比較的是四執行緒加多程序對上單執行緒的牆鐘時間。

> **對論文的影響：**只影響時間欄位。若論文用這個 ablation 主張 KL-LUCB 在時間上的優勢或代價，那個數字混入了平行化的差異。 

---

**A14  [論文結論]** 

### ablation 的門檻與評估預算都與主實驗不同，log 標題卻宣稱相同

- **位置：** `examples/RPNI/run_kllucb_comparison.py:54-57, 130, 149, 168, 985-987, 1185-1192` 
- **來源：** 實驗線。 

預設的六個任務裡，三個 real-world 任務的 agreement_threshold 是 0.8，三個 regular 任務是 0.9。main 用第一個任務的門檻決定資料夾名稱 kllucb_0.8_1000 並印成「agreement_threshold=0.8」的 summary 標題，但 summarize_language_results 是逐任務讀自己的門檻，所以 regular 任務的 success_ratio 是以 0.9 判定的。這支腳本也沒有 --max_evaluations 旗標，cfg 裡沒有這個鍵，所以 ablation 永遠在沒有預算上限的情況下跑到 2 個狀態或沒有候選為止，而 RUNNING.md 指定主實驗用 3000 次的上限。第 54 到 57 行的註解說「與主實驗完全相同的設定」並不成立。

> **對論文的影響：**如果論文把六個任務的 ablation 都標成 0.8 的門檻，regular 三個任務實際是 0.9；ablation 與主實驗的數字也不能直接對照。 

---

**A15  [論文結論]** 

### DFA teacher 在多執行緒下的 race 會產生錯誤標籤，而且會被 cache 固定到整個搜尋

- **位置：** `src/automaton/load_dfa.py:251, 256-258`、`src/learner/dfa_learner.py:335-379`（_predict_with_cache）、`src/experiments/runner.py:83`（parallel 預設 True） 
- **來源：** 本機 code-review 流程 CONFIRMED race，learner 線補充 cache 的放大效果。 

create_automata_dfa_predictor 回傳的 predictor 透過 reset_to_initial() 與 step() 改動共享的 dfa.current_state，但 draw_automata_samples_parallel 的 ThreadPoolExecutor 會並行呼叫它，而 _predict_with_cache 是在 cache lock 之外呼叫 predictor 的。regular 實驗預設 parallel 為 True、n_jobs 為 4，所以這條路徑是預設開啟的。race 之下標籤會被靜默弄錯，load_dfa.py 第 256 至 258 行的 except 還會把 race 中拋出的錯誤轉成標籤 0。一旦某個序列算出錯的 teacher 標籤，它就會以 tuple(seq) 為 key 存進 prediction cache，在同一個實例的整個搜尋裡被重複使用。real-world 任務的 torch teacher 在推論時是 thread-safe 的，所以這個問題只影響三個 regular 任務。

> **對論文的影響：**regular 任務的 agreement 是對一個可能含錯誤標籤的 teacher 量的，錯誤比例無法從 log 估計。 

## B 會 crash 或產生錯誤資料，但不直接改變主表格結論的問題

這一組同樣都是已確認的 bug，差別在於它們影響的是特定路徑、輔助輸出或描述性資訊，主表格裡的 Train 與 States 數字不會因為它們而改變。

---

**B1  [crash 或錯誤資料]** 

### 平行抽樣的例外 fallback 會重複累計已完成的結果

- **位置：** `src/explainer/automata_beam.py:343`，下游 `:490, 513`
- **來源：** 本機 code-review 流程 CONFIRMED。 

draw_automata_samples_parallel 的 except 分支會重新對整個 batch 評分並 append 到 worker_results，卻沒有清掉先前已經 append 的部分結果。前 k 個自動機的統計因此被重複計算，回傳長度變成 N 加 k，接著在第 490 與 513 行的 `positives[idx] += ...` 出現 shape mismatch 的 ValueError。只要 process pool 在中途拋出任何例外，整個 beam 回合就會以另一個錯誤收場，而不是如註解所述優雅地退回循序模式。

---

**B2  [crash 或錯誤資料]** 

### KL-LUCB 比較腳本的 prebuilt init 防呆判斷永遠不會成立

- **位置：** `examples/RPNI/run_kllucb_comparison.py:639`
- **來源：** 本機 code-review 流程 CONFIRMED。 

extract_prebuilt_init 用 `if not automata_pair` 防呆，但初始化失敗時回傳的是 truthy 的 `{'automata': [None, None]}`，接下來的 automata_pair[0].copy() 會 AttributeError。runner.py 的對應位置寫的是 `is not None`，這裡是複製程式碼時產生的分歧。初始 DFA 建構失敗在本機實跑時實際發生過（見 R4），所以這條路徑並不罕見。

---

**B3  [crash 或錯誤資料]** 

### seed_details.csv 的兩個欄位永遠是空的，holdout_size 欄位寫的是要求值

- **位置：** `examples/RPNI/run_kllucb_comparison.py:695-696, 1086`
- **來源：** 本機 code-review 流程 CONFIRMED 欄位問題，實驗線補充 holdout_size。 

save_seed_details_csv 讀的是 teacher_train_agreement 與 teacher_test_agreement，但 seed dict 存的是 teacher_train_acc 與 teacher_test_acc，所以這兩個 CSV 欄位永遠是空的。同一份 CSV 與 summary.csv 裡的 holdout_size 寫的是命令列要求的 10000，實際抽到的不重複樣本只有 2083 到 7128 個（見 A12）。

---

**B4  [crash 或錯誤資料]** 

### 主實驗表格裡 Beam 的初始 training agreement 與其他三列不是同一個量

- **位置：** `src/explainer/automata_beam.py:617-623, 644-651`；重算點 `src/learner/dfa_learner.py:1748-1760`
- **來源：** 實驗線從附帶 log 發現。 

附帶的 real-world log 裡，wafer 的初始 DFA 在第一個 1000 筆 batch 上的 agreement 是 0.7480，SA、GA、PSO 三列的 Init 值也都是 0.7480，但 Beam 那一列的 Init 值是 0.7380。原因是 _make_result 對初始自動機讀取的是「當下累積」的統計，而 iteration 0 之後 origin 的統計可能被用 state 內全部資料重算；程式碼只對最終自動機做了快照保護，沒有對初始自動機做。其他五個任務兩邊一致，所以只在 origin 被重新統計時才會顯現。這只影響 Train 欄位的 Init 值，Final 值不受影響。

---

**B5  [crash 或錯誤資料]** 

### config 與 log 描述的 teacher 架構是死參數，而且與實際 checkpoint 不符

- **位置：** `examples/RPNI/run_kllucb_comparison.py:77-124, 476-481`、`examples/RPNI/run_realworld_experiment.py:58-105, 166-171`；覆蓋點 `models/sequence_classifier.py:146-187`
- **來源：** 可重現性線發現參數不被讀取，實驗線用不依賴 torch 的 unpickler 讀出 checkpoint 內的實際值。 

三個 real-world config 都寫了 hidden_dim 為 256、num_layers 為 2、dropout 為 0.3、embedding_dim 為 64。建構 SequenceClassifier 時只傳了 max_len 與 embedding_dim，而 load() 會用 checkpoint 內的值覆蓋所有建構參數，所以這些欄位對實驗完全沒有作用。從三個 .pth 讀出的實際架構是：mnist 用 embedding 64、128 個 RNN 單元、2 層、dropout 0.5；ECG 用 embedding 16、64 個單元、1 層、dropout 0.5；wafer 用 embedding 8、32 個單元、1 層、dropout 0.5。附帶 log 的參數區塊照樣印出 hidden_dim 256、num_layers 2、dropout 0.3。實驗數字本身不受影響，因為推論用的是 checkpoint；但如果論文是照 config 或 log 描述 teacher 架構，那段描述是錯的。README 裡「新增 real-world dataset」教人設定的 alphabet 與架構參數，同樣全部不會被讀取。

---

**B6  [crash 或錯誤資料]** 

### DOT 載入器把屬性宣告行與起點記號當成狀態

- **位置：** `src/automaton/load_dfa.py:91, 97-99`
- **來源：** 本機 code-review 流程 CONFIRMED，learner 線補充 qi 的情況並實測。 

state regex 會把 DOT 的 default-attribute 行（例如 `node [shape=circle];`）當成狀態，而只有以雙底線開頭的名稱會被跳過，所以 multi_obligation_color_order.dot 用來標示起點的 `qi [shape=point]` 也被建成狀態。實測載入後 teacher.states 多出 qi 與 node 兩個沒有任何邊的狀態，MultiObligationOrder 的 teacher 被算成 39 個狀態，實際應為 37 個。這些 phantom state 不可達，不影響預測，但會灌高 log 與表格裡的 teacher_states。

---

**B7  [crash 或錯誤資料]** 

### make_plots.py 只跑過 0.8 的實驗時整支腳本會 ValueError

- **位置：** `analysis/make_plots.py:439`；另見 `:81, 129, 146`
- **來源：** 本機 code-review 流程 CONFIRMED，實驗線補充 initial_states 的情況。 

main() 在一個 dict literal 裡急切建構全部的圖，包括 threshold 為 0.9 的 combo_figure；照 RUNNING.md 只跑 0.8 時它會 ValueError，連完整的 0.8 那組圖都一張不出。另外 load_rows 會把空字串的 initial_states 轉成 None，而 combo_figure 直接把它放進座標字串並取 max，任何 initial_states 為 0 的任務會讓整張圖無法產生。

---

**B8  [crash 或錯誤資料]** 

### parse_results.py 只掃描沒有任何程式會建立的目錄

- **位置：** `analysis/parse_results.py:12, 105`；CONFIG_RE
- **來源：** 本機 code-review 流程與可重現性線各自發現，本機實跑印證。 

parse_results.py 只讀 test_result/final_result/ 底下的 experiment_log.txt，但實驗腳本不會建立這個目錄，文件也沒有說要手動把結果搬進去；本機實跑直接得到 FileNotFoundError。CONFIG_RE 也會靜默略過帶 --output_suffix 的結果資料夾，而 --output_suffix 正是實驗腳本在錯誤訊息裡教使用者繞過 FileExistsError 的方法。詳細的重現流程問題見 R3。

---

**B9  [crash 或錯誤資料]** 

### 三支 teacher 訓練腳本都指向不存在的 datasets 目錄

- **位置：** `models/mnist_classifier.py:46` 與 `dataset/mnist_stroke_loader.py:67`、`models/ECG_classifier.py:59`、`models/Wafer_classifier.py:63`
- **來源：** 實驗線。 

repo 內的資料放在 dataset 目錄，但 ECG 與 Wafer 的訓練腳本把 data_dir 設成 datasets，mnist 的 loader 預設路徑也是相對於工作目錄的 datasets/mnist-digits-as-stroke-sequences/mnist_strokes.pkl，而 mnist 的訓練腳本沒有覆蓋它。因此重新訓練 mnist 的 teacher 會直接 FileNotFoundError；ECG 與 Wafer 的 loader 會忽略 repo 內已附的資料，改嘗試從網路下載。主實驗使用的是已附的 checkpoint 與 split 檔，所以實驗數字不受影響，影響的是 teacher 訓練的可重現性。

## C 待驗證的疑點

這一組的每一條都有明確的程式機制，但要嘛在預設參數下不會觸發，要嘛涉及方法學解讀而非程式錯誤，要嘛因為缺少外部模組而無法追完。它們不應該被當成已確認的 bug 引用，但作者在改版時應該處理。

---

**C1  [疑點]** 

### perturbation 對長度小於 edit_distance 的序列必定 crash，預設實例不會觸發

- **位置：** `src/learner/dfa_learner.py:468-477`
- **來源：** 本機 code-review 流程列為未驗證疑點，learner 線實測後裁決。 

possible_ops 只對 delete 做長度 gate，replace 對空序列呼叫 randrange(0) 會 ValueError。單一樣本內的多次編輯是連續套用在同一個工作序列上的，所以只要序列長度小於 edit_distance，就有機會在一次擾動內被刪到空再抽到 replace。實測長度 1 搭配 edit_distance 2 時每次呼叫都 crash，長度 6 搭配 7 時 200 次裡 crash 49 次，長度 7 搭配 7 時為 0 次。六組預設 test instance 的長度都大於等於各自的 edit_distance，split 檔裡最短的訓練序列長度是 10，所以預設路徑不會觸發；透過命令列把 --edit_distance 調到大於實例長度，第一批取樣就會讓整個實例炸掉。

---

**C2  [疑點]** 

### 不帶 --max_evaluations 時 beam 沒有評估上限，baseline 卻有 500 次的上限

- **位置：** `src/experiments/runner.py:98, 221`
- **來源：** beam 線。 

beam 讀的是 `cfg.get("max_evaluations")`，預設 None；baseline 讀的是 `cfg.get("max_evaluations", 500)`。兩支實驗入口的 DEFAULT_LANGUAGE_CONFIGS 都沒有這個鍵，只有命令列的 --max_evaluations 會同時覆蓋兩者。附帶的兩份 log 顯示那兩次實驗是用 3000 跑的，所以已發表的表格不受影響；但只要論文裡有任何一組結果是在不帶這個旗標的情況下產生的，beam 就可以無上限地跑（log 顯示 beam 需要 1019 到 1827 次候選評估才會縮到 2 到 3 個狀態），而 baseline 會在 500 次被截斷。

---

**C3  [疑點]** 

### KL-LUCB 的非標準 early stop 把停止門檻放寬到 2ε

- **位置：** `src/explainer/automata_beam.py:515-531`
- **來源：** beam 線。 

標準 KL-LUCB 在 U(ut) 減 L(lt) 小於等於 ε 時停止，主迴圈的條件有做到；但這裡另外加了「連續 10 輪相對改善小於 1% 且 gap 小於等於 2ε 就提前停止」。這會讓回傳的 top 臂的保證從 (ε, δ) 變成 (2ε, δ)，方向是過度樂觀。從 log 看，在目前的樣本規模下 gap 的縮小速度不會連續 10 輪低於 1%，所以既有實驗幾乎不會觸發；較小的 batch_size 或較大的 delta 就可能觸發。

---

**C4  [疑點]** 

### 表格上的成功勾號用點估計判定，統計保證只到 τ 減 0.05

- **位置：** `src/explainer/automata_beam.py:961-977, 1048-1050`、`src/experiments/runner.py:414`
- **來源：** beam 線。 

確認迴圈保證被記錄的 beam 成員若 mean 大於等於 τ 則 lower bound 大於等於 τ 減 0.05（信心 1 減 δ），最終選擇卻用 mean 大於等於 τ 篩選再取狀態最少者。這是 Anchor 的原始語意，不是程式錯誤，但代表「達到 threshold」的真實保證是 agreement 大於等於 τ 減 0.05；再加上是在數十筆歷史紀錄裡挑「估計值恰好過線且狀態最少」的候選，會有 winner's curse 式的樂觀偏差。論文若宣稱「agreement 大於等於 τ 且信心 1 減 δ」則過度陳述。

---

**C5  [疑點]** 

### beam 的時間量測包含 RPNI 建構、graphviz 與繪圖，baseline 的不包含

- **位置：** `src/experiments/runner.py:302-304`
- **來源：** beam 線。 

beam 的計時區間包含最多 40 次 RPNI 嘗試、初始與最終 DFA 的 dfa_to_graphviz、plot_beam_stats 與 validation 評估；baseline 的計時只包含搜尋與最終選擇。init_automaton_time 有回傳但沒有被扣除。方向是對 beam 不利，log 裡 beam 仍然是最快的，所以不會翻轉「beam 較快」的結論，但 Time 欄位的絕對值不能直接解讀成搜尋時間。

---

**C6  [疑點]** 

### regular 任務的 alphabet 順序來自 set，固定 seed 也無法跨行程重現

- **位置：** `src/automaton/dfa_utils.py:13-23`、`src/learner/dfa_learner.py:460`、`examples/RPNI/run_regular_experiment.py:197`、`examples/RPNI/run_kllucb_comparison.py:401`
- **來源：** learner 線與實驗線各自發現。 

get_alphabet 回傳 set，實驗腳本直接把它轉成 list 傳給 DFASampler，perturbation 用 `_r.choice(symbols)` 選符號。字串 set 的迭代順序受 PYTHONHASHSEED 影響，所以同一串亂數在不同行程裡會選到不同符號，perturbation 的回傳值也是 set 的迭代順序，會影響 RPNI 收到的樣本順序。RUNNING.md 已經說明浮點結果不會逐位元相同、改看趨勢，所以這與文件不衝突；但 --no_parallel 旗標說明文字宣稱的「bit-for-bit reproducible」對 regular 任務不成立，除非固定 PYTHONHASHSEED。

---

**C7  [疑點]** 

### SequenceClassifier 對超過 max_len 的序列靜默截斷

- **位置：** `models/sequence_classifier.py:223-226`
- **來源：** 實驗線。 

_prepare_X 把每條序列截到 checkpoint 的 max_len 20。三個固定 test instance 的長度是 12、11、17，加上 edit_distance 的插入後最長是 19，所以預設實驗不會觸發。但訓練集裡存在長度 20 的序列，若使用者指定這類序列當 instance，插入操作產生的長度 21 或 22 的擾動會被 teacher 以前 20 個符號標記，擾動樣本的標籤就不再對應該序列本身。

---

**C8  [疑點]** 

### mnist 的 train 與 test 有大量重疊序列，teacher 的 test accuracy 偏樂觀

- **位置：** `dataset/mnist_stroke_loader.py:182`
- **來源：** 實驗線用 stub unpickler 讀 split 檔。 

mnist 的 12153 條不重複測試序列裡有 3088 條也出現在訓練集，訓練集內另有 537 條序列帶有互相衝突的標籤。這是四方向符號化把不同數字壓成相同短序列的自然結果，不是標籤對齊錯誤，但 log 報告的 clf_test 0.8973 因此含有 in-sample 成分。wafer 與 ECG 使用 UCR 官方切分，重疊分別只有 367 與 60 條，且沒有標籤衝突。這只影響 teacher 準確率的描述，不影響解釋實驗。

---

**C9  [疑點]** 

### DOT 載入器對帶額外屬性的 doublecircle 節點會靜默降級成 non-accepting

- **位置：** `src/automaton/load_dfa.py:91`
- **來源：** learner 線。 

state regex 要求 `[shape=xxx]` 後面立刻接右中括號，像 `"TRAP" [shape=circle, style=filled, fillcolor=lightgray];` 這種節點不會被匹配，只會透過 transition 被建立並預設為 non-accepting。目前三個 DOT 檔裡唯一帶額外屬性的節點剛好是 circle，所以結果正確；一旦有 doublecircle 節點帶額外屬性，teacher 的 accepting set 就會錯而且沒有任何警告。

---

**C10  [疑點]** 

### Explaining-FA 回傳的 CXp 位置被當成 0-based 的 path index

- **位置：** `src/learner/dfa_learner.py:1449-1456`
- **來源：** learner 線。 

_count_blamed_edges 假設 cxp 內的每個位置直接對應 path_edges[pos]，若 Explaining-FA 回傳的是 1-based 位置就會 off-by-one 並靜默跳過最後一個位置。external_modules/Explaining-FA 不在 repo 裡，無法驗證這個假設。

---

**C11  [疑點]** 

### dfa_to_mata 在沒有 accepting state 時會直接修改傳入的 DFA

- **位置：** `src/automaton/dfa_utils.py:397-400`
- **來源：** learner 線。 

為了保證輸出檔合法，它會把 init_state.is_accepting 改成 True。目前所有呼叫端在進入 _propose_delta 前都經過 is_valid_dfa 檢查，所以不會觸發，但這是一個會改變輸入物件的匯出函式。

---

**C12  [疑點]** 

### baseline 共用的 state 物件帶著全為零的標籤陣列

- **位置：** `src/baselines/search_baselines.py:685-694`（_common_init）
- **來源：** beam 線。 

_common_init 把 validation_data 放進 state['data']，但 state['labels'] 是全零的預配置陣列。目前三個 _single 運算子都不讀 state 參數，真正用的是 training_data 與 training_labels，所以這組零標籤是無害的死資料；但任何未來讀取 state 的程式碼都會拿到錯誤標籤。

## R 照文件重現時會卡住的地方

這一節的判準是「照著作者的 README 與 RUNNING.md 一步一步做之後，仍然會出錯或跑出與論文不同結果的地方」。純粹的安裝環境問題不算作者的責任，統一放在本節最後的附註。為了不靠推測，我在一台乾淨的機器上用 uv 建了 README 指定的 Python 3.11 虛擬環境，照文件安裝並執行，過程如下。

| 步驟 | 做法 | 結果 |
|---|---|---|
| 1 | 建立 Python 3.11 venv，執行 `pip install -r requirements.txt`。 | 第一次失敗，卡在 libmata 1.31.1 需要從原始碼編譯而系統沒有 cmake。在 venv 裡補裝 cmake 之後重跑，119 個套件全部裝好，torch、aalpy、pyswarms、libmata、tensorflow 都能 import。 |
| 2 | 原封不動執行 RUNNING.md 的 regular 指令。 | 啟動後立刻 FileExistsError，因為輸出資料夾 test_result/regular_0.8_1000 就是 repo 附帶的參考結果。 |
| 3 | 原封不動執行 RUNNING.md 的 real-world 指令。 | 同樣立刻 FileExistsError，撞到 test_result/realworld_0.8_1000。 |
| 4 | 加上 --output_suffix，用預設規模（batch 1000、init 1000）與 100 次評估上限只跑 SecureHandshake。 | 34 秒跑完，beam、SA、GA、PSO 四個方法都有結果，產物是 experiment_log.txt、各方法的 final_automata、beam 的兩張圖與 shared_init.pkl，沒有任何 csv 檔。開頭印出 ExplainLanguage 不可用的 warning，表格的 Initial validation 同樣是 1.0000。 |
| 5 | 把 init_num_samples 縮到 200 再跑一次。 | 初始 DFA 建構嘗試 40 次全部失敗，因為學出來的狀態數在 10 到 19 之間，不在程式要求的 25 到 65 的範圍內；整個 instance 被跳過，腳本仍以 exit code 0 結束。 |
| 6 | 執行 `python analysis/parse_results.py`。 | FileNotFoundError，因為它只讀 test_result/final_result，而這個目錄不存在。 |
| 7 | 執行 `python analysis/make_plots.py`。 | FileNotFoundError，因為它只讀 analysis/summary_table.csv，而這個檔案要靠步驟 6 產生。 |

---

**R1  [重現]** 

### 照 README 安裝完成後，DELTA 操作會靜默失效

README 的安裝步驟完全沒有提到 external_modules/Explaining-FA，這個模組不在 repo 裡，被 .gitignore 排除，也沒有 submodule 或任何取得方式的說明；但 README 的專案結構圖把它列為「Delta 操作用的 CXp solver」。照文件安裝完成後跑實驗不會報錯，只在 import 時印一行 warning，然後如 A4 所述，DELTA 在每個奇數回合只會回傳父代自己。使用者會以為自己重現了論文方法，實際上跑的是只有 Delete 與 Merge 兩種操作的演算法。

---

**R2  [重現]** 

### RUNNING.md 的兩條重現指令一啟動就失敗

repo 附帶的參考結果放在 test_result/regular_0.8_1000 與 test_result/realworld_0.8_1000，而 RUNNING.md 給的指令（agreement_threshold 0.8、batch_size 1000）推導出來的輸出資料夾正好是同名路徑，腳本在第 320 至 326 行檢查到資料夾已存在就直接 raise FileExistsError。錯誤訊息本身有教怎麼繞過（加 --output_suffix 或先搬走舊資料夾），但文件寫的指令照抄就是會失敗，而且 --output_suffix 又會讓 parse_results.py 略過這個資料夾（B8）。

---

**R3  [重現]** 

### 分析流程照文件走不通，正確的順序沒有寫在任何地方

RUNNING.md 第 4 節描述的 results.csv 沒有任何程式會產生，列出的欄位名稱也對不上任何實際產物；本機實跑證實實驗腳本只產生 experiment_log.txt 與各方法的自動機檔案。實際的分析流程是三步：先把結果資料夾手動搬進 test_result/final_result/ 底下，再執行 parse_results.py 從 log 解析出 analysis/summary_table.csv，最後執行 make_plots.py 讀這個 csv 畫圖。這三步文件都沒有寫，第一步沒有任何腳本會做，而且即使走到第三步，make_plots.py 也會因為 B7 描述的問題在只跑過 0.8 的情況下 ValueError。

---

**R4  [重現]** 

### RUNNING.md 的參數表裡有死參數，也沒有說明初始 DFA 的隱藏限制

參數表列出的 --num_test_instances 與 --max_length 實際上沒有作用（A11）。表中的 --init_num_samples 可以調，但程式在 automata_beam.py 第 743 行要求初始 DFA 的狀態數落在 init_state_range 預設的 25 到 65 之間，否則重抽重學最多 40 次後放棄整個 instance；本機把它縮到 200 就觸發了這個情況，而腳本只印一行錯誤、以 exit code 0 結束。這個範圍限制與失敗行為在 README 與 RUNNING.md 都沒有提到。

---

**R5  [重現]** 

### 照 README 重新訓練 teacher 會失敗

README 的「新增一個 language / dataset」段落引導使用者訓練自己的 classifier，但三支既有的訓練腳本都指向不存在的 datasets 目錄（B9），照樣板改寫的新腳本會遇到同樣的路徑問題。這一段還教人設定 alphabet、hidden_dim、num_layers 與 dropout，這些參數在執行時全部不會被讀取（B5）。

### 附註：安裝面與文件不一致

以下項目照文件操作之後仍然可以繼續，或者屬於環境而非作者程式的問題，依判準不列入主要發現。

- requirements.txt 釘的 libmata 1.31.1 在 PyPI 上只有原始碼發行版，編譯需要 cmake，README 沒有提到；而 libmata 與 python-sat 在 repo 內的程式碼裡完全沒有被 import，它們是 Explaining-FA 的相依套件。tensorflow、transformers、tokenizers、tensorboard 等重量級套件同樣沒有被 import。 
- README 指定 python3.11 建 venv，機器上沒有 3.11 的話要自行取得。 
- README 的 clone 網址指向舊的 repo 名稱 anchor-automata-explainer，GitHub 的 rename redirect 會指到同一個 commit，所以指令可以用。 
- README 把第三個 regular 任務寫成 Navigation Workflow，程式裡實際的名稱是 MultiObligationOrder。 
- pyswarms 會在工作目錄留下一個空的 report.log，這是 pyswarms 的預設行為，不是作者的程式產生的。 
- regular 任務的擾動樣本受 PYTHONHASHSEED 影響（C6），RUNNING.md 已說明只比對趨勢不比對數字，兩者一致。 
- 附帶的參考結果每個任務只有 instance_00，與 A11 描述的單一 instance 行為一致；作者的 log 裡輸出路徑是 /home/yihua/anchor-llm，顯示這批結果是在改名前的目錄跑的。 

## 已否決的候選

以下候選在審查過程中被提出，追完觸發路徑或實測之後判定不成立。列出來是為了讓讀者知道這些方向已經查過，不必重複。

1. build_shared_init 對預配置的零陣列切片可能與較短的 data 錯位：預設參數下 sampler 每一批都精確回傳 1000 筆（六組設定各 20 次蒙地卡羅，所需嘗試次數 1250 到 3700，遠低於 10000 的上限），而且即使不足額，下游會直接因為長度不同而 broadcast ValueError，不會靜默混入錯誤標籤。 
2. DOT 載入器的 edge regex 會掉 attribute：repo 內所有 .dot 檔的邊都是單一 label，dfa_to_graphviz 輸出的多屬性格式不會被重新載入，只是潛在脆弱點。 
3. Delete、Merge、Delta 產生的 DFA 可能不合法：對 SecureHandshake 初始 DFA 產生的 29 個 DELETE、195 個 MERGE、148 個 DELTA 候選，以及 baseline 用的三個單步運算子各 60 次呼叫，逐一檢查 determinism、對整個 alphabet 的 completeness、dangling transition、initial state 與 accepting set，全部 0 個違規。 
4. aalpy 的 copy() 與 pickle 可能換掉 initial state：initial state 的 prefix 恆為空 tuple 且排序鍵唯一為 0，所以在 to_state_setup 與 from_state_setup 之間永遠排第一位；實測 delete 後含過期 prefix 的 DFA 經 copy 與 pickle round trip 仍保持 initial 在首位。 
5. validation 被拿去做候選選擇造成洩漏：beam 只看 all_history 的 training_agreement，baseline 只看固定 batch 的 training_agreement，validation 只用於回報。 
6. SequenceClassifier 的 batch 推論與單筆推論不一致：_prepare_X 永遠補到固定的 max_len，load 與 predict 都呼叫 eval，BatchNorm 用 running statistics，LSTM 的 dropout 在 eval 模式關閉。 
7. 三個 loader 的序列與標籤錯位：mnist 用 train_test_split 同時打亂 X 與 y，ECG 與 Wafer 保留 UCR 官方切分並逐列映射，split 檔裡 X 與 y 長度一致。 
8. quantile 斷點洩漏測試資料：ECG 與 Wafer 的 loader 只用訓練序列擬合斷點。 
9. sig_cache 以 id() 為 key 的汙染：每個進入 new_dfas 的候選都在建立當下寫入自己的 signature，父 DFA 在整個呼叫期間存活，id 不可能被重用。 
10. run_RPNI 因標籤衝突回傳 None：perturbation 以 set 去重，同一序列不會以兩種標籤出現，cache 也保證同序列標籤一致。 
11. draw_automata_samples_parallel 的結果順序與 automata_list 不對齊：sampled_batches、score_payloads 與 worker_results 都用 zip 對齊，除了 B1 之外沒有對齊問題。 
12. _id_reuse_guard 不足以避免 id 重用：origin 與所有候選都被持有，init 階段丟棄的候選也留在清單裡直到函式結束。 
13. beam 的確認迴圈可能無限循環：beta 固定而樣本數增加時上下界都收斂到 mean，只有母體 agreement 恰好等於 τ 減 ε 的邊界情況會拖很久，log 中未見異常。 
14. beam 與 _select_final 回報的狀態數不一致：所有運算子在回傳前都已呼叫 remove_unreachable_states，兩邊一致。 
15. Tee 巢狀使用導致 stdout 還原錯亂：close 會把 sys.stdout 還原成建構時擷取的 console，兩層 finally 的順序與此相容。 
16. --parallel 與 --no_parallel 的 default None 會蓋掉 cfg：get_languages_config 會略過值為 None 的覆蓋。 

## 涵蓋範圍與審查方法

審查分成五條線。9 月 2 日先由本機的 code-review 流程做第一輪正確性審查，同時由另一條線做可重現性的靜態審查；9 月 7 日再分三條線補完正確性審查，分別負責 learner 與 automaton 模組、beam search 與 KL-LUCB 核心、實驗腳本與資料管線，並且在乾淨環境裡實際照文件跑了一遍。每條 CONFIRMED 都追到了實際的實驗入口與預設參數，多數另外用小型腳本實測；為了核對第三方套件的行為，另外讀了 aalpy 1.5.3、pyswarms 1.3.0 與 simanneal 0.5.0 的原始碼。

| 檔案 | 行數 | 審查線 | 結果 |
|---|---|---|---|
| src/learner/dfa_learner.py | 1809 | 本機流程、learner 線 | 已完整審過，找到 A2、A3、A4 與 A15 的 cache 部分，另有 C1、C10 與 C6 的一部分。 |
| src/baselines/search_baselines.py | 1532 | 本機流程（PSO 與 GA）、beam 線（SA 與共用 helper） | 已完整審過，找到 A5 到 A9 與 C12。 |
| examples/RPNI/run_kllucb_comparison.py | 1280 | 本機流程、實驗線 | 已完整審過，找到 A12、A13、A14、B2、B3 與 B5 的一部分。 |
| src/explainer/automata_beam.py | 1096 | 本機流程、beam 線 | 已完整審過，找到 A1、B1、B4、C3、C4；六個 KL-LUCB 核心函式與公式逐項對照無誤。 |
| src/baselines/tune_baseline_params.py | 762 | 實驗線 | 已完整審過，找到 A10。 |
| src/automaton/dfa_utils.py | 632 | learner 線 | 已完整審過，實際被呼叫的函式未發現正確性問題，另有 C11；dfa_product、dfa_union、trim_dfa、merge_linear_edges、simplify_dfa 等六個函式是沒有呼叫端的 dead code，其中 merge_linear_edges 會改變接受語言、trim_dfa 回傳的型別與其他程式不相容。 |
| src/experiments/runner.py | 473 | beam 線 | 已完整審過，與 A1 共用，另有 C2、C5；先前的疑點 (D) 裁決為不成立。 |
| analysis/make_plots.py | 456 | 本機流程、實驗線 | 已完整審過，找到 B7。 |
| examples/RPNI/run_regular_experiment.py | 376 | 可重現性線、實驗線 | 已完整審過，找到 A11、R2 與 C6 的一部分。 |
| examples/RPNI/run_realworld_experiment.py | 341 | 可重現性線、實驗線 | 已完整審過，找到 A11 與 B5。 |
| models/sequence_classifier.py | 323 | 實驗線 | 已完整審過，找到 C7；padding、eval 模式與 device 處理未發現問題。 |
| src/automaton/load_dfa.py | 321 | 本機流程、learner 線 | 已完整審過，找到 A15 的 race 部分、B6、C9；三個 DOT 檔的所有 transition 行都能被正確解析。 |
| dataset/ECG_loader.py、dataset/Wafer_loader.py | 596 | 實驗線 | 已完整審過，未發現正確性問題；B9 的觸發點在呼叫端。 |
| examples/RPNI/run_wafer_param_ablation.py | 243 | 可重現性線、實驗線 | 已完整審過，未發現正確性問題，但它繼承 B5 的錯誤描述。 |
| dataset/mnist_stroke_loader.py | 195 | 實驗線 | 已完整審過，找到 B9 與 C8。 |
| models/mnist_classifier.py、ECG_classifier.py、Wafer_classifier.py | 441 | 實驗線 | 已完整審過，找到 B9。 |
| analysis/parse_results.py | 129 | 本機流程、可重現性線、實驗線 | 已完整審過，找到 B8；三個 regex 與 runner 的實際輸出格式逐一比對過，能正確解析附帶 log 的六張表。 |
| src/learner/factory.py、base.py、__init__.py；src/automaton/metrics.py、__init__.py；src/tee.py | 303 | learner 線、beam 線、實驗線 | 已完整審過，未發現正確性問題。 |

沒有做的事有三件。第一，沒有用完整規模（3000 次評估、六個任務）重跑實驗，本機實跑只到 100 次評估的單一任務，目的是驗證流程而不是數字。第二，Explaining-FA 不在 repo 內，所有 CXp 相關的程式路徑只能靜態審查，A4 裡 regular 任務 DELTA 從未產生候選的根因無法再往下追。第三，GA 與 PSO 的核心迴圈只由本機的 code-review 流程審過一次，9 月 7 日的三條線沒有再獨立覆核。

## 做得好的部分

為了讓這份報告的判斷有對照基準，以下列出審查中確認沒有問題、而且做得比一般研究程式碼好的地方。

- KL-LUCB 的六個核心函式（kl_bernoulli、兩個 bound 求解、compute_beta、select_critical_arms 與停止條件）與 Kaufmann 與 Kalyanakrishnan 的公式以及 Anchor 的實作逐項對照，全部一致；二分法只做 9 次的誤差最大 1.76e-3，而且方向永遠保守，蒙地卡羅檢查 lower bound 超過真值的機率約 0.001，低於名義上的 0.01。 
- seed 處理整體嚴謹：主實驗固定 42，資料切分固定 random_state，KL-LUCB 比較有 per-seed 重跑機制，平行路徑用 per-task 的 random.Random 避免共享。A12 是這套機制裡唯一的破口。 
- 所有路徑都以 PROJECT_ROOT 為基準，換機器不需要改路徑。 
- RUNNING.md 誠實說明浮點結果不會逐位元相同，改以三個趨勢比對，這是合理的做法。 
- teacher classifier 的推論正確：padding 到固定長度、eval 模式、device 處理都沒有問題；三個 split 檔的 alphabet 與 checkpoint 的 symbol2id 一致，三個預設 test instance 都確實存在於對應的訓練集裡，標籤與 log 一致。 
- Delete、Merge、Delta 三種操作在實測的數百個候選上都維持 DFA 的合法性，這是搜尋能穩定跑完的基礎。 
- 實驗腳本拒絕覆寫既有結果資料夾，並在錯誤訊息裡說明繞過方法，這個設計本身是對的，問題只在文件與附帶結果的配置。 

---

這份報告由 Claude Code 在 2026 年 9 月 2 日與 9 月 7 日兩次 session 中產生。四條靜態審查線的原始報告（review_local_findings.md、review_learner.md、review_beam.md、review_experiments.md）、實跑的完整 log，以及所有驗證腳本都保存在與這份報告相同的 review 目錄裡，審查期間 repo 的程式碼沒有被修改。
