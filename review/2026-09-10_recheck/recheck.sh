#!/usr/bin/env bash
REPO=/home/fbi0826/automata-based-explainer
PY=/home/fbi0826/.venv-automata/bin/python
cd "$REPO" || exit 1
echo "######## 第二次複驗實測記錄"
echo "commit: $(git log --oneline -1 43bc43d)"
echo "日期: $(date)"

echo; echo "######## 1. parse_results.py 是否不需手動搬移就能運作"
rm -f analysis/summary_table.csv
$PY analysis/parse_results.py 2>&1 | tail -5
echo "exit=$?  產出列數: $(wc -l < analysis/summary_table.csv 2>/dev/null)"

echo; echo "######## 2. make_plots.py 的 Unicode tau 修正"
echo "--- 原始碼 caption ---"
grep -n 'tau = {threshold}' analysis/make_plots.py
$PY analysis/make_plots.py 2>&1 | tail -6

echo; echo "######## 3. 調參結果自動載入：造一份探測用 CSV"
mkdir -p test_result/tune_probe_test
cat > test_result/tune_probe_test/best_by_algo_cross_task.csv <<'EOF'
algo,config,n_experiments,n_experiments_total,meets_threshold_rate,avg_normalized_loss,avg_states,avg_agreement,avg_time
SA,pool=7,6,6,1.0,0.5,20,0.85,100
GA,pop=13,6,6,1.0,0.5,20,0.85,100
PSO,"n_particles=9,pool=11,ops=3",6,6,1.0,0.5,20,0.85,100
EOF
echo "注意：目錄名是 tune_probe_test，不是預設的 tune_fairflow_baselines_*"

echo; echo "######## 4. 多 instance + 調參自動套用（同時驗證兩件事）"
rm -rf test_result/regular_0.8_300
timeout 1200 $PY examples/RPNI/run_regular_experiment.py --languages SecureHandshake \
    --agreement_threshold 0.8 --batch_size 300 --max_evaluations 100 --num_test_instances 3 2>&1 \
    | grep -E "Selected test instances|instance_0[0-9]/beam/dfa|Tuned params|SA\] Running|GA-Gen\] Generation 1,|Averaged across" | head -20
echo "--- 上面若無 'Averaged across' 一行，表示 print_averaged_summary 未被腳本呼叫 ---"

echo; echo "######## 5. 移除探測 CSV，確認預設路徑（與 2026-09-08 的同參數執行比對）"
rm -rf test_result/tune_probe_test test_result/regular_0.8_200
timeout 900 $PY examples/RPNI/run_regular_experiment.py --languages SecureHandshake \
    --agreement_threshold 0.8 --batch_size 200 --max_evaluations 100 2>&1 \
    | grep -E "Tuned params|teacher_states=|Initial \(RPNI\)|^  \| |Beam evaluations"
echo "--- 2026-09-08 同參數的結果：initial_states=31, init train=0.8700,"
echo "    beam 0.8980/30, SA 0.8250/16, GA 0.8350/20, PSO 0.8750/25 ---"

echo; echo "######## 6. print_averaged_summary 的標準差是哪一種"
$PY -c "
import sys; sys.path.insert(0,'src')
from experiments.runner import print_averaged_summary
def suite(tr, st, t):
    return {'beam': {'method':'beam','train_agreement':tr,'validation_agreement':0.9,'states':st,'time':t}}
r = {'Task_instance_00': suite(0.80,3,10.0),
     'Task_instance_01': suite(0.90,4,20.0),
     'Task_instance_02': suite(1.00,5,30.0)}
print_averaged_summary(r)
print()
print('輸入 states = 3,4,5 -> mean=4.00')
print('population std (除以 n)   = 0.8165')
print('sample std     (除以 n-1) = 1.0000')
" 2>&1 | tail -14

echo; echo "######## 7. 核心演算法檔案這次是否變動"
for f in src/learner/dfa_learner.py src/explainer/automata_beam.py src/baselines/search_baselines.py src/automaton/load_dfa.py src/automaton/dfa_utils.py; do
    n=$(git diff --numstat 2359c33..43bc43d -- $f | wc -l)
    echo "$f: $([ "$n" -eq 0 ] && echo '沒有變動' || git diff --numstat 2359c33..43bc43d -- $f)"
done

echo; echo "######## 8. 參考結果是否套用過調參"
echo "regular  參考 log 中 [Tuned params] 出現次數: $(grep -c 'Tuned params' test_result/regular_0.8_1000/experiment_log.txt)"
echo "realworld 參考 log 中 [Tuned params] 出現次數: $(grep -c 'Tuned params' test_result/realworld_0.8_1000/experiment_log.txt)"
echo "test_result 進版控的檔案:"; git ls-files test_result/

echo; echo "######## 9. 是否有停用自動載入的 CLI 旗標"
grep -n "tuned" examples/RPNI/run_regular_experiment.py examples/RPNI/run_realworld_experiment.py || echo "(沒有任何 tuned 相關旗標)"

echo; echo "######## 清理"
rm -rf test_result/regular_0.8_200 test_result/regular_0.8_300 test_result/tune_probe_test
rm -f analysis/summary_table.csv
cd "$REPO" && git checkout -- analysis/plots/ 2>/dev/null
echo "完成 $(date)"
