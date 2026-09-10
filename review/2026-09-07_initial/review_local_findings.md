# 本機 code-review（正確性線）已驗證結果留存

這份檔案是本機 code-review 流程被停止前輸出的結果留存，內容尚未與雲端審查交叉比對，
最終報告以合併後的 Artifact 為準。狀態標記：CONFIRMED = 已由 verifier 確認；
PLAUSIBLE/unverified = learner/sampling 那批 verifier 被停掉前未完成驗證；REFUTED = 已否決。

## CONFIRMED（12 個）

1. `src/baselines/search_baselines.py:567` — PSO baseline calls pyswarms GlobalBestPSO.optimize(iters=1) in a per-iteration loop; pyswarms 1.3.0 resets swarm.pbest_cost to inf at the start of every optimize() call, wiping personal-best memory each iteration and neutering the cognitive (c1) term. 影響：Beam-vs-PSO 的比較與 tune_baseline_params 的表格量到的不是真正的 PSO。

2. `src/baselines/search_baselines.py:276` — PSO agreement cache keyed by id(dfa) with no reference kept; GC 後位址重用會讓新的 DFA 繼承別的 automaton 的 stale cached agreement，可能贏得 _update_gbest 而被回傳為 PSO best。automata_beam.py:197 有 _id_reuse_guard 防這件事，PSO 沒有。

3. `src/automaton/load_dfa.py:251` — create_automata_dfa_predictor 的 predictor 透過 reset_to_initial()/step() 改動共享的 dfa.current_state，但 draw_automata_samples_parallel 的 ThreadPoolExecutor 會並行呼叫它（regular 實驗預設 parallel=True），race 之下 label 會被靜默弄錯；load_dfa.py:256-258 的 except 還會把 race 中的錯誤轉成 label 0。

4. `src/explainer/automata_beam.py:343` — draw_automata_samples_parallel 的 except fallback 重新評分全部 batch 並 append 到 worker_results，卻沒清掉先前已 append 的部分結果：前 k 個 automata 的統計被重複計算、回傳長度變 N+k，導致 automata_beam.py:490/513 的 positives[idx] += ... shape mismatch ValueError。

5. `examples/RPNI/run_kllucb_comparison.py:639` — extract_prebuilt_init 用 `if not automata_pair` 防呆，但 init 失敗回傳的是 truthy 的 `{'automata': [None, None]}`，automata_pair[0].copy() 會 AttributeError；runner.py 有正確的 `is not None` 寫法，這裡是複製時的分歧。

6. `analysis/parse_results.py:105` — 只掃 test_result/final_result/（沒有任何程式會建立），照文件跑到這步會 FileNotFoundError；CONFIG_RE 也會靜默略過帶 --output_suffix 的資料夾。（與可重現性線的發現相同。）

7. `src/baselines/search_baselines.py:1302` — GA sequential fallback 在 offspring 評分失敗時，把「population 裡最佳個體」的 fitness 指給它（註解卻寫 parent's fitness），讓從未被評分的 DFA 以精英分數長期存活，扭曲 selection 與 early stopping。

8. `analysis/make_plots.py:439` — main() 在一個 dict literal 裡急切建構全部圖，包括 combo_figure(threshold=0.9)；照 RUNNING.md 只跑 tau=0.8 時它會 ValueError，連完整的 tau=0.8 圖都一張不出。

9. `src/baselines/search_baselines.py:789` + `:1506` — all_history 為空時 _select_final 把 initial DFA 在 validation data 上算的值當 training_agreement 回報；且 pso_dfa_search 的 catch-all except 包住 optimize() 與 history 收集迴圈，中途錯誤會丟光已收集的 history 並回報 "No candidates generated"。

10. `examples/RPNI/run_kllucb_comparison.py:1086` — save_seed_details_csv 讀 teacher_train_agreement/teacher_test_agreement，但 seed dict 存的是 teacher_train_acc/teacher_test_acc（695-696 行），兩個 CSV 欄位永遠是空的。

11. `examples/RPNI/run_regular_experiment.py:205`（run_realworld_experiment.py:138 同 pattern）— 所有 DEFAULT_LANGUAGE_CONFIGS 都固定了 test_instance，而選取邏輯永遠優先它，所以文件宣稱的 --num_test_instances（與 regular 的 --max_length）實際上是死參數，宣稱平均 N 個 instance 的 run 實際只跑 1 個。

12. `src/automaton/load_dfa.py:91` — state regex 會把 DOT 的 default-attribute 行（`node [shape=circle];`、`qi [shape=point]`）當成狀態，產生 phantom unreachable states，灌高 len(dfa.states) 的統計（不影響預測）。

## PLAUSIBLE / 未驗證（4 個）

A. `src/learner/dfa_learner.py:477` — perturbation() 對空序列可能選到 'replace'（只有 'delete' 有長度 gate），random.randrange(0) 會 ValueError；序列比 edit distance 短時幾乎必炸 KL-LUCB 取樣迴圈。

B. `examples/RPNI/run_kllucb_comparison.py:686` — external holdout 用與 search 相同 seed 的 sampler 抽出，且 DFASampler.__init__ 會 seed 全域 random，search 會重播產生 holdout 的同一條 perturbation stream，external_holdout_agreement 實質上是 in-sample，KL-LUCB ablation 的 win/tie/loss 與 success_ratio 被高估。

C. `src/learner/dfa_learner.py:1226` — collect_merge_pairs_simple 不再跳過 initial-state pairs，且 top max_pairs 截斷發生在 _propose_merge 的 initial-state filter 之前，必被拒絕的 pair 可能餓死 MERGE 提案。

D. `src/experiments/runner.py:134` — build_shared_init 對 preallocated zeros 的 state["labels"][:batch_size] 切片，而 training_data 是實際抽到的較短 list；beam 記錄的樣本少於 batch_size 時，下游 (labels == 1) & accepts 會 shape mismatch 或靜默混入 phantom label-0 樣本。

## REFUTED（1 個）

- `src/automaton/load_dfa.py:105` edge-regex 掉 attribute：repo 內所有 .dot 邊都是單一 `[label="x"]`，multi-attribute 的 dfa_to_graphviz 輸出不會被重新載入，僅屬 latent fragility，不構成實際 bug。
