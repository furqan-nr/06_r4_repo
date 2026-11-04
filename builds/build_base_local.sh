#!/bin/bash
# usage: build_base.sh <base> <pip>
set -e
B=$1; PIP=$2
W=/home/claude/r5builds/work_$B
[ "$B" = "1.4.6" ] && W=/home/claude/heldout/work146
cd /home/claude/repo
python3 builds/make_faults.py --source /home/claude/tree_$B --faults /home/claude/r5pools/faults_$B.json \
  --out /home/claude/r5builds/$B --work $W --pip $PIP > /home/claude/r5builds/log_$B.txt 2>&1
mkdir -p /home/claude/r5builds/$B
cp $W/wheel_clean/*.whl /home/claude/r5builds/$B/
rm -rf $W/target $W/target_clean_saved
echo "BUILT $B" >> /home/claude/r5builds/log_$B.txt
