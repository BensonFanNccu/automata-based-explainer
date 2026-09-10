# 實驗腳本、資料處理與分析程式的正確性審查報告

審查範圍是 examples/RPNI 底下的四支實驗腳本、src/baselines/tune_baseline_params.py、dataset 底下的三個 loader、models 底下的 classifier 相關程式、analysis 底下的兩支分析程式，以及 src/tee.py。為了追蹤觸發路徑，我另外精讀了 src/explainer/automata_beam.py、src/learner/dfa_learner.py 的 DFASampler 與 propose_automata、src/experiments/runner.py、src/automaton 底下的 dfa_utils.py、metrics.py、load_dfa.py，以及 src/baselines/search_baselines.py 的 SharedInit、_common_init、_select_final 與三個 baseline 入口；這些檔案只作為追蹤依據，不另外對它們提出 finding。本機沒有 numpy、torch、aalpy、pandas，所以我用純 Python 重製 DFASampler.perturbation 來驗證隨機流重播，並寫了不依賴 numpy 與 torch 的 stub unpickler 來讀取 models 底下的 split 檔與 checkpoint 檔；驗證腳本都放在 scratchpad 的 agent_exp 目錄下，沒有動到 repo。

已知且不重複報告的項目有 run_kllucb_comparison.py:639 的 truthy 防呆、run_kllucb_comparison.py:1086 的 CSV 欄位名稱錯誤、兩支主實驗腳本的 --num_test_instances 與 --max_length 死參數、parse_results.py 只掃 final_result、make_plots.py 急切建構 tau 等於 0.9 的圖，以及 RUNNING.md 的 FileExistsError 與 external_modules 缺失。

---

## 1. CONFIRMED 的正確性 bug（依嚴重程度排序）

### 1.1 KL-LUCB ablation 的 external holdout 與搜尋本身重播同一條隨機流，holdout 不是 out-of-sample（run_kllucb_comparison.py:686-687、703、752，觸發點在 src/learner/dfa_learner.py:307-309 與 441）

這一條就是已知 PLAUSIBLE (B)，我的裁決是 CONFIRMED，完整的追蹤與數據放在第 3 節。這裡先摘要問題本身。create_explainer 每次都建立新的 DFASampler 並傳入同一個 seed，而 DFASampler.__init__ 在 seed 不為 None 時會呼叫 random.seed(seed) 與 np.random.seed(seed) 重設全域亂數；perturbation 在沒有傳入 rng 時直接使用全域 random 模組。因此第 686 行建立 holdout sampler 時全域亂數被設成 seed，第 687 行抽出 holdout；第 703 行為 WITH KL-LUCB 再建一個 sampler，全域亂數又被重設回同一個 seed，接下來 automata_beam 的初始抽樣、origin automaton 的第一個 batch 以及所有走 draw_automata_samples 的循序抽樣，都從同一個起點重播同一串亂數。第 752 行為 NO KL-LUCB 建立 sampler 時又重設一次，所以 NO KL-LUCB 那一支的第一個 1000 筆 batch 正好是 holdout 前 1000 個不重複的擾動樣本，並且完整包含 WITH 那一支用來建 RPNI 與當 validation set 的 init samples。

觸發情境是預設參數就會觸發，不需要特殊輸入。用純 Python 重製 perturbation 後的量化結果是，六個任務、seed 0 到 2 全部符合下列事實：validation set 是 holdout 的嚴格子集；搜尋端前一到三個 1000 筆的循序 batch 百分之百落在 holdout 內；NO KL-LUCB 那一支的第一個 batch 是 validation set 的超集合；作為對照，用不同 seed 抽出的獨立 batch 落在 holdout 內的比例只有 17% 到 53%。另外，DFASampler.perturbation 的 max_trials 是 10000，而 --holdout_size 預設也是 10000，所以 holdout 實際只會得到 2000 到 7200 個不重複樣本，summary.csv 與 seed_details.csv 寫入的 holdout_size 欄位卻是要求的 10000，而不是實際抽到的數量。

對論文結論的影響是「會」。summarize_language_results 的 success_ratio、with_win_rate、no_win_rate、tie_rate 全部以 external_holdout_agreement 為依據（第 835 到 873 行），而這個量並不是獨立估計；兩支變體都被同樣的機制汙染，所以 with 對 no 的勝負方向不必然偏向某一邊，但 success_ratio 對兩支都偏樂觀，且腳本與 docstring 宣稱的「external hold-out」在方法學上不成立。修正方式很簡單，holdout 應該用一個不同的 seed 或私有的 random.Random 抽出，或者在建立搜尋端 sampler 之後才抽 holdout 並且改用私有 rng。

### 1.2 ablation 的 beam_time 比較不公平，WITH KL-LUCB 走多執行緒與 process pool，NO KL-LUCB 永遠單執行緒（run_kllucb_comparison.py:579-585 設定 parallel 與 n_jobs，實際分歧在 src/explainer/automata_beam.py:489、510、964 與 938）

兩支變體都用相同的 cfg 建立 AutomataBeamSearch，預設 parallel 為 True、n_jobs 為 4。WITH KL-LUCB 在 kllucb_automata 內對未抽樣的候選與 critical arms 呼叫 _draw_kllucb_samples，只要候選數大於 1 就走 draw_automata_samples_parallel，抽樣用 ThreadPoolExecutor、評分用 ProcessPoolExecutor。NO KL-LUCB 的分支在 automata_beam.py:938 直接呼叫 draw_automata_samples，抽樣與評分都是循序的，cfg 的 parallel 對它完全無效。因此 run_beam_once 量到的 time_total 與 beam_time，以及 summary 的 beam_time_mean 與 beam_time_std，比較的是四執行緒加多程序對上單執行緒的牆鐘時間。

觸發情境是預設參數就會觸發。對論文結論的影響是「會，但只影響時間欄位」，若論文用這個 ablation 主張 KL-LUCB 在時間上的優勢或代價，那個數字混入了平行化差異；agreement 與 states 欄位不受影響。

### 1.3 real-world 任務的 teacher 超參數在 config 裡是死參數，而且與實際 checkpoint 不符，log 印出的「Experiment Parameters」描述了錯誤的 teacher 架構（run_kllucb_comparison.py:77-80、99-102、121-124；run_realworld_experiment.py:58-61、80-83、102-105；建構點在 run_kllucb_comparison.py:476-481 與 run_realworld_experiment.py:166-171）

三個 real-world config 都寫了 embedding_dim 為 64、hidden_dim 為 256、num_layers 為 2、dropout 為 0.3、max_length 為 20。建構 SequenceClassifier 時只傳了 max_len 與 embedding_dim，hidden_dim、num_layers、dropout 根本沒有傳入；而 SequenceClassifier.load（models/sequence_classifier.py:146-187）會用 checkpoint 內的 max_len、embedding_dim、dropout、rnn_units、num_layers 覆蓋所有建構參數，所以 config 裡這五個欄位對實驗完全沒有作用。我用不依賴 torch 的 unpickler 讀出三個 .pth 的實際超參數：mnist 是 embedding 64、rnn_units 128、2 層、dropout 0.5；ECG 是 embedding 16、rnn_units 64、1 層、dropout 0.5；wafer 是 embedding 8、rnn_units 32、1 層、dropout 0.5；三者 max_len 都是 20。這與 models 底下三支訓練腳本的設定一致，也就是說 config 中的 hidden_dim 256、num_layers 2、dropout 0.3 對任何一個資料集都不是事實。test_result/realworld_0.8_1000/experiment_log.txt 第 1305 到 1313 行的參數區塊照樣印出 hidden_dim 256、num_layers 2、dropout 0.3。

觸發情境是每次執行都會印出錯誤描述。對論文結論的影響是「不確定」，實驗數字本身不受影響，因為推論用的是 checkpoint；但如果論文是照這些 config 或 log 描述 teacher 架構，那段描述就是錯的。這一條與已知的 --num_test_instances 屬於同一類「參數看似被用其實沒有」的問題。

### 1.4 tune_baseline_params.py 選出的參數從未被寫回或被主實驗讀取，主實驗永遠使用固定預設值（src/baselines/tune_baseline_params.py:313-343 寫出 best_by_algo.csv；讀取端在 src/experiments/runner.py:231、236、243、245）

調參腳本只把結果寫到 tune_results.csv、best_by_algo.csv 與 summary_top20.txt。主實驗的 run_baseline 用 cfg.get 讀 sa_candidate_pool_size、ga_population_size、pso_particles、pso_candidate_pool_size，預設值分別是 10、10、5、5；兩支主實驗腳本的 DEFAULT_LANGUAGE_CONFIGS 都沒有這些鍵，parse_args 也沒有對應旗標，整個 repo 沒有任何程式讀 best_by_algo.csv 或 tune_results。因此無論調參結果如何，Beam 對 SA、GA、PSO 的主比較永遠使用 SA pool 10、GA population 10、PSO 5 particles 與 pool 5。附帶的三個問題是，AGREEMENT_THRESHOLD 在第 57 行寫死為 0.8，不管 --tune_root 指向的實驗是用哪個門檻；第 58 行的 BATCH_SIZE 500 只用於 _common_init 的預配置與 log 顯示，實際評分用的是 shared_init 內 1000 筆的固定 training batch，所以 log 印出的「Batch size: 500」是誤導；整支腳本沒有設定任何 seed，每一格網格只跑一次，排名建立在單次無 seed 的結果上。

觸發情境是照 README 的指令執行調參後再跑主實驗，就會得到「調過參」但實際未採用的比較。對論文結論的影響是「不確定」，如果論文 5.3 節只是獨立呈現調參表，那主結果沒有錯；如果論文宣稱主比較使用了調參後的最佳 baseline 設定，這個宣稱不成立。

### 1.5 KL-LUCB 比較腳本的輸出資料夾名稱與 summary 標題只用第一個任務的門檻，預設同時混跑 0.8 與 0.9 的任務（run_kllucb_comparison.py:1185-1192、985-987；各任務門檻在 130、149、168 行）

預設 --languages 是六個任務，mnist、ECG、wafer 的 agreement_threshold 是 0.8，三個 regular 任務是 0.9。main 用 first_cfg 的門檻決定資料夾名稱 kllucb_0.8_1000 並印成「KL-LUCB SUMMARY (agreement_threshold=0.8)」，但 summarize_language_results 第 829 行是逐任務讀自己的門檻，所以 regular 任務的 success_ratio 是以 0.9 判定的。summary.csv 內 agreement_threshold 欄位是逐任務正確的，所以資料可以還原，但 log 標題與資料夾名稱會誤導讀者。另外這支腳本沒有 --max_evaluations 旗標，cfg 也沒有這個鍵，所以 ablation 永遠在無預算限制下跑到 2 個狀態或沒有候選為止，而 RUNNING.md 指定主實驗用 --max_evaluations 3000；第 54 到 57 行註解宣稱「與主實驗完全相同的設定」並不成立。

觸發情境是用預設參數執行。對論文結論的影響是「不確定」，如果論文把六個任務的 ablation 都標成 tau 等於 0.8，regular 三個任務實際是 0.9。

### 1.6 三支 teacher 訓練腳本指向不存在的 datasets 目錄，mnist 訓練腳本會直接 crash（models/mnist_classifier.py:46 未傳 data_path，dataset/mnist_stroke_loader.py:67 預設路徑；models/ECG_classifier.py:59；models/Wafer_classifier.py:63）

repo 內的資料放在 dataset（單數）底下，但 ECG_classifier.py 與 Wafer_classifier.py 把 data_dir 設成 PROJECT_ROOT 底下的 datasets（複數），mnist_stroke_loader 的預設 data_path 是相對於工作目錄的 datasets/mnist-digits-as-stroke-sequences/mnist_strokes.pkl，而 mnist_classifier.py 沒有覆蓋它。我確認過 repo 根目錄沒有 datasets 目錄。因此 mnist_classifier.py 在 open 時會 FileNotFoundError；ECG 與 Wafer 的 loader 會忽略 repo 內已附的 TXT 檔，改嘗試從網路下載到 datasets 底下，離線時同樣以 FileNotFoundError 結束。

觸發情境是嘗試重新訓練任一 teacher。對論文結論的影響是「不會」，因為實驗使用的是已附的 checkpoint 與 split 檔，log 也顯示「Model loaded from ...」；影響的是 teacher 訓練的可重現性。

---

## 2. PLAUSIBLE 的疑點

### 2.1 SequenceClassifier 對超過 max_len 的序列靜默截斷（models/sequence_classifier.py:223-226）

_prepare_X 把每條序列截到 checkpoint 的 max_len 20。三個固定 test_instance 的長度分別是 12、11、17，加上 edit_distance 3、2、2 的插入後最長是 19，所以預設實驗不會觸發。但 X_train 內存在長度 20 的序列（split 檔驗證 train 長度範圍是 10 到 20），若使用者指定這類序列作為 instance，或未來啟用 num_test_instances 路徑取前幾條訓練序列，插入操作產生的長度 21 或 22 的擾動會被 teacher 以前 20 個符號標記，擾動樣本的 label 就不再是該序列本身的 label。

### 2.2 regular 任務的 alphabet 順序來自 set，跨程序不可重現（run_kllucb_comparison.py:401、run_regular_experiment.py:197，來源是 src/automaton/dfa_utils.py:13-23）

get_alphabet 回傳 set，兩支腳本都直接 list 後傳給 DFASampler，perturbation 用 _r.choice(symbols) 選符號，所以同一串亂數在不同 PYTHONHASHSEED 下會選到不同符號；perturbation 回傳值也是 set 的迭代順序，會影響 RPNI 收到的樣本順序。這只影響可重現性，不影響統計量的定義，但 --no_parallel 旗標說明文字宣稱的「bit-for-bit reproducible」對 regular 任務不成立，除非固定 PYTHONHASHSEED。

### 2.3 主實驗 summary 表中 Beam 的「Init」訓練 agreement 與其他方法用的不是同一個量（顯示在 run_regular_experiment.py 與 run_realworld_experiment.py 透過 runner.print_suite_summary 印出的表，根因在 src/explainer/automata_beam.py:617-623）

realworld log 第 797 行顯示 wafer 的 origin automaton 在第一個 1000 筆 batch 上的 agreement 是 0.7480，SA 第 947 行在固定 training batch 上算出的初始 agreement 也是 0.7480，但第 1288 行 summary 表中 Beam 的 Init 值是 0.7380。原因是 _make_result 對 origin 呼叫 get_automata_metadata 讀取當下累積的統計，而 origin 的統計在迭代 0 之後可能被改動（dfa_learner.py:1748-1760 在 iteration 0 會用 state 內全部資料重算 origin 的統計，後續也可能再抽樣）；程式碼第 644 到 651 行的註解只對 final automaton 做了快照保護，沒有對 initial 做。其他五個任務的 Init 值在兩邊一致，所以只有在 origin 被重新統計時才會顯現。影響僅限「Train (Init→Final)」欄的 Init 值，Final 值不受影響。

### 2.4 make_plots.combo_figure 在 initial_states 缺失時會 TypeError（analysis/make_plots.py:81、129、146）

load_rows 把空字串的 initial_states 轉成 None，combo_figure 直接把它放進座標字串並取 max。runner._print_one_suite 只有在 initial_states 為真值時才印出這個欄位，所以任何 initial_states 為 0 的任務會讓整張圖無法產生。目前附帶的 log 六個任務都有 initial_states，所以未觸發。

### 2.5 mnist split 有大量 train 與 test 重疊序列，teacher 的 test accuracy 偏樂觀（dataset/mnist_stroke_loader.py:182 的 train_test_split 與符號化設計）

用 stub unpickler 讀 models/mnist_train_test_split.pkl 的結果是，12153 條不重複的測試序列中有 3088 條也出現在訓練集，且訓練集內有 537 條序列帶有互相衝突的 label。這是四方向符號化把不同數字壓成相同短序列的自然結果，不是 label 對齊錯誤，但 log 報告的 clf_test 0.8973 因此含有 in-sample 成分。wafer 與 ECG 使用 UCR 官方切分，重疊分別是 367 與 60 條，label 無衝突。這只影響 teacher 準確率的描述，不影響解釋實驗。

### 2.6 tune_baseline_params.py 的排名建立在無 seed 的單次執行（src/baselines/tune_baseline_params.py 全檔）

整支腳本沒有呼叫 random.seed 或 np.random.seed，SA 使用全域 random、GA 使用 DEAP 的全域 random、PSO 使用 np.random，每個網格點只跑一次，然後 write_best_by_algo_table 以 states 與 agreement 排序選出最佳設定。相鄰網格點之間的差異很可能小於單次執行的隨機變異，所以 best_by_algo.csv 選出來的「最佳參數」可靠度不足。這是方法學疑點而非程式錯誤，且由於 1.4 的原因，主實驗也沒有使用這些結果。

---

## 3. 對已知 PLAUSIBLE (B) 的裁決

裁決是 CONFIRMED。以下是 seed 設定點與亂數消耗順序的完整追蹤，並附上純 Python 重製的量化結果。

### 3.1 seed 的設定點

run_one_language_seed（run_kllucb_comparison.py:661）進入時先呼叫 set_all_seeds(seed)，設定 random、np.random 與 torch。接著 build_teacher_context 對 regular 任務會用全域 random 產生 100 條 X_train 與 50 條 X_test 只供印出接受率，對 real-world 任務不消耗全域亂數。第 686 行 create_explainer 建立 holdout 用的 DFASampler，DFASampler.__init__（dfa_learner.py:307-309）再次呼叫 random.seed(seed) 與 np.random.seed(seed)，set_instance_label 只做一次 teacher 預測不消耗亂數。第 687 行呼叫 sampler 抽 holdout，perturbation 沒有收到 rng 參數，於是用全域 random 從 seed 的起點開始抽，直到累積 10000 個不重複樣本或 10000 次 trial，實際上一定在 10000 次 trial 處停下。第 703 行 create_explainer 為 WITH KL-LUCB 再建一個 DFASampler，全域 random 又被設回 seed，因此第 750 行 automata_beam 的 init 抽樣（init_num_samples 500 或 1000）從與 holdout 完全相同的起點重播；perturbation 的每一次 trial 消耗的亂數只取決於 instance 與亂數流，不取決於 num_samples，所以第 k 次 trial 在兩邊產生完全相同的序列。init 抽樣結束後，第 811 行對 origin 的 1000 筆 batch 與第 821 到 827 行的追加 batch 繼續消耗同一條流，第 964 行 beam 只有一個 automaton 時的 continue_sampling 也走循序路徑，都在同一條流上。只有 kllucb_automata 第 489 行與第 510 行在候選數大於 1 且 parallel 為 True 時走 draw_automata_samples_parallel，改用 random.Random(f"{seed}:{counter}") 的獨立流，這部分不會重播 holdout。第 752 行為 NO KL-LUCB 第三次建立 DFASampler，全域 random 再次設回 seed；由於 prebuilt_init 略過 init 抽樣，第 811 行的第一個 1000 筆 batch 直接從流的起點開始，之後第 938 行對每個候選的循序抽樣繼續同一條流。

### 3.2 重製結果

我把 dfa_learner.py:419-519 的 perturbation 逐行搬到純 Python，使用各任務 config 中的 instance、alphabet、edit_distance 與 init_num_samples，對 seed 0、1、2 各做一次。以下列出 seed 0 的數字，seed 1 與 2 的結果在同一個量級。

mnist 的 holdout 實際有 2846 個不重複樣本；validation set 500 筆全部落在 holdout 內；搜尋端前三個 1000 筆循序 batch 落在 holdout 內的比例都是 100%，第四個是 72%；validation set 加前三個 batch 已覆蓋 holdout 的 91%；NO KL-LUCB 的第一個 batch 包含整個 validation set；用另一個 seed 抽出的獨立 batch 只有 47% 落在 holdout 內。

ECG 的 holdout 實際有 2083 個樣本；validation set 全部在 holdout 內；前兩個循序 batch 100% 在 holdout 內，第三個是 70%；validation set 加前三個 batch 已覆蓋 holdout 的 100%；獨立對照 batch 只有 52% 在 holdout 內。

wafer 的 holdout 實際有 2179 個樣本；validation set 全部在 holdout 內；前兩個循序 batch 100% 在 holdout 內，第三個是 78%；validation set 加前三個 batch 覆蓋 holdout 的 100%；獨立對照 batch 只有 48%。

SecureHandshake 的 holdout 實際有 7128 個樣本；validation set 1000 筆全部在 holdout 內；前四個循序 batch 100% 在 holdout 內；validation set 加四個 batch 覆蓋 holdout 的 64%；獨立對照 batch 只有 18%。DocumentReleaseWorkflow 與 MultiObligationOrder 的形態相同，holdout 分別是 5613 與 5213 個樣本，前四個循序 batch 皆 100% 在 holdout 內，獨立對照分別是 26% 與 33%。

### 3.3 結論

holdout 與搜尋端循序抽樣使用的亂數確實重疊，而且不是部分重疊，而是從同一個起點逐 trial 完全相同；validation set 是 holdout 的嚴格子集；兩支變體的初始 batch 都完全落在 holdout 內。independent 對照組的重疊率顯示，即使沒有重播，擾動鄰域有限也會造成兩到五成的自然重疊，但重播把前幾千次 trial 的重疊拉到 100%。因此 external_holdout_agreement 的確實質上是 in-sample 的量，以它計算的 win、tie、loss 與 success_ratio 不能被解讀為對新樣本的表現。至於「被高估」的方向，兩支變體都被汙染，WITH 那一支的候選評分有一部分來自獨立流，NO 那一支的候選評分則全部來自全域流，兩者受汙染的程度不完全對稱，所以我對「勝負比例偏向哪一邊」保留判斷，但對「success_ratio 偏樂觀」與「holdout 不獨立」給予 CONFIRMED。

---

## 4. REFUTED 的候選

SequenceClassifier 的 batch 推論與單筆推論不一致這個懷疑不成立，因為 _prepare_X 永遠把序列補到固定的 max_len，與 batch 內其他序列無關，load 與 predict 都呼叫 eval，BatchNorm 使用 running statistics，LSTM 的 dropout 在 eval 模式下關閉，所以結果與 batch 組成無關。

三個 loader 的序列與 label 錯位這個懷疑不成立，因為 mnist 用 sklearn 的 train_test_split 同時打亂 X 與 y，ECG 與 Wafer 保留 UCR 官方切分並逐列映射 label；用 stub unpickler 讀出的三個 split 檔中 X 與 y 長度一致，ECG 與 wafer 沒有任何序列帶衝突 label。

quantile 斷點洩漏測試資料這個懷疑不成立，因為 ECG_loader.py:256-257 與 Wafer_loader.py:260-261 只用訓練序列擬合斷點。

run_kllucb_comparison.py 的 dfa_accepts_sequence 與搜尋端的 check_dfa_path_accepted 語意不同這個懷疑不成立，兩者都把缺失轉移視為拒絕，並以最後狀態的 is_accepting 判定。

NO KL-LUCB 使用不同 validation set 這個懷疑不成立，automata_beam.py:729-730 會把 prebuilt_init 的 validation_data 與 labels 複製進搜尋，所以兩支變體的 final_validation_agreement 在同一組樣本上計算。

Tee 巢狀使用導致 stdout 還原錯亂這個懷疑不成立，src/tee.py 的 close 會把 sys.stdout 還原成建構時擷取的 console，run_kllucb_comparison.py 兩層 finally 區塊中先手動還原再 close 的順序與這個行為相容，主 log 與語言 log 都能正確關閉。

--parallel 與 --no_parallel 的 default 為 None 會蓋掉 cfg 的 parallel 這個懷疑不成立，get_languages_config 會略過值為 None 的覆蓋。

summarize_language_results 使用 np.std 的 ddof 為 0 這件事不構成錯誤，因為整個 repo 只有這裡計算標準差，沒有與 ddof 為 1 混用；只需注意它是十個 seed 的母體標準差。

tune_baseline_params.py 把 instance 等於 None 傳給三個 baseline 會 TypeError 這個懷疑不成立，sa_dfa_search、ga_dfa_search、pso_dfa_search 都接受 **kwargs。

tune_baseline_params.py 的 BATCH_SIZE 500 與主實驗的 1000 不一致會改變評分這個懷疑不成立，batch_size 在 _common_init（search_baselines.py:694）只用來預配置 labels 陣列，實際評分用的是 shared_init 內 1000 筆的固定 training batch。

run_kllucb_comparison.py 對 regular 任務在 build_regular_context 用全域 random 產生 X_train 與 X_test 會干擾搜尋亂數這個懷疑不成立，因為 create_explainer 隨後會重設全域亂數，這些序列也只用於印出接受率。

---

## 5. 用附帶 log 做 sanity check 的結果摘要

test_result 底下只有 regular_0.8_1000、realworld_0.8_1000 與 wafer_ablation_grid，沒有 kllucb 的輸出，所以 1.1 只能靠純 Python 重製驗證，無法對照實際 CSV。

兩份主實驗 log 的每個任務都印出「Selected test instances: 1」，印證已知的 --num_test_instances 死參數，所謂平均多個 instance 的實驗實際只有一條序列。

兩份 log 的六個任務中 Initial (RPNI) 的 validation agreement 都是 1.0000，這與 automata_beam.py:794-795 把 RPNI 用的 init samples 直接當 validation set 的設計一致，因此主實驗表中的「validation agreement」是在初始 DFA 的建構集上量的，不是獨立集合；再加上第 3 節對照組顯示，同一 instance 的獨立 1000 筆 batch 有 18% 到 24% 落在 500 筆的 validation set 內（real-world 任務），主實驗的 training 與 validation 之間也存在自然重疊，只是沒有 ablation 那麼嚴重。

realworld log 第 797 行 wafer 的 origin 第一個 batch agreement 是 0.7480，第 947 行 SA 印出的初始 agreement 也是 0.7480，但第 1288 行 summary 表中 Beam 的 Init 值是 0.7380，印證 2.3 所述 Beam 的 Init 值與其他方法不是同一個量；其他五個任務兩邊一致。

realworld log 第 1299 到 1360 行的參數區塊對三個資料集都印出 hidden_dim 256、num_layers 2、dropout 0.3、embedding_dim 64，與我從 .pth 讀出的實際值（mnist 128 單元 2 層、ECG 64 單元 1 層、wafer 32 單元 1 層，dropout 皆 0.5，embedding 分別是 64、16、8）不符，印證 1.3。

兩份 log 的參數區塊都顯示 max_evaluations 為 3000 與 agreement_threshold 為 0.8，代表 regular 任務的主實驗是用 --agreement_threshold 0.8 蓋掉 config 預設的 0.9；而 run_kllucb_comparison.py 沒有 --max_evaluations 旗標且 regular 預設仍是 0.9，印證 1.5 所述 ablation 與主實驗設定不同。

wafer_ablation_grid/summary.txt 的九格結果中 Val(Init->Final) 的 Init 全部是 1.0000，與上述 validation set 即 RPNI 建構集的觀察一致；該檔第 4 點結論把 validation 下降歸因於壓縮過度，這個解讀沒有考慮 validation set 本身就是初始 DFA 的建構集，初始值 1.0 是建構上的必然而非泛化能力的證據。

split 檔的實際內容是 mnist 訓練 56000 筆、測試 14000 筆、10 類；ECG 訓練 500 筆、測試 4500 筆、5 類且高度不平衡；wafer 訓練 1000 筆、測試 6164 筆、2 類。三個 config 的 test_instance 都確實存在於對應的 X_train 中（mnist 在索引 8814，label 7；ECG 在索引 39，label 0；wafer 在索引 402，label 0），與 log 印出的 label 一致。三個 split 的 alphabet 都完整涵蓋 config 宣告的符號集合，checkpoint 的 symbol2id 與資料 token 一致。

---

## 6. 涵蓋範圍聲明

examples/RPNI/run_kllucb_comparison.py 已完整逐行審過 1280 行，發現 4 個 CONFIRMED 問題（1.1、1.2、1.3、1.5）與 1 個 PLAUSIBLE 疑點（2.2），並對已知 (B) 給出 CONFIRMED 裁決。

src/baselines/tune_baseline_params.py 已完整逐行審過 762 行，發現 1 個 CONFIRMED 問題（1.4）與 1 個 PLAUSIBLE 疑點（2.6）。

examples/RPNI/run_regular_experiment.py 已完整審過，除已知死參數外，發現 1 個 PLAUSIBLE 疑點（2.2 的 alphabet 順序）並共享 2.3 的表格顯示問題，未發現其他正確性問題。

examples/RPNI/run_realworld_experiment.py 已完整審過，發現 1 個 CONFIRMED 問題（1.3 的死參數與錯誤描述）並共享 2.3 的表格顯示問題。

examples/RPNI/run_wafer_param_ablation.py 已完整審過，未發現正確性問題；它繼承 run_realworld_experiment.py 的 config，所以 1.3 的錯誤描述同樣會出現在它的 log 內。

dataset/ECG_loader.py 已完整審過，未發現正確性問題；1.6 的路徑問題觸發點在呼叫端。

dataset/Wafer_loader.py 已完整審過，未發現正確性問題；1.6 的路徑問題觸發點在呼叫端。

dataset/mnist_stroke_loader.py 已完整審過，發現 1 個 CONFIRMED 問題（1.6 的預設路徑）與 1 個 PLAUSIBLE 疑點（2.5）。

models/sequence_classifier.py 已完整審過，發現 1 個 PLAUSIBLE 疑點（2.1 的靜默截斷），batch 與單筆推論一致性、padding、eval 模式與 device 處理均未發現問題。

models/mnist_classifier.py 已完整審過，發現 1 個 CONFIRMED 問題（1.6，未傳 data_path 導致 crash）。

models/ECG_classifier.py 已完整審過，發現 1 個 CONFIRMED 問題（1.6 的 datasets 路徑）。

models/Wafer_classifier.py 已完整審過，發現 1 個 CONFIRMED 問題（1.6 的 datasets 路徑）。

analysis/make_plots.py 已完整審過，除已知問題外發現 1 個 PLAUSIBLE 疑點（2.4）。

analysis/parse_results.py 已完整審過，除已知問題外未發現其他正確性問題；HEADER_RE、INITIAL_RE 與 ROW_RE 與 runner._print_one_suite 的實際輸出格式逐一比對過，能正確解析附帶 log 的六張表。

src/tee.py 已完整審過，未發現正確性問題。
