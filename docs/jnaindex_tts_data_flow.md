# IndexTTS 语音合成数据业务流程

> **与当前仓库对齐**：`start_all.sh` 与 `index-tts-vllm/server/.env` 默认使用 **端口 6006**；下文若仍出现 9081/9082，多为历史方案或示例，以 **`tts_server_v2_batch.py` 实际监听端口** 及 **`start_all.sh` 启动命令** 为准。详见 [各服务配置与常见问题说明.md](各服务配置与常见问题说明.md)。

## 1. 模块概述

### 1.1 模块定位
IndexTTS 模块是 AI 数字人 PPT 视频生成系统中的**语音合成核心组件**，负责将文本（口播文案）转换为高质量的语音音频。该模块基于 IndexTTS-vLLM 架构，实现了快速、高质量的文本到语音转换，并支持情感控制功能。

### 1.2 技术特点
- **高质量语音合成**：基于 IndexTTS 模型生成自然流畅的语音
- **vLLM 加速推理**：使用 vLLM 框架加速推理，提升生成速度
- **情感控制**：支持多种情感参数（sad/happy/angry/surprise/fearful/disgusted/default）
- **情感参考音频**：支持通过参考音频提取情感特征
- **情感向量控制**：支持直接传入情感向量（emo_vec）
- **情感文本控制**：支持使用情感文本引导情感表达
- **批量处理**：支持批量文本合成，提升处理效率
- **CUDA 缓存清理**：集成 CudaCacheCleanupMiddleware 防止显存泄漏
- **文件自动清理**：生成的音频文件自动清理，避免磁盘占用
- **端口**：当前编排默认 **6006**（见 `start_all.sh`；旧文档中的双端口 9081/9082 为历史描述）

### 1.3 服务信息
| 项目 | 值 |
|------|-----|
| **入口文件** | `index-tts-vllm/server/tts_server_v2_batch.py` |
| **服务端口** | **6006**（默认；以 `.env` 与启动命令为准） |
| **框架** | FastAPI + IndexTTS + vLLM |
| **核心算法** | IndexTTS |
| **情感模型** | Qwen Emotion（可选） |
| **依赖服务** | PyTorch, CUDA |
| **调用地址** | `http://127.0.0.1:6006`（服务间调用，与 `digital_human_interface` 中写死 URL 一致） |

---

## 2. 系统架构

### 2.1 整体架构图
```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │digital_human│  │  Web UI      │  │  第三方调用  │           │
│  │_interface   │  │  (webui_v2)  │  │  (API)       │           │
│  └─────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              ↓ HTTP
┌─────────────────────────────────────────────────────────────────┐
│                     API 服务层 (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  tts_server_v2_batch.py                                 │  │
│  │                                                         │  │
│  │  端点:                                                   │  │
│  │  ├── /v2/infer         - 单文本 TTS 合成                 │  │
│  │  ├── /batch_tts        - 批量 TTS 合成                   │  │
│  │  ├── /tts_url          - 单文本 TTS (简化)               │  │
│  │  ├── /batch_tts_url    - 批量 TTS (简化)                 │  │
│  │  └── /health           - 健康检查                        │  │
│  │                                                         │  │
│  │  中间件:                                                 │  │
│  │  └── CudaCacheCleanupMiddleware - CUDA 缓存清理          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     推理服务层 (IndexTTS)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  infer_vllm_v2.py                                       │  │
│  │                                                         │  │
│  │  核心功能:                                               │  │
│  │  ├── 模型推理                                             │  │
│  │  ├── 情感控制                                             │  │
│  │  ├── 音频特征提取                                         │  │
│  │  └── 波形生成                                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        输出层                                    │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │WAV 音频文件 │  │  临时存储    │  │  文件清理    │           │
│  │(语音输出)   │  │  (temp/)     │  │  (自动清理)  │           │
│  └─────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心目录结构
```
index-tts-vllm/
├── server/
│   ├── tts_server_v2_batch.py       # 批处理 API 服务器
│   ├── api_server_v2.py             # API 服务器
│   └── .env                         # 环境变量配置
├── indextts/
│   └── infer_vllm_v2.py             # VLLM 推理核心（含情感控制）
├── webui_v2.py                      # Web UI 界面
├── requirements.txt                 # 依赖列表
└── checkpoints/                     # 模型权重目录
```

---

## 3. 数据业务流程详解

### 3.1 整体数据流
```
用户请求 (文本 + 情感参数)
  ↓
┌──────────────────────────────────────────────────────────┐
│ 1. API 接收请求 (FastAPI)                                  │
│    - 文本内容                                               │
│    - 情感参数 (emotion)                                     │
│    - 情感参考音频 (可选)                                     │
│    - 情感向量 (可选)                                         │
│    - 说话人 ID (可选)                                        │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 2. 参数解析和验证                                           │
│    - 验证文本内容                                           │
│    - 解析情感参数                                           │
│    - 加载情感参考音频（如果提供）                              │
│    - 计算情感向量（如果需要）                                  │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 3. 情感控制处理                                             │
│    - 根据 emotion 参数选择情感控制方式                        │
│    - 提取情感特征                                           │
│    - 生成情感向量                                           │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 4. TTS 推理 (IndexTTS)                                     │
│    - 加载输入文本                                           │
│    - 应用情感控制                                           │
│    - 模型推理                                               │
│    - 生成音频波形                                           │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 5. 音频处理和保存                                           │
│    - 波形转 WAV 格式                                        │
│    - 保存到临时目录                                         │
│    - 返回音频路径                                           │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 6. CUDA 缓存清理 (中间件)                                   │
│    - 请求结束后清理 CUDA 缓存                               │
│    - 释放显存                                               │
└──────────────────────────────────────────────────────────┘
  ↓
返回音频文件路径/URL
```

### 3.2 核心 API 端点数据流

#### 3.2.1 单文本 TTS 接口 (`POST /v2/infer`)

**请求参数**：
```python
text: str                             # 要合成的文本
emotion: str = "default"              # 情感参数 (sad/happy/angry/surprise/fearful/disgusted/default)
speaker_id: Optional[str] = None      # 说话人 ID
emo_audio_prompt: Optional[str] = None  # 情感参考音频路径
emo_alpha: float = 0.5                # 情感混合系数 (0-1)
emo_vector: Optional[List[float]] = None  # 情感向量
use_emo_text: bool = False            # 是否使用情感文本
emo_text: Optional[str] = None        # 情感引导文本
use_random: bool = False              # 是否使用随机情感
```

**处理流程**：
```
1. 参数验证
   ├─ 检查文本是否为空
   ├─ 验证情感参数
   └─ 检查说话人 ID

2. 情感控制
   ├─ 如果提供 emo_audio_prompt，提取音频情感特征
   ├─ 如果提供 emo_vector，使用直接情感向量
   ├─ 如果使用 emo_text，通过 Qwen 情感模型解析
   └─ 如果使用 random，随机生成情感向量

3. 模型推理
   ├─ 加载文本和说话人特征
   ├─ 应用情感控制
   ├─ IndexTTS 推理
   └─ 生成音频波形

4. 音频保存
   ├─ 将波形转换为 WAV 格式
   ├─ 保存到临时目录
   └─ 返回文件路径

5. CUDA 缓存清理
   └─ 中间件自动清理
```

**返回结果**：
```json
{
  "success": true,
  "audio_path": "/path/to/output/audio.wav",
  "audio_url": "http://127.0.0.1:9081/audio/audio.wav",
  "duration": 5.2,
  "text": "合成的文本内容"
}
```

#### 3.2.2 批量 TTS 接口 (`POST /batch_tts`)

**请求参数**：
```python
texts: List[str]                      # 要合成的文本列表
emotion: str = "default"              # 情感参数
speaker_id: Optional[str] = None      # 说话人 ID
emo_control_method: str = "default"   # 情感控制方法
emo_audio_prompt: Optional[str] = None  # 情感参考音频
emo_vec: Optional[List[float]] = None  # 情感向量
```

**处理流程**：
```
1. 参数验证
2. 遍历文本列表
3. 对每个文本执行 TTS 推理
4. 收集所有音频路径
5. 返回结果列表
```

**返回结果**：
```json
{
  "success": true,
  "results": [
    {"text": "文本 1", "audio_path": "/path/to/audio1.wav", "duration": 3.2},
    {"text": "文本 2", "audio_path": "/path/to/audio2.wav", "duration": 4.5}
  ]
}
```

#### 3.2.3 简化 TTS 接口 (`POST /tts_url`)

**请求参数**：
```python
text: str                             # 要合成的文本
emotion: str = "default"              # 情感参数
speaker_id: Optional[str] = None      # 说话人 ID
```

**返回结果**：
```
直接返回 WAV 音频文件（Content-Type: audio/wav）
```

#### 3.2.4 健康检查接口 (`GET /health`)

**返回结果**：
```json
{
  "status": "healthy",
  "model_loaded": true,
  "gpu_available": true,
  "device": "cuda:0"
}
```

---

## 4. 情感控制系统

### 4.1 情感参数说明

| 情感参数 | 描述 | 适用场景 |
|---------|------|---------|
| **default** | 默认情感（中性） | 一般讲解、说明 |
| **happy** | 快乐、积极 | 欢迎词、正面内容 |
| **sad** | 悲伤、低沉 | 严肃内容、反思 |
| **angry** | 愤怒、激动 | 强调、警告 |
| **surprise** | 惊讶、惊奇 | 意外内容、转折 |
| **fearful** | 恐惧、担忧 | 警示、风险提示 |
| **disgusted** | 厌恶、反感 | 批评、否定 |

### 4.2 情感控制方法

#### 4.2.1 情感名称控制
```python
# 直接使用情感名称
emotion = "happy"
```

#### 4.2.2 情感参考音频
```python
# 通过参考音频提取情感特征
emo_audio_prompt = "/path/to/happy_voice.wav"
emo_alpha = 0.5  # 情感混合系数
```

#### 4.2.3 情感向量控制
```python
# 直接传入情感向量
emo_vector = [0.1, 0.8, 0.2, 0.1, 0.0, 0.1, 0.0]  # 7 维情感向量
```

#### 4.2.4 情感文本控制
```python
# 使用情感文本引导
use_emo_text = True
emo_text = "我很高兴向大家介绍这个产品"
```

#### 4.2.5 随机情感
```python
# 随机生成情感向量
use_random = True
```

### 4.3 Qwen 情感模型

**核心代码**：`indextts/infer_vllm_v2.py` 中的 `QwenEmotion` 类

```python
class QwenEmotion:
    """使用 Qwen 情感模型解析文本情感并返回情感向量"""
    
    def __init__(self):
        self.model = load_qwen_model()
    
    def predict(self, text: str) -> List[float]:
        """
        根据文本预测情感向量
        
        参数:
            text: 输入文本
        
        返回:
            7 维情感向量 [sad, happy, angry, surprise, fearful, disgusted, default]
        """
        prompt = f"分析以下文本的情感：{text}"
        result = self.model.generate(prompt)
        return parse_emotion_vector(result)
```

---

## 5. CUDA 缓存清理中间件

### 5.1 中间件实现

**核心代码**：`server/tts_server_v2_batch.py` 中的 `CudaCacheCleanupMiddleware`

```python
class CudaCacheCleanupMiddleware(BaseHTTPMiddleware):
    """
    在 TTS 推理请求结束后释放 PyTorch CUDA 缓存，防止显存碎片堆积。
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 清理 CUDA 缓存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return response
```

### 5.2 清理策略

| 清理时机 | 清理方式 | 效果 |
|---------|---------|------|
| **请求结束** | `torch.cuda.empty_cache()` | 释放未使用的显存 |
| **批量处理完成** | 清理临时文件 | 释放磁盘空间 |
| **定时清理** | 后台任务 | 防止显存泄漏 |

---

## 6. 文件管理

### 6.1 音频文件存储

**存储路径**：
```
index-tts-vllm/
├── output/                      # 输出音频目录
│   └── audio_*.wav             # 生成的音频文件
└── temp/                        # 临时文件目录
    └── temp_*.wav              # 临时音频文件
```

### 6.2 文件清理策略

**自动清理**：
```python
# 请求完成后清理临时文件
def cleanup_temp_files(file_paths: List[str]):
    for path in file_paths:
        if os.path.exists(path) and path.startswith("temp_"):
            os.remove(path)
```

**定时清理**：
```python
# 定时清理 24 小时前的文件
async def cleanup_old_files():
    cutoff_time = time.time() - 24 * 3600
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.getmtime(file_path) < cutoff_time:
                os.remove(file_path)
```

---

## 7. 部署与配置

### 7.1 配置文件 (server/.env)

```bash
# 服务配置
TTS_PORT=9081
TTS_HOST=0.0.0.0

# 模型配置
MODEL_PATH=/path/to/index-tts-model
DEVICE=cuda

# 情感模型配置
QWEN_MODEL_PATH=/path/to/qwen-emotion

# 文件路径配置
OUTPUT_DIR=./output
TEMP_DIR=./temp

# 清理配置
CLEANUP_INTERVAL=3600  # 清理间隔（秒）
```

### 7.2 启动命令

**启动服务**：
```bash
cd /home/ubuntu/workspace/PPTTalK/index-tts-vllm/server
uvicorn tts_server_v2_batch:app --host 0.0.0.0 --port 9081 --reload
```

**使用启动脚本**：
```bash
# 启动所有服务
start_all.sh start

# 单独启动 TTS 服务
cd index-tts-vllm/server
python tts_server_v2_batch.py
```

### 7.3 环境变量支持

```bash
# 可通过环境变量覆盖配置
export TTS_PORT=9082
export MODEL_PATH=/custom/path/to/model
export DEVICE=cuda:0
```

---

## 8. 性能优化

### 8.1 vLLM 加速推理

**优化点**：
- 使用 vLLM 框架加速推理
- 支持 PagedAttention 显存管理
- 支持连续批处理

**性能提升**：
- 传统推理：约 5-10 秒/句
- vLLM 推理：约 2-4 秒/句
- 提升约 50-60%

### 8.2 模型预加载

**优化点**：
- 服务启动时预加载 IndexTTS 模型
- 消除首个请求的冷启动延迟

**性能提升**：
- 传统冷启动：首个请求额外增加 10-20 秒
- 预加载模式：首个请求即快速响应

### 8.3 CUDA 缓存管理

**优化点**：
- 请求结束后自动清理 CUDA 缓存
- 防止显存碎片堆积
- 避免 OOM 错误

### 8.4 批量处理

**优化点**：
- 支持批量文本合成
- 复用模型推理上下文
- 提升整体吞吐量

---

## 9. 常见问题与排查

### 9.1 启动问题

#### 问题 1：模型文件不存在
```
Error: Model file not found at /path/to/model
```
**解决方案**：
- 下载 IndexTTS 预训练模型
- 确保 `.env` 中的 `MODEL_PATH` 配置正确

#### 问题 2：CUDA 不可用
```
Error: CUDA is not available
```
**解决方案**：
```bash
# 检查 CUDA 安装
nvcc --version
nvidia-smi

# 检查 PyTorch CUDA 支持
python -c "import torch; print(torch.cuda.is_available())"
```

### 9.2 推理问题

#### 问题 1：显存不足 (OOM)
**可能原因**：
- 文本过长
- 批量过大
- CUDA 缓存未清理

**解决方案**：
- 缩短文本长度
- 减少批量大小
- 确保 `CudaCacheCleanupMiddleware` 已启用

#### 问题 2：情感控制无效
**可能原因**：
- 情感参数拼写错误
- 情感模型未加载
- 参考音频格式不支持

**解决方案**：
- 检查情感参数值（必须为 7 种之一）
- 确保 Qwen 情感模型正确加载
- 使用 WAV 格式参考音频

### 9.3 性能问题

#### 问题 1：推理速度慢
**可能原因**：
- GPU 性能不足
- 模型未预加载
- 批量处理未启用

**解决方案**：
- 使用更高性能 GPU
- 确保服务启动时模型预加载
- 使用批量接口 `/batch_tts`

---

## 10. 集成与调用

### 10.1 与 digital_human_interface 集成

**调用流程**：
```
digital_human_interface (Port 9088)
  ↓
调用 IndexTTS API (Port 9081)
  ├─ POST /v2/infer
  │   输入：text, emotion, speaker_id
  │   输出：音频路径和 URL
  └─ 轮询直到完成
```

**集成代码示例**：
```python
import httpx
import asyncio

async def synthesize_speech(text: str, emotion: str = "default"):
    """
    合成语音（通过 digital_human_interface 调用）
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "http://127.0.0.1:9081/v2/infer",
            json={
                "text": text,
                "emotion": emotion,
            }
        )
        
        if resp.status_code == 200:
            result = resp.json()
            if result["success"]:
                return result["audio_path"]
            else:
                raise Exception(f"TTS 失败：{result.get('error')}")
```

### 10.2 完整数据链路

```
PPT 文件
  ↓
[LibreOffice] → PDF
  ↓
[PaddleOCR-VL] → Markdown (每页)
  ↓
[LangChain + DeepSeek] → 口播文案 (每页)
  ↓
[IndexTTS-vLLM] → 音频文件 (每页)  ← 本模块
  ↓
[Wav2Lip] → 数字人视频
  ↓
[FFmpeg] → 合并视频
  ↓
[视频合并服务] → 添加 BGM
  ↓
[SimpleHLSSlicer] → HLS 切片 → 最终输出
```

---

## 11. 总结

### 11.1 核心优势
1. **高质量语音**：基于 IndexTTS 模型，生成自然流畅的语音
2. **vLLM 加速**：推理速度提升 50-60%
3. **情感控制**：支持 7 种情感和多种控制方式
4. **模型预加载**：服务启动时预加载，消除冷启动延迟
5. **CUDA 缓存清理**：自动清理显存，防止 OOM
6. **批量处理**：支持批量合成，提升吞吐量
7. **文件自动清理**：避免磁盘空间占用
8. **双端口支持**：支持负载均衡和高可用
9. **完整 API**：提供 RESTful API，易于集成
10. **Web UI**：提供可视化操作界面

### 11.2 技术亮点
1. **IndexTTS 模型**：高质量语音合成
2. **vLLM 框架**：PagedAttention 显存管理
3. **Qwen 情感模型**：智能情感分析
4. **情感参考音频**：从音频提取情感特征
5. **情感向量控制**：精确控制情感表达
6. **CUDA 缓存清理**：防止显存泄漏
7. **批量推理**：连续批处理提升效率
8. **模型预加载**：快速响应首个请求
9. **文件清理**：自动清理临时文件
10. **多端口支持**：负载均衡和高可用

### 11.3 应用场景
- **教育领域**：课件讲解音频生成
- **有声书制作**：自动化语音合成
- **语音助手**：智能客服语音
- **广播系统**：自动化播报
- **娱乐媒体**：虚拟主播语音

---

**文档版本**: v2.0  
**更新日期**: 2026-04-17  
**维护者**: AI 数字人项目组
