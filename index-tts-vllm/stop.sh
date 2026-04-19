#!/usr/bin/env bash
# Index-TTS-vLLM 服务一键停止（仅停止 GPU:1 上的服务，不碰 0 卡）

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

TARGET_GPU=1

# 结束进程组（主进程由 setsid 启动时 pgid=pid，结束整组可释放显存；否则仅结束该进程）
kill_group() {
  local pid="$1"
  [[ -z "$pid" || ! "$pid" =~ ^[0-9]+$ ]] && return
  local pgid
  pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
  if [[ -n "$pgid" && "$pgid" =~ ^[0-9]+$ && "$pgid" == "$pid" ]]; then
    kill -TERM -"$pgid" 2>/dev/null
  else
    kill -TERM "$pid" 2>/dev/null
  fi
}

# 递归收集某进程及其所有子进程 PID
get_tree_pids() {
  local p="$1"
  [[ -z "$p" || ! "$p" =~ ^[0-9]+$ ]] && return
  echo "$p"
  for c in $(pgrep -P "$p" 2>/dev/null); do
    get_tree_pids "$c"
  done
}

# 判断某进程（或其子进程）是否在指定 GPU 上
is_on_gpu() {
  local main_pid="$1"
  local gpu_id="$2"
  local gpu_pids
  gpu_pids=$(nvidia-smi -i "$gpu_id" --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' ')
  [[ -z "$gpu_pids" ]] && return 1
  local tree_pids
  tree_pids=$(get_tree_pids "$main_pid")
  for t in $tree_pids; do
    for g in $gpu_pids; do
      [[ "$t" == "$g" ]] && return 0
    done
  done
  return 1
}

do_stop() {
  stopped=0

  # 优先按 PID 文件停止（由 start.sh 产生，固定为 GPU:1 上的服务）
  if [[ -f server/.tts_server.pid ]]; then
    pid=$(cat server/.tts_server.pid)
    if kill -0 "$pid" 2>/dev/null; then
      kill_group "$pid"
      echo "已停止 TTS 服务及子进程 (主 PID: $pid)，GPU:$TARGET_GPU 显存将释放。"
      stopped=1
    fi
    rm -f server/.tts_server.pid
  fi

  # 补杀：仅结束“在 GPU:1 上”的 TTS 主进程，不碰 0 卡
  for pid in $(pgrep -f "python server/tts_server_v2_batch.py" 2>/dev/null); do
    [[ -z "$pid" ]] && continue
    if kill -0 "$pid" 2>/dev/null && is_on_gpu "$pid" "$TARGET_GPU"; then
      kill_group "$pid"
      echo "已停止 TTS 服务及子进程 (PID: $pid)，GPU:$TARGET_GPU 显存将释放。"
      stopped=1
    fi
  done

  [[ "$stopped" -eq 0 ]] && echo "未发现运行中的 TTS 服务（GPU:$TARGET_GPU）。"

  sleep 1
}

do_stop
