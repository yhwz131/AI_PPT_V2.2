#!/bin/bash
# 停止 PaddleOCR-VL API 后端（含占用 8802 端口的进程）
# 使用: ./stop.sh

cd "$(dirname "$0")"
PID_FILE=".api_paddleocr_vl_ai_ppt.pid"
PORT=8802

# 1. 用 PID 文件结束主进程
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null
    sleep 1
    kill -9 "$PID" 2>/dev/null
    echo "已停止 PID=$PID"
  fi
  rm -f "$PID_FILE"
fi

# 2. 结束占用 8802 端口的进程（uvicorn 子进程等）
if command -v fuser &>/dev/null; then
  if fuser "$PORT/tcp" &>/dev/null; then
    fuser -k "$PORT/tcp" 2>/dev/null
    echo "已结束占用端口 $PORT 的进程"
  fi
elif command -v lsof &>/dev/null; then
  PIDS=$(lsof -ti ":$PORT" 2>/dev/null)
  if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs -r kill -9 2>/dev/null
    echo "已结束占用端口 $PORT 的进程"
  fi
fi

# 3. 兜底：按进程名结束
if pgrep -f "api_paddleocr_vl_ai_ppt.py" >/dev/null; then
  pkill -9 -f "api_paddleocr_vl_ai_ppt.py" 2>/dev/null
  echo "已通过进程名结束 api_paddleocr_vl_ai_ppt.py"
fi

# 再等 1 秒后确认端口已释放
sleep 1
if command -v fuser &>/dev/null && fuser "$PORT/tcp" &>/dev/null; then
  echo "警告: 端口 $PORT 仍被占用，请手动检查: lsof -i :$PORT 或 fuser -v $PORT/tcp"
else
  echo "已停止，端口 $PORT 已释放"
fi
