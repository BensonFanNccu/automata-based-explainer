#!/usr/bin/env bash
# 完整重現 RUNNING.md 記載的兩條實驗指令（脫離 Claude Code session 執行）
REPO=/home/fbi0826/automata-based-explainer
PY=/home/fbi0826/.venv-automata/bin/python
OUT=/home/fbi0826/automata-run

cd "$REPO" || exit 1
echo "### COMMIT: $(git log --oneline -1)"
echo "### REGULAR start $(date)"
"$PY" examples/RPNI/run_regular_experiment.py \
    --agreement_threshold 0.8 --batch_size 1000 --max_evaluations 3000
echo "### REGULAR exit=$? $(date)"

echo "### REALWORLD start $(date)"
"$PY" examples/RPNI/run_realworld_experiment.py \
    --agreement_threshold 0.8 --batch_size 1000 --max_evaluations 3000
echo "### REALWORLD exit=$? $(date)"

echo "### ALL DONE $(date)"
