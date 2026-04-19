#!/usr/bin/env bash
# Index-TTS-vLLM 服务一键启动
# 用法: ./start.sh [--background]  可选 --background/-d 后台运行

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# 固定使用 GPU 1，不占用 0 卡
export CUDA_VISIBLE_DEVICES=1

# 激活 conda 环境
if command -v conda &>/dev/null; then
  eval "$(conda shell.bash hook 2>/dev/null)" || source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh"
  conda activate index-tts-vllm
fi

# 确保必要目录存在
mkdir -p outputs server/upload_temp

if [[ "${1:-}" == "--background" || "${1:-}" == "-d" ]]; then
  mkdir -p logs
  # 使用 setsid 使服务在独立会话中运行，子进程同属一组，stop.sh 可一次结束整组以释放显存
  setsid nohup python server/tts_server_v2_batch.py >> logs/tts_server.log 2>&1 &
  echo $! > server/.tts_server.pid
  echo "TTS 服务已在后台启动（仅 GPU:1），PID: $(cat server/.tts_server.pid)"
  echo "日志: $ROOT/logs/tts_server.log  停止: ./stop.sh"
else
  exec python server/tts_server_v2_batch.py
fi
