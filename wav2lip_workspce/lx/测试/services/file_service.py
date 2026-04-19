import os
import uuid
import shutil
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import UploadFile

class FileService:
    def __init__(self, upload_dir="uploaded_files"):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
    
    def save_uploaded_file(self, file: UploadFile, file_id: str = None) -> Dict[str, Any]:
        """保存上传的文件"""
        if file_id is None:
            file_id = str(uuid.uuid4())
        
        original_filename = file.filename
        file_extension = os.path.splitext(original_filename)[1]
        safe_filename = f"{file_id}{file_extension}"
        file_path = os.path.join(self.upload_dir, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(file_path)
        
        return {
            "file_id": file_id,
            "original_filename": original_filename,
            "safe_filename": safe_filename,
            "file_path": file_path,
            "file_size": file_size,
            "uploaded_time": datetime.now().isoformat()
        }
    
    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """根据文件ID获取文件信息"""
        for filename in os.listdir(self.upload_dir):
            if filename.startswith(file_id):
                file_path = os.path.join(self.upload_dir, filename)
                if os.path.exists(file_path):
                    return {
                        "file_id": file_id,
                        "filename": filename,
                        "file_path": file_path,
                        "file_size": os.path.getsize(file_path),
                        "uploaded_time": datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
                    }
        return None
    
    def delete_file(self, file_id: str) -> bool:
        """删除文件"""
        file_info = self.get_file_info(file_id)
        if file_info and os.path.exists(file_info["file_path"]):
            os.remove(file_info["file_path"])
            return True
        return False