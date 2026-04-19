"""
配置模型定义
使用Pydantic模型进行配置验证和类型提示
"""
import logging
from pathlib import Path
import os
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional


class Settings(BaseSettings):
    """应用配置模型"""



    # 基础路径配置
    BASE_DIR: Path = Field(
        default=Path(__file__).parent.parent,
        description="项目根目录绝对路径"
    )


    # 文件上传配置
    UPLOAD_FOLDER: str = Field(
        default="static/video/uploads",
        description="视频上传目录相对路径"
    )
    CONVERTED_FOLDER: str = Field(
        default="static/video/converted",
        description="转换后文件目录相对路径"
    )
    MAX_CONTENT_LENGTH: int = Field(
        default=100,
        description="最大文件上传大小(MB)"
    )

    # PPT文件处理配置
    FILE_FOLDER: str = Field(
        default="static/file/uploads",
        description="PPT上传目录相对路径"
    )
    PDF_FOLDER: str = Field(
        default="static/file/pdf",
        description="PPT转换为PDF目录相对路径"
    )
    IMG_FOLDER: str = Field(
        default="static/file/images",
        description="PPT转换为图片目录相对路径"
    )

    # LibreOffice配置
    LIBREOFFICE_PATH: str = Field(
        default="C:/Program Files/LibreOffice/program/soffice.exe",
        description="LibreOffice可执行文件路径"
    )
    LIBREOFFICE_TIMEOUT: int = Field(
        default=120,
        description="LibreOffice转换超时时间(秒)"
    )

    # 应用配置
    APP_TITLE: str = Field(
        default="数字人上传服务",
        description="应用标题"
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        description="应用版本"
    )

    # 服务器配置
    HOST: str = Field(
        default="0.0.0.0",
        description="服务器监听地址"
    )
    PORT: int = Field(
        default=9088,
        description="服务器监听端口"
    )
    DEBUG: bool = Field(
        default=True,
        description="调试模式"
    )

    # FFmpeg配置
    FFMPEG_PATH: str = Field(
        default="ffmpeg",
        description="FFmpeg可执行文件路径"
    )
    FFPROBE_PATH: str = Field(
        default="ffprobe",
        description="FFprobe可执行文件路径"
    )
    SEGMENT_TIME: int = Field(
        default=10,
        description="HLS分段时间(秒)"
    )

    # 视频编码配置
    VIDEO_CODEC: str = Field(
        default="libx264",
        description="视频编码器"
    )
    AUDIO_CODEC: str = Field(
        default="aac",
        description="音频编码器"
    )
    VIDEO_BITRATE: str = Field(
        default="2M",
        description="视频码率"
    )
    MAXRATE: str = Field(
        default="2M",
        description="最大码率"
    )
    BUFSIZE: str = Field(
        default="4M",
        description="缓冲区大小"
    )

    # 数字人相关文件上传配置
    # 基础相对路径
    UPLOAD_BASE_FOLDER: str = Field(
        default="static/Digital_human/Customized_digital_human",
        description="数字人文件上传基础目录相对路径"
    )

    # 子目录配置
    UPLOAD_IMAGE_FOLDER: str = Field(
        default="image",
        description="头像图片存储子目录"
    )

    UPLOAD_AUDIO_FOLDER: str = Field(
        default="audio",
        description="音频文件存储子目录"
    )

    UPLOAD_VIDEO_FOLDER: str = Field(
        default="video",
        description="视频文件存储子目录"
    )

    # 文件类型白名单配置
    ALLOWED_IMAGE_EXTENSIONS: List[str] = Field(
        default=['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
        description="允许的图片格式"
    )

    ALLOWED_AUDIO_EXTENSIONS: List[str] = Field(
        default=['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac'],
        description="允许的音频格式"
    )

    ALLOWED_VIDEO_EXTENSIONS: List[str] = Field(
        default=['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'],
        description="允许的视频格式"
    )

    # 文件大小限制（单位：字节）
    MAX_IMAGE_SIZE: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="最大图片文件大小"
    )

    MAX_AUDIO_SIZE: int = Field(
        default=50 * 1024 * 1024,  # 50MB
        description="最大音频文件大小"
    )

    MAX_VIDEO_SIZE: int = Field(
        default=500 * 1024 * 1024,  # 500MB
        description="最大视频文件大小"
    )

    # 安全配置
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="应用密钥"
    )

    # 任务管理配置
    MAX_CONCURRENT_TASKS: int = Field(
        default=5,
        description="最大并发任务数"
    )
    TASK_CLEANUP_HOURS: int = Field(
        default=24,
        description="任务清理时间(小时)"
    )

    # CORS 配置
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:9088,http://127.0.0.1:9088",
        description="允许的CORS源列表，逗号分隔"
    )

    # 文件覆盖策略配置
    FILE_OVERWRITE_POLICY: str = Field(
        default="rename",  # rename: 重命名, overwrite: 覆盖, reject: 拒绝
        description="文件覆盖策略: rename(自动重命名), overwrite(覆盖), reject(拒绝上传)"
    )

    # 计算属性 - 获取上传文件夹的绝对路径
    @property
    def upload_folder_absolute(self) -> Path:
        """获取上传文件夹的绝对路径"""
        return self.BASE_DIR / self.UPLOAD_FOLDER

    @property
    def converted_folder_absolute(self) -> Path:
        """获取转换文件夹的绝对路径"""
        return self.BASE_DIR / self.CONVERTED_FOLDER

    @property
    def file_folder_absolute(self) -> Path:
        """获取PPT上传目录绝对路径"""
        return self.BASE_DIR / self.FILE_FOLDER

    @property
    def pdf_folder_absolute(self) -> Path:
        """获取PPT转换为PDF目录绝对路径"""
        return self.BASE_DIR / self.PDF_FOLDER

    @property
    def img_folder_absolute(self) -> Path:
        """获取PPT转换为图片目录绝对路径"""
        return self.BASE_DIR / self.IMG_FOLDER

    # 数字人上传相关计算属性
    @property
    def upload_base_folder_absolute(self) -> Path:
        """获取上传基础目录的绝对路径"""
        return self.BASE_DIR / self.UPLOAD_BASE_FOLDER

    @property
    def upload_image_folder_absolute(self) -> Path:
        """获取头像图片上传目录的绝对路径"""
        return self.upload_base_folder_absolute / self.UPLOAD_IMAGE_FOLDER

    @property
    def upload_audio_folder_absolute(self) -> Path:
        """获取音频上传目录的绝对路径"""
        return self.upload_base_folder_absolute / self.UPLOAD_AUDIO_FOLDER

    @property
    def upload_video_folder_absolute(self) -> Path:
        """获取视频上传目录的绝对路径"""
        return self.upload_base_folder_absolute / self.UPLOAD_VIDEO_FOLDER

    @property
    def max_content_length_bytes(self) -> int:
        """获取最大文件大小的字节数"""
        return self.MAX_CONTENT_LENGTH * 1024 * 1024

    def ensure_directories_exist(self):
        """确保所有必要的上传目录都存在"""
        directories = [
            self.upload_folder_absolute,
            self.converted_folder_absolute,
            self.file_folder_absolute,
            self.pdf_folder_absolute,
            self.img_folder_absolute,
            self.upload_image_folder_absolute,
            self.upload_audio_folder_absolute,
            self.upload_video_folder_absolute
        ]

        for directory in directories:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                logging.info(f"创建目录: {directory}")

    # 验证器
    @validator("BASE_DIR")
    def validate_base_dir(cls, v: Path) -> Path:
        """验证基础目录是否存在，不存在则创建"""
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
            logging.info(f"创建项目根目录: {v}")
        return v

    @validator("UPLOAD_BASE_FOLDER", "UPLOAD_IMAGE_FOLDER",
               "UPLOAD_AUDIO_FOLDER", "UPLOAD_VIDEO_FOLDER",
               "UPLOAD_FOLDER", "CONVERTED_FOLDER",
               "FILE_FOLDER", "PDF_FOLDER", "IMG_FOLDER")
    def validate_folder_names(cls, v: str) -> str:
        """验证文件夹名称，防止路径遍历攻击"""
        if ".." in v or v.startswith("/"):
            raise ValueError("文件夹名称不能包含'..'或以'/'开头")
        return v

    @validator("FILE_OVERWRITE_POLICY")
    def validate_overwrite_policy(cls, v: str) -> str:
        """验证文件覆盖策略"""
        if v not in ["rename", "overwrite", "reject"]:
            raise ValueError("FILE_OVERWRITE_POLICY 必须是 'rename', 'overwrite' 或 'reject'")
        return v

    @validator("LIBREOFFICE_PATH")
    def validate_libreoffice_path(cls, v: str) -> str:
        """验证LibreOffice路径是否存在"""
        if v and not os.path.exists(v):
            logging.warning(f"LibreOffice路径不存在: {v}")
        return v

    class Config:
        """Pydantic配置"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"