# MuseTalk 高清口型同步集成文档

## 文档信息

| 项目 | 内容 |
|------|------|
| **文档名称** | MuseTalk 高清口型同步集成文档 |
| **版本** | v5.0 |
| **创建日期** | 2026-04-21 |
| **作者** | AI 数字人项目组 |
| **描述** | MuseTalk 高清模式的架构设计、持久化缓存、配置说明、性能优化与故障排查 |

---

## 1. 概述

### 1.1 双模式策略

系统采用「快速 + 高清」双模式并行策略，用户可在前端选择生成质量：

| 模式 | 引擎 | 特点 | 适用场景 |
|------|------|------|----------|
| **快速模式 (fast)** | Wav2Lip | 速度快（~10s/段），画质一般 | 预览、快速迭代 |
| **高清模式 (hd)** | MuseTalk V1.5 | 画质优（面部细节保真），速度较慢 | 正式发布、竞赛演示 |

两种模式复用同一个 5000 端口服务，通过 `quality_mode` 参数路由到不同的推理引擎。

### 1.2 技术选型

MuseTalk 是由腾讯开源的实时高质量唇形同步模型，基于 Latent Diffusion 架构：

- **UNet**：musetalkV15/unet.pth — 条件去噪网络
- **VAE**：Stable Diffusion VAE — 图像编解码
- **Whisper**：音频特征提取（与 OpenAI Whisper 同架构，独立权重）
- **PositionalEncoding (PE)**：音频特征位置编码
- **FaceParsing**：面部分割，用于精细融合

---

## 2. 架构设计

### 2.1 系统集成架构

```
前端 (UploadPage.vue)
  │  quality_mode: 'fast' | 'hd'
  ▼
9088 网关 (my_digital_human.py)
  │  透传 quality_mode → 5000 服务
  │  HD 模式轮询超时: 15 分钟（450 × 2s）
  │  快速模式轮询超时: 5 分钟（150 × 2s）
  ▼
5000 服务 (video_generator.py)
  │  _process_parallel() 根据 quality_mode 路由:
  │    fast → run_wav2lip()
  │    hd   → run_musetalk()
  ▼
┌──────────────────────────────────────────────┐
│           run_musetalk() 流程 (v5.0)          │
│                                              │
│  1. _init_musetalk() — 懒加载模型            │
│  2. 计算 face_file_hash（纯内容 hash）       │
│  3. 检查持久化缓存：                         │
│     ├── 命中 → 加载 coords/latents/masks     │
│     └── 未命中 → 完整预处理 → 保存缓存       │
│  4. Whisper 音频特征提取                     │
│  5. UNet 批量推理（FP16, batch=128）         │
│     ├── Producer: UNet 推理 → compose_queue  │
│     └── Consumer: 帧合成 → FFmpeg NVENC 管道 │
│  6. 混合音频                                 │
│  7. 释放 CUDA 缓存                          │
└──────────────────────────────────────────────┘
```

### 2.2 模型加载策略（2026-04-25 更新）

**默认：服务启动时预加载**（`main.py` 中 `_preload_musetalk()` → `generator._init_musetalk()`），与 Wav2Lip、Whisper 一并执行，消除首次 HD 约 30s 的模型冷启动。预加载失败时仅打印警告，**首次 HD 请求仍会触发懒加载**。

**懒加载路径**（与预加载共用同一套逻辑）：

- `_init_musetalk()` 内使用 `threading.Lock` 双重检查，防止并发重复加载
- 加载时临时切换工作目录到 MuseTalk 根目录（部分内部模块依赖相对路径），完成后恢复

**运行环境**：5000 服务须在 **MuseTalk** conda 环境中启动（与 PyTorch 2.x、diffusers、mmpose 等依赖一致），勿混用仅含旧版依赖的环境。

### 2.3 请求链路

```
前端 POST /api/digital-human/generate/stream
  → 9088 POST http://127.0.0.1:5000/generate/upload (quality_mode=hd)
    → 5000 返回 202 + task_id
  → 9088 轮询 GET http://127.0.0.1:5000/status/{task_id}
    → 202 (processing) ... 重复轮询 ...
    → 200 (completed) + download_url
  → 9088 GET download_url → 保存视频文件
```

---

## 3. 配置说明

### 3.1 5000 服务配置 (`wav2lip_workspce/lx/测试/config.py`)

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `musetalk_dir` | `MUSETALK_DIR` | `{project_root}/MuseTalk` | MuseTalk 代码根目录 |
| `musetalk_unet_config` | `MUSETALK_UNET_CONFIG` | `{musetalk_dir}/models/musetalk/musetalk.json` | UNet 配置 JSON |
| `musetalk_unet_path` | `MUSETALK_UNET_PATH` | `{musetalk_dir}/models/musetalkV15/unet.pth` | UNet 权重 |
| `musetalk_vae_type` | `MUSETALK_VAE_TYPE` | `sd-vae` | VAE 类型 |
| `musetalk_whisper_dir` | `MUSETALK_WHISPER_DIR` | `{musetalk_dir}/models/whisper` | Whisper 模型目录 |
| `musetalk_dwpose_config` | — | `{musetalk_dir}/musetalk/utils/dwpose/...py` | DWPose 配置文件（代码内路径） |
| `musetalk_dwpose_checkpoint` | — | `{musetalk_dir}/models/dwpose/dw-ll_ucoco_384.pth` | DWPose 权重 |
| `musetalk_use_float16` | `MUSETALK_USE_FLOAT16` | `true` | 是否使用 FP16 推理 |
| `musetalk_batch_size` | `MUSETALK_BATCH_SIZE` | `8` | UNet 初始 batch（运行时可自适应上调） |
| `musetalk_gpu_id` | `MUSETALK_GPU_ID` | `0` | 使用的 GPU 编号 |

### 3.2 9088 网关超时配置 (`digital_human_interface/routers/my_digital_human.py`)

| 参数 | 快速模式 | 高清模式 | 说明 |
|------|----------|----------|------|
| `poll_task_status_async.max_attempts` | 150 | 450 | 轮询最大次数 |
| `poll_task_status_async.interval` | 2s | 2s | 轮询间隔 |
| **总轮询时长** | **5 分钟** | **15 分钟** | max_attempts × interval |
| `httpx.AsyncClient.timeout` | 300s | 900s | HTTP 客户端超时 |

### 3.3 5000 服务并行超时 (`video_generator.py`)

| 参数 | 快速模式 | 高清模式 | 说明 |
|------|----------|----------|------|
| `_process_parallel.timeout` | 300s | 600s | ThreadPoolExecutor future 超时 |

### 3.4 模型文件清单

```
MuseTalk/
├── models/
│   ├── musetalkV15/
│   │   ├── unet.pth              # UNet 权重 (~800MB)
│   │   └── musetalk.json         # UNet 配置
│   ├── whisper/
│   │   ├── config.json
│   │   ├── model.safetensors     # Whisper 权重
│   │   ├── preprocessor_config.json
│   │   └── tokenizer.json
│   ├── dwpose/
│   │   └── dw-ll_ucoco_384.pth   # DWPose 权重
│   └── sd-vae/                   # Stable Diffusion VAE
│       ├── config.json
│       └── diffusion_pytorch_model.safetensors
└── musetalk/
    └── utils/
        ├── audio_processor.py    # 音频处理（已修复边界越界）
        ├── preprocessing.py      # 人脸检测 + bbox
        ├── blending.py           # 面部融合
        └── utils.py              # datagen 批次生成
```

---

## 4. 性能优化

### 4.1 推理加速

| 优化项 | 版本 | 说明 | 效果 |
|--------|------|------|------|
| **FP16 精度** | v2.0 | UNet / VAE / PE 全部转为半精度 | 推理速度提升 ~40%，显存占用减半 |
| **自适应 batch_size** | v2.0 | `_auto_batch_size()` 根据可用显存自动计算最大 batch | 充分利用 GPU 并行能力 |
| **单图模式优化** | v2.0 | 输入为单张图片时，VAE 编码仅 1 次并复用 latent | 消除冗余 N 次 VAE encode |
| **增量推理** | v2.0 | 静默帧检测（whisper 能量 < 阈值），跳过 UNet | 可跳过 5-20% 帧 |
| **模型常驻** | v2.0 | 首次加载后常驻显存，后续请求 ~0s | 消除冷启动延迟 |
| **并行流水线** | v2.0 | 背景视频、口型同步、字幕三路并行 | 总耗时 ≈ max(三路) |
| **零磁盘 IO 流水线** | v3.0 | cv2.VideoCapture 直接读帧到内存，FFmpeg stdin 管道输出 | **消除 ~260s 磁盘 IO** |
| **FaceParsing 掩码缓存** | v3.0 | 单图模式掩码仅计算 1 次，视频模式每 25 帧计算 1 次 | **消除 ~150s 重复神经网络推理** |
| **稀疏 DWPose 检测** | v2.0 | 每 N 帧检测 1 次 + bbox 线性插值 | 1361 帧仅检测 6 帧 |
| **VAE 关键帧编码** | v2.0 | 每 N 帧编码 1 次，中间帧复用 latent | 1361 帧仅编码 11 帧 |
| **持久化预处理缓存** | v5.0 | coords/latents/masks 持久化到磁盘，纯内容 hash 索引 | **预处理从 ~150s 降至 ~3s** |
| **NVENC 硬件编码** | v5.0 | FFmpeg 管道改用 `h264_nvenc` GPU 编码 | 编码速度提升 3-5 倍 |
| **Producer-Consumer 流水线** | v5.0 | UNet 推理（producer）与帧合成（consumer）通过 Queue 并行 | 推理与合成重叠执行 |
| **队列语义** | v5.0.1 | 增量推理时 **`None` 表示静默帧**（复用上一合成帧），**不是**流结束；`finally` 仅投递独立 `object()` 作为结束哨兵，避免与静默帧混淆导致死锁（见 `修缮与功能总结.md` §14.6） | 修复「bg任务完成」后卡死 |
| **去除 deepcopy** | v5.0 | 帧合成不再 `copy.deepcopy` 原始帧 | 减少 CPU/内存开销 |
| **MediaPipe Task API** | v5.0 | 适配 0.10.x 新版 ImageSegmenter 人像分割 | 修复背景扣除失败 |

### 4.2 v5.0 持久化预处理缓存架构（核心改动）

**问题**：每次 HD 生成都重新执行 DWPose + VAE + FaceParsing 预处理，对 1361 帧视频耗时 ~150s，占总耗时 60-70%。

**方案**：将预处理结果持久化到磁盘，后续请求直接加载。

```
首次请求（预处理 + 缓存写入）：
  face_video → MD5(size + head_64KB + tail_64KB) → hash
  DWPose 检测 → coord_list  → coords.pkl
  VAE 编码    → latent_list → latents.pt
  FaceParsing → mask_pairs  → masks.pkl
  元信息      → meta.json

后续请求（缓存命中）：
  face_video → 相同 hash → 加载 coords.pkl + latents.pt + masks.pkl (~3s)
  跳过 DWPose / VAE / FaceParsing → 直接进入 UNet 推理
```

**缓存目录结构**：

```
musetalk_cache/
├── {hash_1}/
│   ├── meta.json       # 来源路径、帧数、FPS、创建时间
│   ├── coords.pkl      # 人脸坐标列表 (pickle)
│   ├── latents.pt      # VAE latent 张量 (torch)
│   └── masks.pkl       # FaceParsing 掩码对 (pickle)
├── {hash_2}/
│   └── ...
```

**缓存管理 API**（5000 端口）：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/musetalk/cache/status` | GET | 查看所有缓存条目 |
| `/musetalk/preprocess` | POST | 对指定 face 文件预处理并缓存 |
| `/musetalk/preprocess-all` | POST | 批量预处理所有数字人 |
| `/musetalk/cache/{hash}` | DELETE | 清除指定缓存 |
| `/musetalk/cache` | DELETE | 清除全部缓存 |

**自动触发**：上传新数字人时自动调用 `/musetalk/preprocess`（`my_digital_human.py` 中 `_trigger_musetalk_preprocess`）。

### 4.3 v3.0 零磁盘 IO 架构

**旧流水线（v2.0）—— 73% 时间浪费在磁盘 IO：**

```
视频 → FFmpeg 拆帧 → 1361 张 PNG 写磁盘 → cv2.imread 逐张读回内存
→ GPU 推理 (22.7s)
→ get_image() 每帧跑 FaceParsing → cv2.imwrite 1169 张 PNG 写磁盘
→ FFmpeg image2 逐张读 PNG → 最终视频
```

**新流水线（v3.0）—— 全内存，零 PNG 中转：**

```
视频 → cv2.VideoCapture 直接读帧到内存列表
→ GPU 推理 (22.7s)
→ get_image_blending() 使用缓存掩码 → FFmpeg stdin 管道直写
→ 最终视频
```

**关键改动：**

1. **帧读取**：`cv2.VideoCapture` 替代 `ffmpeg → PNG → cv2.imread`
2. **合成输出**：`subprocess.Popen(stdin=PIPE)` + `rawvideo` 替代 `cv2.imwrite → image2`
3. **FaceParsing**：`get_image_prepare_material()` 预算掩码 + `get_image_blending()` 快速复用

### 4.3 自适应 batch_size 算法

```python
@staticmethod
def _auto_batch_size(device, fp16: bool) -> int:
    free = torch.cuda.mem_get_info(device)[0] / (1024 ** 3)  # 可用显存 GB
    per_sample_gb = 0.045 if fp16 else 0.09    # 每样本显存开销
    headroom_gb = 2.0                           # 安全余量
    usable = max(free - headroom_gb, 1.0)
    bs = int(usable / per_sample_gb)
    bs = max(8, min(bs, 256))                   # 限制在 [8, 256]
    return (bs // 8) * 8                        # 对齐到 8 的倍数
```

### 4.4 显存管理

```python
# run_musetalk() 中的显存释放策略：

# 1. 推理完成后立即释放中间张量
del active_chunks, active_latent_list, gen
torch.cuda.empty_cache()

# 2. 帧合成完成后释放帧 map
del res_frame_map

# 3. finally 块确保异常时也清理
finally:
    torch.cuda.empty_cache()
    gc.collect()

# 4. 任务结束后全局清理
_release_gpu_memory()
  → wav2lip_model.clear_video_cache()
  → torch.cuda.empty_cache()
  → gc.collect()
```

### 4.5 显存占用参考

| 阶段 | 估计显存 | 说明 |
|------|----------|------|
| 模型加载 | ~3.5 GB | UNet + VAE + Whisper + PE (FP16) |
| 编译后首次推理 | ~6-8 GB | TensorRT/inductor 编译缓存 |
| 推理峰值（batch=128） | ~10-12 GB | 大 batch 时 |
| 推理后清理 | ~3.5 GB | 释放推理中间张量后 |

**建议**：MuseTalk 部署在 GPU 0，其他 GPU 密集型服务（如 TTS）分配到其他 GPU。

### 4.8 HD 模式时间估算算法

v5.0 更新：基于实测数据重写，修正 TTS 语速和 UNet 耗时的严重低估。

**旧算法问题**：`estimated_audio_duration = total_chars * 0.05`（117 字 = 5.85s），实际 TTS 生成 ~68s 音频（0.4s/字），偏差 12 倍。UNet 每 batch 设为 0.35s，实测 ~10s，偏差 29 倍。导致 41s 估算 vs 472s 实际。

```python
if quality_mode == "hd":
    # 中文 TTS 实际语速 ~0.4s/字
    real_audio_est = total_chars * 0.4
    chars_per_seg = total_chars / max(1, total_segments)
    frames_per_seg = int(chars_per_seg * 0.4 * 25)

    # 每段：缓存加载 5s + UNet (~10s/128帧batch) + 合成 (~0.13s/帧) + 后处理 15s
    unet_batches = max(1, frames_per_seg // 128)
    per_seg = 5 + unet_batches * 10 + frames_per_seg * 0.13 + 15
    stage5_time = max(120, int(per_seg * total_segments))
```

**示例**：117 字 / 2 段 → 估算 384s（旧算法 41s，实际 472s）。

### 4.7 依赖安装

```bash
# 在 MuseTalk conda 环境中安装加速依赖
conda activate MuseTalk
pip install tensorrt-cu12==10.0.1
pip install --no-deps torch_tensorrt==2.3.0 --extra-index-url https://download.pytorch.org/whl/cu121
pip install triton==2.3.0
```

---

## 5. 代码改动清单

### 5.1 新增 / 修改的文件

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `wav2lip_workspce/lx/测试/config.py` | 修改 | 新增 MuseTalk 模型路径和优化参数 |
| `wav2lip_workspce/lx/测试/models.py` | 修改 | `VideoGenerationRequest` 新增 `quality_mode` 字段 |
| `wav2lip_workspce/lx/测试/api/routes.py` | 修改 | `/generate/upload` 接口新增 `quality_mode` 参数 |
| `wav2lip_workspce/lx/测试/services/video_generator.py` | 修改 | 新增 `_init_musetalk()`、`run_musetalk()`；`_process_parallel()` 路由逻辑；显存释放增强 |
| `wav2lip_workspce/lx/测试/main.py` | 修改 | 新增 `_preload_musetalk()` 可选预加载 |
| `digital_human_interface/routers/my_digital_human.py` | 修改 | 透传 `quality_mode`；HD 模式轮询超时 15 分钟 |
| `frontend-new/src/api/digitalHuman.ts` | 修改 | `GenerationRequest` 新增 `quality_mode` 字段 |
| `frontend-new/src/pages/UploadPage.vue` | 修改 | 新增「生成质量」选择 UI |
| `start_all.sh` | 修改 | wav2lip 服务改用 MuseTalk conda 环境 |
| `MuseTalk/musetalk/utils/audio_processor.py` | 修改 | 修复 `get_whisper_chunk` 越界崩溃（替换 exit() 为零填充） |

### 5.2 Conda 环境

5000 端口服务（同时承载 Wav2Lip 和 MuseTalk）运行在 **MuseTalk** conda 环境中。`start_all.sh` 中配置：

```bash
"wav2lip|MuseTalk|0|$PROJECT_ROOT/wav2lip_workspce/lx/测试|python main.py|5000|wav2lip.pid"
```

该环境需要同时安装：
- MuseTalk 依赖（torch、transformers、mmdet、mmpose 等）
- Wav2Lip 依赖（face-alignment 等）
- 5000 服务依赖（fastapi、uvicorn、httpx 等）
- mediapipe（人物抠像）

---

## 6. 故障排查

### 6.1 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `get_landmark_and_bbox() got an unexpected keyword argument 'bbox_shift'` | 参数名错误 | 已修复：改为 `upperbondrange=0` |
| `AssertionError` + `exit()` 导致服务崩溃 | `audio_processor.py` 音频特征越界后调用 `exit()` | 已修复：改为零填充 + 安全跳过 |
| `No module named 'mediapipe'` | MuseTalk 环境缺少 mediapipe | `pip install mediapipe && pip install "numpy<2"` |
| `No module named 'face_detection'` | 错误的包名 | 应安装 `face-alignment` 而非 `face_detection` |
| 9088 报告「成功: 0, 失败: N」但 5000 日志显示生成成功 | 网关轮询超时（默认仅 5 分钟） | 已修复：HD 模式超时提升到 15 分钟 |
| `name 'self' is not defined` | `_release_gpu_memory` 为静态方法但代码中误用 self | 检查装饰器 `@staticmethod` |
| CUDA OOM | batch_size 过大或显存不足 | 降低 `MUSETALK_BATCH_SIZE`，或确保 FP16 开启 |
| `module 'mediapipe' has no attribute 'solutions'` | MediaPipe ≥ 0.10.x 移除旧 API | 已修复 (v5.0)：适配 Task API，自动下载 `selfie_segmenter.tflite` |
| HD 模式生成后人物带背景 | MediaPipe mask 生成失败，fallback 到绿幕 colorkey | 已修复 (v5.0)：MediaPipe Task API 适配 |
| 缓存永远未命中（`[first_run]`） | hash 算法使用 mtime，上传临时文件 mtime 改变 | 已修复 (v5.0)：hash 改为纯内容（size + 首尾 64KB） |
| 预估时间严重偏低（41s vs 472s） | TTS 语速估算 0.05s/字（实际 0.4s/字）、UNet 时间 0.35s/batch（实际 ~10s） | 已修复 (v5.0)：基于实测数据重写 |

### 6.2 诊断命令

```bash
# 查看 MuseTalk 推理日志（带阶段进度）
tail -f /home/ubuntu/workspace/PPTTalK/logs/wav2lip.log | grep "MuseTalk"

# 检查 GPU 显存使用
nvidia-smi

# 测试 5000 服务状态
curl http://127.0.0.1:5000/docs

# 手动重启 wav2lip 服务
cd /home/ubuntu/workspace/PPTTalK
bash start_all.sh stop wav2lip
bash start_all.sh start wav2lip

# 手动重启 9088 网关
bash start_all.sh stop digital
bash start_all.sh start digital
```

### 6.3 日志阶段标识

`run_musetalk()` 输出 5 个阶段进度日志，便于定位性能瓶颈：

```
[MuseTalk] 模型加载完成 (8.2s) — FP16=True, batch_size=128, GPU=0, VRAM=3502/4096MB
[MuseTalk] torch.compile(backend=torch_tensorrt) 已启用 — UNet + PE + VAE.decoder
[MuseTalk] 自适应 batch_size: 32 -> 128
[MuseTalk] 阶段1/5: 提取音频特征... (0.5s)
[MuseTalk] 音频特征提取完成, 305 chunks (2.1s)
[MuseTalk] 阶段2/5: 人脸检测与裁剪... (2.1s)
[MuseTalk] 单图模式：VAE 编码 1 次，复用 latent
[MuseTalk] 人脸检测完成, 1 张有效人脸 (3.8s)
[MuseTalk] 增量推理: 15 静默帧将跳过 UNet，仅推理 290 活跃帧
[MuseTalk] 阶段3/5: UNet 推理 (batch=128, FP16=True)... (3.8s)
[MuseTalk] 推理进度: 3/3 batches (8.1s)
[MuseTalk] UNet 推理完成, 生成 290 帧 (8.1s)
[MuseTalk] 单图模式: FaceParsing 掩码已缓存 (3.9s)
[MuseTalk] 阶段4/5: 帧合成 + 管道编码... (8.1s)
[MuseTalk] 帧合成 + 编码完成 (14.5s)
[MuseTalk] 阶段5/5: 混合音频... (14.5s)
[MuseTalk] 视频生成成功: /tmp/.../digital_human_raw.mp4 — 305 帧, 总耗时 16.2s, 实际 18.8 fps
[MuseTalk] CUDA 缓存已清理
```

---

## 7. 后续规划

| 优化方向 | 状态 | 说明 |
|----------|------|------|
| ~~增量推理~~ | **已实现 (v2.0)** | 静默帧检测（whisper 能量阈值），跳过 UNet 推理 |
| ~~自适应 batch_size~~ | **已实现 (v2.0)** | 根据可用显存自动计算最大 batch |
| ~~单图模式优化~~ | **已实现 (v2.0)** | VAE 编码仅 1 次，复用 latent |
| ~~稀疏 DWPose 检测~~ | **已实现 (v2.0)** | 每 N 帧检测 + 线性插值 |
| ~~零磁盘 IO~~ | **已实现 (v3.0)** | VideoCapture 输入 + FFmpeg 管道输出，消除全部 PNG 中转 |
| ~~FaceParsing 缓存~~ | **已实现 (v3.0)** | 掩码预算 + get_image_blending 复用，单图仅 1 次 |
| ~~持久化预处理缓存~~ | **已实现 (v5.0)** | coords/latents/masks 磁盘缓存，纯内容 hash 索引，预处理 ~150s→~3s |
| ~~NVENC 硬件编码~~ | **已实现 (v5.0)** | h264_nvenc GPU 编码，速度提升 3-5 倍 |
| ~~Producer-Consumer 流水线~~ | **已实现 (v5.0)** | UNet 推理与帧合成通过 Queue 并行 |
| ~~MediaPipe 适配~~ | **已实现 (v5.0)** | Task API (ImageSegmenter) 适配 0.10.x，背景扣除修复 |
| ~~HD 时间估算修复~~ | **已实现 (v5.0)** | 基于实测数据重写，偏差从 11.5 倍降至合理范围 |
| **实时推理模式** | 待实现 | 流式输出帧，降低首帧延迟 |
| **多 GPU 分布** | 待实现 | MuseTalk 和 Wav2Lip 分配到不同 GPU |
| **INT8 量化** | 待实现 | 进一步降低显存和提升推理速度 |

---

**文档版本**: v5.0
**最后更新**: 2026-04-22 (V2.3.5: 持久化缓存 + NVENC + MediaPipe适配 + 时间估算修复)
**维护者**: AI 数字人项目组
