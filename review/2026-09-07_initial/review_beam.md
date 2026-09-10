# automata_beam.py、runner.py 與 SA baseline 的正確性審查報告

審查標的為 src/explainer/automata_beam.py（全文 1096 行）、src/experiments/runner.py（全文 473 行），以及 src/baselines/search_baselines.py 的共用 helper（第 1 到 120 行、第 627 到 841 行）與 SA 段（第 842 到 1088 行）。為了追觸發路徑，另外完整讀了 src/learner/dfa_learner.py 的 DFASampler、三種運算子與 propose_automata、src/automaton/dfa_utils.py 與 metrics.py、src/learner/factory.py、examples/RPNI 的兩個實驗入口、simanneal 0.5.0 與 aalpy 1.5.3 的原始碼（以 pip download 解壓到 scratch 目錄），以及 test_result/regular_0.8_1000 與 test_result/realworld_0.8_1000 兩份 experiment_log.txt。驗證腳本在 scratchpad/agent_beam/ 底下，分別是 kllucb_check.py（KL-LUCB 信心界與 beta 公式的數值對照）、sa_schedule.py（SA 溫度排程）與 perturb_mc.py（sampler 實際回傳筆數與 validation 集重疊比例的蒙地卡羅）。

## 1. CONFIRMED 的正確性 bug（依嚴重程度排序）

### C1. 所謂的 validation 資料就是建初始 DFA 的 RPNI 訓練樣本，Validation 欄位量到的不是對 teacher 的忠實度

位置在 automata_beam.py 第 750 行（init 迴圈抽樣）、第 794 到 795 行（validation 指派）、第 670 到 671 行（_make_result 回傳）；runner.py 第 140 到 141 行（build_shared_init 原樣轉交）；search_baselines.py 第 685 到 686 行（_common_init）、第 764 行與第 789 行（_select_final 計算 validation）、第 1067 行（SA）、第 1186 行（GA）、第 1424 行（PSO）。

資料流追蹤結果如下。automata_beam 第 750 行在每一次 init attempt 呼叫 `self.sample_fcn(num_samples=init_num_samples, compute_labels=True)`，這是 DFASampler.__call__，它用 perturbation 抽出 init_num_samples 筆擾動序列並向 teacher 取得標籤。第 751 到 754 行把同一批樣本切成正負例交給 `create_init_automata`，也就是 aalpy 的 `run_RPNI`。迴圈跳出時的 init_samples 正是被採用的那個 origin_automaton 的 RPNI 輸入。第 794 到 795 行直接把 `self.validation_data = list(init_samples)` 與 `self.validation_labels = init_labels`。_make_result 把它們放進結果 dict，runner.build_shared_init 第 140 到 141 行原樣轉給 SharedInit，_common_init 再原樣交給 SA、GA 與 PSO。相對地，所有方法的 training 資料都另外來自 `sample_fcn(num_samples=batch_size)` 的新抽樣，beam 是 KL-LUCB 逐輪新抽，三個 baseline 則固定使用 beam 抽到的第一批 1000 筆。

針對補充指示的三個問題，答案如下。

第一，validation 資料確實就是 RPNI 的訓練樣本，不是另外抽的 held-out 集合，這一點 CONFIRMED。

第二，RPNI 的輸出保證與其輸入樣本一致（aalpy run_RPNI 的文件寫明「Resulting model conforms to the provided data」，而 make_input_complete 只補 sink 邊，不影響原本就能完整走訪的序列），所以 Initial validation 恆等於 1.0000，六個任務的 log 全部如此，這是恆真式而不是量測結果。Final validation 量到的是「精簡後的 DFA 在初始 DFA 的歸納樣本上與初始 DFA 一致的比例」，本質上是與初始 DFA 的相似度，而不是與 teacher 的局部一致性。realworld log 的 wafer 列是最清楚的例子：SA 與 GA 回傳未修改的 36 state 初始 DFA，其 training agreement 只有 0.748，卻在 Validation 欄位拿到 1.0000；PSO 回傳 34 state 拿到 0.942；beam 精簡到 5 state 只拿到 0.716。這一欄實際上獎勵「不去動初始 DFA」。

第三，這個機制對四個方法是對稱的，而且沒有任何方法用 validation 做選擇（beam 用 all_history 裡的 training_agreement，baseline 用固定 batch 上的 training_agreement），所以不存在選擇性洩漏。但效果並不對稱，越積極精簡的方法在這一欄越吃虧。因此任何依據 Validation (Init→Final) 欄位對 beam 所下的結論，無論是「beam 在 validation 上也維持得不錯」或「beam 在 validation 上輸給某個 baseline」，都不能成立，因為該欄位量的不是對 teacher 的忠實度。另外我用 perturbation 的蒙地卡羅量了 validation 集與每一批 training batch 的重疊比例，regular 三個任務分別是 7.2%、11.8% 與 15.1%，realworld 三個任務分別是 36.7%、46.9% 與 47.5%，所以即使把它當成同分布的另一組樣本，也不是乾淨的 held-out。

對論文結論的影響是「會」。凡是使用 Validation 欄位的敘述都需要重新解讀，Train 欄位與 States 欄位不受這個問題影響。

### C2. SA 的溫度排程與實際 move 數脫鉤，退火從未發生

位置在 search_baselines.py 第 1056 到 1057 行（effective_steps 的計算）、第 900 到 931 行（每個 move 消耗 pool_size 次評估）、第 985 到 989 行（early stopping），以及 simanneal anneal.py 第 193 到 195 行（溫度按 step 除以 steps 做指數降溫）。

runner 的預設值是 sa_steps=500、max_evaluations=500（附帶 log 的那兩次實驗是 3000）、sa_candidate_pool_size=10。第 1056 行 `effective_steps = max(int(steps), int(max_evaluations) + 1)` 的註解寫著「確保有足夠的 move 用完評估預算」，它假設每個 step 消耗一次評估；但 move() 每次會評估 pool_size 等於 10 個候選，所以預算只夠 50 個 move（log 的設定則是 300 個），而降溫是按 step 除以 effective_steps 計算的。用預設值計算，第 50 個 move 時溫度仍為 3.99，dE 等於 0.25 的接受機率是 0.939。log 裡 SecureHandshake 的 SA 只做了 34 個 move 就因為連續 10 輪沒有新的 best 而停止，此時溫度為 10 乘上 exp(−ln(10000)·34/3001)，約為 9.0，就算 agreement 掉整整 1.0 的 move 也有 0.90 的機率被接受。換句話說 Metropolis 幾乎接受一切，SA 退化成「每輪從 10 個鄰居挑最低 energy 的那一個然後無條件移動過去」的貪婪隨機下降，從頭到尾沒有低溫階段。log 同時顯示 SA 只用掉 3000 之中的 340（SecureHandshake）與 214（mnist）就 early stop，因為 DFA 縮到最小之後 energy 無法再下降。

觸發情境是 runner 的預設呼叫路徑，regular 與 realworld 兩個實驗都會發生。對論文結論的影響是「會」，表格裡的 SA 列不是 simulated annealing 的結果，而是一個退化演算法的結果；「beam 優於 SA」的幅度可能被高估，SA 被低估的可能性偏高，但實際幅度無法從程式碼判定。

### C3. SA 每個 step 多做一次未計入預算的 agreement 評估

位置在 search_baselines.py 第 991 到 1000 行（energy）與 simanneal anneal.py 第 182 行、第 196 到 199 行。

move() 回傳 None，所以 simanneal 在每個 step 之後呼叫 `self.energy()`，在 1000 筆 training 資料上重算 self.state 的 agreement，anneal() 開頭也會算一次。這些評估沒有加進 evaluations_count，SA 實際做的評估次數是 (pool_size + 1) 乘上 step 數再加 1，比報告的數字多約 10%，而 Time 欄位包含這些工作。對 agreement 與 state 數的結果沒有影響，對「相同評估預算」的公平性敘述與 SA 的 Time 欄位有輕微影響。

## 2. PLAUSIBLE 的疑點

### P1. 預設參數下 beam 沒有評估上限而 baseline 有 500 的上限

位置在 runner.py 第 98 行 `max_evaluations=cfg.get("max_evaluations")`（beam，預設 None）與第 221 行 `max_evaluations=cfg.get("max_evaluations", 500)`（baseline）。兩個實驗入口的 DEFAULT_LANGUAGE_CONFIGS 都沒有 max_evaluations 這個 key，只有 CLI 的 --max_evaluations 會同時覆蓋兩者。附帶的 log 顯示那兩次實驗是用 3000 跑的，所以上限相同；但如果論文裡有任何一組結果是在不帶 --max_evaluations 的情況下產生的，beam 可以無上限地跑（log 顯示 beam 需要 1019 到 1827 次候選評估才會縮到 2 到 3 個 state），而 baseline 會在 500 次被截斷。標為 PLAUSIBLE 是因為取決於實際的執行指令。

### P2. KL-LUCB 的非標準 early stop 把停止門檻放寬到 2ε

位置在 automata_beam.py 第 515 到 531 行，關鍵判斷在第 525 行。標準 KL-LUCB 在 U(ut) − L(lt) ≤ ε 時停止，第 508 行的主迴圈條件有做到；但這裡另外加了「連續 10 輪相對改善小於 1% 且 gap ≤ 2ε 就提前停止」。這會讓回傳的 top 臂的 (ε, δ) 保證變成 (2ε, δ)，偏差方向是過度樂觀，也就是用較少的樣本就宣告分出高下。從 log 觀察，每個候選最多累積 9001 筆樣本，gap 的縮小速度在這個規模下不會連續 10 輪低於 1%，所以在既有實驗裡幾乎不會觸發；但若參數改變（例如較小的 batch_size 或較大的 delta）就可能觸發。

### P3. beam 的時間量測包含 RPNI 建構、graphviz 與繪圖

位置在 runner.py 第 302 到 304 行。從 start 到 beam_elapsed 之間包含最多 40 次 RPNI 嘗試（每次 1000 筆樣本與 teacher 查詢）、初始與最終 DFA 的 dfa_to_graphviz、plot_beam_stats，以及 validation 評估；baseline 的計時只包含搜尋、_select_final 裡的 graphviz 與 validation 評估。init_automaton_time 有回傳但沒有被扣除。方向是對 beam 不利，也就是 beam 的時間被高估；log 中 beam 仍然是最快的，所以不會翻轉「beam 較快」的結論，但 Time 欄位的絕對值不能直接解讀成搜尋時間。

### P4. success 與表格上的勾號是用點估計判定，統計保證只到 τ − ε_stop

位置在 automata_beam.py 第 1048 到 1050 行與第 961 到 977 行，以及 runner.py 第 414 行。to_sample 迴圈保證被記錄的 beam 成員若 mean ≥ τ 則 lb ≥ τ − 0.05（信心 1 − δ），最終選擇卻用 mean ≥ τ 篩選再取 state 最少者。這是 Anchor 的原始語意，不是程式錯誤，但表示「達到 threshold」的真實保證是 agreement ≥ τ − 0.05；再加上是在數十筆歷史紀錄中挑「估計值恰好過線且 state 最少」的候選，會有 winner's curse 式的樂觀偏差。Train 欄位的最終數字就是這個被挑中的估計值。

### P5. 範圍外的觀察：regular 實驗中 DELTA 每一輪都只回傳父代本身

位置在 dfa_learner.py 第 1623 行與第 1654 到 1655 行，證據是 regular_0.8_1000/experiment_log.txt 裡所有 op=DELTA 的行都是 candidates=1。_propose_delta 永遠把父代放進候選清單，若 CXP 分析回傳空集合就只剩父代。regular 三個任務的每一個 DELTA 回合都只有 1 個候選，而 realworld 的 mnist 在第 1 輪就有 42 個 DELTA 候選，表示 regular 實驗裡 DELTA 運算子實際上沒有作用。論文若宣稱三種運算子都參與了 regular 實驗的精簡，與 log 不符。根因在 _aggregate_cxp_analysis 或外部的 ExplainLanguage，不在我負責的檔案，這裡只記錄現象。

## 3. 對已知 PLAUSIBLE (D) 的裁決：REFUTED（預設參數下不會發生）

(D) 的疑慮是 runner.py 第 134 到 135 行用 `state["labels"][:batch_size]` 切預先配置的零陣列，而 `state["data"][:batch_size]` 是實際抽到的較短 list，beam 記錄的樣本少於 batch_size 時會 shape mismatch 或混入幽靈的 label 0 樣本。

追蹤結果如下。第一，automata_beam.update_automata_state（第 407 到 427 行）與 draw_automata_samples_parallel（第 353 到 372 行）都以同樣的順序做 `state["data"].extend(raw_data)` 與 `state["labels"][current_idx:current_idx+n] = labels` 然後 `current_idx += n`，所以對任何 i < current_idx，data[i] 與 labels[i] 永遠對齊。第二，錯位只會在 build_shared_init 執行時 current_idx 小於 batch_size 的情況發生，此時 data[:batch_size] 有 current_idx 筆而 labels[:batch_size] 有 batch_size 筆，compute_acceptance_stats 的 `(labels == 1) & accepts` 會因為兩個陣列長度不同而直接拋出 numpy 的 broadcast ValueError，所以結果會是第一個 baseline 立刻 crash，而不是靜默混入幽靈樣本。第三，automata_beam 在 init 之後第一件事就是第 806 行對 origin 抽一整批 batch_size 的樣本，DFASampler.perturbation 只有在鄰域裡不重複序列不足、連續 51 次抽到重複或超過 10000 次嘗試時才會回傳較少筆數。我把 perturbation 的程式碼逐字複製後對六個預設設定各做 20 次蒙地卡羅（perturb_mc.py），每一次都精確回傳 1000 筆，所需嘗試次數在 1250 到 3700 之間，遠低於 10000 的上限，也從未觸發連續重複的停止條件；附帶 log 的「1000 training samples」也證實這一點。第四，即使某個極端設定（例如長度 3 的 instance 配上 4 個符號與 edit_distance 1，鄰域只有幾十個不重複序列）讓每批都不足，整個搜尋累積的樣本數也會在幾批之後超過 batch_size，此時 labels[:batch_size] 與 data[:batch_size] 依然對齊，只是不再是「恰好第一批」，而是第一批加上第二批的開頭並且會含重複序列，這與 docstring 的說法不符，但不會產生錯誤的標籤。

因此 (D) 在預設參數下不會發生，標 REFUTED；唯一殘餘的是 docstring 對「exact first batch」的描述在 sampler 回傳不足額時會失準。

## 4. REFUTED 的候選（簡短）

- aalpy 的 Dfa.copy() 與 pickle 是否可能換掉 initial state 或漏掉 state，導致 process pool 裡評分的自動機與主程序的不同。追過 aalpy 1.5.3 的 Automaton.copy、__reduce__、Dfa.to_state_setup 與 from_state_setup 之後確認不會。to_state_setup 依 prefix 長度排序，initial state 的 prefix 是空 tuple、排序鍵為 0 且是唯一的 0，所以永遠排第一位，from_state_setup 就會拿它當 initial；state_id 由 RPNI 產生且唯一，sink 只在缺邊時加入一次，所以字典不會覆蓋。
- beam 回報的是 remove_unreachable_states 之後的 state 數，而 _select_final 回報的是紀錄裡的 state 數，兩者是否不一致。確認 _delete_candidate_from_state、_merge_candidate_from_pair、_delta_candidate_from_edge 與三個 _propose_*_single 在回傳前都已呼叫 remove_unreachable_states，所以紀錄裡的 state 數已是修剪後的值，_make_result 第 625 行的修剪是無作用的，兩邊一致。
- _common_init 把 validation_data 放進 state['data'] 但 state['labels'] 全為零，是否會讓 baseline 用錯標籤。確認 _propose_single_neighbor 與三個 _single 運算子都不讀 state 參數，真正用的 data 與 labels 是 training_data 與 training_labels，所以這個零標籤的 state 目前是死資料，無害但屬於潛在地雷。
- _id_reuse_guard 是否足以避免 id 重用。origin 由 self.automatas 與區域變數持有，所有候選都被 extend 進 guard，init 階段被丟棄的候選仍留在 discarded_candidates 清單裡直到函式結束，所以曾被當 key 的物件都不會被回收，REFUTED。
- kllucb_automata 的 init_stats 陣列與 self.state 是否重複計數。兩者由同一次抽樣分別加上同一個增量，get_init_stats 之後再讀 state 的值與陣列一致，REFUTED。
- draw_automata_samples_parallel 的結果順序是否與 automata_list 對齊。sampled_batches 依 futures 順序收集，score_payloads 與 worker_results 都用 zip 對齊，回傳的 tuple 依 automata_list 順序，除了已知的 fallback 重複 append 之外沒有對齊問題，REFUTED。
- validation 是否被拿去做選擇造成洩漏。beam 的最終選擇只看 all_history 的 training_agreement，baseline 的 _select_final 只看紀錄裡的 training_agreement，validation 只用於回報，REFUTED。
- beam 第 962 行的確認迴圈是否可能無限循環。beta 固定而樣本數增加時 ub 與 lb 都收斂到 mean，三種情況都會停止，只有母體 agreement 恰好等於 τ − ε_stop 的邊界情況會拖很久；log 中單一候選最多 9001 筆，未見異常，不列為 bug。
- DELTA 回合把父代重新放進候選並再次寫入 all_history，是否影響最終選擇。同一物件的兩筆紀錄 state 數相同，min 取先插入者，回報的 training_agreement 是較早的估計值，只影響數字的小數位，不影響選中的 DFA。

## 5. KL-LUCB 實作與公式對照的總結

我把 automata_beam.py 第 32 到 119 行的六個函式用 ast 抽出來，以 numpy 做數值驗證（kllucb_check.py），並逐項對照 Kaufmann 與 Kalyanakrishnan 的 KL-LUCB 以及 Anchor 的實作，結果如下。

- kl_bernoulli 的公式正確，兩端以 1e-12 裁切，p 為 0 或 1 時不會產生 NaN。
- dup_bernoulli 與 dlow_bernoulli 用 Pinsker 不等式給的 sqrt(level/2) 當二分區間，區間正確；n_iter 為 10 只做 9 次二分（alibi 用 17），與 200 次二分的解相比最大誤差為 1.76e-3，而且方向永遠保守，也就是 ub 只會偏高、lb 只會偏低，因此只會多抽一點樣本，不會產生過度樂觀的判斷。以 δ 等於 0.01、n 等於 1000、p 等於 0.9 為例，lb 為 0.8687 而精確值為 0.8688。蒙地卡羅檢查 n 等於 1000 時 P(lb 大於真值) 約 0.001，低於名義上的 0.01。
- compute_beta 與論文的 β(t, δ) = log(k1·K·t^α/δ) + log log(k1·K·t^α/δ) 完全一致，k1 為 405.5、α 為 1.1，K 取候選數，四組參數的數值差為 0。
- select_critical_arms 依平均值分成 top 與 rest，只更新 rest 的 ub 與 top 的 lb，取 rest 中 ub 最大者與 top 中 lb 最小者，與 KL-LUCB 一致；沿用舊值的部分只會被讀取於對應集合，與 Anchor 相同。
- 停止條件 U(ut) − L(lt) ≤ ε 正確，t 每輪加一，未抽樣的臂先各抽 1 筆，都與 Anchor 相同；非標準的 2ε early stop 見 P2。
- 樣本數與評估次數的計數方面，t_nsamples、t_positives、t_negatives 與 KL-LUCB 的陣列同步累加；max_evaluations 計的是「提出的候選數」（含無效候選與 DELTA 回合的父代），不是 teacher 查詢數，teacher 查詢數在 num_preds，也就是 current_idx。
- beam 選出後的確認迴圈用 beta = log(1/(δ/(1+(B−1)K)))，與 Anchor 相同；to_sample 的條件與 alibi 的版本略有差異（mean 小於 τ 時這裡以 ub ≥ τ 而非 ub ≥ τ + ε_stop 判斷繼續），方向上此處對 mean 小於 τ 的候選稍早停止，對 mean 大於 τ 的候選略晚停止，不構成錯誤。
- 成功判定與最終選擇的統計語意見 P4，保證只到 τ − ε_stop，這與 Anchor 相同，但論文若宣稱「agreement ≥ τ 且信心 1 − δ」則過度陳述。
- 並行路徑方面，除了已知的 fallback 重複 append 之外，seed 化的 per-task RNG、zip 對齊與 state 寫入都正確；pickle 進出 process pool 不改變自動機的語言。

## 6. 涵蓋範圍聲明

- src/explainer/automata_beam.py 第 1 到 1096 行已逐行完整審過，發現 1 個新的 CONFIRMED 問題（C1，validation 來源，與 runner.py 共用）與 2 個 PLAUSIBLE 疑點（P2、P4），未再發現已知清單之外會 crash 或改變數值的正確性 bug。
- src/experiments/runner.py 第 1 到 473 行已逐行完整審過，與 C1 共用一個 CONFIRMED 問題，另有 2 個 PLAUSIBLE 疑點（P1、P3）；已知 (D) 裁決為 REFUTED。
- src/baselines/search_baselines.py 第 1 到 120 行的 logging 與 loss helper 已完整審過，未發現正確性問題。
- src/baselines/search_baselines.py 第 627 到 841 行的 SharedInit、_common_init、_compute_agreement 與 _select_final 已完整審過，除了已知的第 789 行問題之外未發現新的正確性問題；_common_init 的零標籤 state 屬無害的死資料。
- src/baselines/search_baselines.py 第 842 到 1088 行的 DFAAnnealer 與 sa_dfa_search 已完整審過，發現 2 個 CONFIRMED 問題（C2、C3）。
- src/baselines/search_baselines.py 第 1102 到 1532 行的 GA 與 PSO wrapper 只為確認共用 helper 的呼叫方式而讀過，未對其核心迴圈另作審查。
