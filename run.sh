#!/bin/bash
# 切换到目录
# 激活环境
source venv/bin/activate
# 记录开始时间
echo "Job started at $(date)" >> run.log

# 依次执行
python3 1_scrape.py >> run.log 2>&1
python3 2_analyze.py >> run.log 2>&1
python3 3_email.py >> run.log 2>&1

echo "Job finished at $(date)" >> run.log
echo "-----------------------------------" >> run.log
