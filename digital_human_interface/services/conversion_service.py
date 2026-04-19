import os
from typing import Dict, Any
from fastapi import HTTPException
from pathlib import Path
from config.config import Settings
from core.libreoffice_converter import converter


class ConversionService:
    """转换服务类，处理PPT转换逻辑"""

    def __init__(self, settings: Settings, task_storage: Dict[str, Any]):
        # 验证 settings 参数类型
        if not isinstance(settings, Settings):
            raise ValueError(f"settings 参数应该是 Settings 实例，但实际是 {type(settings)}")

        self.settings = settings
        self.task_storage = task_storage
        print(f"ConversionService 初始化成功: PDF路径 = {self.settings.pdf_folder_absolute}")

    async def start_pdf_conversion(self, file_path: str, task_id: str) -> None:
        """启动PDF转换任务"""
        try:
            print(f"开始PDF转换: file_path={file_path}, task_id={task_id}")

            # 确保文件存在
            if not os.path.exists(file_path):
                raise Exception(f"输入文件不存在: {file_path}")

            self.task_storage[task_id] = {
                "status": "processing",
                "progress": 0,
                "message": "正在转换为PDF"
            }

            # 执行PDF转换
            pdf_path = await converter.convert_to_pdf(
                file_path,
                self.settings.pdf_folder_absolute,
                timeout=self.settings.LIBREOFFICE_TIMEOUT
            )

            # 确保PDF文件生成
            if not os.path.exists(pdf_path):
                raise Exception(f"PDF文件未生成: {pdf_path}")

            pdf_filename = Path(pdf_path).name
            pdf_url = f"/static/file/pdf/{pdf_filename}"

            print(f"PDF转换成功: {pdf_path}, URL: {pdf_url}")

            self.task_storage[task_id].update({
                "status": "completed",
                "progress": 100,
                "pdf_path": pdf_path,
                "pdf_url": pdf_url,
                "message": "PDF转换完成"
            })

        except Exception as e:
            print(f"PDF转换失败: {e}")
            self.task_storage[task_id].update({
                "status": "failed",
                "error": str(e),
                "message": f"转换失败: {str(e)}"
            })

    async def start_image_conversion(self, file_path: str, task_id: str,
                                     image_format: str = "png") -> None:
        """启动图片转换任务"""
        try:
            # 确保文件存在
            if not os.path.exists(file_path):
                raise Exception(f"输入文件不存在: {file_path}")

            output_dir = os.path.join(self.settings.img_folder_absolute, task_id)
            os.makedirs(output_dir, exist_ok=True)

            self.task_storage[task_id] = {
                "status": "processing",
                "progress": 0,
                "message": "正在转换为图片序列"
            }

            # 执行图片转换
            image_paths = await converter.convert_to_images(
                file_path, output_dir, image_format,
                timeout=self.settings.LIBREOFFICE_TIMEOUT
            )

            # 生成图片URL列表
            image_urls = []
            for img_path in image_paths:
                img_filename = Path(img_path).name
                image_url = f"/static/file/images/{task_id}/{img_filename}"
                image_urls.append(image_url)

            self.task_storage[task_id].update({
                "status": "completed",
                "progress": 100,
                "image_paths": image_paths,
                "image_urls": image_urls,
                "image_count": len(image_urls),
                "message": f"图片转换完成，共生成 {len(image_urls)} 张图片"
            })

        except Exception as e:
            self.task_storage[task_id].update({
                "status": "failed",
                "error": str(e),
                "message": f"转换失败: {str(e)}"
            })

    def get_task_info(self, task_id: str) -> Dict[str, Any]:
        """获取任务信息"""
        if task_id not in self.task_storage:
            raise HTTPException(status_code=404, detail="任务不存在")
        return self.task_storage[task_id]