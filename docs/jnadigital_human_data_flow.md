# 数字人接口服务数据业务流程

## 1. 模块概述

### 1.1 模块定位
数字人接口服务（digital_human_interface）是 AI 数字人 PPT 视频生成系统的**核心业务调度和对外接口层**，负责接收前端请求、协调各子服务（PaddleOCR、IndexTTS、Wav2Lip）、管理任务状态、推送实时进度，并提供视频合并、HLS 切片等后处理能力。

### 1.2 技术特点
- **FastAPI 框架**：基于 FastAPI 构建的高性能异步 API 服务
- **异步任务调度**：使用 BackgroundTasks 和线程池管理异步任务
- **SSE 实时监控**：通过 Server-Sent Events 实时推送处理进度和日志
- **任务管理系统**：完整的任务创建、状态跟踪、重试机制
- **视频后处理**：视频合并、BGM 混音、HLS 切片
- **文件管理**：文件上传、下载、预览、清理
- **模板系统**：支持自定义数字人模板和配置
- **GPU 监控**：实时监控 GPU 使用率和内存
- **多服务协调**：统一调度和协调 OCR、TTS、Wav2Lip 服务

### 1.3 服务信息
| 项目 | 值 |
|------|-----|
| **入口文件** | `digital_human_interface/main.py` |
| **服务端口** | 9088 |
| **框架** | FastAPI + Uvicorn |
| **依赖服务** | PaddleOCR (8802), IndexTTS (**6006**), Wav2Lip (5000) |
| **调用地址** | `http://127.0.0.1:9088` |

---

## 2. 系统架构

### 2.1 整体架构图
```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Vue 3 前端  │  │  Postman     │  │  第三方调用  │           │
│  │  (frontend- │  │  (API 测试)  │  │  (API)       │           │
│  │   new)      │  │              │  │              │           │
│  └─────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                    ↓ HTTP              ↓ SSE
┌─────────────────────────────────────────────────────────────────┐
│                   核心业务层 (digital_human_interface)             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  main.py (FastAPI, Port 9088)                           │  │
│  │                                                         │  │
│  │  路由层 (routers/):                                     │  │
│  │  ├── my_digital_human.py  - 数字人管理路由              │  │
│  │  ├── conversion.py        - PPT 转换路由               │  │
│  │  ├── files.py             - 文件管理路由                │  │
│  │  ├── video.py             - 视频处理路由                │  │
│  │  ├── tts.py               - TTS 合成路由                │  │
│  │  └── sse_monitor.py       - SSE 监控路由                │  │
│  │                                                         │  │
│  │  服务层 (services/):                                    │  │
│  │  ├── conversion_service.py   - PPT 转图片服务           │  │
│  │  ├── file_service.py         - 文件管理服务             │  │
│  │  ├── video_merge_service.py  - 视频合并 + BGM 服务      │  │
│  │  ├── video_his_service.py    - HLS 切片服务             │  │
│  │  ├── cleanup_service.py      - 定时清理服务             │  │
│  │  └── scheduler_service.py    - 任务调度服务             │  │
│  │                                                         │  │
│  │  核心层 (core/):                                        │  │
│  │  ├── converter.py            - 转换器基类               │  │
│  │  └── libreoffice_converter.py - LibreOffice 转换器      │  │
│  │                                                         │  │
│  │  配置层 (config/):                                      │  │
│  │  └── settings.py             - 全局配置                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                    ↓ HTTP              ↓ HTTP              ↓ HTTP
┌──────────────────────┐  ┌──────────────────┐  ┌──────────────┐
│  PaddleOCR 服务      │  │  IndexTTS 服务   │  │  Wav2Lip 服务│
│  Port 8802           │  │  Port 6006       │  │  Port 5000   │
│  OCR + 口播文案       │  │  语音合成         │  │  唇形同步     │
└──────────────────────┘  └──────────────────┘  └──────────────┘
```

### 2.2 目录结构
```
digital_human_interface/
├── main.py                          # FastAPI 入口（1494 行）
├── config/
│   └── settings.py                  # 配置管理（314 行）
├── routers/
│   ├── my_digital_human.py          # 数字人管理路由（2023 行）
│   ├── conversion.py                # PPT 转换路由（185 行）
│   ├── files.py                     # 文件管理路由
│   ├── video.py                     # 视频处理路由（259 行）
│   ├── tts.py                       # TTS 合成路由
│   └── sse_monitor.py               # SSE 监控路由（50 行）
├── services/
│   ├── conversion_service.py        # PPT 转图片服务（200 行）
│   ├── file_service.py              # 文件管理服务（150 行）
│   ├── video_merge_service.py       # 视频合并 + BGM 服务（200 行）
│   ├── video_his_service.py         # HLS 切片服务（100 行）
│   ├── cleanup_service.py           # 定时清理服务（150 行）
│   └── scheduler_service.py         # 任务调度服务（150 行）
├── core/
│   ├── converter.py                 # 转换器基类
│   └── libreoffice_converter.py     # LibreOffice 转换器（100 行）
├── templates/
│   └── index.html                   # 控制台监控面板（说明见 jnadigital_human_console.md）
└── static/
    └── Digital_human/               # 数字人模板目录
```

---

## 3. 数据业务流程详解

### 3.1 完整视频生成流程
```
用户提交 PPT 文件 + 配置参数
  ↓
┌──────────────────────────────────────────────────────────┐
│ 1. 接收请求 (main.py / my_digital_human.py)               │
│    - 创建 task_id (UUID)                                  │
│    - 初始化任务状态                                       │
│    - 建立 SSE 推送通道                                    │
│    - 启动异步任务                                         │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 2. PPT 转换 (conversion_service)                          │
│    - 调用 LibreOffice 转换 PPT → PDF                     │
│    - 使用 pdftoppm 将 PDF → 逐页图像                      │
│    - 图像存储到临时目录                                   │
│    - SSE 推送转换进度                                     │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 3. OCR 识别 + 口播文案 (调用 PaddleOCR, Port 8802)        │
│    - 逐页调用 POST /parse 接口                            │
│    - PaddleOCR-VL 识别页面内容                            │
│    - 调用 DeepSeek 生成口播文案 (style 参数)              │
│    - 返回: page_content + voice_content (每页)            │
│    - SSE 推送识别进度                                     │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 4. TTS 语音合成 (调用 IndexTTS, Port 6006)                 │
│    - 逐页调用 POST /v2/infer 接口                         │
│    - IndexTTS 生成音频文件                                │
│    - 支持情感参数 (emotion)                               │
│    - 输出: audio.wav (每页)                               │
│    - SSE 推送合成进度                                     │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 5. 数字人视频生成 (调用 Wav2Lip, Port 5000)               │
│    - 调用 POST /generate/upload 接口                      │
│    - Wav2Lip 唇形同步                                     │
│    - MediaPipe 人像分割                                   │
│    - Whisper 字幕生成                                     │
│    - 并行处理：背景视频 + Wav2Lip + 字幕                  │
│    - 输出: video.mp4 (每页)                               │
│    - SSE 推送生成进度                                     │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 6. 视频合并 (video_merge_service)                         │
│    - 合并所有页面视频                                     │
│    - 调用 mix_bgm 函数添加 BGM                            │
│    - 输出: merged_video.mp4                               │
│    - SSE 推送合并进度                                     │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 7. HLS 切片 (video_his_service)                           │
│    - 视频切片为 .m3u8 + .ts 文件                          │
│    - 生成 HLS 播放列表                                    │
│    - 输出: playlist.m3u8 + segment_*.ts                   │
│    - SSE 推送切片进度                                     │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ 8. 任务完成                                               │
│    - 更新任务状态为 completed                             │
│    - 返回 HLS 播放地址                                    │
│    - 清理临时文件                                         │
│    - SSE 推送完成消息                                     │
└──────────────────────────────────────────────────────────┘
```

### 3.2 核心 API 端点数据流

#### 3.2.1 数字人生成流式接口 (`POST /api/digital-human/generate/stream`)

**请求参数**：
```python
file: UploadFile                    # PPT 文件
digital_human_id: str               # 数字人 ID
template_id: Optional[str]          # 模板 ID（可选）
bgm_enabled: bool = False           # BGM 开关
emotion: str = "default"            # 情感参数
style: str = "normal"               # 口播文案风格
```

**处理流程**：
```
1. 参数验证和任务初始化
2. 建立 SSE 连接
3. 异步执行生成流程
   ├─ PPT 转换
   ├─ OCR 识别
   ├─ TTS 合成
   ├─ 数字人视频生成
   ├─ 视频合并
   └─ HLS 切片
4. 实时推送进度到 SSE
5. 返回最终结果
```

**SSE 推送格式**：
```text
event: progress
data: {"task_id": "xxx", "progress": 50, "message": "正在生成音频..."}

event: log
data: {"task_id": "xxx", "level": "info", "message": "OCR 识别完成"}

event: complete
data: {"task_id": "xxx", "status": "completed", "result": {...}}

event: error
data: {"task_id": "xxx", "error": "错误信息"}
```

#### 3.2.2 任务创建接口 (`POST /api/digital-human/generate/task`)

**请求参数**：
```python
file: UploadFile                    # PPT 文件
digital_human_id: str               # 数字人 ID
template_id: Optional[str]          # 模板 ID
bgm_enabled: bool = False           # BGM 开关
emotion: str = "default"            # 情感参数
style: str = "normal"               # 口播文案风格
```

**返回结果**：
```json
{
  "task_id": "uuid",
  "status": "pending",
  "status_url": "/api/digital-human/generate/task/{task_id}"
}
```

#### 3.2.3 获取任务状态接口 (`GET /api/digital-human/generate/task/{task_id}`)

**返回结果**：
```json
{
  "task_id": "uuid",
  "status": "processing",
  "progress": 50,
  "message": "正在生成音频...",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:05:00"
}
```

#### 3.2.4 上传数字人接口 (`POST /api/digital-human/upload`)

**请求参数**：
```python
file: UploadFile                    # 数字人文件（视频/图片）
name: str                           # 数字人名称
description: Optional[str]          # 描述
```

**处理流程**：
```
1. 文件类型验证（视频/图片）
2. 文件大小限制检查
3. 保存到 static/Digital_human/ 目录
4. 生成数字人 ID
5. 返回数字人信息
```

#### 3.2.5 数字人列表接口 (`GET /api/digital-human/list`)

**返回结果**：
```json
{
  "digital_humans": [
    {
      "id": "dh_001",
      "name": "数字人 A",
      "description": "描述",
      "file_path": "/path/to/file",
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

#### 3.2.6 视频合并接口 (`POST /api/video/merge`)

**请求参数**：
```python
video_paths: List[str]             # 视频文件路径列表
output_path: str                    # 输出路径
bgm_path: Optional[str]            # BGM 路径
bgm_volume: float = 0.2            # BGM 音量
```

**处理流程**：
```
1. 验证所有视频文件存在
2. 调用 FFmpeg 合并视频
3. 如果指定 BGM，调用 mix_bgm 函数
4. 返回合并后的视频路径
```

#### 3.2.7 HLS 切片接口 (`POST /api/video/hls`)

**请求参数**：
```python
video_path: str                     # 视频路径
output_dir: str                     # 输出目录
segment_duration: int = 10         # 每段时长（秒）
```

**返回结果**：
```json
{
  "playlist_url": "/path/to/playlist.m3u8",
  "segments": [
    "/path/to/segment_0.ts",
    "/path/to/segment_1.ts"
  ]
}
```

#### 3.2.8 SSE 监控接口 (`GET /api/sse/monitor/{task_id}`)

**处理流程**：
```
1. 建立 SSE 连接
2. 订阅任务进度更新
3. 实时推送进度和日志
4. 任务完成时关闭连接
```

#### 3.2.9 PPT 转换接口 (`POST /api/convert`)

**请求参数**：
```python
file: UploadFile                    # PPT/PDF 文件
format: str = "images"             # 输出格式（images/pdf）
```

**处理流程**：
```
1. 验证文件类型
2. 调用 conversion_service
3. 如果是 PPT，先转换为 PDF
4. 使用 pdftoppm 将 PDF 转为图像
5. 返回图像路径列表
```

#### 3.2.10 文件管理接口

**上传文件** (`POST /api/upload`):
```python
file: UploadFile                    # 任意文件
```

**文件列表** (`GET /api/files/list`):
```python
directory: Optional[str]           # 目录路径
```

**删除文件** (`DELETE /api/files/delete`):
```python
file_path: str                      # 文件路径
```

---

## 4. 服务层详解

### 4.1 转换服务 (conversion_service.py)

**核心功能**：将 PPT/PDF 文件转换为逐页图像

**处理流程**：
```python
async def convert_ppt_to_images(file_path: str, output_dir: str) -> List[str]:
    """
    将 PPT 文件转换为图像
    
    1. 如果是 PPT，使用 LibreOffice 转换为 PDF
    2. 使用 pdftoppm 将 PDF 转换为图像
    3. 返回图像路径列表
    """
    # 1. PPT → PDF（如果需要）
    if file_path.endswith(('.ppt', '.pptx')):
        pdf_path = await libreoffice_converter.convert_to_pdf(file_path)
    else:
        pdf_path = file_path
    
    # 2. PDF → 图像
    image_paths = await pdftoppm_convert(pdf_path, output_dir)
    
    return image_paths
```

### 4.2 视频合并服务 (video_merge_service.py)

**核心功能**：合并多个视频并添加 BGM

**mix_bgm 函数**：
```python
def mix_bgm(video_path: str, bgm_path: str, output_path: str, volume: float = 0.2) -> bool:
    """
    将 BGM 混合到视频中
    
    参数:
        video_path: 原视频路径
        bgm_path: BGM 路径
        output_path: 输出路径
        volume: BGM 音量 (0-1)
    
    处理:
        使用 FFmpeg 将 BGM 以指定音量混合到视频
    """
    cmd = [
        settings.ffmpeg_path,
        '-i', video_path,
        '-i', bgm_path,
        '-filter_complex', f'[1:a]volume={volume}[bgm];[0:a][bgm]amix',
        '-c:v', 'copy',
        output_path
    ]
    subprocess.run(cmd, check=True)
    return True
```

### 4.3 HLS 切片服务 (video_his_service.py)

**核心功能**：将视频切片为 HLS 格式

**SimpleHLSSlicer 类**：
```python
class SimpleHLSSlicer:
    def slice(self, video_path: str, output_dir: str, segment_duration: int = 10) -> str:
        """
        将视频切片为 HLS 格式
        
        参数:
            video_path: 视频路径
            output_dir: 输出目录
            segment_duration: 每段时长（秒）
        
        返回:
            playlist.m3u8 路径
        """
        playlist_path = os.path.join(output_dir, "playlist.m3u8")
        cmd = [
            settings.ffmpeg_path,
            '-i', video_path,
            '-c', 'copy',
            '-map', '0',
            '-f', 'hls',
            '-hls_time', str(segment_duration),
            '-hls_list_size', '0',
            playlist_path
        ]
        subprocess.run(cmd, check=True)
        return playlist_path
```

### 4.4 清理服务 (cleanup_service.py)

**核心功能**：定时清理临时文件和旧任务

**清理策略**：
```python
async def cleanup_old_files():
    """
    清理策略:
    1. 删除 24 小时前的临时文件
    2. 清理已完成的任务数据
    3. 监控磁盘空间，超过阈值时告警
    """
    cutoff_time = time.time() - 24 * 3600
    
    # 清理临时目录
    for root, dirs, files in os.walk(settings.temp_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.getmtime(file_path) < cutoff_time:
                os.remove(file_path)
    
    # 清理旧任务
    cleanup_old_tasks()
    
    # 检查磁盘空间
    check_disk_space()
```

### 4.5 任务调度服务 (scheduler_service.py)

**核心功能**：管理定时任务

**调度逻辑**：
```python
class SchedulerService:
    def __init__(self):
        self.tasks = {}
    
    def add_task(self, task_id: str, func: Callable, interval: int):
        """添加定时任务"""
        self.tasks[task_id] = {
            'func': func,
            'interval': interval,
            'running': False
        }
    
    def remove_task(self, task_id: str):
        """移除定时任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
    
    async def run_task(self, task_id: str):
        """执行定时任务"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task['running'] = True
            try:
                await task['func']()
            finally:
                task['running'] = False
```

### 4.6 文件服务 (file_service.py)

**核心功能**：文件存储、上传、下载管理

**主要方法**：
```python
class FileService:
    async def save_file(self, file: UploadFile, directory: str) -> str:
        """保存上传的文件"""
        file_path = os.path.join(directory, file.filename)
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        return file_path
    
    async def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    def list_files(self, directory: str) -> List[str]:
        """列出目录中的文件"""
        return os.listdir(directory)
```

---

## 5. 核心转换器

### 5.1 转换器基类 (converter.py)

**定义**：所有转换器的抽象基类

```python
class BaseConverter:
    def convert(self, input_path: str, output_path: str) -> bool:
        raise NotImplementedError
```

### 5.2 LibreOffice 转换器 (libreoffice_converter.py)

**核心功能**：使用 LibreOffice 将 PPT 转换为 PDF

**处理流程**：
```python
class LibreOfficeConverter:
    def convert_to_pdf(self, ppt_path: str, output_dir: str) -> str:
        """
        将 PPT 文件转换为 PDF
        
        1. 验证文件存在性
        2. 构建 LibreOffice 命令
        3. 执行转换
        4. 返回 PDF 路径
        """
        cmd = [
            settings.libreoffice_path,
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', output_dir,
            ppt_path
        ]
        subprocess.run(cmd, check=True)
        
        pdf_path = os.path.join(output_dir, os.path.basename(ppt_path).rsplit('.', 1)[0] + '.pdf')
        return pdf_path
```

---

## 6. 配置管理

### 6.1 全局配置 (config/settings.py)

**核心配置项**：
```python
class Settings:
    # 基础配置
    host: str = "0.0.0.0"
    port: int = 9088
    debug: bool = False
    
    # 路径配置
    base_dir: str = Path(__file__).parent.parent
    upload_dir: str = base_dir / "uploads"
    temp_dir: str = base_dir / "temp"
    output_dir: str = base_dir / "output"
    static_dir: str = base_dir / "static"
    
    # 数字人配置
    digital_human_dir: str = static_dir / "Digital_human"
    
    # FFmpeg 配置
    ffmpeg_path: str = "ffmpeg"
    
    # LibreOffice 配置
    libreoffice_path: str = "libreoffice"
    
    # 服务地址配置
    paddleocr_url: str = "http://127.0.0.1:8802"
    tts_url: str = "http://127.0.0.1:6006"  # 示例；实际业务中 TTS 地址见 my_digital_human.py 等写死 URL
    wav2lip_url: str = "http://127.0.0.1:5000"
    
    # 上传限制
    max_upload_size: int = 100 * 1024 * 1024  # 100MB
    
    # 清理配置
    cleanup_interval: int = 3600  # 清理间隔（秒）
    disk_space_threshold: float = 0.9  # 磁盘空间阈值
    
    # HLS 配置
    hls_segment_duration: int = 10  # HLS 每段时长（秒）
    
    @property
    def paddleocr_parse_url(self) -> str:
        return f"{self.paddleocr_url}/parse"
    
    @property
    def tts_infer_url(self) -> str:
        return f"{self.tts_url}/v2/infer"
    
    @property
    def wav2lip_generate_url(self) -> str:
        return f"{self.wav2lip_url}/generate/upload"
```

---

## 7. 部署与配置

### 7.1 启动命令

**启动服务**：
```bash
cd /home/ubuntu/workspace/PPTTalK/digital_human_interface
uvicorn main:app --host 0.0.0.0 --port 9088 --reload
```

**使用启动脚本**：
```bash
# 启动所有服务
start_all.sh start

# 停止所有服务
start_all.sh stop

# 查看服务状态
start_all.sh status
```

### 7.2 环境变量

```bash
# .env 文件（可选）
HOST=0.0.0.0
PORT=9088
DEBUG=false

PADDLEOCR_URL=http://127.0.0.1:8802
TTS_URL=http://127.0.0.1:6006
WAV2LIP_URL=http://127.0.0.1:5000

FFMPEG_PATH=ffmpeg
LIBREOFFICE_PATH=libreoffice

MAX_UPLOAD_SIZE=104857600
CLEANUP_INTERVAL=3600
DISK_SPACE_THRESHOLD=0.9
```

---

## 8. SSE 实时监控

### 8.1 SSE 推送机制

**连接建立**：
```python
@app.get("/api/sse/monitor/{task_id}")
async def sse_monitor(task_id: str):
    async def event_stream():
        # 订阅任务更新
        while True:
            task = tasks.get(task_id)
            if not task:
                yield f"event: error\ndata: {{'error': '任务不存在'}}\n\n"
                break
            
            yield f"event: progress\ndata: {{'task_id': '{task_id}', 'progress': {task.progress}, 'message': '{task.message}'}}\n\n"
            
            if task.status in ['completed', 'failed']:
                yield f"event: complete\ndata: {{'task_id': '{task_id}', 'status': '{task.status}'}}\n\n"
                break
            
            await asyncio.sleep(1)
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### 8.2 推送事件类型

| 事件类型 | 描述 | 数据格式 |
|---------|------|---------|
| **progress** | 进度更新 | `{"task_id": "xxx", "progress": 50, "message": "..."}` |
| **log** | 日志信息 | `{"task_id": "xxx", "level": "info", "message": "..."}` |
| **complete** | 任务完成 | `{"task_id": "xxx", "status": "completed", "result": {...}}` |
| **error** | 错误信息 | `{"task_id": "xxx", "error": "..."}` |

---

## 9. 性能优化

### 9.1 异步处理

- 所有 I/O 操作使用异步处理
- 使用 BackgroundTasks 管理后台任务
- 线程池执行耗时操作

### 9.2 资源管理

- 临时文件自动清理
- 磁盘空间监控
- 连接池管理

### 9.3 缓存策略

- 任务状态缓存
- 配置信息缓存
- 数字人列表缓存

---

## 10. 常见问题与排查

### 10.1 启动问题

#### 问题 1：服务无法启动
```
Error: Address already in use
```
**解决方案**：
```bash
# 检查端口占用
lsof -i :9088
# 杀死占用进程
kill -9 <PID>
```

#### 问题 2：依赖服务未启动
```
ConnectionError: Could not connect to paddleocr service
```
**解决方案**：
- 确保 PaddleOCR、IndexTTS、Wav2Lip 服务已启动
- 检查服务端口是否正确

### 10.2 处理问题

#### 问题 1：PPT 转换失败
**可能原因**：
- LibreOffice 未安装
- PPT 文件损坏
- 权限不足

**解决方案**：
```bash
apt update && apt install -y libreoffice
```

#### 问题 2：视频合并失败
**可能原因**：
- FFmpeg 未安装
- 视频格式不兼容
- 磁盘空间不足

**解决方案**：
```bash
apt update && apt install -y ffmpeg
```

### 10.3 性能问题

#### 问题 1：处理速度慢
**可能原因**：
- 依赖服务响应慢
- 网络延迟
- CPU 资源不足

**解决方案**：
- 检查各子服务状态
- 优化网络配置
- 增加 CPU 资源

---

## 11. 集成与调用

### 11.1 前端调用示例

```typescript
// 生成视频
async function generateVideo(file: File, digitalHumanId: string) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('digital_human_id', digitalHumanId);
  formData.append('bgm_enabled', 'false');
  formData.append('emotion', 'default');
  formData.append('style', 'normal');

  const response = await fetch('/api/digital-human/generate/stream', {
    method: 'POST',
    body: formData
  });

  // 处理 SSE
  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    // 解析 SSE 事件
    const events = parseSSEEvents(text);
    for (const event of events) {
      handleSSEEvent(event);
    }
  }
}
```

### 11.2 Python 调用示例

```python
import httpx
import asyncio

async def generate_video(file_path: str, digital_human_id: str):
    async with httpx.AsyncClient(timeout=300.0) as client:
        with open(file_path, 'rb') as f:
            files = {'file': ('ppt.pptx', f, 'application/vnd.openxmlformats-officedocument.presentationml.presentation')}
            data = {
                'digital_human_id': digital_human_id,
                'bgm_enabled': 'false',
                'emotion': 'default',
                'style': 'normal'
            }
            
            resp = await client.post(
                'http://127.0.0.1:9088/api/digital-human/generate/task',
                files=files,
                data=data
            )
            
            if resp.status_code == 202:
                task_id = resp.json()['task_id']
                # 轮询任务状态
                while True:
                    status_resp = await client.get(f'http://127.0.0.1:9088/api/digital-human/generate/task/{task_id}')
                    status_data = status_resp.json()
                    
                    if status_data['status'] == 'completed':
                        return status_data['result']
                    elif status_data['status'] == 'failed':
                        raise Exception(f"视频生成失败: {status_data.get('error')}")
                    
                    await asyncio.sleep(5)
```

### 11.3 完整数据链路

```
PPT 文件
  ↓
[digital_human_interface] → 接收请求，创建任务
  ↓
[LibreOffice] → PDF
  ↓
[pdftoppm] → 逐页图像
  ↓
[PaddleOCR-VL] → Markdown + 口播文案
  ↓
[IndexTTS-vLLM] → 音频文件
  ↓
[Wav2Lip] → 数字人视频
  ↓
[video_merge_service] → 合并视频 + BGM
  ↓
[video_his_service] → HLS 切片
  ↓
返回 HLS 播放地址
```

---

## 12. 总结

### 12.1 核心优势
1. **统一接口**：提供统一的 API 接口，简化前端调用
2. **异步处理**：所有耗时操作异步执行，不阻塞请求
3. **实时监控**：SSE 实时推送处理进度，提升用户体验
4. **任务管理**：完整的任务生命周期管理
5. **视频后处理**：支持视频合并、BGM 混音、HLS 切片
6. **文件管理**：完善的文件上传、下载、清理机制
7. **多服务协调**：统一调度和协调多个子服务
8. **GPU 监控**：实时监控 GPU 使用状态
9. **模板系统**：支持自定义数字人模板
10. **高可用性**：完善的错误处理和重试机制

### 12.2 技术亮点
1. **FastAPI 框架**：高性能异步 API 框架
2. **SSE 推送**：实时进度和日志推送
3. **FFmpeg 集成**：专业视频处理
4. **LibreOffice 转换**：PPT 转 PDF
5. **异步任务调度**：BackgroundTasks + 线程池
6. **磁盘监控**：自动清理和告警
7. **HLS 切片**：流媒体播放支持
8. **BGM 混音**：背景音乐混合
9. **配置管理**：灵活的环境变量支持
10. **日志系统**：完善的日志记录

### 12.3 应用场景
- **教育领域**：课件视频自动生成
- **企业培训**：培训视频批量生成
- **在线教育**：课程视频制作
- **知识分享**：技术分享视频
- **营销宣传**：产品演示视频

---

**文档版本**: v2.0  
**更新日期**: 2026-04-17  
**维护者**: AI 数字人项目组
