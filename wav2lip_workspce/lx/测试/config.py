import os
import socket
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)
except ImportError:
    pass

class Config:
    def __init__(self):
        self.host_ip = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "5000"))
        self.base_url = f"http://{self.host_ip}:{self.port}"
        
        _base = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.dirname(os.path.dirname(os.path.dirname(_base)))

        self.output_dir = os.path.join(_base, "image_output")
        self.upload_dir = os.path.join(_base, "uploaded_files")
        self.temp_dir = os.path.join(_base, "temp_files")
        
        self.wav2lip_dir = os.getenv("WAV2LIP_DIR", os.path.join(_project_root, "Wav2Lip"))
        self.wav2lip_checkpoint = os.getenv("WAV2LIP_CHECKPOINT", os.path.join(self.wav2lip_dir, "models", "Wav2Lip-SD-GAN.pt"))

        self.sfx_dir = os.path.join(_base, "assets", "sfx")
        self.default_notification_sound = os.getenv("SFX_NOTIFICATION", os.path.join(self.sfx_dir, "完成提示音.wav"))
        self.default_transition_sound = os.getenv("SFX_TRANSITION", os.path.join(self.sfx_dir, "转场音效.wav"))
        self.default_bgm = os.getenv("SFX_BGM", os.path.join(self.sfx_dir, "商务背景音乐.mp3"))

        self.sound_effects_dir = "sound_effects"
        
        self._create_dirs()
    
    def _get_local_ip(self):
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return None
    
    def _create_dirs(self):
        """创建必要目录"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.sound_effects_dir, exist_ok=True)

config = Config()