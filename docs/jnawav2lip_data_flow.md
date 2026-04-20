# Wav2Lip 唇形同步与视频生成数据业务流程

## 1. 模块概述

### 1.1 模块定位
Wav2Lip 模块是 AI 数字人 PPT 视频生成系统中的**数字人视频合成核心组件**，负责将音频文件与面部视频进行唇形同步，并生成最终的数字人视频。该模块基于 Wav2Lip 算法，实现了从音频到唇形同步视频的完整转换流程。

### 1.2 技术特点
- **唇形同步**：基于 Wav2Lip 算法实现高精度唇形同步
- **模型预加载**：服务启动时预加载 Wav2Lip 模型 + 人脸检测器 + Whisper 模型，消除冷启动延迟
- **人像分割**：支持绿幕背景和通用人像分割（MediaPipe）；软边缘 mask（形态学清理 + 渐变阈值 + 大核高斯模糊）替代硬二值化，消除锯齿
- **视频合成**：支持数字人与背景视频的叠加
- **音效系统**：集成背景音乐（BGM）、转场音效和完成提示音
- **字幕生成**：基于 Whisper 模型的自动字幕生成；带降级重试（large-v3 → medium → small → base → tiny）与卡拉OK风格回退，确保字幕始终产出
- **并行处理**：多任务并行执行（背景视频 + Wav2Lip + 字幕），提升生成速度
- **显存管理**：每批次推理后显式释放 GPU tensor；任务结束调用 `clear_video_cache()` 清空帧缓存并触发 `torch.cuda.empty_cache()` + `gc.collect()`，防止多任务后显存堆积
- **面部增强**：Wav2Lip 96×96 上采样后通过 Unsharp Mask 锐化（`_sharpen_face`）+ 椭圆羽化融合消除矩形硬边，零显存开销
- **高质量编码**：所有 `libx264` 步骤统一 `-crf 18 -preset medium`，减少多次重编码画质损失
- **无数字人模式**：`face_video` 为可选参数，不传时仅生成背景视频 + 音频 + 字幕
- **BGM 参数透传**：支持 `bgm_enabled`、`bgm_path` 表单参数
- **线程安全**：所有 `os.chdir()` 已移除，使用 `subprocess.run(cwd=...)` 替代
- **任务管理**：完整的任务状态跟踪和文件清理机制

### 1.3 服务信息
| 项目 | 值 |
|------|-----|
| **入口文件** | `wav2lip_workspce/lx/测试/main.py` |
| **服务端口** | 5000 |
| **框架** | FastAPI + OpenCV + FFmpeg |
| **核心算法** | Wav2Lip + MediaPipe + Whisper |
| **依赖服务** | FFmpeg, Whisper, MediaPipe |
| **调用地址** | `http://127.0.0.1:5000`（服务间调用） |

---

## 2. 系统架构

### 2.1 整体架构图
```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │digital_human│  │  Web UI      │  │  第三方调用  │           │
│  │_interface   │  │  (FastAPI)   │  │  (API)       │           │
│  └─────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              ↓ HTTP POST
┌─────────────────────────────────────────────────────────────────┐
│                     API 服务层 (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  main.py (Port 5000)                                   │  │
│  │  - / (API 信息)                                        │  │
│  │  - /generate (文件路径)                                 │  │
│  │  - /generate/upload (文件上传, multipart)               │  │
│  │  - /upload (文件上传)                                   │  │
│  │  - /status/{task_id} (任务状态)                         │  │
│  │  - /download/{task_id} (视频下载)                      │  │
│  │  - /video_path/{task_id} (获取路径)                    │  │
│  │  - /open_folder/{task_id} (打开文件夹)                 │  │
│  │  - /cleanup (清理旧任务)                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     业务服务层 (Services)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │视频生成服务  │  │音频处理服务  │  │字幕生成服务  │             │
│  │(VideoGenerator)│  │(AudioProcessor)│  │(SubtitleService)│  │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │文件服务     │  │Wav2Lip模型  │  │              │             │
│  │(FileService)│  │(wav2lip_model)│  │              │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     核心算法层 (Algorithms)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │Wav2Lip      │  │MediaPipe    │  │Whisper      │             │
│  │(唇形同步)   │  │(人像分割)   │  │(语音识别)   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        输出层                                    │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │MP4 文件     │  │  临时存储    │  │  文件管理    │           │
│  │(数字人视频)  │  │  (temp_files/)│  │  (清理策略)  │           │
│  └─────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心目录结构
```
wav2lip_workspce/
├── lx/                                # 项目根目录
│   ├── 测试/                            # 简体中文数字人项目（主用）
│   │   ├── main.py                     # FastAPI 入口（93 行，含模型预加载）
│   │   ├── config.py                   # 配置管理（54 行，支持 .env）
│   │   ├── models.py                   # 数据模型（Pydantic）
│   │   ├── api/
│   │   │   └── routes.py               # API 路由（461 行）
│   │   ├── services/
│   │   │   ├── video_generator.py      # 视频生成服务（703 行）
│   │   │   ├── audio_processor.py      # 音频处理服务
│   │   │   ├── subtitle_service.py     # 字幕生成服务
│   │   │   ├── file_service.py         # 文件管理服务
│   │   │   └── wav2lip_model.py        # Wav2Lip 模型封装
│   │   ├── output/                      # 输出目录
│   │   ├── uploaded_files/              # 上传文件目录
│   │   ├── temp_files/                  # 临时文件目录
│   │   └── assets/sfx/                  # 音效文件目录（完成提示音、转场音效、商务BGM）
│   └── digital_human_project/          # 类似结构的数字人项目（备用）
└── Wav2Lip/                             # 官方 Wav2Lip 代码库
    ├── inference.py                    # 推理脚本
    ├── models/
    │   ├── wav2lip.py                 # Wav2Lip 模型
    │   └── syncnet.py                 # 同步网络
    ├── face_detection/                # 面部检测模块
    └── checkpoints/                   # 预训练模型
        └── Wav2Lip-SD-GAN.pt          # Wav2Lip 模型权重
```

---

## 3. 数据业务流程详解

### 3.1 整体数据流
```
用户请求
  ↓
┌──────────────────────────────────────────────┐
│  1. API 接收请求 (FastAPI)                    │
│     - 背景图片                                │
│     - 人脸视频（可选）                         │
│     - 音频文件                                │
│     - 配置参数 (位置、大小、动画等)             │
│     - BGM 配置 (bgm_enabled, bgm_path)        │
│     - 欢迎文本 (welcome_text)                 │
└──────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────┐
│  2. 任务创建与状态初始化                          │
│     - 生成 task_id (UUID)                      │
│     - 初始化任务状态为 pending                   │
│     - 启动后台任务线程                           │
└──────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────┐
│  3. 并行处理阶段（有 face_video 时）             │
│     - 生成背景视频 (FFmpeg)                      │
│     - Wav2Lip 唇形同步 (Pytorch)                 │
│     - 字幕生成 (Whisper)                         │
└──────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────┐
│  3. 并行处理阶段（无 face_video 时）             │
│     - 生成背景视频 (FFmpeg)                      │
│     - 字幕生成 (Whisper)                         │
│     - Wav2Lip 任务标记为成功（跳过）               │
└──────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────┐
│  4. 串行处理阶段                                │
│     - 调整数字人大小（无数字人时跳过）              │
│     - 人像分割 MediaPipe（无数字人时跳过）          │
│     - 叠加数字人到背景（无数字人时跳过）             │
│     - 添加音频                                   │
│     - 添加字幕                                   │
│     - 添加音效系统（BGM + 转场 + 提示音）          │
└──────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────┐
│  5. 任务完成与清理                                │
│     - 更新任务状态为 completed                    │
│     - 保存输出路径                               │
│     - 清理临时文件                               │
│     - 调用 _release_gpu_memory()（清空帧缓存+CUDA缓存）│
│     - 显示完成通知                               │
└──────────────────────────────────────────────┘
  ↓
返回视频下载链接/文件路径
```

### 3.2 核心 API 端点数据流

#### 3.2.1 生成视频接口 (`POST /generate`)

**请求参数**：
```python
background_image: str     # 背景图片路径
face_video: str           # 人脸视频路径（必填）
audio_path: str           # 音频文件路径
output_name: str          # 输出文件名
position: str             # 数字人位置 (center, top-left, bottom-right 等)
size: float               # 数字人大小比例 (0-1)
animation: str            # 动画效果 (fly_in, fade_in)
animation_duration: float  # 动画持续时间 (秒)
welcome_text: str         # 欢迎文本
topic_name: str           # 主题名称
generate_subtitles: bool  # 是否生成字幕
sound_effects: object     # 音效配置
```

**处理流程**：
```
1. 参数验证
   ├─ 校验文件路径存在性
   ├─ 校验音效配置（若无则使用默认值）
   └─ 生成任务 ID

2. 任务初始化
   ├─ 创建任务记录
   ├─ 状态设为 pending
   └─ 启动后台任务

3. 并行处理
   ├─ 生成背景视频
   │   ├─ 调整图片大小
   │   ├─ 添加文字动画（welcome_text + topic_name）
   │   └─ 生成指定时长视频
   ├─ Wav2Lip 唇形同步
   │   ├─ 模型推理（支持预加载模型或 subprocess 模式）
   │   └─ 生成唇形同步视频
   └─ 生成字幕
       ├─ 调用 Whisper 语音识别
       └─ 生成 ASS 格式字幕

4. 串行处理
   ├─ 调整数字人大小
   ├─ 人像分割（MediaPipe 通用人像分割，失败则回退绿幕方案）
   ├─ 叠加数字人到背景
   ├─ 添加音频
   ├─ 添加字幕
   └─ 添加音效系统

5. 任务完成
   ├─ 状态设为 completed
   ├─ 保存输出路径
   ├─ 清理临时文件
   └─ 返回结果
```

**返回结果**：
```json
{
  "message": "视频生成任务已开始",
  "task_id": "uuid",
  "status_url": "/status/{task_id}",
  "download_url": "/download/{task_id}",
  "video_path_url": "/video_path/{task_id}",
  "open_folder_url": "/open_folder/{task_id}",
  "output_directory": "/path/to/output"
}
```

#### 3.2.2 文件上传接口 (`POST /generate/upload`)

**请求参数**（multipart/form-data）：
```python
background_image: UploadFile         # 背景图片（必填）
face_video: Optional[UploadFile]     # 人脸视频（可选，不传则无数字人模式）
audio_path: UploadFile               # 音频文件（必填）
output_name: str = "my_presentation"
position: str = "bottom-left"
size: float = 0.3
animation: str = "fly_in"
animation_duration: float = 6.0
welcome_text: str = "欢迎来到云南水利水电职业技术学院"
topic_name: str = "AI 知识讲堂"
generate_subtitles: bool = True
bgm_enabled: str = "true"           # 背景音乐开关
bgm_path: Optional[str] = None      # 自定义背景音乐路径
```

**处理流程**：
```
1. 文件类型验证
   ├─ 图片: jpeg, png, jpg
   ├─ 视频: mp4, avi, mov（face_video 可选）
   └─ 音频: mpeg, wav, mp3

2. 文件保存
   ├─ 保存到临时目录 (tempfile.mkdtemp)
   └─ 生成 UUID 文件名

3. 参数组装
   ├─ 组装 settings 字典
   ├─ 配置音效系统（默认启用）
   ├─ 设置 BGM 参数（bgm_enabled + bgm_path）
   └─ 生成 task_id

4. 启动后台任务
   ├─ 执行 generate_video
   └─ finally 块清理临时目录

5. 返回结果
   └─ 提供任务 ID 和状态查询 URL
```

**返回结果**：
```json
{
  "message": "视频生成任务已开始（文件上传模式）",
  "task_id": "uuid",
  "status_url": "/status/{task_id}",
  "download_url": "/download/{task_id}",
  "video_path_url": "/video_path/{task_id}",
  "open_folder_url": "/open_folder/{task_id}",
  "output_directory": "/path/to/output"
}
```

#### 3.2.3 文件上传接口 (`POST /upload`)

**请求参数**：
```python
file: UploadFile  # 支持图片、视频、音频文件
```

**处理流程**：
```
1. 文件类型验证
   ├─ 图片: jpeg, png, jpg, gif
   ├─ 视频: mp4, avi, mov, mkv
   └─ 音频: mpeg, wav, mp3, m4a

2. 文件保存
   ├─ 生成唯一文件 ID
   ├─ 保存到 uploaded_files/ 目录
   └─ 记录文件信息

3. 返回结果
   └─ 文件 ID、路径、大小等信息
```

#### 3.2.4 任务状态查询接口 (`GET /status/{task_id}`)

**处理流程**：
```
1. 任务存在性检查
2. 获取任务状态
3. 构建响应数据
   ├─ 状态信息 (pending/processing/completed/failed)
   ├─ 进度信息
   ├─ 时间信息
   ├─ 错误信息（如果有）
   └─ 输出路径（如果完成）
4. 返回状态码
   ├─ 200: 完成
   ├─ 202: 处理中
   └─ 500: 失败
```

---

## 4. 视频生成核心流程

### 4.1 模型预加载

**核心代码**：`main.py` 中的 `_preload_wav2lip()` 和 `_preload_whisper()`

```python
def _preload_wav2lip():
    """启动时预加载 Wav2Lip 模型 + 人脸检测器，消除推理时的冷启动开销"""
    try:
        from services import wav2lip_model
        wav2lip_model.init(config.wav2lip_dir, config.wav2lip_checkpoint)
        wav2lip_model.load()
        print("Wav2Lip model + face detector preloaded successfully")
    except Exception as e:
        print(f"Wav2Lip preload failed (will use subprocess fallback): {e}")

def _preload_whisper():
    """启动时预加载 Whisper 模型，避免首个视频字幕生成时的冷启动"""
    try:
        from api.routes import generator
        if generator.subtitle_service.load_whisper_model("large-v3"):
            print("Whisper model preloaded successfully")
    except Exception as e:
        print(f"Whisper preload failed (will load on first use): {e}")
```

### 4.2 并行处理阶段

**核心代码**：`VideoGenerator._process_parallel()`

```python
def _process_parallel(self, settings, temp_dir, task_id):
    """并行处理视频生成的各个阶段"""
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        
        # 并行任务1：生成背景视频
        futures['bg'] = executor.submit(
            self.create_background_video,
            settings['background_image'],
            self.audio_processor.get_audio_duration(settings['audio_path']),
            os.path.join(temp_dir, "background.mp4"),
            settings['welcome_text'],
            settings['topic_name'],
            settings['animation'],
            settings.get('animation_duration', 6.0)
        )
        
        # 并行任务2：生成数字人视频（如果有 face_video）
        if settings.get('face_video'):
            dh_raw = os.path.join(temp_dir, "digital_human_raw.mp4")
            futures['wav2lip'] = executor.submit(
                self.run_wav2lip,
                settings['face_video'],
                settings['audio_path'],
                dh_raw
            )
        else:
            # 无数字人模式：标记为成功，后续跳过数字人相关处理
            futures['wav2lip'] = executor.submit(lambda: True)
        
        # 并行任务3：生成字幕
        subtitle_path = os.path.join(temp_dir, "blue_karaoke_subtitles.ass")
        if settings['generate_subtitles']:
            futures['subtitle'] = executor.submit(
                self.subtitle_service.create_karaoke_subtitles_from_audio,
                settings['audio_path'],
                subtitle_path
            )
        
        # 等待所有并行任务完成
        results = {}
        for name, future in futures.items():
            try:
                results[name] = future.result(timeout=300)
                tasks[task_id]['progress'] = f'{name}任务完成'
            except Exception as e:
                print(f"❌ 并行任务 {name} 失败: {e}")
                results[name] = None
        
        return results, dh_raw, subtitle_path
```

**并行任务详情**：

1. **背景视频生成**
   - 输入：背景图片、音频时长、欢迎文本、主题名称
   - 处理：调整图片大小、添加文字动画、生成指定时长视频
   - 输出：`background.mp4`

2. **Wav2Lip 唇形同步**
   - 输入：人脸视频、音频文件
   - 处理：调用 Wav2Lip 模型推理（支持预加载模型或 subprocess 模式）
   - 输出：`digital_human_raw.mp4`
   - 无数字人模式：跳过推理，直接返回 True

3. **字幕生成**
   - 输入：音频文件
   - 处理：调用 Whisper 语音识别
   - 输出：`blue_karaoke_subtitles.ass`

### 4.3 串行处理阶段

**核心代码**：`VideoGenerator.generate_video()`

```python
def generate_video(self, settings: Dict[str, Any], task_id: str):
    """生成视频的主要逻辑（并行版本）"""
    tasks[task_id]['status'] = 'processing'
    tasks[task_id]['start_time'] = datetime.now().isoformat()
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 1. 并行处理多个任务
        tasks[task_id]['progress'] = '并行处理中...'
        parallel_results, dh_raw, subtitle_path = self._process_parallel(settings, temp_dir, task_id)
        
        if not parallel_results.get('wav2lip', False):
            raise Exception("数字人生成失败")
        
        # 2. 无数字人模式：直接跳过以下处理
        if settings.get('face_video'):
            tasks[task_id]['progress'] = '调整数字人大小...'
            dh_resized = os.path.join(temp_dir, "digital_human_resized.mp4")
            self.resize_digital_human(dh_raw, dh_resized, settings['size'])
            
            tasks[task_id]['progress'] = '绿幕抠图处理...'
            # 通用抠像：生成 mask（白=人像），overlay 时按 mask 透明叠加到PPT背景上
            dh_mask = os.path.join(temp_dir, "digital_human_mask.mp4")
            mask_ok = self.create_person_mask_video(
                input_video=dh_resized,
                output_mask_video=dh_mask,
                model_selection=1,
                threshold=0.5,
                blur_ksize=11
            )
            
            # 3. 叠加数字人
            tasks[task_id]['progress'] = '叠加数字人...'
            video_with_dh = os.path.join(temp_dir, "with_dh.mp4")
            success = self.overlay_digital_human(
                os.path.join(temp_dir, "background.mp4"),
                dh_resized,
                video_with_dh,
                settings['position'],
                digital_human_mask_video=dh_mask
            )
            video_with_audio = os.path.join(temp_dir, "with_audio.mp4")
            self.add_audio_to_video(video_with_dh, settings['audio_path'], video_with_audio)
        else:
            # 无数字人模式：直接使用背景视频 + 音频
            video_with_audio = os.path.join(temp_dir, "with_audio.mp4")
            self.add_audio_to_video(
                os.path.join(temp_dir, "background.mp4"),
                settings['audio_path'],
                video_with_audio
            )
        
        # 4. 添加字幕
        final_output = os.path.join(self.output_dir, f"{settings['output_name']}_{task_id}.mp4")
        if subtitle_path and os.path.exists(subtitle_path):
            tasks[task_id]['progress'] = '添加字幕...'
            self.add_ass_subtitles_to_video(video_with_audio, subtitle_path, final_output)
        else:
            shutil.copy2(video_with_audio, final_output)
        
        # 5. 添加音效系统（BGM + 转场 + 完成提示音）
        sound_effects_config = settings.get('sound_effects', {})
        if sound_effects_config.get('enabled', False):
            tasks[task_id]['progress'] = '添加音效系统...'
            self.add_sound_effects(final_output, sound_effects_config)
        
        # 6. 完成处理
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['output_path'] = final_output
        
        return final_output
        
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
        return None
```

**串行任务详情**：

1. **调整数字人大小**（无数字人时跳过）
   - 输入：原始数字人视频、大小比例
   - 处理：按比例调整视频大小
   - 输出：`digital_human_resized.mp4`

2. **人像分割**（无数字人时跳过）
   - 输入：调整大小后的数字人视频
   - 处理：
     - 优先：MediaPipe 通用人像分割生成 mask
     - 兜底：绿幕抠图
   - 输出：`digital_human_mask.mp4`

3. **叠加数字人**（无数字人时跳过）
   - 输入：背景视频、数字人视频、mask 视频
   - 处理：根据位置参数叠加数字人
   - 输出：`with_dh.mp4`

4. **添加音频**
   - 输入：带数字人的视频（或背景视频）、音频文件
   - 处理：将音频与视频合成
   - 输出：`with_audio.mp4`

5. **添加字幕**
   - 输入：带音频的视频、字幕文件
   - 处理：将 ASS 字幕添加到视频
   - 输出：`final_output.mp4`

6. **添加音效系统**
   - 输入：最终视频、音效配置
   - 处理：添加背景音乐、转场音效、完成提示音
   - 输出：最终视频文件

### 4.4 Wav2Lip 模型推理

**核心代码**：`services/wav2lip_model.py` 和 `VideoGenerator.run_wav2lip()`

```python
def run_wav2lip(self, face_video: str, audio: str, output: str) -> bool:
    """Wav2Lip 模型推理（支持预加载模型或 subprocess 模式）"""
    # 使用预加载模型推理（如果可用）
    # 或使用 subprocess 调用官方 inference.py
    # 注意：不再使用 os.chdir()，而是通过 sys.path 和 subprocess.run(cwd=...) 指定工作目录
    ...
```

**显存管理（2026-04-20 更新）**：

| 位置 | 操作 | 说明 |
|------|------|------|
| `_process_batch` 结束 | `del img_t, mel_t` | 每批次推理后立即释放 GPU tensor，防止单任务内缓存累积 |
| `_process_batch` 贴回 | `_sharpen_face()` + 椭圆羽化融合 | Unsharp Mask 锐化 + 高斯椭圆 alpha 加权融合，纯 CPU/numpy 操作，零显存 |
| `infer()` 正常结束 | `torch.cuda.empty_cache()` | 推理完成后释放 CUDA 碎片缓存 |
| `infer()` 异常退出 | `torch.cuda.empty_cache()` | OOM 等异常时也确保清理，防止后续任务受影响 |
| `_face_detect_cached` OOM 降 batch | `torch.cuda.empty_cache()` | 降批次前主动清缓存，提高降级成功率 |
| `clear_video_cache()` | 清空帧字典 + `empty_cache()` + `gc.collect()` | 任务结束后由 `VideoGenerator._release_gpu_memory()` 统一调用 |

**`clear_video_cache` 函数**（新增）：
```python
def clear_video_cache():
    """清除视频帧缓存以释放内存"""
    with _video_cache_lock:
        _video_cache.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    import gc
    gc.collect()
    print("[Wav2Lip] Video cache cleared & CUDA cache released")
```

### 4.5 人像分割流程

**核心代码**：`VideoGenerator.create_person_mask_video()`

```python
def create_person_mask_video(
    self,
    input_video: str,
    output_mask_video: str,
    model_selection: int = 1,
    threshold: float = 0.6,   # 2026-04-21: 从 0.5 提高到 0.6
    blur_ksize: int = 21      # 2026-04-21: 从 11 增大到 21
) -> bool:
    """通用人像分割：生成软边缘 mask 视频"""
    # ... MediaPipe SelfieSegmentation 逐帧处理 ...
    if res.segmentation_mask is not None:
        m = (res.segmentation_mask * 255.0).clip(0, 255).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)  # 填补空洞
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)    # 去噪点
        m = cv2.GaussianBlur(m, (blur_ksize, blur_ksize), 0)
        mask = np.where(m > int(threshold * 255), m, 0).astype(np.uint8)  # 软阈值
```

**分割流程（2026-04-21 优化）**：
1. 加载 MediaPipe Selfie Segmentation 模型
2. 逐帧处理视频
3. 对每一帧进行人像分割，获取 0-1 连续概率图
4. 形态学清理：`MORPH_CLOSE` 填补空洞、`MORPH_OPEN` 去噪点
5. 大核高斯模糊（21×21）平滑边缘
6. **软阈值**：保留高于阈值部分的原始渐变值（0-255），而非硬二值化（仅 0/255），实现自然过渡
7. 输出 mask 视频

---

## 5. 音效处理系统

### 5.1 音效配置结构

**默认配置**（来自 `config.py`）：
```python
# 音效文件目录
self.sfx_dir = os.path.join(_base, "assets", "sfx")
self.default_notification_sound = os.path.join(self.sfx_dir, "完成提示音.wav")
self.default_transition_sound = os.path.join(self.sfx_dir, "转场音效.wav")
self.default_bgm = os.path.join(self.sfx_dir, "商务背景音乐.mp3")
```

**配置示例**：
```json
{
  "enabled": true,
  "final_notification": {
    "enabled": true,
    "sound_file": "/path/to/完成提示音.wav",
    "start_before_end": 2.0,
    "volume": -5,
    "fade_duration": 0.3
  },
  "transition_sounds": {
    "enabled": true,
    "sound_file": "/path/to/转场音效.wav",
    "volume": -3
  },
  "background_music": {
    "enabled": true,
    "music_file": "/path/to/商务背景音乐.mp3",
    "volume_ratio": 0.2,
    "style": "corporate"
  }
}
```

### 5.2 BGM 参数透传

**`POST /generate/upload` 接口**：
- `bgm_enabled: str = Form("true")` — 背景音乐开关（"true"/"false"）
- `bgm_path: Optional[str] = Form(None)` — 自定义背景音乐路径

**处理逻辑**：
```python
'background_music': {
    'enabled': bgm_enabled.lower() != "false",
    'music_file': bgm_path if bgm_path else config.default_bgm,
    'volume_ratio': 0.2,
    'style': 'corporate'
}
```

---

## 6. 字幕生成系统

### 6.1 字幕生成流程

**核心功能**：基于 Whisper 模型的语音识别和字幕生成

**处理流程**：
1. 调用 Whisper 模型识别音频
2. 生成时间戳和文本
3. 转换为 ASS 格式字幕
4. 添加卡拉 OK 效果（可选）
5. 嵌入到视频中
6. 加载 Whisper 模型（带降级链，见 6.3）
7. 调用 Whisper 转录音频（支持 2 次重试，首次失败后降级模型再试）
8. 修复时间轴对齐（`_fix_timestamp_alignment`）
9. 智能分割过长字幕段（`_smart_split_long_segments`）
10. 生成卡拉OK风格 ASS 字幕（`\k` 标记 + `TVStyle`）
11. 嵌入到视频中
### 6.2 字幕样式
- 卡拉OK `\k` 标记：每字按时长分配发光进度
- 支持颜色和描边设置
- 智能长句分割：超过 30 字的句子按标点拆分为多段

### 6.3 Whisper 模型降级与容错（2026-04-20 更新）

**加载降级链**：
```
large-v3 → medium → small → base → tiny
```
每一级加载前先 `torch.cuda.empty_cache()`；若全链失败，进入卡拉OK回退。

**转录重试**：
- 最多重试 2 次
- 第 1 次 `RuntimeError`（通常是 OOM）后降级到 `small` 模型再重试
- 两次均失败则调用 `_generate_fallback_subtitle`

**卡拉OK回退字幕**（`_generate_fallback_subtitle`）：
- 用 `ffprobe` 获取音频时长
- 按动态字体大小生成同款 `TVStyle` + `\k` 标记 ASS 字幕
- 保证即使 Whisper 完全不可用，视频也有字幕输出（非空白）

**ASS 字幕特点**：
- 支持丰富的样式设置
- 支持卡拉 OK 效果
- 支持位置调整
- 支持颜色和字体设置

---

## 7. 部署与配置

### 7.1 配置文件 (`config.py`)

```python
class Config:
    def __init__(self):
        self.host_ip = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "5000"))
        self.base_url = f"http://{self.host_ip}:{self.port}"
        
        _base = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.dirname(os.path.dirname(os.path.dirname(_base)))

        self.output_dir = os.path.join(_base, "image_output")
        self.upload_dir = os.path.join(_base, "uploaded_files")
        self.temp_dir = os.path.join(_base, "temp_files")
        
        self.wav2lip_dir = os.getenv("WAV2LIP_DIR", os.path.join(_project_root, "Wav2Lip"))
        self.wav2lip_checkpoint = os.getenv("WAV2LIP_CHECKPOINT", os.path.join(self.wav2lip_dir, "models", "Wav2Lip-SD-GAN.pt"))

        self.sfx_dir = os.path.join(_base, "assets", "sfx")
        self.default_notification_sound = os.path.join(self.sfx_dir, "完成提示音.wav")
        self.default_transition_sound = os.path.join(self.sfx_dir, "转场音效.wav")
        self.default_bgm = os.path.join(self.sfx_dir, "商务背景音乐.mp3")

        self.sound_effects_dir = "sound_effects"
        
        self._create_dirs()
```

> **注意（2026-04-17 修复）**：`output_dir`、`upload_dir`、`temp_dir` 已改为基于 `__file__` 的绝对路径。此前使用相对路径时，若 `os.chdir()` 被调用（如 Wav2Lip 推理中），会导致目录解析到错误位置。同时 `wav2lip_model.py` 和 `video_generator.py` 中的 `os.chdir()` 调用已全部移除，改为 `subprocess.run(cwd=...)` 和 `sys.path` 操作，确保线程安全。

### 7.2 环境变量支持

```bash
# .env 文件（可选）
HOST=0.0.0.0
PORT=5000
WAV2LIP_DIR=/home/ubuntu/workspace/PPTTalK/Wav2Lip
WAV2LIP_CHECKPOINT=/home/ubuntu/workspace/PPTTalK/Wav2Lip/models/Wav2Lip-SD-GAN.pt
SFX_NOTIFICATION=/path/to/完成提示音.wav
SFX_TRANSITION=/path/to/转场音效.wav
SFX_BGM=/path/to/商务背景音乐.mp3
```

### 7.3 启动脚本

**启动命令**：
```bash
cd /home/ubuntu/workspace/PPTTalK/wav2lip_workspce/lx/测试
python main.py
```

**启动流程**：
1. 预加载 Wav2Lip 模型 + 人脸检测器
2. 预加载 Whisper 模型（large-v3）
3. 检查 FFmpeg 安装
4. 检查 Whisper 安装
5. 检查 OpenCC 安装（简繁转换）
6. 启动 FastAPI 服务
7. 显示服务信息和访问地址

---

## 8. 性能优化

### 8.1 模型预加载

**优化点**：
- 服务启动时预加载 Wav2Lip 模型 + 人脸检测器
- 服务启动时预加载 Whisper 模型（large-v3）
- 消除首个请求的冷启动延迟

**性能提升**：
- 传统冷启动：首次请求额外增加 30-60 秒模型加载时间
- 预加载模式：模型在服务启动时加载，首个请求即快速响应

### 8.2 并行处理

**优化点**：
- 使用 ThreadPoolExecutor 并行执行 3 个任务
- 背景视频生成、Wav2Lip 推理、字幕生成并行进行
- 减少总处理时间

**性能提升**：
- 传统串行：约 10-15 分钟
- 并行处理：约 5-8 分钟
- 提升约 40-50%

### 8.3 资源管理

**优化点**：
- 临时文件自动清理
- 任务完成后清理临时目录
- 24 小时自动清理旧任务
- **GPU 显存主动释放（2026-04-20）**：
  - `_process_batch` 每批推理后 `del img_t, mel_t`
  - `infer()` 正常/异常结束时 `torch.cuda.empty_cache()`
  - 每个视频任务结束后 `VideoGenerator._release_gpu_memory()` 清空帧缓存 + CUDA 缓存 + GC
  - 效果：多任务连续生成时显存维持稳定，不再单调增长
- **输出质量优化（2026-04-21）**：
  - 面部锐化（Unsharp Mask）+ 椭圆羽化融合：纯 CPU/numpy，零显存开销
  - 背景抠除软边缘 mask：形态学 + 渐变阈值，消除硬二值化锯齿
  - 统一 `-crf 18 -preset medium` 编码，提升全局清晰度
  - 初始方案 GFPGAN 逐帧调用因速度慢 10 倍 + 显存占用 11GB 被弃用

### 8.4 线程安全

**优化点**：
- 移除所有 `os.chdir()` 调用
- 使用 `subprocess.run(cwd=...)` 指定工作目录
- 使用 `sys.path.insert()` 动态添加模块路径
- 避免多线程环境下的路径冲突

---

## 9. 常见问题与排查

### 9.1 启动问题

#### 问题 1：FFmpeg 未安装
```
❌ 未找到 FFmpeg，请确保已安装
```
**解决方案**：
```bash
apt update && apt install -y ffmpeg
```

#### 问题 2：Wav2Lip 模型文件不存在
```
❌❌❌❌ Wav2Lip模型文件不存在
```
**解决方案**：
- 下载 Wav2Lip 预训练模型
- 确保 `config.wav2lip_checkpoint` 路径正确
- 可通过环境变量 `WAV2LIP_CHECKPOINT` 指定

#### 问题 3：MediaPipe 导入失败
```
❌ MediaPipe 导入失败，无法通用抠像: No module named 'mediapipe'
```
**解决方案**：
```bash
pip install mediapipe
```
> **注意**：Python 3.8 环境需使用兼容版本（如 0.10.9），否则可能出现导入或类型注解相关错误。

### 9.2 处理问题

#### 问题 1：唇形同步失败
**可能原因**：
- 音频文件格式不支持
- 人脸视频质量差
- Wav2Lip 模型加载失败

**解决方案**：
- 使用 WAV 或 MP3 格式音频
- 使用清晰的人脸视频
- 确保模型文件正确

#### 问题 2：人像分割失败
**可能原因**：
- MediaPipe 未安装
- 视频中人脸不清晰
- 光线条件差

**解决方案**：
- 安装 MediaPipe
- 使用光线良好的视频
- 确保人脸在画面中
- 失败时会回退到绿幕方案

#### 问题 3：字幕生成失败或无字幕（2026-04-20 新增）
**可能原因**：
- Whisper `large-v3` 模型与 Wav2Lip 并行时 GPU OOM
- Whisper 模型文件损坏或路径错误
- 音频格式不支持

**解决方案**：
- ≥ 2026-04-20 版本已内置**降级链**（large-v3 → medium → small → base → tiny）和 **2 次重试**，无需手动干预
- 若所有降级均失败，会自动生成**卡拉OK风格回退字幕**，视频仍有字幕
- 查看日志中 `⚠️ Whisper 转录第 N 次失败` 行了解具体降级过程

### 9.3 性能问题

#### 问题 1：处理速度慢
**可能原因**：
- CPU 性能不足
- GPU 未使用
- 模型未预加载

**解决方案**：
- 使用 GPU 加速
- 确保服务启动时模型预加载成功
- 优化视频分辨率

#### 问题 2：多任务后 GPU 显存持续堆积（2026-04-20 新增）
**现象**：
- 连续生成多个视频后 `nvidia-smi` 显示 Wav2Lip 进程显存不断增长

**可能原因（旧版本）**：
- `_process_batch` GPU tensor 未显式释放
- `infer()` 完成后未调 `torch.cuda.empty_cache()`
- `_video_cache` 存储的帧数组长期驻留内存

**解决方案**：
- ≥ 2026-04-20 版本已修复上述三处泄漏，确保使用最新代码重启服务
- 若问题仍存在，检查是否有其他进程（如 Whisper 或 MediaPipe）未释放显存
- 可手动调用 `wav2lip_model.clear_video_cache()` 强制清理

---

## 10. 集成与调用

### 10.1 与 digital_human_interface 集成

**调用流程**：
```
digital_human_interface (Port 9088)
  ↓
调用 Wav2Lip API (Port 5000)
  ├─ POST /generate/upload
  │   输入：multipart (背景图 + 音频 + 可选人脸视频)
  │   参数：position, size, animation, welcome_text, topic_name, bgm_enabled, bgm_path
  │   输出：任务 ID (202 Accepted)
  └─ GET /status/{task_id}
      输入：任务 ID
      输出：视频状态和下载链接
```

**集成代码示例**：
```python
import httpx
import asyncio

async def generate_digital_human_video(background_image_path, audio_path, face_video_path=None):
    """
    生成数字人视频（通过 digital_human_interface 调用）
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        files = {
            "background_image": ("img1.png", open(background_image_path, "rb"), "image/png"),
            "audio_path": ("1.wav", open(audio_path, "rb"), "audio/wav"),
        }
        if face_video_path:
            files["face_video"] = ("video_file.mp4", open(face_video_path, "rb"), "video/mp4")
        
        submit_data = {
            "position": "bottom-left",
            "topic_name": "AI 知识讲堂",
            "animation_duration": 6.0,
            "welcome_text": "欢迎来到云南水利水电职业技术学院",
            "bgm_enabled": "false",
        }
        
        resp = await client.post(
            "http://127.0.0.1:5000/generate/upload",
            files=files,
            data=submit_data
        )
        
        if resp.status_code == 202:
            task_id = resp.json()["task_id"]
            # 轮询任务状态
            while True:
                status_resp = await client.get(f"http://127.0.0.1:5000/status/{task_id}")
                status_data = status_resp.json()
                
                if status_data["status"] == "completed":
                    return status_data["output_path"]
                elif status_data["status"] == "failed":
                    raise Exception(f"视频生成失败: {status_data.get('error')}")
                
                await asyncio.sleep(5)
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
[IndexTTS-vLLM] → 音频文件 (每页)
  ↓
[Wav2Lip] → 数字人视频 (每页)  ← 本模块
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
1. **高精度唇形同步**：基于 Wav2Lip 算法，实现自然的唇形与音频同步
2. **模型预加载**：服务启动时预加载模型，消除冷启动延迟
3. **多模态融合**：支持背景图片、人脸视频、音频的有机结合
4. **智能人像分割**：支持绿幕和通用人像分割，适应多种场景
5. **丰富的特效系统**：支持动画效果、音效系统（BGM + 转场 + 提示音）、字幕生成
6. **并行处理优化**：多任务并行执行，提升生成速度
7. **完整的 API 接口**：提供 RESTful API，支持文件路径和文件上传两种模式
8. **完善的任务管理**：支持任务状态跟踪、文件清理
9. **线程安全**：移除所有 `os.chdir()` 调用，确保多线程环境稳定
10. **无数字人模式**：`face_video` 可选，支持仅背景 + 音频 + 字幕的成片模式

### 11.2 技术亮点
1. **Wav2Lip 集成**：高精度唇形同步算法
2. **MediaPipe 人像分割**：无需绿幕的通用抠像；软边缘 mask（形态学 + 渐变阈值）消除锯齿
3. **Whisper 字幕生成**：自动语音识别和字幕生成；降级链 + 卡拉OK回退确保字幕必出
4. **FFmpeg 视频处理**：专业的视频编辑和合成；统一 CRF 18 高质量编码
5. **并行计算**：ThreadPoolExecutor 提升性能（3 路并行：bg / wav2lip / subtitle）
6. **容错机制**：多重兜底方案确保生成成功
7. **音效系统**：BGM + 转场音效 + 完成提示音
8. **BGM 参数透传**：`bgm_enabled` + `bgm_path` 支持自定义背景音乐
9. **模型预加载**：Wav2Lip + Whisper 启动时预加载
10. **线程安全**：`subprocess.run(cwd=...)` 替代 `os.chdir()`
11. **GPU 显存主动管理**：batch 后释放 tensor、任务结束清空帧缓存 + CUDA 缓存，防止多任务堆积
12. **面部增强与融合**：Unsharp Mask 锐化提升 96×96 上采样清晰度；椭圆羽化融合消除 Wav2Lip 矩形硬边

### 11.3 应用场景
- **教育领域**：课件讲解、在线课程
- **企业培训**：产品演示、培训视频
- **营销宣传**：产品介绍、品牌推广
- **娱乐媒体**：虚拟主播、数字代言人
- **客服服务**：智能客服、语音助手

---

**文档版本**: v2.1  
**更新日期**: 2026-04-21  
**维护者**: AI 数字人项目组
