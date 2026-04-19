#!/usr/bin/env bash
# =============================================================================
# PPTTalK 一键环境部署脚本
# 适用：Ubuntu 22.04 + Conda 已安装 + 双卡 RTX 4090 (CUDA 12.4 / 11.7)
# 用法：bash setup_env.sh [选项]
#
# 选项：
#   --all           部署全部（默认行为）
#   --service NAME  仅部署指定服务（digital / paddleocr / tts / wav2lip / frontend）
#   --skip-models   跳过模型路径校验提示
#   --check-only    仅执行环境检查，不安装任何内容
#   --help          显示帮助
# =============================================================================
set -euo pipefail
IFS=$'\n\t'

# ─────────────────────────── 颜色 ───────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[OK]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
error()   { echo -e "${RED}[ERR]${RESET}  $*" >&2; }
step()    { echo -e "\n${BOLD}${GREEN}══ $* ══${RESET}"; }

# ─────────────────────────── 路径常量 ───────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

SVC_DIGITAL="$PROJECT_ROOT/digital_human_interface"
SVC_PADDLEOCR="$PROJECT_ROOT/paddleocr"
SVC_TTS="$PROJECT_ROOT/index-tts-vllm"
SVC_WAV2LIP="$PROJECT_ROOT/wav2lip_workspce/lx/测试"
SVC_FRONTEND="$PROJECT_ROOT/frontend-new"

# ─────────────────────────── 参数解析 ───────────────────────────
DEPLOY_TARGETS=()
SKIP_MODELS=false
CHECK_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)         DEPLOY_TARGETS=(digital paddleocr tts wav2lip frontend) ;;
    --service)     shift; DEPLOY_TARGETS=("$1") ;;
    --skip-models) SKIP_MODELS=true ;;
    --check-only)  CHECK_ONLY=true ;;
    --help|-h)
      grep '^#' "$0" | head -20 | sed 's/^# \?//'
      exit 0 ;;
    *) warn "未知参数: $1，忽略" ;;
  esac
  shift
done

# 默认部署全部
[[ ${#DEPLOY_TARGETS[@]} -eq 0 ]] && DEPLOY_TARGETS=(digital paddleocr tts wav2lip frontend)

# ─────────────────────────── 工具函数 ───────────────────────────

# 初始化 conda（兼容未 source bashrc 的非交互式场景）
init_conda() {
  # 已经可以直接调用则跳过
  if command -v conda &>/dev/null; then
    local conda_base; conda_base="$(conda info --base 2>/dev/null)"
    # shellcheck source=/dev/null
    [[ -f "$conda_base/etc/profile.d/conda.sh" ]] && \
      source "$conda_base/etc/profile.d/conda.sh"
    return 0
  fi

  # 尝试常见安装位置
  local candidates=(
    "$HOME/miniconda/etc/profile.d/conda.sh"
    "$HOME/miniconda3/etc/profile.d/conda.sh"
    "$HOME/anaconda3/etc/profile.d/conda.sh"
    "$HOME/anaconda/etc/profile.d/conda.sh"
    "/opt/conda/etc/profile.d/conda.sh"
    "/usr/local/conda/etc/profile.d/conda.sh"
    "/opt/miniconda3/etc/profile.d/conda.sh"
  )
  for f in "${candidates[@]}"; do
    if [[ -f "$f" ]]; then
      # shellcheck source=/dev/null
      source "$f"
      return 0
    fi
  done

  error "未找到 conda，请先安装 Miniconda/Anaconda 并确保其在 PATH 中"
  return 1
}

# 创建或更新 conda 环境
ensure_conda_env() {
  local env_name="$1" python_ver="$2"
  if PYTHONWARNINGS=ignore conda env list 2>/dev/null | awk '{print $1}' | grep -qx "$env_name"; then
    info "conda 环境 '$env_name' 已存在，跳过创建"
  else
    info "创建 conda 环境: $env_name (Python $python_ver) ..."
    conda create -y -n "$env_name" python="$python_ver"
    success "环境 '$env_name' 创建完成"
  fi
}

# 在指定 conda 环境中运行命令
run_in_env() {
  local env_name="$1"; shift
  conda run -n "$env_name" --no-capture-output "$@"
}

# 检查命令是否存在
need_cmd() {
  if ! command -v "$1" &>/dev/null; then
    error "缺少依赖命令: $1  →  $2"
    return 1
  fi
  success "命令检测: $1 $(command -v "$1")"
}

# 检查目录/文件是否存在，缺失时给出提示
check_path() {
  local path="$1" desc="$2"
  if [[ -e "$path" ]]; then
    success "路径存在: $path"
  else
    warn "缺失 ($desc): $path"
  fi
}

# ═══════════════════════════════════════════════════════════════
# 第一步：系统依赖检查
# ═══════════════════════════════════════════════════════════════
check_system() {
  step "系统依赖检查"

  local fail=0

  # conda 需特殊处理（非交互式 shell 可能不在 PATH）
  init_conda 2>/dev/null || true
  if command -v conda &>/dev/null; then
    success "命令检测: conda $(conda --version 2>/dev/null)"
  else
    error "缺少依赖命令: conda  →  请安装 Miniconda: https://docs.conda.io"
    fail=1
  fi

  need_cmd ffmpeg   "sudo apt install ffmpeg"                  || fail=1
  need_cmd ffprobe  "sudo apt install ffmpeg"                  || fail=1
  need_cmd libreoffice "sudo apt install libreoffice"          || fail=1
  need_cmd git      "sudo apt install git"                     || fail=1

  # Node.js / npm (前端构建用)
  if command -v node &>/dev/null; then
    local node_ver; node_ver="$(node -v)"
    success "Node.js $node_ver 已安装"
  else
    warn "Node.js 未安装，前端构建将跳过  →  建议安装 v18+ (nvm install 18)"
  fi

  # GPU 检测
  if command -v nvidia-smi &>/dev/null; then
    local gpu_info; gpu_info="$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || true)"
    if [[ -n "$gpu_info" ]]; then
      echo "$gpu_info" | while IFS= read -r line; do
        success "GPU 检测: $line"
      done
    else
      warn "nvidia-smi 可用但未检测到 GPU"
    fi
  else
    warn "nvidia-smi 未找到，将以 CPU 模式运行"
  fi

  if [[ "$fail" -eq 1 ]]; then
    error "系统依赖不满足，请先安装缺失工具后重新运行"
    exit 1
  fi
}

# ═══════════════════════════════════════════════════════════════
# 第二步：模型文件路径校验
# ═══════════════════════════════════════════════════════════════
check_models() {
  [[ "$SKIP_MODELS" == true ]] && return 0

  step "模型路径校验（--skip-models 可跳过）"

  # PaddleOCR 模型
  check_path "$SVC_PADDLEOCR/models/PaddleOCR-VL-0.9B" \
    "PaddleOCR-VL 模型，参考 paddleocr/.env 中 VL_MODEL_DIR"

  # IndexTTS 模型
  check_path "$SVC_TTS/checkpoints/IndexTTS-2-vLLM" \
    "IndexTTS-2-vLLM 检查点，参考 index-tts-vllm/server/.env 中 MODEL_DIR"

  # Wav2Lip 模型
  check_path "$PROJECT_ROOT/Wav2Lip/models/Wav2Lip-SD-GAN.pt" \
    "Wav2Lip 模型权重，路径见 wav2lip_workspce/lx/测试/config.py"

  echo ""
  warn "以上 [缺失] 路径需手动下载模型，脚本无法自动获取大文件"
  warn "模型下载完成后重新运行本脚本（或使用 --skip-models 跳过校验）"
}

# ═══════════════════════════════════════════════════════════════
# 第三步：.env 文件校验与生成
# ═══════════════════════════════════════════════════════════════
setup_dotenv() {
  step ".env 配置文件检查"

  # digital_human_interface/.env
  if [[ ! -f "$SVC_DIGITAL/.env" ]]; then
    warn "$SVC_DIGITAL/.env 不存在，正在从模板生成..."
    cat > "$SVC_DIGITAL/.env" <<DOTENV
BASE_DIR=$SVC_DIGITAL
UPLOAD_FOLDER=static/video/uploads
CONVERTED_FOLDER=static/video/converted
MAX_CONTENT_LENGTH=100
HOST=0.0.0.0
PORT=9088
DEBUG=False
LIBREOFFICE_PATH=/usr/bin/libreoffice
FFMPEG_PATH=/usr/bin/ffmpeg
FFPROBE_PATH=/usr/bin/ffprobe
SEGMENT_TIME=10
VIDEO_CODEC=libx264
AUDIO_CODEC=aac
VIDEO_BITRATE=2M
MAXRATE=2M
BUFSIZE=4M
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:9088,http://127.0.0.1:9088
SECRET_KEY=change-me-in-production
MAX_CONCURRENT_TASKS=5
TASK_CLEANUP_HOURS=24
DOTENV
    success "已生成 $SVC_DIGITAL/.env（请按需修改 CORS_ORIGINS / SECRET_KEY）"
  else
    success "$SVC_DIGITAL/.env 已存在"
  fi

  # paddleocr/.env
  if [[ ! -f "$SVC_PADDLEOCR/.env" ]]; then
    warn "$SVC_PADDLEOCR/.env 不存在，正在生成模板..."
    cat > "$SVC_PADDLEOCR/.env" <<DOTENV
VL_MODEL_DIR = $PROJECT_ROOT/paddleocr/models/PaddleOCR-VL-0.9B
LAYOUT_MODEL_DIR = $PROJECT_ROOT/paddleocr/models/PaddleOCR-VL-0.9B/PP-DocLayoutV2
UPLOAD_BASE_DIR=$PROJECT_ROOT/paddleocr/output
UPLOAD_BASE_URL=127.0.0.1
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DOTENV
    success "已生成 $SVC_PADDLEOCR/.env（请填写 DEEPSEEK_API_KEY）"
  else
    success "$SVC_PADDLEOCR/.env 已存在"
  fi

  # index-tts-vllm/server/.env
  if [[ ! -f "$SVC_TTS/server/.env" ]]; then
    warn "$SVC_TTS/server/.env 不存在，正在生成模板..."
    mkdir -p "$SVC_TTS/server"
    cat > "$SVC_TTS/server/.env" <<DOTENV
HOST=0.0.0.0
PORT=6006
MODEL_DIR=$PROJECT_ROOT/index-tts-vllm/checkpoints/IndexTTS-2-vLLM
IS_FP16=False
GPU_MEMORY_UTILIZATION=0.15
QWENEMO_GPU_MEMORY_UTILIZATION=0.10
REF_AUDIO_ROOT_PATH=$PROJECT_ROOT/index-tts-vllm/outputs/
ALLOWED_AUDIO_EXTENSIONS=.wav,.mp3,.m4a
DEFAULT_OUTPUT_PATH=$PROJECT_ROOT/index-tts-vllm/outputs/
EXPIRE_DAYS=7
LOG_ROTATION_SIZE=10 MB
LOG_RETENTION_COUNT=10
UPLOAD_TEMP_PATH=$PROJECT_ROOT/index-tts-vllm/server/upload_temp
DOTENV
    success "已生成 $SVC_TTS/server/.env"
  else
    success "$SVC_TTS/server/.env 已存在"
  fi

  # frontend-new/.env.production（构建时 API 地址）
  if [[ ! -f "$SVC_FRONTEND/.env.production" ]]; then
    warn "前端生产 .env 不存在，生成中..."
    echo "VITE_API_BASE=" > "$SVC_FRONTEND/.env.production"
    warn "请在 $SVC_FRONTEND/.env.production 中填写 VITE_API_BASE（留空代表同域相对路径）"
  else
    success "$SVC_FRONTEND/.env.production 已存在"
  fi
}

# ═══════════════════════════════════════════════════════════════
# 第四步：创建必要目录
# ═══════════════════════════════════════════════════════════════
setup_dirs() {
  step "创建运行时必要目录"

  local dirs=(
    "$SVC_DIGITAL/static/video/uploads"
    "$SVC_DIGITAL/static/video/converted"
    "$SVC_DIGITAL/static/file/bgm"
    "$SVC_PADDLEOCR/output"
    "$SVC_TTS/outputs"
    "$SVC_TTS/server/upload_temp"
    "$SVC_WAV2LIP/image_output"
    "$SVC_WAV2LIP/uploaded_files"
    "$SVC_WAV2LIP/temp_files"
    "$PROJECT_ROOT/logs"
    "$PROJECT_ROOT/.pids"
    "$PROJECT_ROOT/frontend"
  )

  for d in "${dirs[@]}"; do
    mkdir -p "$d"
    success "目录: $d"
  done
}

# ═══════════════════════════════════════════════════════════════
# 服务部署函数
# ═══════════════════════════════════════════════════════════════

deploy_digital() {
  step "部署 digital_human_interface (conda: digital / Python 3.11 / 端口 9088)"

  init_conda || { error "conda 初始化失败，无法继续"; exit 1; }
  ensure_conda_env "digital" "3.11"

  info "安装 Python 依赖..."
  run_in_env "digital" pip install -r "$SVC_DIGITAL/requirements.txt" \
    --quiet --exists-action i

  success "digital_human_interface 环境就绪"
}

deploy_paddleocr() {
  step "部署 paddleocr (conda: ppocrvl / Python 3.11 / GPU 0 / 端口 8802)"

  init_conda || { error "conda 初始化失败，无法继续"; exit 1; }
  ensure_conda_env "ppocrvl" "3.11"

  # PaddlePaddle-GPU（与 CUDA 12 兼容的安装方式）
  if run_in_env "ppocrvl" python -c "import paddle" 2>/dev/null; then
    info "PaddlePaddle 已安装，跳过"
  else
    info "安装 PaddlePaddle-GPU (CUDA 12)..."
    run_in_env "ppocrvl" pip install paddlepaddle-gpu==3.0.0 \
      -i https://www.paddlepaddle.org.cn/packages/stable/cu123/ \
      --quiet
  fi

  # PaddleOCR
  if run_in_env "ppocrvl" python -c "import paddleocr" 2>/dev/null; then
    info "PaddleOCR 已安装，跳过"
  else
    info "安装 PaddleOCR..."
    run_in_env "ppocrvl" pip install paddleocr --quiet
  fi

  # LangChain + OpenAI（文案生成依赖）
  info "安装 LangChain / OpenAI / python-dotenv..."
  run_in_env "ppocrvl" pip install langchain langchain-openai \
    openai python-dotenv beautifulsoup4 fastapi uvicorn \
    --quiet --exists-action i

  success "paddleocr 环境就绪"
  warn "请确认 $SVC_PADDLEOCR/.env 中的 DEEPSEEK_API_KEY 已填写"
}

deploy_tts() {
  step "部署 index-tts-vllm (conda: index-tts-vllm / Python 3.12 / GPU 1 / 端口 6006)"

  init_conda || { error "conda 初始化失败，无法继续"; exit 1; }
  ensure_conda_env "index-tts-vllm" "3.12"

  # vLLM 需要 PyTorch，先检查
  if run_in_env "index-tts-vllm" python -c "import torch; print(torch.__version__)" 2>/dev/null; then
    info "PyTorch 已安装，跳过"
  else
    info "安装 PyTorch 2.x (CUDA 12.6)..."
    run_in_env "index-tts-vllm" pip install \
      torch torchvision torchaudio \
      --index-url https://download.pytorch.org/whl/cu126 \
      --quiet
  fi

  info "安装 requirements.txt（含 vLLM 0.16.0）..."
  run_in_env "index-tts-vllm" pip install \
    -r "$SVC_TTS/requirements.txt" \
    -c "$SVC_TTS/overrides.txt" \
    --quiet --exists-action i

  # IndexTTS 本身作为本地包安装
  if [[ -f "$SVC_TTS/setup.py" ]] || [[ -f "$SVC_TTS/pyproject.toml" ]]; then
    info "以开发模式安装 IndexTTS 包..."
    run_in_env "index-tts-vllm" pip install -e "$SVC_TTS" --quiet
  fi

  success "index-tts-vllm 环境就绪"
  warn "请确认模型目录: $SVC_TTS/checkpoints/IndexTTS-2-vLLM"
}

deploy_wav2lip() {
  step "部署 wav2lip (conda: wav2lip_fixed / Python 3.8 / GPU 0 / 端口 5000)"

  init_conda || { error "conda 初始化失败，无法继续"; exit 1; }
  ensure_conda_env "wav2lip_fixed" "3.8"

  # PyTorch 1.13.1 + CUDA 11.7（固定版本，与 Wav2Lip 兼容）
  if run_in_env "wav2lip_fixed" python -c "import torch; assert '1.13' in torch.__version__" 2>/dev/null; then
    info "PyTorch 1.13.x 已安装，跳过"
  else
    info "安装 PyTorch 1.13.1+cu117..."
    run_in_env "wav2lip_fixed" pip install \
      torch==1.13.1+cu117 torchvision==0.14.1+cu117 torchaudio==0.13.1 \
      --extra-index-url https://download.pytorch.org/whl/cu117 \
      --quiet
  fi

  info "安装 Wav2Lip 服务依赖..."
  run_in_env "wav2lip_fixed" pip install \
    -r "$SVC_WAV2LIP/requirements.txt" \
    --quiet --exists-action i

  # Whisper（字幕生成）
  if run_in_env "wav2lip_fixed" python -c "import whisper" 2>/dev/null; then
    info "Whisper 已安装，跳过"
  else
    info "安装 OpenAI Whisper..."
    run_in_env "wav2lip_fixed" pip install openai-whisper --quiet
  fi

  # 检查 Wav2Lip 核心模型目录
  if [[ ! -d "$PROJECT_ROOT/Wav2Lip" ]]; then
    warn "Wav2Lip 代码目录不存在: $PROJECT_ROOT/Wav2Lip"
    warn "请克隆 Wav2Lip 仓库并放置模型权重到 models/Wav2Lip-SD-GAN.pt"
  fi

  success "wav2lip 环境就绪"
}

deploy_frontend() {
  step "部署前端 (Vue 3 + Vite + TypeScript → frontend/)"

  if ! command -v node &>/dev/null; then
    warn "Node.js 未安装，跳过前端构建"
    warn "安装方式: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash && nvm install 18"
    return 0
  fi

  if ! command -v npm &>/dev/null; then
    warn "npm 未安装，跳过前端构建"
    return 0
  fi

  info "Node.js $(node -v), npm $(npm -v)"

  if [[ ! -f "$SVC_FRONTEND/package.json" ]]; then
    error "前端 package.json 不存在: $SVC_FRONTEND/package.json"
    return 1
  fi

  info "安装前端依赖 (npm install)..."
  npm install --prefix "$SVC_FRONTEND" --silent

  info "构建前端 (npm run build)..."
  npm run build --prefix "$SVC_FRONTEND"

  info "部署构建产物到 $PROJECT_ROOT/frontend/ ..."
  mkdir -p "$PROJECT_ROOT/frontend"
  # 保留已有的 basic_information.json 等数据文件
  rsync -a --delete \
    --exclude "basic_information.json" \
    "$SVC_FRONTEND/dist/" "$PROJECT_ROOT/frontend/"

  success "前端部署完成 → $PROJECT_ROOT/frontend/"
  info "Nginx 应将静态根目录指向 $PROJECT_ROOT/frontend/"
}

# ═══════════════════════════════════════════════════════════════
# 检查模式：只检查不安装
# ═══════════════════════════════════════════════════════════════
run_check_only() {
  step "环境检查模式（--check-only）"
  check_system
  check_models

  step "Conda 环境检查"
  init_conda 2>/dev/null || true
  for env in digital ppocrvl "index-tts-vllm" wav2lip_fixed; do
    if PYTHONWARNINGS=ignore conda env list 2>/dev/null | awk '{print $1}' | grep -qx "$env"; then
      success "conda 环境存在: $env"
    else
      warn "conda 环境缺失: $env"
    fi
  done

  # 检查端口占用
  step "端口占用检查"
  for port in 5000 6006 8802 9088; do
    if ss -tlnp 2>/dev/null | grep -q ":$port "; then
      info "端口 $port 已被监听（服务可能正在运行）"
    else
      info "端口 $port 空闲"
    fi
  done
}

# ═══════════════════════════════════════════════════════════════
# 最终摘要
# ═══════════════════════════════════════════════════════════════
print_summary() {
  echo ""
  echo -e "${BOLD}${GREEN}╔═══════════════════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}${GREEN}║              PPTTalK 环境部署完成                    ║${RESET}"
  echo -e "${BOLD}${GREEN}╚═══════════════════════════════════════════════════════╝${RESET}"
  echo ""
  echo -e "  ${CYAN}启动所有服务：${RESET}  bash $PROJECT_ROOT/start_all.sh start"
  echo -e "  ${CYAN}停止所有服务：${RESET}  bash $PROJECT_ROOT/start_all.sh stop"
  echo -e "  ${CYAN}查看服务状态：${RESET}  bash $PROJECT_ROOT/start_all.sh status"
  echo ""
  echo -e "  ${YELLOW}端口映射：${RESET}"
  echo -e "    9088  → digital_human_interface  (主入口)"
  echo -e "    8802  → paddleocr                (OCR / 文案生成)"
  echo -e "    6006  → index-tts-vllm           (语音合成)"
  echo -e "    5000  → wav2lip                  (数字人视频合成)"
  echo -e "    5173  → 前端开发服务             (npm run dev)"
  echo ""
  echo -e "  ${YELLOW}前端已构建到：${RESET} $PROJECT_ROOT/frontend/"
  echo -e "  ${YELLOW}日志目录：${RESET}     $PROJECT_ROOT/logs/"
  echo ""
  echo -e "  ${RED}注意事项：${RESET}"
  echo -e "    1. 检查各 .env 文件中的 API KEY 和模型路径是否正确"
  echo -e "    2. paddleocr/.env 中的 DEEPSEEK_API_KEY 必须填写"
  echo -e "    3. 确认 Wav2Lip-SD-GAN.pt 模型已放置到正确路径"
  echo -e "    4. IndexTTS-2-vLLM checkpoints 目录需手动下载"
  echo ""
}

# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════
main() {
  echo -e "\n${BOLD}${CYAN}PPTTalK 一键环境部署脚本${RESET}"
  echo -e "项目根目录: ${PROJECT_ROOT}"
  echo -e "部署目标:   ${DEPLOY_TARGETS[*]}"
  echo ""

  if [[ "$CHECK_ONLY" == true ]]; then
    run_check_only
    exit 0
  fi

  check_system
  check_models
  setup_dotenv
  setup_dirs

  for target in "${DEPLOY_TARGETS[@]}"; do
    case "$target" in
      digital)    deploy_digital   ;;
      paddleocr)  deploy_paddleocr ;;
      tts)        deploy_tts       ;;
      wav2lip)    deploy_wav2lip   ;;
      frontend)   deploy_frontend  ;;
      *)
        warn "未知部署目标: $target（可选: digital / paddleocr / tts / wav2lip / frontend）"
        ;;
    esac
  done

  print_summary
}

main "$@"
