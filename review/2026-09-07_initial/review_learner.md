# 程式碼審查報告：src/learner 與 src/automaton（正確性 bug）

審查範圍是 src/learner/dfa_learner.py、src/automaton/dfa_utils.py、src/automaton/load_dfa.py、src/automaton/metrics.py、src/automaton/__init__.py、src/learner/base.py、src/learner/factory.py，全部逐行讀完。為了追觸發路徑，我也讀了 src/explainer/automata_beam.py、src/experiments/runner.py、src/baselines/search_baselines.py 的相關片段，以及 examples/RPNI 下的三個實驗入口，但沒有對那些檔案另外報 finding。

驗證方式：本機沒有 aalpy、numpy、torch，我用 `pip3 download` 取得 aalpy 1.5.3 與 numpy 的 wheel，解壓到 scratchpad 後以 sys.path 載入（沒有安裝到系統環境），並用假的 pydot 與 matplotlib 模組取代不需要的相依套件，直接以 repo 內的程式碼跑 DOT teacher 載入、DFASampler 擾動、RPNI 初始化、以及 Delete、Merge、Delta 三種操作。測試腳本放在 /tmp/claude-1002/-home-fbi0826/45267091-de48-48ad-8aae-1eea1c512735/scratchpad/agent_learner/ 底下（harness.py、test_A.py、test_C.py、test_C2.py、test_ops.py）。所有數字都是這些腳本實際跑出來的結果。

## 1. CONFIRMED 的正確性 bug（依嚴重程度排序）

### 1.1 MERGE 提案被 initial state 的配對餓死，部分初始 DFA 完全沒有 MERGE 候選（嚴重）

位置是 src/learner/dfa_learner.py 第 1190 至 1247 行的 `collect_merge_pairs_simple`，以及第 1281 與 1296 行的 `_propose_merge`。

問題描述：`collect_merge_pairs_simple` 已經把「跳過含 initial state 的配對」那兩行註解掉（第 1226 至 1227 行），而 `_propose_merge` 是在拿到截斷後的前 `max_pairs` 個配對之後才過濾掉含 initial state 的配對（第 1296 行），所以必定被拒絕的配對會佔掉有限的提案名額。

觸發機制有三個環節疊在一起。第一，`itertools.combinations(dfa.states, 2)` 依 `dfa.states` 的順序列舉，而 initial state 在 RPNI 輸出與 aalpy 的 `copy()` 之後永遠是 `states[0]`，所以所有 `(s0, s_k)` 配對排在最前面。第二，主標籤相同的配對一律給 1.0 分，`pair_scores.sort(reverse=True)` 是穩定排序，所以在 1.0 分的群組裡 `(s0, s_k)` 配對仍然排在最前面。第三，initial state 出現在每一條路徑上，它的主標籤就是全體樣本的多數標籤（實測六組全部是 0），因此任何 non-accepting 且主標籤為 0 的狀態都會和 s0 組成 1.0 分的配對。當這種狀態數量達到 20 個，前 20 名全部是含 s0 的配對，過濾後一個都不剩。

實測結果（beam_size 為預設的 1，所以 `max_pairs` 為 20；用三個 regular teacher 的預設 test_instance 與 edit_distance，各跑 10 個 sampler seed）如下。SecureHandshake 十次初始化裡，可用配對數依序是 16、3、0、0、0、6、7、9、5、6。DocumentReleaseWorkflow 十次裡是 5、9、9、11、5、4、0、6、15、5。MultiObligationOrder 十次裡是 15、6、3、0、6、13、10、7、14、15。三十次初始化中有五次的 20 個名額全部被 initial state 佔走，`_propose_merge` 實際回傳 0 個候選；其餘多數情況只剩下不到一半的名額。以 DocumentReleaseWorkflow seed 7 為例，我模擬了四個 DELETE 加 MERGE 回合，每一回合 `_propose_delete` 產生 31 至 34 個候選，`_propose_merge` 都是 0 個。初始 DFA 越大（35 個狀態以上）越容易被完全餓死。

對論文結論的影響：會影響。論文描述的方法有 Delete、Merge、Delta 三個操作，但實作中 MERGE 在相當比例的實例上是被削弱甚至完全關閉的，因此 Beam Search 的結果（最終狀態數與 agreement）是在一個與描述不符的操作集合下跑出來的。影響方向無法確定，但「實作演算法不等於論文演算法」這一點是確定的。另外 `_propose_merge` 第 1284 至 1289 行的註解明確寫著 top-20 排序不變、只丟掉必定為 None 的任務，代表作者知道排序沒改，卻沒注意到名額被吃掉的後果。

### 1.2 MERGE 會依「路徑經過的多數標籤」翻轉合併後狀態的 accepting 狀態，與 docstring 宣稱的語意不符（中等）

位置是 src/learner/dfa_learner.py 第 217 至 220 行的 `_merge_candidate_from_pair`，以及第 983 至 995 行的 `_propose_merge_single`。

問題描述：docstring 說「若兩個狀態的 accepting 狀態不一致，才由 majority_labels 決定」，但程式碼無條件執行 `s1_new.is_accepting = (merged_majority == 1)`。在 beam 路徑上，`collect_merge_pairs_simple` 已經把 accepting 狀態不同的配對全部過濾掉，所以「不一致」的前提永遠不成立，翻轉卻照樣發生。而且 `majority_labels` 統計的是「經過該狀態的樣本」的標籤，不是「結束於該狀態的樣本」，所以一個位於通往 accepting state 路上的中繼狀態，很容易被判成多數標籤 1。

實測結果：以 SecureHandshake 的初始 DFA（30 個狀態）對所有非 initial 的可合併配對呼叫 `_merge_candidate_from_pair`，195 個合法候選中有 70 個合併後狀態的 accepting 狀態與兩個輸入狀態都不同，例如 s8 與 s9 都是 non-accepting，合併後變成 accepting。

對論文結論的影響：不確定。候選仍會經過 KL-LUCB 評估，回報的 agreement 數值本身沒有錯，但 MERGE 實際上是「合併加改標籤」，搜尋軌跡與論文描述的 Merge 操作不同。

### 1.3 Delta 的「補上缺失 transition」分支是死路，所以沒有 Explaining-FA 時 Delta 完全沒有作用（低）

位置是 src/learner/dfa_learner.py 第 251 至 252 行的 `_delta_candidate_from_edge`，第 1616 行與第 1664 行的 `_propose_delta`。

問題描述：`_aggregate_cxp_analysis` 會為「部分追蹤的 false-reject 路徑」記錄缺失的 `(src_state, symbol)`，`_propose_delta` 也把它們放進 `all_blamed_edges` 並替每個目標狀態建立任務，但 `_delta_candidate_from_edge` 一開始就以 `if symbol not in src_new.transitions: return None` 拒絕所有缺失 symbol 的任務。docstring 第 1616 行宣稱的「add missing transitions」在任何情況下都不會發生。

實測結果：把 SecureHandshake 初始 DFA 的一條 transition 刪掉後，對所有目標狀態呼叫 `_delta_candidate_from_edge`，非 None 的候選數為 0；同一條路徑丟進 `_collect_cxp_records_for_path` 確實回傳 `missing=[('s3', 'ack')]`，證明記錄有產生但無法轉成候選。

兩種情境的評估如下。沒有 Explaining-FA 時，`_collect_cxp_records_for_path` 在第 106 行直接回傳空的 CXP 記錄，只剩缺失 transition 記錄，而該分支是死路，因此 Delta 在每個奇數 iteration 只會回傳 `[dfa]`（父 DFA 自己），是完整的 no-op；已知報告說「退化成只用 missing transition」是高估了。有 Explaining-FA 時，rewire 分支正常運作，缺失分支雖然死路，但初始 DFA 經 `make_input_complete("sink_state")` 後對整個 alphabet 完整（實測 SecureHandshake 初始 DFA 的 alphabet 與 sampler 的 alphabet 完全相同且無缺失），且 Delete、Merge、Delta 三種操作都保持完整性（見第 4 節），所以缺失 transition 實際上不會出現，這條死路在預設流程下不影響結果。

對論文結論的影響：在有 Explaining-FA 的實驗環境下不會影響；在沒有 Explaining-FA 的環境下，Delta 完全沒有貢獻，這一點已與已知報告合併看待。

## 2. PLAUSIBLE 的疑點

### 2.1 load_dfa.py 的 state regex 會把帶有額外屬性的 doublecircle 節點靜默降級成 non-accepting

位置是 src/automaton/load_dfa.py 第 91 行。`state_pattern` 要求 `[shape=xxx]` 後面立刻接右中括號，像 multi_obligation_color_order.dot 裡的 `"TRAP" [shape=circle, style=filled, fillcolor=lightgray];` 就不會被匹配，該狀態只會透過 transition 被建立並預設為 non-accepting。目前三個 DOT 檔裡唯一帶額外屬性的節點剛好是 circle，所以結果正確；一旦有 doublecircle 節點帶額外屬性，teacher 的 accepting set 就會錯而且沒有任何警告。這是潛在問題，現有 teacher 不受影響。

### 2.2 `qi [shape=point]` 也會變成 phantom state

位置是 src/automaton/load_dfa.py 第 97 至 99 行。只有以雙底線開頭的名稱會被跳過，multi_obligation_color_order.dot 使用 `qi` 當起點記號，實測載入後 `teacher.states` 多出 `qi` 與 `node` 兩個沒有任何邊的狀態（39 個狀態，實際應為 37）。這是已知 phantom state finding 的變體，影響僅限 metadata 裡的 teacher_states 數字，不影響 predictor。

### 2.3 Explaining-FA 回傳的 CXP 位置被當成 0-based 的 path index

位置是 src/learner/dfa_learner.py 第 1449 至 1456 行的 `_count_blamed_edges`。程式假設 `cxp` 內的每個位置直接對應 `path_edges[pos]`，若 Explaining-FA 回傳 1-based 位置就會 off-by-one 並靜默跳過最後一個位置。external_modules/Explaining-FA 不在 repo 裡，我無法驗證這個假設。

### 2.4 prediction cache 會把 race 汙染過的標籤永久固定下來

位置是 src/learner/dfa_learner.py 第 335 至 379 行的 `_predict_with_cache`。這是已知的 load_dfa.py 第 251 行 race 的放大器：一旦某個序列在 ThreadPoolExecutor 下算出錯的 teacher 標籤，它就會被以 `tuple(seq)` 為 key 存進 cache，在同一個實例的整個搜尋（包括後續所有 KL-LUCB 批次）中被重複使用。實驗預設 parallel 為 True、n_jobs 為 4，所以這條路徑是預設開啟的。我沒有另外報 race 本身，只補充它的持久化效果。

### 2.5 sampler 的 alphabet 順序來自 set，讓 regular 實驗即使固定 seed 也無法跨行程重現

位置是 src/learner/dfa_learner.py 第 460 行附近的 `symbols` 與 `_r.choice(symbols)`。regular 實驗把 `get_alphabet(teacher)` 回傳的 set 轉成 list 傳入，字串 set 的迭代順序受 PYTHONHASHSEED 影響，所以擾動樣本在不同行程間不同。這只影響重現性，不影響單次結果的正確性。

### 2.6 `dfa_to_mata` 在沒有 accepting state 時會直接修改傳入的 DFA

位置是 src/automaton/dfa_utils.py 第 397 至 400 行。它把 `init_state.is_accepting` 改成 True 以保證輸出檔合法。目前所有呼叫端在進入 `_propose_delta` 前都經過 `is_valid_dfa` 檢查，所以不會觸發，但這是一個會改變輸入物件的匯出函式。

## 3. 對已知 PLAUSIBLE (A)、(C) 的裁決

### (A) perturbation 對空序列或短序列的 crash

裁決是：程式缺陷本身 CONFIRMED，但在所有預設實驗路徑下 REFUTED，不會影響已回報的實驗。

機制驗證：`possible_ops` 在第 468 至 471 行只對 delete 做長度 gate，replace 在第 477 行對空序列呼叫 `randrange(0)` 會丟 ValueError。單一樣本內的多次編輯是連續套用在同一個工作序列上的，所以 crash 條件是「序列在一次擾動中被刪到長度 0，且下一個抽到的操作是 replace」。要刪到 0 需要至少 `len(instance)` 次 delete，而編輯總數最多 `edit_distance`，還要剩至少一次編輯，因此觸發條件是 `len(instance) < edit_distance`，或原本就是空序列。實測每次呼叫 `perturbation(1000)` 的 crash 次數（200 次試驗）是：長度 1 搭配 edit_distance 2 為 200 次，長度 2 搭配 3 為 199 次，長度 4 搭配 5 為 176 次，長度 6 搭配 7 為 49 次，長度 7 搭配 7 為 0 次；空序列搭配 edit_distance 1 第一次呼叫就 crash。

觸發路徑追查：regular 實驗三組預設 test_instance 的長度分別是 11、10、7，edit_distance 分別是 7、5、5；若改用 `get_test_instances` 自動產生，`min_test_length` 預設 10。real-world 三組預設 test_instance 長度是 12、11、17，edit_distance 是 3、2、2；若改用 `X_train[:n]`，我直接讀取 models 下三個 split pkl，mnist、ECG、wafer 的 X_train 最短長度都是 10。run_kllucb_comparison.py 六組預設設定都指定了 test_instance，長度同上。所以預設路徑下 `len(instance) >= edit_distance` 恆成立，不會 crash。只有透過 CLI 的 `--edit_distance` 覆寫到大於實例長度，或自行提供極短的 test_instance，才會在第一批取樣就炸掉整個實例。

### (C) collect_merge_pairs_simple 的 initial-state 配對餓死 MERGE

裁決是 CONFIRMED，詳細機制與實測數字見第 1.1 節。三十次預設設定的初始化中有五次 MERGE 候選數為 0，其餘多數只剩不到一半名額，且在後續回合持續發生。

## 4. REFUTED 的候選（簡短）

- Delete、Merge、Delta 產生的 DFA 是否仍然合法：我對 SecureHandshake 初始 DFA 產生的 29 個 DELETE 候選、195 個 MERGE 候選、148 個 DELTA rewire 候選，以及 SA、GA、PSO 使用的 `_propose_delete_single`、`_propose_merge_single`、`_propose_delta_single` 各 60 次呼叫，逐一檢查 determinism（由 dict 保證）、對整個 alphabet 的 completeness、沒有 dangling transition、initial state 仍在狀態集合且未被更動、至少一個 accepting state，全部 0 個違規。
- `copy()` 與 pickle 在操作後是否仍把 initial state 放在 `states[0]`：aalpy 的 `to_state_setup` 依可能過期的 prefix 長度排序，但 initial state 的 prefix 恆為空 tuple 且會被重新計算，非 initial 狀態不可能有空 prefix，實測 delete 後的 DFA 含過期 prefix 時 `copy()` 與 pickle round trip 仍保持 initial 在首位。
- `sig_cache` 以 `id()` 為 key 的汙染：被丟棄的候選釋放後 id 可能被重用，但每個進入 `new_dfas` 的候選都在建立當下寫入自己的 signature（第 1180、1318、1693 行），讀取時一定讀到自己的值；父 DFA 在整個呼叫期間存活，id 不可能被重用。
- `run_RPNI` 因標籤衝突回傳 None 造成 `candidate.states` crash：`perturbation` 以 set 去重，同一序列不會以兩種標籤出現，且 cache 保證同序列標籤一致。
- `use_prediction_cache=False` 時標籤形狀變成二維導致 broadcast 錯誤：`SequenceClassifier.predict` 回傳 `np.concatenate` 的一維陣列，DFA predictor 也是一維，不會發生。
- 多個 worker 共用同一個 `dfa_explicit.mata` 檔案的競爭：`_collect_cxp_records` 會等所有 future 完成（逾時者除外）後才回到主流程，下一次 `dfa_to_mata` 重寫時沒有未讀取的 worker 需要該檔案。
- `serialize_dfa` 沒有把 initial state 編進 signature：initial state 永遠是 s0 且從不被刪除或合併，不會因此把不同 DFA 視為相同。
- `_propose_merge_single` 第 985 行的 `if nxt == s2_new` 分支永遠不成立（前一個迴圈已把 s2 的自環改指向 s1），但這只是冗餘，結果正確。
- 單一符號 alphabet 與單一狀態 DFA：單一符號 alphabet 下 replace 會空轉但不 crash，鄰域只有 `2*edit_distance+1` 個序列，`no_progress` 機制會提前結束；單一狀態 DFA 會被 `is_valid_dfa` 擋在 beam 之外，`_propose_delete` 與 `collect_merge_pairs_simple` 對它也回傳空結果。

## 5. dead code 附註

以下函式經 grep 確認在整個 repo（src 與 examples）沒有任何呼叫端，即使有問題也不影響實驗。

- src/automaton/dfa_utils.py 第 57 至 100 行的 `dfa_product`、`dfa_intersection`、`dfa_union`：product 建構在任一方缺少 symbol 時直接跳過該 symbol，對 union 而言這會把只在其中一個 DFA 有定義的字串判為拒絕，語意不對。
- src/automaton/dfa_utils.py 第 126 至 148 行的 `make_dfa_complete`：邏輯正確，未被使用（實際使用的是 aalpy 的 `make_input_complete`）。
- src/automaton/dfa_utils.py 第 151 至 185 行的 `trim_dfa`：回傳的 `states` 是 set（第 183 行），與其他程式碼假設的 list 不相容，例如 `dfa.states[idx]` 會失敗。
- src/automaton/dfa_utils.py 第 188 至 261 行的 `merge_linear_edges`：第 229 行把 `p --a--> s --a--> q` 折成 `p --a--> q`，會改變接受語言，不是保語意的簡化。
- src/automaton/dfa_utils.py 第 264 至 340 行的 `merge_parallel_edges` 與第 343 至 347 行的 `simplify_dfa`：把整組 symbol 換成 `*`，只適合視覺化，未被使用。
- src/learner/dfa_learner.py 第 604 行的 `update_state_metrics`、第 404 行的 `build_lookups`、第 1328 行的 `_trace_path`、第 381 行的 `prediction_cache_info`、第 595 行的 `DFALearner.compute_agreement`：都沒有呼叫端。`set_n_covered` 有被 runner 呼叫，但 `n_covered_ex` 沒有任何讀取者。
- src/learner/__init__.py 第 9 行的 `__all__` 列出了 `DFASampler` 卻沒有 import 它，`from learner import *` 會丟 AttributeError；目前沒有人這樣 import。
- src/learner/factory.py 第 73 至 74 行讓 `get_learner('dfa', new_instance=False)` 也回傳新實例，與 docstring 的「shared instance」不符；沒有程式依賴共享實例，無害。

## 6. 涵蓋範圍聲明

- src/learner/dfa_learner.py 已完整審過（1809 行），發現 3 個 CONFIRMED 問題（第 1.1、1.2、1.3 節）、3 個 PLAUSIBLE 疑點（第 2.3、2.4、2.5 節），並對 (A) 與 (C) 做出裁決。
- src/automaton/dfa_utils.py 已完整審過（632 行），實際被呼叫的函式（`get_alphabet`、`is_valid_dfa`、`check_dfa_path_accepted`、`remove_unreachable_states`、`serialize_dfa`、`dfa_to_mata`、`dfa_to_graphviz`、`plot_beam_stats`）未發現正確性問題，另有 1 個 PLAUSIBLE 疑點（第 2.6 節）與 6 項 dead code 附註。
- src/automaton/load_dfa.py 已完整審過（321 行），除已知的 race 與 phantom state 之外，發現 2 個 PLAUSIBLE 疑點（第 2.1、2.2 節）；三個 DOT 檔的所有 transition 行都能被 regex 正確解析，也沒有重複的 (state, symbol) 邊。
- src/automaton/metrics.py 已完整審過，未發現正確性問題。
- src/automaton/__init__.py 已完整審過，未發現正確性問題。
- src/learner/base.py 已完整審過，未發現正確性問題。
- src/learner/factory.py 已完整審過，未發現正確性問題，僅有 1 項 dead code 附註。
