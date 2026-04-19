#!/usr/bin/env bash
# ============================================================
#  AIPPT 一键启动 / 停止脚本
#  用法:
#    ./start_all.sh              启动所有服务（后台）
#    ./start_all.sh start        启动所有服务（后台）
#    ./start_all.sh stop         停止所有服务
#    ./start_all.sh restart      重启所有服务
#    ./start_all.sh status       查看各服务运行状态
#    ./start_all.sh start paddleocr          仅启动 paddleocr
#    ./start_all.sh start tts                仅启动 IndexTTS
#    ./start_all.sh start wav2lip            仅启动 Wav2Lip
#    ./start_all.sh start digital            仅启动数字人接口
#    ./start_all.sh stop paddleocr           仅停止 paddleocr
#    ./start_all.sh stop tts                 仅停止 IndexTTS
#    ./start_all.sh stop wav2lip             仅停止 Wav2Lip
#    ./start_all.sh stop digital             仅停止数字人接口
#    ./start_all.sh start frontend           仅启动前端
#    ./start_all.sh stop frontend            仅停止前端
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$PROJECT_ROOT/.pids"
LOG_DIR="$PROJECT_ROOT/logs"

mkdir -p "$PID_DIR" "$LOG_DIR"

# ============ 服务定义 ============
# 格式: 名称|conda环境|GPU|工作目录|启动命令|端口|PID文件名

declare -a SERVICES=(
    "paddleocr|ppocrvl|0|$PROJECT_ROOT/paddleocr|python api_paddleocr_vl_ai_ppt.py|8802|paddleocr.pid"
    "tts|index-tts-vllm|1|$PROJECT_ROOT/index-tts-vllm|python server/tts_server_v2_batch.py --gpu_memory_utilization 0.3 --qwenemo_gpu_memory_utilization 0.2 --is_fp16|6006|tts.pid"
    "wav2lip|wav2lip_fixed|0|$PROJECT_ROOT/wav2lip_workspce/lx/测试|python main.py|5000|wav2lip.pid"
    "digital|digital||$PROJECT_ROOT/digital_human_interface|python main.py|9088|digital.pid"
    # 前端由 Nginx 提供（静态文件），无需额外进程
    # 部署新版：cd frontend-new && node_modules/.bin/vite build && cp -r dist/* ../frontend/
)

# ============ 颜色定义 ============
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============ 工具函数 ============

print_banner() {
    echo -e "${CYAN}"
    echo "============================================================"
    echo "   AIPPT 一键管理脚本"
    echo "============================================================"
    echo -e "${NC}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

parse_service() {
    local entry="$1"
    IFS='|' read -r S_NAME S_CONDA S_GPU S_DIR S_CMD S_PORT S_PIDFILE <<< "$entry"
}

get_pid() {
    local pidfile="$PID_DIR/$1"
    if [ -f "$pidfile" ]; then
        cat "$pidfile"
    fi
}

is_running() {
    local pid
    pid=$(get_pid "$1")
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

wait_for_port() {
    local port="$1"
    local max_wait="${2:-60}"
    local waited=0
    while [ "$waited" -lt "$max_wait" ]; do
        if python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',$port)); s.close()" 2>/dev/null; then
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    return 1
}

cleanup_port() {
    local port="$1"
    local service_name="$2"
    
    if [ -n "$port" ]; then
        log_info "清理端口 $port ..."
        if command -v fuser &>/dev/null; then
            if fuser "$port/tcp" &>/dev/null; then
                log_warn "端口 $port 被占用，正在清理..."
                fuser -k "$port/tcp" 2>/dev/null || true
                sleep 1
            fi
        elif command -v lsof &>/dev/null; then
            local pids
            pids=$(lsof -ti ":$port" 2>/dev/null)
            if [ -n "$pids" ]; then
                log_warn "端口 $port 被占用，正在清理..."
                echo "$pids" | xargs -r kill -9 2>/dev/null || true
                sleep 1
            fi
        fi
    fi
}

activate_conda() {
    local env_name="$1"

    # 非交互式 shell 中 conda 可能未初始化，先尝试手动初始化
    if ! command -v conda &>/dev/null; then
        local conda_base="${CONDA_BASE:-$HOME/miniconda}"
        if [ -f "$conda_base/etc/profile.d/conda.sh" ]; then
            source "$conda_base/etc/profile.d/conda.sh"
        elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
            source "$HOME/miniconda3/etc/profile.d/conda.sh"
        elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
            source "$HOME/anaconda3/etc/profile.d/conda.sh"
        fi
    fi

    if command -v conda &>/dev/null; then
        eval "$(conda shell.bash hook 2>/dev/null)"
        conda activate "$env_name"
    else
        log_error "未找到 conda，无法激活环境: $env_name"
        return 1
    fi
}

# ============ 启动单个服务 ============

start_service() {
    local entry="$1"
    parse_service "$entry"

    if is_running "$S_PIDFILE"; then
        log_warn "服务 [$S_NAME] 已在运行 (PID=$(get_pid "$S_PIDFILE"))，跳过"
        return 0
    fi

    log_info "正在启动服务 [$S_NAME] ..."
    if [ -n "$S_CONDA" ]; then
        echo -e "  ${BLUE}Conda环境:${NC} $S_CONDA"
    fi
    echo -e "  ${BLUE}GPU:${NC} ${S_GPU:-无}"
    echo -e "  ${BLUE}端口:${NC} $S_PORT"
    echo -e "  ${BLUE}工作目录:${NC} $S_DIR"
    echo -e "  ${BLUE}启动命令:${NC} $S_CMD"

    # 清理端口
    cleanup_port "$S_PORT" "$S_NAME"

    (
        cd "$S_DIR" || exit 1

        if [ -n "$S_GPU" ]; then
            export CUDA_VISIBLE_DEVICES="$S_GPU"
        fi

        if [ -n "$S_CONDA" ]; then
            activate_conda "$S_CONDA" || exit 1
        fi

        mkdir -p "$LOG_DIR"
        export PYTHONUNBUFFERED=1
        setsid nohup $S_CMD >> "$LOG_DIR/${S_NAME}.log" 2>&1 &
        echo $! > "$PID_DIR/$S_PIDFILE"
    )

    if [ $? -ne 0 ]; then
        log_error "服务 [$S_NAME] 启动准备失败（conda 环境或工作目录异常），请检查日志: $LOG_DIR/${S_NAME}.log"
        return 1
    fi

    sleep 2

    if is_running "$S_PIDFILE"; then
        log_info "服务 [$S_NAME] 启动成功 (PID=$(get_pid "$S_PIDFILE"))"
        log_info "等待端口 $S_PORT 就绪..."
        if wait_for_port "$S_PORT" 60; then
            log_info "服务 [$S_NAME] 端口 $S_PORT 已就绪"
        else
            log_warn "服务 [$S_NAME] 端口 $S_PORT 等待超时，请检查日志: $LOG_DIR/${S_NAME}.log"
        fi
    else
        log_error "服务 [$S_NAME] 启动失败，请检查日志: $LOG_DIR/${S_NAME}.log"
        return 1
    fi
}

# ============ 停止单个服务 ============

stop_service() {
    local entry="$1"
    parse_service "$entry"

    if ! is_running "$S_PIDFILE"; then
        log_warn "服务 [$S_NAME] 未在运行，跳过"
        rm -f "$PID_DIR/$S_PIDFILE"
        # 清理端口
        cleanup_port "$S_PORT" "$S_NAME"
        return 0
    fi

    local pid
    pid=$(get_pid "$S_PIDFILE")
    log_info "正在停止服务 [$S_NAME] (PID=$pid) ..."

    local pgid
    pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')

    if [ -n "$pgid" ] && [ "$pgid" != "0" ]; then
        kill -TERM -- -"$pgid" 2>/dev/null || true
    else
        kill -TERM "$pid" 2>/dev/null || true
    fi

    local waited=0
    while [ "$waited" -lt 15 ]; do
        if ! kill -0 "$pid" 2>/dev/null; then
            break
        fi
        sleep 1
        waited=$((waited + 1))
    done

    if kill -0 "$pid" 2>/dev/null; then
        log_warn "服务 [$S_NAME] 未响应 SIGTERM，发送 SIGKILL..."
        if [ -n "$pgid" ] && [ "$pgid" != "0" ]; then
            kill -9 -- -"$pgid" 2>/dev/null || true
        else
            kill -9 "$pid" 2>/dev/null || true
        fi
        sleep 2
    fi

    # 确保所有子进程（如 vLLM EngineCore）也被清理
    if [ -n "$pgid" ] && [ "$pgid" != "0" ]; then
        local remaining
        remaining=$(ps -o pid= --ppid "$pid" 2>/dev/null | tr -d ' ')
        if [ -n "$remaining" ]; then
            log_warn "清理残留子进程: $remaining"
            echo "$remaining" | xargs -r kill -9 2>/dev/null || true
            sleep 1
        fi
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
        log_info "服务 [$S_NAME] 已停止"
    else
        log_error "服务 [$S_NAME] 停止失败，请手动处理: kill -9 $pid"
    fi

    rm -f "$PID_DIR/$S_PIDFILE"

    # 清理端口
    cleanup_port "$S_PORT" "$S_NAME"
}

# ============ 查看服务状态 ============

show_status() {
    echo ""
    echo -e "${CYAN}==================== 服务状态 ====================${NC}"
    printf "%-14s %-16s %-6s %-8s %-8s %s\n" "服务名称" "Conda环境" "GPU" "端口" "状态" "PID"
    echo "----------------------------------------------------------------------"

    for entry in "${SERVICES[@]}"; do
        parse_service "$entry"

        local status="已停止"
        local pid="-"
        if is_running "$S_PIDFILE"; then
            status="${GREEN}运行中${NC}"
            pid=$(get_pid "$S_PIDFILE")
        fi

        printf "%-14s %-16s %-6s %-8s " "$S_NAME" "${S_CONDA:--}" "${S_GPU:--}" "$S_PORT"
        echo -e "$status $pid"
    done

    echo ""
    echo -e "日志目录: ${BLUE}$LOG_DIR${NC}"
    echo -e "PID目录:  ${BLUE}$PID_DIR${NC}"
    echo ""
}

# ============ 查找服务条目 ============

find_service() {
    local target="$1"
    for entry in "${SERVICES[@]}"; do
        parse_service "$entry"
        if [ "$S_NAME" = "$target" ]; then
            echo "$entry"
            return 0
        fi
    done
    return 1
}

# ============ 主逻辑 ============

print_banner

ACTION="${1:-start}"
TARGET="${2:-all}"

case "$ACTION" in
    start)
        if [ "$TARGET" = "all" ]; then
            log_info "按顺序启动所有 AIPPT 服务..."
            echo ""

            has_failure=0
            for entry in "${SERVICES[@]}"; do
                start_service "$entry" || has_failure=1
                echo ""
            done

            echo -e "${GREEN}============================================================${NC}"
            if [ "$has_failure" -ne 0 ]; then
                log_warn "部分服务启动失败，请检查上方输出和日志目录"
            else
                log_info "所有服务启动完毕！"
            fi
            echo ""
            echo -e "  ${CYAN}PaddleOCR 服务:${NC}    http://0.0.0.0:8802"
            echo -e "  ${CYAN}IndexTTS 服务:${NC}     http://0.0.0.0:6006"
            echo -e "  ${CYAN}Wav2Lip 服务:${NC}      http://0.0.0.0:5000"
            echo -e "  ${CYAN}数字人接口服务:${NC}    http://0.0.0.0:9088"
            echo -e "  ${CYAN}数字人控制台:${NC}      http://0.0.0.0:9088/console"
            echo -e "  ${CYAN}API文档:${NC}           http://0.0.0.0:9088/docs"
            echo -e "  ${CYAN}前端页面:${NC}          http://0.0.0.0:5173"
            echo ""
            echo -e "  ${YELLOW}日志目录:${NC} $LOG_DIR"
            echo -e "  ${YELLOW}停止服务:${NC} $0 stop"
            echo -e "  ${YELLOW}查看状态:${NC} $0 status"
            echo -e "${GREEN}============================================================${NC}"
        else
            if entry=$(find_service "$TARGET"); then
                start_service "$entry"
            else
                log_error "未知服务: $TARGET (可选: paddleocr, tts, wav2lip, digital, frontend)"
                exit 1
            fi
        fi
        ;;

    stop)
        if [ "$TARGET" = "all" ]; then
            log_info "按逆序停止所有 AIPPT 服务..."
            echo ""

            reversed=()
            for (( i=${#SERVICES[@]}-1; i>=0; i-- )); do
                reversed+=("${SERVICES[$i]}")
            done

            for entry in "${reversed[@]}"; do
                stop_service "$entry" || true
                echo ""
            done

            log_info "所有服务已停止"
        else
            if entry=$(find_service "$TARGET"); then
                stop_service "$entry"
            else
                log_error "未知服务: $TARGET (可选: paddleocr, tts, wav2lip, digital, frontend)"
                exit 1
            fi
        fi
        ;;

    restart)
        if [ "$TARGET" = "all" ]; then
            bash "$0" stop all || true
            echo ""
            sleep 3
            bash "$0" start all
        else
            bash "$0" stop "$TARGET" || true
            echo ""
            sleep 2
            bash "$0" start "$TARGET"
        fi
        ;;

    status)
        show_status
        ;;

    *)
        echo "用法: $0 {start|stop|restart|status} [服务名|all]"
        echo ""
        echo "可用服务:"
        echo "  paddleocr   - PaddleOCR-VL 口播文案识别服务 (端口 8802)"
        echo "  tts         - IndexTTS 语音合成服务 (端口 6006)"
        echo "  wav2lip     - Wav2Lip 唇形同步与视频生成服务 (端口 5000)"
        echo "  digital     - 数字人接口总控服务 (端口 9088)"
        echo "  frontend    - 前端页面服务 (端口 5173)"
        echo "  all         - 所有服务"
        echo ""
        echo "示例:"
        echo "  $0 start          启动所有服务"
        echo "  $0 stop           停止所有服务"
        echo "  $0 restart        重启所有服务"
        echo "  $0 status         查看服务状态"
        echo "  $0 start tts      仅启动 IndexTTS 服务"
        echo "  $0 stop wav2lip   仅停止 Wav2Lip 服务"
        exit 1
        ;;
esac
