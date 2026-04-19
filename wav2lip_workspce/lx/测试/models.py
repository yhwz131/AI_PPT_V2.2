from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from config import config as _cfg

def _default_sfx_config():
    return {
        "enabled": True,
        "final_notification": {
            "enabled": True,
            "sound_file": _cfg.default_notification_sound,
            "start_before_end": 1.0,
            "volume": -5,
            "fade_duration": 0.3
        },
        "transition_sounds": {
            "enabled": True,
            "sound_file": _cfg.default_transition_sound,
            "transition_points": [],
            "volume": -3
        },
        "background_music": {
            "enabled": True,
            "music_file": _cfg.default_bgm,
            "volume_ratio": 0.2,
            "style": "corporate"
        }
    }

class SoundEffectsConfig(BaseModel):
    """音效配置"""
    enabled: Optional[bool] = True
    final_notification: Optional[Dict] = Field(default_factory=lambda: {
        "enabled": True,
        "sound_file": _cfg.default_notification_sound,
        "start_before_end": 1.0,
        "volume": -5,
        "fade_duration": 0.3
    })
    transition_sounds: Optional[Dict] = Field(default_factory=lambda: {
        "enabled": True,
        "sound_file": _cfg.default_transition_sound,
        "transition_points": [],
        "volume": -3
    })
    background_music: Optional[Dict] = Field(default_factory=lambda: {
        "enabled": True,
        "music_file": _cfg.default_bgm,
        "volume_ratio": 0.2,
        "style": "corporate"
    })

class VideoGenerationRequest(BaseModel):
    background_image: str
    face_video: str
    audio_path: str
    output_name: Optional[str] = "my_presentation"
    position: Optional[str] = "bottom-left"
    size: Optional[float] = 0.3
    animation: Optional[str] = "fly_in"
    animation_duration: Optional[float] = 6.0
    welcome_text: Optional[str] = "欢迎来到AI PPT 数字人讲解平台"
    topic_name: Optional[str] = "AI 知识讲堂"
    generate_subtitles: Optional[bool] = True
    sound_effects: Optional[SoundEffectsConfig] = Field(
        default_factory=lambda: SoundEffectsConfig(
            enabled=True,
            final_notification={
                "enabled": True,
                "sound_file": _cfg.default_notification_sound,
                "start_before_end": 2.0,
                "volume": -5,
                "fade_duration": 0.3
            },
            transition_sounds={
                "enabled": True,
                "sound_file": _cfg.default_transition_sound,
                "volume": -3
            },
            background_music={
                "enabled": True,
                "music_file": _cfg.default_bgm,
                "volume_ratio": 0.2,
                "style": "corporate"
            }
        )
    )

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: str
    created_time: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    error: Optional[str] = None
    output_path: Optional[str] = None
    file_size: Optional[str] = None
    absolute_path: Optional[str] = None
    file_exists: Optional[bool] = None
    download_url: Optional[str] = None

class FileUploadResponse(BaseModel):
    success: bool
    message: str
    file_id: Optional[str] = None
    filename: Optional[str] = None
    file_size: Optional[int] = None
    file_path: Optional[str] = None
    uploaded_time: Optional[str] = None

# 全局任务状态存储
tasks = {}