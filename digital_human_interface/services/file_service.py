import os
import uuid
import aiofiles
from pathlib import Path
from fastapi import UploadFile, HTTPException
from typing import Dict, Any
from config.config import Settings


class FileService:
    """文件服务类，处理文件上传和管理"""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def save_uploaded_file(self, file: UploadFile) -> Dict[str, Any]:
        """
        保存上传的文件

        Args:
            file: 上传的文件对象

        Returns:
            Dict: 包含文件信息的字典
        """
        # 验证文件类型
        if not file.filename.lower().endswith(('.ppt', '.pptx')):
            raise HTTPException(status_code=400, detail="只支持PPT和PPTX格式文件")

        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix.lower()
        safe_filename = f"{file_id}{file_extension}"
        file_path = os.path.join(self.settings.FILE_FOLDER, safe_filename)
        print(file_path)

        try:
            # 异步保存文件
            async with aiofiles.open(file_path, "wb") as buffer:
                content = await file.read()
                await buffer.write(content)

            file_size = os.path.getsize(file_path)

            return {
                "file_id": file_id,
                "filename": file.filename,
                "file_path": file_path,
                "file_size": file_size
            }

        except Exception as e:
            # 清理失败的文件
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    def get_file_by_id(self, file_id: str) -> str:
        """
        根据文件ID获取文件路径

        Args:
            file_id: 文件ID

        Returns:
            str: 文件路径
        """
        file_pattern = os.path.join(self.settings.FILE_FOLDER, f"{file_id}.*")
        import glob
        existing_files = glob.glob(file_pattern)

        if not existing_files:
            raise HTTPException(status_code=404, detail="文件不存在")

        return existing_files[0]