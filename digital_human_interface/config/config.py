"""
配置管理模块
负责配置的加载、验证和管理
"""
import os
import logging
from typing import Optional, Dict, Any
from .settings import Settings  # 从settings模块导入Pydantic配置模型

# 配置缓存
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """
    获取配置实例（单例模式）

    Returns:
        Settings: 配置实例

    Example:
        >>> settings = get_settings()
        >>> print(settings.BASE_DIR)
    """
    global _settings
    if _settings is None:
        _settings = _load_settings()
    return _settings


def _load_settings() -> Settings:
    """
    加载配置并创建必要的目录结构

    Returns:
        Settings: 配置实例
    """
    try:
        # 使用Pydantic的Settings类，它会自动从环境变量和.env文件加载配置
        settings = Settings()

        # 由于Pydantic模型已经在验证器中创建目录，这里主要进行日志记录
        logging.info("配置加载成功")
        logging.info(f"项目根目录: {settings.BASE_DIR}")
        logging.info(f"视频上传目录: {settings.upload_folder_absolute}")
        logging.info(f"视频转换目录: {settings.converted_folder_absolute}")
        logging.info(f"PPT上传目录: {settings.file_folder_absolute}")
        logging.info(f"PPT转换为PDF目录: {settings.pdf_folder_absolute}")
        logging.info(f"PPT转换为图片目录: {settings.img_folder_absolute}")

        # 验证LibreOffice配置
        if hasattr(settings, 'LIBREOFFICE_PATH'):
            logging.info(f"LibreOffice路径: {settings.LIBREOFFICE_PATH}")

        return settings

    except Exception as e:
        logging.error(f"配置加载失败: {e}")
        raise


def reload_settings() -> Settings:
    """
    重新加载配置

    Returns:
        Settings: 新的配置实例
    """
    global _settings
    _settings = _load_settings()
    return _settings


def validate_ffmpeg_available() -> bool:
    """
    验证FFmpeg是否可用

    Returns:
        bool: FFmpeg是否可用
    """
    import subprocess
    try:
        settings = get_settings()
        result = subprocess.run([settings.FFMPEG_PATH, '-version'],
                                capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        logging.error(f"FFmpeg验证失败: {e}")
        return False


def get_static_config() -> Dict[str, Any]:
    """
    获取静态文件配置（兼容性函数）

    Returns:
        Dict[str, Any]: 静态文件配置字典
    """
    settings = get_settings()
    return {
        "upload_dir": settings.upload_folder_absolute,
        "pdf_dir": settings.pdf_folder_absolute,
        "images_dir": settings.img_folder_absolute
    }


# 初始化日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)