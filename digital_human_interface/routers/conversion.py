import uuid

from fastapi import APIRouter, Form, BackgroundTasks, Depends, HTTPException
from typing import Dict, Any

from config import get_settings
from core.dependencies import get_conversion_service
from services.file_service import FileService
from services.conversion_service import ConversionService

# 创建转换路由蓝图
router = APIRouter(
    prefix="/conversion",
    tags=["PPT转换服务"],
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "资源不存在"},
        500: {"description": "服务器内部错误"}
    }
)

def get_file_service() -> FileService:
    """FileService依赖注入"""
    return FileService(get_settings())


@router.post("/start", summary="开始转换任务", response_model=Dict[str, Any])
async def start_conversion(
        background_tasks: BackgroundTasks,
        file_id: str = Form(..., description="文件ID"),
        convert_type: str = Form(..., description="转换类型：pdf或images"),
        image_format: str = Form("png", description="图片格式（png或jpg）"),
        file_service: FileService = Depends(get_file_service),
        conversion_service: ConversionService = Depends(get_conversion_service)
) -> Dict[str, Any]:
    """
    开始PPT转换任务

    - **file_id**: 上传文件时返回的文件ID
    - **convert_type**: 转换类型，pdf或images
    - **image_format**: 图片格式，当convert_type为images时有效
    - **返回**: 任务ID和任务状态
    """
    if convert_type not in ["pdf", "images"]:
        raise HTTPException(status_code=400, detail="convert_type必须是'pdf'或'images'")

    if convert_type == "images" and image_format not in ["png", "jpg"]:
        raise HTTPException(status_code=400, detail="image_format必须是'png'或'jpg'")

    try:
        # 获取文件路径
        file_path = file_service.get_file_by_id(file_id)
        task_id = str(uuid.uuid4())

        # 根据转换类型启动不同的后台任务
        if convert_type == "pdf":
            background_tasks.add_task(
                conversion_service.start_pdf_conversion,
                file_path, task_id
            )
        else:
            background_tasks.add_task(
                conversion_service.start_image_conversion,
                file_path, task_id, image_format
            )

        return {
            "code": 200,
            "message": "转换任务已开始",
            "data": {
                "task_id": task_id,
                "file_id": file_id,
                "convert_type": convert_type,
                "status": "processing"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动转换任务失败: {str(e)}")


@router.get("/tasks/{task_id}", summary="获取转换任务状态")
async def get_conversion_status(
        task_id: str,
        conversion_service: ConversionService = Depends(get_conversion_service)
) -> Dict[str, Any]:
    """
    获取转换任务状态和结果

    - **task_id**: 转换任务ID
    - **返回**: 任务状态、进度和结果信息
    """
    try:
        task_info = conversion_service.get_task_info(task_id)

        response_data = {
            "task_id": task_id,
            "status": task_info["status"],
            "progress": task_info.get("progress", 0),
            "message": task_info.get("message", "")
        }

        # 根据任务状态添加额外信息
        if task_info["status"] == "completed":
            if "pdf_url" in task_info:
                response_data.update({
                    "type": "pdf",
                    "pdf_url": task_info["pdf_url"],
                    "download_url": task_info["pdf_url"]
                })
            else:
                response_data.update({
                    "type": "images",
                    "image_urls": task_info.get("image_urls", []),
                    "image_count": task_info.get("image_count", 0)
                })

        elif task_info["status"] == "failed":
            response_data["error"] = task_info.get("error", "未知错误")

        return {
            "code": 200,
            "message": "查询成功",
            "data": response_data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")


@router.get("/tasks/{task_id}/preview", summary="预览转换结果")
async def preview_conversion(
        task_id: str,
        conversion_service: ConversionService = Depends(get_conversion_service)
) -> Dict[str, Any]:
    """
    预览转换结果

    - **task_id**: 转换任务ID
    - **返回**: 转换结果的预览信息
    """
    try:
        task_info = conversion_service.get_task_info(task_id)

        if task_info["status"] != "completed":
            return {
                "code": 200,
                "message": "转换尚未完成",
                "data": {
                    "task_id": task_id,
                    "status": task_info["status"],
                    "progress": task_info.get("progress", 0)
                }
            }

        preview_data = {"task_id": task_id, "status": "completed"}

        if "pdf_url" in task_info:
            preview_data.update({
                "type": "pdf",
                "pdf_url": task_info["pdf_url"],
                "downloadable": True
            })
        else:
            preview_data.update({
                "type": "images",
                "image_urls": task_info.get("image_urls", []),
                "image_count": task_info.get("image_count", 0),
                "preview_available": True
            })

        return {
            "code": 200,
            "message": "预览数据获取成功",
            "data": preview_data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预览数据失败: {str(e)}")