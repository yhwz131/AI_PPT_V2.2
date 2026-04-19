from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Path,Request
from typing import Dict, Any
from config import get_settings
from core.dependencies import get_conversion_service
from routers.conversion import start_conversion, get_conversion_status
from services.conversion_service import ConversionService
from services.file_service import FileService

# 创建文件路由蓝图
router = APIRouter(
    prefix="/files",
    tags=["文件管理"],
    responses={
        404: {"description": "接口不存在"},
        500: {"description": "服务器内部错误"}
    }
)

def get_file_service() -> FileService:
    """FileService依赖注入"""
    return FileService(get_settings())

@router.post("/upload", summary="上传PPT文件", response_model=Dict[str, Any])
async def upload_file(
        file: UploadFile = File(..., description="PPT文件（.ppt或.pptx格式）"),
        file_service: FileService = Depends(get_file_service)
) -> Dict[str, Any]:
    """
    上传PPT文件接口

    - **file**: 要上传的PPT文件，支持PPT和PPTX格式
    - **返回**: 文件ID、文件名、文件大小等信息
    """
    try:
        file_info = await file_service.save_uploaded_file(file)

        return {
            "code": 200,
            "message": "文件上传成功",
            "data": file_info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.get("/{file_id}/info", summary="获取文件信息")
async def get_file_info(
        file_id: str,
        file_service: FileService = Depends(get_file_service)
) -> Dict[str, Any]:
    """
    根据文件ID获取文件信息

    - **file_id**: 上传文件时返回的文件ID
    - **返回**: 文件基本信息
    """
    try:
        file_path = file_service.get_file_by_id(file_id)

        return {
            "code": 200,
            "message": "查询成功",
            "data": {
                "file_id": file_id,
                "file_path": file_path,
                "exists": os.path.exists(file_path)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询文件信息失败: {str(e)}")


@router.post("/preview", summary="ppt预览", response_model=Dict[str, Any])
async def preview(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(..., description="PPT文件（.ppt或.pptx格式）"),
        file_service: FileService = Depends(get_file_service),
        conversion_service: ConversionService = Depends(get_conversion_service)
) -> Dict[str, Any]:
    try:
        # 直接使用 file_service 上传文件
        file_info = await file_service.save_uploaded_file(file)

        if file_info:
            file_id = file_info["file_id"]
            # PPT转换为PDF
            # 获取文件路径
            file_path = file_service.get_file_by_id(file_id)
            task_id = str(uuid.uuid4())
            background_tasks.add_task(
                conversion_service.start_pdf_conversion,
                file_path, task_id
            )
            return {
                "code": 200,
                "message": "转换任务已开始",
                "data": {
                    "task_id": task_id,
                    "file_id": file_id,
                    "convert_type": "pdf",
                    "status": "processing"
                }
            }
        else:
            return {
                "code": 500,
                "message": "文件上传失败"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件预览失败: {str(e)}")


import os
import uuid
import requests
from pathlib import Path
from typing import Dict, Any
from fastapi import HTTPException, UploadFile, File, Depends, Form


@router.post("/upload_bgm", summary="上传背景音乐", response_model=Dict[str, Any])
async def upload_bgm(
        file: UploadFile = File(..., description="音频文件（mp3/wav格式）")
) -> Dict[str, Any]:
    bgm_dir = os.path.join("static", "file", "bgm")
    os.makedirs(bgm_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".mp3"
    save_path = os.path.join(bgm_dir, f"{file_id}{ext}")
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    abs_path = os.path.abspath(save_path)
    relative_url = f"/static/file/bgm/{file_id}{ext}"
    return {
        "code": 200,
        "message": "背景音乐上传成功",
        "data": {"bgm_path": abs_path, "bgm_url": relative_url, "file_name": file.filename}
    }


@router.post("/voice_over_script_generation", summary="口播文案生成", response_model=Dict[str, Any])
async def voice_over_script_generation(
        file: UploadFile = File(..., description="PPT文件（.ppt或.pptx格式）"),
        pdf_path: str = Form(..., description="已转换的PDF文件路径"),
        style: str = Form("normal", description="文案风格: brief/normal/professional")
) -> Dict[str, Any]:
    """
    口播文案生成接口

    参数说明:
    - file: 客户端上传的PPT文件（虽然已转换，但仍需上传用于记录）
    - pdf_path: 已转换的PDF文件路径（服务端本地路径）
    """
    try:
        print(f"接收到口播文案生成请求")
        print(f"PDF文件路径: {pdf_path}")

        # 1. 验证PDF文件路径是否存在
        # 处理 /static/... URL 路径：去掉前缀还原为文件系统相对路径
        cleaned_path = pdf_path
        if cleaned_path.startswith("/static/"):
            cleaned_path = cleaned_path[1:]  # "/static/file/pdf/x.pdf" → "static/file/pdf/x.pdf"

        pdf_file_path = Path(cleaned_path)

        if not pdf_file_path.is_absolute():
            possible_paths = [
                pdf_file_path,
                Path(f"static/file/pdf/{pdf_file_path.name}"),
                Path(f"static/file/pdf/{pdf_file_path}"),
                Path(f"static/{pdf_file_path}"),
            ]

            found = False
            for possible_path in possible_paths:
                if possible_path.exists():
                    pdf_file_path = possible_path
                    found = True
                    print(f"找到PDF文件: {pdf_file_path}")
                    break

            if not found:
                print(f"PDF文件不存在，尝试路径: {[str(p) for p in possible_paths]}")
                raise HTTPException(
                    status_code=404,
                    detail=f"PDF文件不存在: {pdf_path}"
                )
        else:
            if not pdf_file_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"PDF文件不存在: {pdf_path}"
                )

        print(f"使用PDF文件: {pdf_file_path}")

        # 2. 调用解析服务生成口播文案
        url = "http://127.0.0.1:8802/parse"

        try:
            # 打开PDF文件
            with open(pdf_file_path, 'rb') as pdf_file:
                files = {
                    'file': (pdf_file_path.name, pdf_file, 'application/pdf')
                }

                print(f"发送请求到解析服务: {url}, style={style}")
                response = requests.post(url, files=files, data={"style": style})

                if response.status_code != 200:
                    print(f"解析服务返回错误: {response.status_code}, 内容: {response.text[:200]}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"解析服务返回错误: {response.status_code}"
                    )

                response_data = response.json()
                ppt_list = response_data["ppt_list"]
                text = ""

                for item in ppt_list:
                    try:
                        page_num = int(item.get('page_num', 0)) + 1
                        title = item.get('title', '').strip()
                        content = item.get('content', '').strip()

                        text += f"<div><h4>第{page_num}页</h4>\n"
                        if title:
                            text += f"<h3>标题: {title}</h3>\n"
                        if content:
                            text += f"<p>内容: {content}</p></div>\n\n"
                    except (ValueError, TypeError) as e:
                        print(f"处理页面数据时出错: {e}")
                        continue

                return {
                    "code": 200,
                    "message": "口播文案生成成功",
                    "data": {
                        "script": text,
                        "pdf_path": str(pdf_file_path)
                    }
                }

        except requests.exceptions.Timeout:
            print("解析服务请求超时")
            raise HTTPException(
                status_code=504,
                detail="解析服务响应超时"
            )
        except requests.exceptions.RequestException as e:
            print(f"请求解析服务失败: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"连接解析服务失败: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"口播文案生成失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"口播文案生成失败: {str(e)}")