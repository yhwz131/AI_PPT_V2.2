"""
FastAPI视频转换应用主入口
基于配置文件的重构版本
"""
import os
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel

# 导入配置和核心功能
from config import get_settings
from config.config import validate_ffmpeg_available
from core.converter import ConversionTask, convert_mp4_to_hls_async, conversion_tasks

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 获取配置
settings = get_settings()

# 创建视频处理模块的路由器
router_video = APIRouter(prefix="/video", tags=["视频处理模块"])


# Pydantic模型
class ConversionResponse(BaseModel):
    """转换响应模型"""
    success: bool
    task_id: str = None
    message: str
    data: Dict[str, Any] = None


class ProgressResponse(BaseModel):
    """进度响应模型"""
    success: bool
    task_id: str
    status: str
    progress: float
    message: str
    data: Dict[str, Any]


class TaskListResponse(BaseModel):
    """任务列表响应模型"""
    success: bool
    count: int
    tasks: List[Dict[str, Any]]


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    success: bool
    message: str
    timestamp: str
    active_tasks: int
    total_tasks: int
    ffmpeg_available: bool
    config: Dict[str, Any]


@router_video.post("/convert",summary="视频切片", response_model=ConversionResponse)
async def start_conversion(
        background_tasks: BackgroundTasks,
        input_video_path: str = Form(..., description="输入视频文件路径"),
        output_dir: str = Form(..., description="输出目录路径"),
        segment_time: int = Form(default=None, description="分段时长（秒）")
):
    """
    开始视频转换任务（支持自定义输入输出路径）

    Args:
        background_tasks: FastAPI后台任务管理器
        input_video_path: 输入视频文件路径（视频已保存）
        output_dir: 自定义输出目录路径
        segment_time: HLS分段时长，如果为None则使用配置中的默认值
    """
    try:
        # 验证输入视频文件是否存在
        if not os.path.exists(input_video_path):
            raise HTTPException(
                status_code=400,
                detail=f"输入视频文件不存在: {input_video_path}"
            )

        # 验证输入文件是否为视频文件
        file_extension = os.path.splitext(input_video_path.lower())[1]
        if file_extension not in settings.ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式，允许的格式: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}"
            )

        # 验证和创建用户指定的输出目录
        try:
            # 确保输出路径是绝对路径
            if not os.path.isabs(output_dir):
                output_dir = os.path.abspath(output_dir)

            # 检查路径安全性（防止路径遍历攻击）
            allowed_dirs = getattr(settings, 'allowed_output_base_dirs', [])
            if allowed_dirs:
                if not any(output_dir.startswith(allowed_dir) for allowed_dir in allowed_dirs):
                    raise HTTPException(
                        status_code=400,
                        detail="输出路径不在允许的目录范围内"
                    )

            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)

            # 检查目录写入权限
            test_file = os.path.join(output_dir, "test_write.tmp")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except IOError:
                raise HTTPException(
                    status_code=400,
                    detail="输出目录没有写入权限"
                )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"输出路径无效: {str(e)}"
            )

        # 获取原始文件名
        original_filename = os.path.basename(input_video_path)

        # 生成任务ID
        task_id = str(uuid.uuid4())
        task = ConversionTask(task_id, input_video_path, output_dir)
        conversion_tasks[task_id] = task

        # 使用配置或传入的分段时间
        actual_segment_time = segment_time or settings.SEGMENT_TIME

        # 启动后台任务
        background_tasks.add_task(
            convert_mp4_to_hls_async,
            task_id, input_video_path, output_dir
        )

        return ConversionResponse(
            success=True,
            task_id=task_id,
            message="转换任务已开始",
            data={
                "original_filename": original_filename,
                "input_file": input_video_path,
                "output_dir": output_dir,
                "segment_time": actual_segment_time,
                "max_file_size": f"{settings.MAX_CONTENT_LENGTH}MB",
                "start_time": task.start_time.isoformat() if task.start_time else None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理请求时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"处理请求时发生错误: {str(e)}")

@router_video.get("/progress/{task_id}",summary="状态轮询", response_model=ProgressResponse)
async def get_conversion_progress(task_id: str):
    """获取转换任务进度"""
    if task_id not in conversion_tasks:
        raise HTTPException(status_code=404, detail="任务ID不存在")

    task = conversion_tasks[task_id]

    # 计算已用时间
    elapsed_time = 0
    if task.start_time:
        if task.end_time:
            elapsed_time = (task.end_time - task.start_time).total_seconds()
        else:
            elapsed_time = (datetime.now() - task.start_time).total_seconds()

    # 生成可访问的M3U8 URL
    m3u8_url = ""
    if task.m3u8_file and os.path.exists(task.m3u8_file):
        relative_path = os.path.relpath(task.m3u8_file, settings.BASE_DIR)
        m3u8_url = f"/{relative_path.replace(os.sep, '/')}"

    return ProgressResponse(
        success=True,
        task_id=task_id,
        status=task.status,
        progress=round(task.progress, 2),
        message=task.message,
        data={
            "current_time": round(task.current_time, 2),
            "total_duration": round(task.total_duration, 2),
            "speed": task.speed,
            "elapsed_time": round(elapsed_time, 2),
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "end_time": task.end_time.isoformat() if task.end_time else None,
            "m3u8_url": m3u8_url
        }
    )


@router_video.get("/tasks",summary="获取所有任务列表", response_model=TaskListResponse)
async def list_tasks():
    """获取所有任务列表"""
    tasks_list = []
    for task_id, task in conversion_tasks.items():
        elapsed_time = 0
        if task.start_time:
            if task.end_time:
                elapsed_time = (task.end_time - task.start_time).total_seconds()
            else:
                elapsed_time = (datetime.now() - task.start_time).total_seconds()

        tasks_list.append({
            "task_id": task_id,
            "status": task.status,
            "progress": round(task.progress, 2),
            "message": task.message,
            "elapsed_time": round(elapsed_time, 2),
            "original_filename": os.path.basename(task.input_file)
        })

    return TaskListResponse(
        success=True,
        count=len(tasks_list),
        tasks=tasks_list
    )


@router_video.get("/health",summary="服务健康检查", response_model=HealthCheckResponse)
async def health_check():
    """服务健康检查"""

    ffmpeg_available = validate_ffmpeg_available()

    return HealthCheckResponse(
        success=True,
        message="服务运行正常",
        timestamp=datetime.now().isoformat(),
        active_tasks=len([t for t in conversion_tasks.values() if t.status == "processing"]),
        total_tasks=len(conversion_tasks),
        ffmpeg_available=ffmpeg_available,
        config={
            "max_file_size": f"{settings.MAX_CONTENT_LENGTH}MB",
            "allowed_extensions": settings.ALLOWED_EXTENSIONS,
            "max_concurrent_tasks": settings.MAX_CONCURRENT_TASKS
        }
    )