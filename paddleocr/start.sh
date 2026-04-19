#!/bin/bash
# PaddleOCR-VL API 后端启动脚本（指定 GPU 0 / CPU 0）
# 使用: ./start.sh

set -e
cd "$(dirname "$0")"

# 使用 GPU 0（若仅用 CPU 可改为 export CUDA_VISIBLE_DEVICES=""）
export CUDA_VISIBLE_DEVICES=0

# 监听所有网卡，允许外网访问（默认 0.0.0.0:8802）
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8802}"

# 激活 conda 环境并后台启动
# shellcheck source=/dev/null
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate ppocrvl

# 日志目录
mkdir -p logs
LOG_FILE="logs/api_paddleocr_vl_ai_ppt.log"
PID_FILE=".api_paddleocr_vl_ai_ppt.pid"

# 若已在运行则先提示
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "服务已在运行 (PID=$OLD_PID)，请先执行 ./stop.sh"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

echo "正在启动 api_paddleocr_vl_ai_ppt.py (CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES) ..."
nohup python api_paddleocr_vl_ai_ppt.py >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "已启动，PID=$(cat "$PID_FILE")，日志: $LOG_FILE"
