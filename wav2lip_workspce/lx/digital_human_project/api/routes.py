from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import tempfile
import shutil
from datetime import datetime
from typing import Optional

from config import config
from models import (
    VideoGenerationRequest, TaskStatusResponse, FileUploadResponse,
    tasks, SoundEffectsConfig
)
from services.file_service import FileService
from services.video_generator import VideoGenerator

# 创建FastAPI应用
app = FastAPI(
    title="简体中文数字人视频生成器 API",
    description="基于FastAPI的数字人视频生成服务，支持文件上传",
    version="1.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化服务
file_service = FileService()
generator = VideoGenerator()

def get_video_url(task_id: str) -> str:
    """获取视频的完整URL地址"""
    return f"{config.base_url}/download/{task_id}"

@app.get("/", summary="API信息")
async def index():
    """获取API基本信息"""
    return {
        "message": "简体中文数字人视频生成器 API",
        "version": "1.0",
        "framework": "FastAPI",
        "endpoints": {
            "/": "GET - 查看API信息",
            "/docs": "GET - 交互式API文档",
            "/generate": "POST - 生成视频（文件路径）",
            "/generate/upload": "POST - 生成视频（文件上传）",
            "/upload": "POST - 上传文件",
            "/status/{task_id}": "GET - 查询任务状态",
            "/download/{task_id}": "GET - 下载生成的视频",
            "/video_path/{task_id}": "GET - 获取视频文件路径",
            "/open_folder/{task_id}": "GET - 打开视频所在文件夹",
            "/cleanup": "POST - 清理已完成的任务"
        },
        "output_directory": os.path.abspath(generator.output_dir),
        "upload_directory": os.path.abspath("uploaded_files"),
        "base_url": config.base_url
    }

@app.post("/upload", summary="上传文件", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(..., description="支持图片、视频、音频文件"),
    file_service: FileService = Depends(lambda: file_service)
):
    """
    上传文件接口
    """
    try:
        allowed_types = {
            'image/jpeg', 'image/png', 'image/jpg', 'image/gif',
            'video/mp4', 'video/avi', 'video/mov', 'video/mkv',
            'audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/m4a'
        }
        
        if file.content_type not in allowed_types:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"不支持的文件类型: {file.content_type}"
                }
            )
        
        file_info = file_service.save_uploaded_file(file)
        
        return FileUploadResponse(
            success=True,
            message="文件上传成功",
            file_id=file_info["file_id"],
            filename=file_info["original_filename"],
            file_size=file_info["file_size"],
            file_path=file_info["file_path"],
            uploaded_time=file_info["uploaded_time"]
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"文件上传失败: {str(e)}"
            }
        )

@app.post("/generate", summary="生成视频（文件路径）", status_code=202)
async def generate_video(request: VideoGenerationRequest, background_tasks: BackgroundTasks):
    """生成数字人视频（使用文件路径）"""
    try:
        if request.sound_effects is None:
            request.sound_effects = SoundEffectsConfig(
                enabled=True,
                final_notification={
                    "enabled": True,
                    "sound_file": config.default_notification_sound,
                    "start_before_end": 2.0,
                    "volume": -5,
                    "fade_duration": 0.3
                },
                transition_sounds={
                    "enabled": True,
                    "sound_file": config.default_transition_sound,
                    "volume": -3
                },
                background_music={
                    "enabled": True,
                    "music_file": config.default_bgm,
                    "volume_ratio": 0.2,
                    "style": "corporate"
                }
            )
        
        required_files = {
            'background_image': request.background_image,
            'face_video': request.face_video,
            'audio_path': request.audio_path
        }
        
        for field, file_path in required_files.items():
            if not os.path.exists(file_path):
                raise HTTPException(status_code=400, detail=f"文件不存在: {file_path}")
        
        settings = request.dict()
        task_id = str(uuid.uuid4())
        
        tasks[task_id] = {
            'status': 'pending',
            'progress': '等待开始',
            'settings': settings,
            'created_time': datetime.now().isoformat()
        }
        
        def run_generation():
            generator.generate_video(settings, task_id)
        
        background_tasks.add_task(run_generation)
        
        return {
            "message": "视频生成任务已开始",
            "task_id": task_id,
            "status_url": f"/status/{task_id}",
            "download_url": f"/download/{task_id}",
            "video_path_url": f"/video_path/{task_id}",
            "open_folder_url": f"/open_folder/{task_id}",
            "output_directory": os.path.abspath(generator.output_dir)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"请求处理失败: {str(e)}")

@app.post("/generate/upload", summary="生成视频（文件上传）", status_code=202)
async def generate_video_upload(
    background_tasks: BackgroundTasks,
    background_image: UploadFile = File(...),
    face_video: UploadFile = File(...),
    audio_path: UploadFile = File(...),
    output_name: str = Form("my_presentation"),
    position: str = Form("bottom-left"),
    size: float = Form(0.3),
    animation: str = Form("fly_in"),
    animation_duration: float = Form(6.0),
    welcome_text: str = Form("欢迎来到云南水利水电职业技术学院"),
    topic_name: str = Form("AI 知识讲堂"),
    generate_subtitles: bool = Form(True)
):
    """生成数字人视频（使用文件上传）"""
    try:
        allowed_image_types = ['image/jpeg', 'image/png', 'image/jpg']
        allowed_video_types = ['video/mp4', 'video/avi', 'video/mov']
        allowed_audio_types = ['audio/mpeg', 'audio/wav', 'audio/mp3']
        
        if background_image.content_type not in allowed_image_types:
            raise HTTPException(status_code=400, detail="背景图片格式不支持，请使用JPEG或PNG格式")
        
        if face_video.content_type not in allowed_video_types:
            raise HTTPException(status_code=400, detail="人脸视频格式不支持，请使用MP4、AVI或MOV格式")
        
        if audio_path.content_type not in allowed_audio_types:
            raise HTTPException(status_code=400, detail="音频格式不支持，请使用MP3或WAV格式")
        
        temp_dir = tempfile.mkdtemp()
        bg_image_path = os.path.join(temp_dir, f"bg_{uuid.uuid4()}{os.path.splitext(background_image.filename)[1]}")
        face_video_path = os.path.join(temp_dir, f"face_{uuid.uuid4()}{os.path.splitext(face_video.filename)[1]}")
        audio_file_path = os.path.join(temp_dir, f"audio_{uuid.uuid4()}{os.path.splitext(audio_path.filename)[1]}")
        
        with open(bg_image_path, "wb") as buffer:
            shutil.copyfileobj(background_image.file, buffer)
        with open(face_video_path, "wb") as buffer:
            shutil.copyfileobj(face_video.file, buffer)
        with open(audio_file_path, "wb") as buffer:
            shutil.copyfileobj(audio_path.file, buffer)
        
        settings = {
            'background_image': bg_image_path,
            'face_video': face_video_path,
            'audio_path': audio_file_path,
            'output_name': output_name,
            'position': position,
            'size': size,
            'animation': animation,
            'animation_duration': animation_duration,
            'welcome_text': welcome_text,
            'topic_name': topic_name,
            'generate_subtitles': generate_subtitles,
            'sound_effects': {
                'enabled': True,
                'final_notification': {
                    'enabled': True,
                    'sound_file': config.default_notification_sound,
                    'start_before_end': 2.0,
                    'volume': -5,
                    'fade_duration': 0.3
                },
                'transition_sounds': {
                    'enabled': True,
                    'sound_file': config.default_transition_sound,
                    'volume': -3
                },
                'background_music': {
                    'enabled': bgm_enabled.lower() != "false",
                    'music_file': bgm_path if bgm_path else config.default_bgm,
                    'volume_ratio': 0.2,
                    'style': 'corporate'
                }
            }
        }
        
        task_id = str(uuid.uuid4())
        
        tasks[task_id] = {
            'status': 'pending',
            'progress': '等待开始',
            'settings': settings,
            'created_time': datetime.now().isoformat(),
            'temp_dir': temp_dir
        }
        
        def run_generation():
            try:
                generator.generate_video(settings, task_id)
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
        
        background_tasks.add_task(run_generation)
        
        return {
            "message": "视频生成任务已开始（文件上传模式）",
            "task_id": task_id,
            "status_url": f"/status/{task_id}",
            "download_url": f"/download/{task_id}",
            "video_path_url": f"/video_path/{task_id}",
            "open_folder_url": f"/open_folder/{task_id}",
            "output_directory": os.path.abspath(generator.output_dir)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"请求处理失败: {str(e)}")

@app.get("/status/{task_id}", summary="查询任务状态")
async def get_task_status(task_id: str):
    """根据任务ID查询生成状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    
    response_data = {
        "task_id": task_id,
        "status": task['status'],
        "progress": task.get('progress', '未知'),
        "created_time": task['created_time']
    }
    
    if 'start_time' in task:
        response_data['start_time'] = task['start_time']
    if 'end_time' in task:
        response_data['end_time'] = task['end_time']
    
    if 'error' in task:
        response_data['error'] = task['error']
    
    if 'output_path' in task:
        file_exists = os.path.exists(task['output_path'])
        response_data['output_path'] = get_video_url(task_id) if file_exists else None
        response_data['file_size'] = f"{os.path.getsize(task['output_path']) / (1024 * 1024):.2f} MB" if file_exists else None
        response_data['absolute_path'] = os.path.abspath(task['output_path']) if file_exists else None
        response_data['file_exists'] = file_exists
        response_data['download_url'] = get_video_url(task_id) if file_exists else None
    
    if task['status'] == 'completed':
        response_data['status_code'] = 200
        return JSONResponse(
            status_code=200,
            content={
                "message": "视频生成成功",
                **response_data
            }
        )
    elif task['status'] == 'failed':
        response_data['status_code'] = 500
        return JSONResponse(
            status_code=500,
            content={
                "message": "视频生成失败",
                **response_data
            }
        )
    else:
        response_data['status_code'] = 202
        return JSONResponse(
            status_code=202,
            content={
                "message": "任务处理中",
                **response_data
            }
        )

@app.get("/video_path/{task_id}", summary="获取视频文件路径")
async def get_video_path(task_id: str):
    """获取生成的视频文件路径信息"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="视频尚未生成完成")
    
    if 'output_path' not in task or not os.path.exists(task['output_path']):
        raise HTTPException(status_code=404, detail="视频文件不存在")
    
    try:
        video_path = task['output_path']
        file_info = {
            "task_id": task_id,
            "video_path": video_path,
            "video_url": get_video_url(task_id),
            "absolute_path": os.path.abspath(video_path),
            "file_name": os.path.basename(video_path),
            "file_size_bytes": os.path.getsize(video_path),
            "file_size_mb": round(os.path.getsize(video_path) / (1024 * 1024), 2),
            "file_exists": True,
            "download_url": f"/download/{task_id}",
            "created_time": task.get('end_time', '未知')
        }
        
        return file_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件信息失败: {str(e)}")

@app.get("/download/{task_id}", summary="下载生成的视频")
async def download_video(task_id: str):
    """下载生成的视频文件"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="视频尚未生成完成")
    
    if 'output_path' not in task or not os.path.exists(task['output_path']):
        raise HTTPException(status_code=404, detail="视频文件不存在")
    
    try:
        return FileResponse(
            task['output_path'],
            media_type='video/mp4',
            filename=f"{task['settings']['output_name']}.mp4"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")

@app.get("/open_folder/{task_id}", summary="打开视频所在文件夹")
async def open_video_folder(task_id: str):
    """打开视频文件所在的文件夹"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="视频尚未生成完成")
    
    if 'output_path' not in task or not os.path.exists(task['output_path']):
        raise HTTPException(status_code=404, detail="视频文件不存在")
    
    try:
        folder_path = os.path.dirname(task['output_path'])
        generator.open_file_in_explorer(task['output_path'])
        return {
            "message": "正在打开文件夹",
            "folder_path": folder_path,
            "video_path": task['output_path'],
            "video_url": get_video_url(task_id),
            "absolute_path": os.path.abspath(task['output_path'])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开文件夹失败: {str(e)}")

@app.post("/cleanup", summary="清理已完成的任务")
async def cleanup_tasks():
    """清理24小时前已完成的任务"""
    try:
        cutoff_time = datetime.now().timestamp() - 24 * 3600
        
        tasks_to_remove = []
        for task_id, task in tasks.items():
            if task['status'] in ['completed', 'failed']:
                created_time = datetime.fromisoformat(task['created_time']).timestamp()
                if created_time < cutoff_time:
                    if 'output_path' in task and os.path.exists(task['output_path']):
                        os.remove(task['output_path'])
                    tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del tasks[task_id]
        
        return {
            "message": f"清理了 {len(tasks_to_remove)} 个旧任务",
            "remaining_tasks": len(tasks)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")