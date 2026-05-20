import os
import sys
import tempfile
import subprocess
import shutil
import cv2
import numpy as np
import platform
import copy
import glob
import pickle
import gc
import json
import hashlib
import queue
from datetime import datetime
from typing import Dict, Any, Optional, List
import threading
import traceback
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import config
from models import tasks, cancelled_tasks

MUSETALK_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "musetalk_cache")
from services.audio_processor import AudioProcessor
from services.subtitle_service import SubtitleService

class VideoGenerator:
    def __init__(self):
        self.output_dir = config.output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.audio_processor = AudioProcessor()
        self.subtitle_service = SubtitleService()

        self._musetalk_ready = False
        self._musetalk_models = {}
        self._musetalk_lock = threading.Lock()
        self._gpu_inference_lock = threading.Lock()

    @staticmethod
    def _release_gpu_memory(scope: str = "task"):
        """释放 GPU 显存缓存
        scope:
            "task"  — 仅清理推理中间产物（默认，每次任务结束调用）
            "full"  — 同上 + 强制回收所有 Python 垃圾对象
        """
        try:
            from services import wav2lip_model
            wav2lip_model.clear_video_cache()
        except Exception as e:
            print(f"[VideoGenerator] GPU memory release skipped: {e}")
        try:
            import torch, gc
            gc.collect()
            if scope == "full":
                gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                alloc = torch.cuda.memory_allocated() / (1024 ** 2)
                resv = torch.cuda.memory_reserved() / (1024 ** 2)
                print(f"[GPU Cleanup] scope={scope}, allocated: {alloc:.0f}MB / reserved: {resv:.0f}MB")
        except Exception:
            pass
    
    def get_video_url(self, task_id: str) -> str:
        """获取视频的完整URL地址"""
        return f"{config.base_url}/download/{task_id}"
    
    def show_completion_notification(self, video_path, task_id):
        """显示完成通知"""
        try:
            abs_path = os.path.abspath(video_path)
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            duration = self.get_video_duration(video_path)
            
            print("\n" + "="*80)
            print("🎉 视频生成完成！")
            print("="*80)
            print(f"📂 文件位置: {abs_path}")
            print(f"📊 文件大小: {file_size:.2f} MB")
            print(f"⏱️ 视频时长: {duration:.2f} 秒")
            print(f"🔢 任务ID: {task_id}")
            print(f"🌐 下载URL: {self.get_video_url(task_id)}")
            print("="*80)
            
            self.open_file_in_explorer(abs_path)
            
        except Exception as e:
            print(f"⚠️ 显示通知时出错: {e}")
    
    def get_video_duration(self, video_path):
        """获取视频时长"""
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error', '-show_entries', 
                'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 
                video_path
            ], capture_output=True, text=True)
            return float(result.stdout.strip())
        except:
            return 0

    def get_video_dimensions(self, video_path):
        """获取视频宽高 (width, height)，失败返回 (1920, 1080)"""
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height', '-of', 'csv=p=0',
                video_path
            ], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(',')
                if len(parts) >= 2:
                    return int(parts[0]), int(parts[1])
        except Exception:
            pass
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                if w > 0 and h > 0:
                    return w, h
        except Exception:
            pass
        return 1920, 1080
    
    def open_file_in_explorer(self, file_path):
        """在文件管理器中打开文件所在文件夹"""
        try:
            folder_path = os.path.dirname(file_path)
            system = platform.system()
            
            if system == "Windows":
                os.startfile(folder_path)
            elif system == "Darwin":
                subprocess.run(["open", folder_path])
            elif system == "Linux":
                subprocess.run(["xdg-open", folder_path])
            else:
                print(f"💡 提示: 视频已保存到: {folder_path}")
                
        except Exception as e:
            print(f"⚠️ 无法打开文件管理器: {e}")
            print(f"💡 请手动访问文件夹: {os.path.dirname(file_path)}")
    
    def _get_ubuntu_font(self):
        """查找可用字体"""
        fonts = [
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        ]
        
        for font_path in fonts:
            if os.path.exists(font_path):
                return font_path
        return None
    
    def _create_frosted_background_image(self, image_path, output_png, target_width=1920, target_height=1080,
                                          welcome_text="", topic_name="", is_first_page=True):
        """生成毛玻璃白色背景 + 标题文字的静态图片。
        - 底层：PPT 截图做高斯模糊（毛玻璃质感）
        - 叠加半透明白色蒙版
        - 主标题：topic_name（大号、深色）
        - 副标题：welcome_text（小号、灰色），仅在第一页显示
        """
        from PIL import Image, ImageDraw, ImageFont, ImageFilter

        try:
            img = Image.open(image_path).convert("RGB")
        except Exception:
            img = Image.new("RGB", (target_width, target_height), (255, 255, 255))

        img = img.resize((target_width, target_height), Image.LANCZOS)
        blurred = img.filter(ImageFilter.GaussianBlur(radius=30))

        overlay = Image.new("RGBA", (target_width, target_height), (255, 255, 255, 200))
        base = blurred.convert("RGBA")
        base = Image.alpha_composite(base, overlay)
        result = base.convert("RGB")

        draw = ImageDraw.Draw(result)

        font_path = self._get_ubuntu_font()
        try:
            font_title = ImageFont.truetype(font_path, 72) if font_path else ImageFont.load_default()
            font_sub = ImageFont.truetype(font_path, 42) if font_path else ImageFont.load_default()
        except Exception:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        title_color = (50, 50, 50)
        sub_color = (120, 120, 120)

        if topic_name:
            bbox = draw.textbbox((0, 0), topic_name, font=font_title)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = (target_width - tw) // 2
            ty = (target_height - th) // 2 - (40 if is_first_page and welcome_text else 0)
            draw.text((tx, ty), topic_name, fill=title_color, font=font_title)

        if is_first_page and welcome_text:
            bbox = draw.textbbox((0, 0), welcome_text, font=font_sub)
            sw, sh = bbox[2] - bbox[0], bbox[3] - bbox[1]
            sx = (target_width - sw) // 2
            sy = ty + th + 30 if topic_name else (target_height - sh) // 2
            draw.text((sx, sy), welcome_text, fill=sub_color, font=font_sub)

        result.save(output_png, "PNG")
        return output_png

    def create_background_video(self, image_path, duration, output_path, welcome_text, topic_name,
                                animation, animation_duration=6.0, target_width=1920, target_height=1080,
                                is_first_page=True):
        """创建背景视频：毛玻璃白色背景 + 标题，支持竖屏/横屏"""
        try:
            work_dir = os.path.dirname(output_path)
            bg_png = os.path.join(work_dir, "frosted_bg.png")
            self._create_frosted_background_image(
                image_path, bg_png, target_width, target_height,
                welcome_text, topic_name, is_first_page
            )

            img = cv2.imread(image_path)
            if img is None:
                print(f"❌ 无法读取图片: {image_path}")
                return False

            original_height, original_width = img.shape[:2]
            scale = max(target_width / original_width, target_height / original_height)
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)

            scaled_img_path = os.path.join(work_dir, "scaled_image.jpg")
            resize_cmd = f'ffmpeg -i "{image_path}" -vf "scale={new_width}:{new_height}" -y "{scaled_img_path}"'
            subprocess.run(resize_cmd, shell=True, check=True)

            temp_bg_path = os.path.join(work_dir, "temp_bg.mp4")
            bg_cmd = (
                f'ffmpeg -loop 1 -i "{bg_png}" -t {duration} '
                f'-c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -y "{temp_bg_path}"'
            )
            subprocess.run(bg_cmd, shell=True, check=True)

            if os.path.exists(scaled_img_path):
                if animation == "fly_in":
                    filter_complex = (
                        f'[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable[scaled];'
                        f'[0:v][scaled]overlay=x=\'if(lte(t,{animation_duration}),W-W*t/{animation_duration},0)\':y=0'
                    )
                elif animation == "fade_in":
                    filter_complex = (
                        f'[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable[scaled];'
                        f'[0:v][scaled]overlay=enable=\'between(t,0,{animation_duration})*t/{animation_duration}\':x=0:y=0'
                    )
                else:
                    filter_complex = (
                        f'[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable[scaled];'
                        f'[0:v][scaled]overlay=x=0:y=0'
                    )

                cmd = [
                    'ffmpeg', '-i', temp_bg_path, '-loop', '1', '-i', scaled_img_path,
                    '-filter_complex', filter_complex, '-t', str(duration),
                    '-c:v', 'libx264', '-crf', '18', '-preset', 'medium',
                    '-pix_fmt', 'yuv420p', '-y', output_path
                ]
                subprocess.run(cmd, check=True)
            else:
                shutil.copy2(temp_bg_path, output_path)

            for f in [temp_bg_path, scaled_img_path, bg_png]:
                if os.path.exists(f):
                    os.remove(f)

            return True
        except Exception as e:
            print(f"❌❌❌❌ 背景视频创建失败: {e}")
            return False
    
    def run_wav2lip(self, face_video, audio_path, output_path):
        """运行Wav2Lip（优先使用预加载模型，失败时回退到subprocess）"""
        try:
            from services.wav2lip_model import _model as preloaded_model
            if preloaded_model is not None:
                return self._run_wav2lip_preloaded(face_video, audio_path, output_path)
        except Exception:
            pass
        return self._run_wav2lip_subprocess(face_video, audio_path, output_path)

    def _run_wav2lip_preloaded(self, face_video, audio_path, output_path):
        """使用预加载模型运行Wav2Lip（快速，无冷启动）"""
        try:
            from services import wav2lip_model
            print("[Wav2Lip] Using preloaded model (fast path)")
            result = wav2lip_model.infer(
                os.path.abspath(face_video),
                os.path.abspath(audio_path),
                os.path.abspath(output_path)
            )
            if result:
                return True
            print("[Wav2Lip] Preloaded inference failed, falling back to subprocess")
            return self._run_wav2lip_subprocess(face_video, audio_path, output_path)
        except Exception as e:
            print(f"[Wav2Lip] Preloaded error: {e}, falling back to subprocess")
            return self._run_wav2lip_subprocess(face_video, audio_path, output_path)

    def _run_wav2lip_subprocess(self, face_video, audio_path, output_path):
        """运行Wav2Lip（原始subprocess方式，作为备选）"""
        try:
            if not os.path.exists(config.wav2lip_checkpoint):
                print("❌❌❌❌ Wav2Lip模型文件不存在")
                return False
            
            cmd = [
                "python", "inference.py",
                "--checkpoint_path", config.wav2lip_checkpoint,
                "--face", os.path.abspath(face_video),
                "--audio", os.path.abspath(audio_path),
                "--outfile", os.path.abspath(output_path)
            ]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=500,
                cwd=config.wav2lip_dir
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                return True
            else:
                print("❌❌❌❌ Wav2Lip失败")
                return False
        except Exception as e:
            print(f"❌❌❌❌ Wav2Lip异常: {e}")
            return False
    
    @staticmethod
    def _auto_batch_size(device, fp16: bool) -> int:
        """根据 GPU 可用显存自动计算最大 batch_size（保守策略）"""
        import torch
        try:
            free = torch.cuda.mem_get_info(device)[0] / (1024 ** 3)
        except Exception:
            return config.musetalk_batch_size
        per_sample_gb = 0.045 if fp16 else 0.09
        headroom_gb = 2.0
        usable = max(free - headroom_gb, 1.0)
        bs = int(usable / per_sample_gb)
        bs = max(8, min(bs, 128))
        bs = (bs // 8) * 8
        return bs

    def _init_musetalk(self):
        """懒加载 MuseTalk 模型（线程安全，仅加载一次）
        优化：torch.compile 加速、自适应 batch_size、TensorRT 探测
        """
        if self._musetalk_ready:
            return
        with self._musetalk_lock:
            if self._musetalk_ready:
                return
            print("[MuseTalk] 开始加载模型...")
            import torch
            import time as _time
            t0 = _time.time()

            musetalk_dir = config.musetalk_dir
            if musetalk_dir not in sys.path:
                sys.path.insert(0, musetalk_dir)

            saved_cwd = os.getcwd()
            try:
                os.chdir(musetalk_dir)

                from musetalk.utils.utils import load_all_model, datagen
                from musetalk.utils.preprocessing import (
                    get_landmark_and_bbox, read_imgs, coord_placeholder,
                )
                from musetalk.utils.blending import get_image, get_image_prepare_material, get_image_blending
                from musetalk.utils.face_parsing import FaceParsing
                from musetalk.utils.audio_processor import AudioProcessor as MTAudioProcessor
                from transformers import WhisperModel

                device = torch.device(
                    f"cuda:{config.musetalk_gpu_id}"
                    if torch.cuda.is_available() else "cpu"
                )

                vae, unet, pe = load_all_model(
                    unet_model_path=config.musetalk_unet_path,
                    vae_type=config.musetalk_vae_type,
                    unet_config=config.musetalk_unet_config,
                    device=device,
                )
                timesteps = torch.tensor([0], device=device)

                if config.musetalk_use_float16:
                    pe = pe.half()
                    vae.vae = vae.vae.half()
                    unet.model = unet.model.half()

                pe = pe.to(device)
                vae.vae = vae.vae.to(device)
                unet.model = unet.model.to(device)

                # ── torch.compile 已禁用 ──
                # PyTorch 2.3 + diffusers UNet2DConditionModel + CUDA Graphs 存在兼容性问题
                # (CUDA capture internal assert / dynamic batch shape 不兼容)
                # 保留其他优化：FP16 + 自适应 batch + 单图复用 + 静默帧跳过
                print("[MuseTalk] torch.compile 已跳过（PyTorch 2.3 + UNet CUDA Graphs 兼容性问题）")

                # ── 自适应 batch_size ──
                auto_bs = self._auto_batch_size(device, config.musetalk_use_float16)
                if auto_bs > config.musetalk_batch_size:
                    print(f"[MuseTalk] 自适应 batch_size: {config.musetalk_batch_size} -> {auto_bs}")
                    config.musetalk_batch_size = auto_bs

                mt_audio = MTAudioProcessor(
                    feature_extractor_path=config.musetalk_whisper_dir,
                )
                weight_dtype = unet.model.dtype
                whisper = WhisperModel.from_pretrained(config.musetalk_whisper_dir)
                whisper = whisper.to(device=device, dtype=weight_dtype).eval()
                whisper.requires_grad_(False)

                fp = FaceParsing(left_cheek_width=90, right_cheek_width=90)

                self._musetalk_models = {
                    "vae": vae,
                    "unet": unet,
                    "pe": pe,
                    "whisper": whisper,
                    "audio_processor": mt_audio,
                    "face_parsing": fp,
                    "device": device,
                    "timesteps": timesteps,
                    "weight_dtype": weight_dtype,
                    "datagen": datagen,
                    "get_landmark_and_bbox": get_landmark_and_bbox,
                    "read_imgs": read_imgs,
                    "coord_placeholder": coord_placeholder,
                    "get_image": get_image,
                    "get_image_prepare_material": get_image_prepare_material,
                    "get_image_blending": get_image_blending,
                }
                self._musetalk_ready = True
                elapsed = _time.time() - t0
                mem_alloc = torch.cuda.memory_allocated(device) / (1024 ** 2)
                mem_resv = torch.cuda.memory_reserved(device) / (1024 ** 2)
                print(
                    f"[MuseTalk] 模型加载完成 ({elapsed:.1f}s) — "
                    f"FP16={config.musetalk_use_float16}, batch_size={config.musetalk_batch_size}, "
                    f"GPU={config.musetalk_gpu_id}, VRAM={mem_alloc:.0f}/{mem_resv:.0f}MB"
                )
            except Exception as e:
                print(f"[MuseTalk] 模型加载失败: {e}")
                traceback.print_exc()
                raise
            finally:
                os.chdir(saved_cwd)

    @staticmethod
    def _detect_silent_frames(whisper_chunks, threshold: float = 0.02):
        """检测静默帧：whisper 特征能量低于阈值的帧标记为静默，可跳过 UNet 推理"""
        import torch
        silent = []
        for i, chunk in enumerate(whisper_chunks):
            energy = chunk.abs().mean().item() if isinstance(chunk, torch.Tensor) else 0
            silent.append(energy < threshold)
        return silent

    # ── MuseTalk 预处理缓存 ──

    @staticmethod
    def _face_file_hash(filepath: str) -> str:
        """基于文件内容计算唯一 hash（文件大小 + 首尾各 64KB），不依赖 mtime"""
        st = os.stat(filepath)
        h = hashlib.md5()
        h.update(f"size:{st.st_size}".encode())
        with open(filepath, "rb") as f:
            head = f.read(65536)
            h.update(head)
            if st.st_size > 131072:
                f.seek(-65536, 2)
                h.update(f.read(65536))
        return h.hexdigest()

    @staticmethod
    def _read_video_frames(filepath: str):
        """从视频/图片文件读取帧列表和 fps"""
        ext = os.path.splitext(filepath)[1].lower()
        is_single = ext not in ('.mp4', '.avi', '.mov', '.mkv', '.flv')
        if is_single:
            frames = [cv2.imread(filepath)]
            return frames, 25.0, True
        cap = cv2.VideoCapture(filepath)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()
        return frames, fps, False

    def _get_cache_dir(self, face_path: str) -> str:
        fhash = self._face_file_hash(face_path)
        return os.path.join(MUSETALK_CACHE_DIR, fhash)

    def _load_preprocess_cache(self, face_path: str, device):
        """尝试加载预处理缓存，命中返回 dict，未命中返回 None"""
        import torch
        cache_dir = self._get_cache_dir(face_path)
        meta_path = os.path.join(cache_dir, "meta.json")
        if not os.path.exists(meta_path):
            return None
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            with open(os.path.join(cache_dir, "coords.pkl"), "rb") as f:
                coord_list = pickle.load(f)
            latent_list = torch.load(
                os.path.join(cache_dir, "latents.pt"),
                map_location=device, weights_only=True,
            )
            with open(os.path.join(cache_dir, "masks.pkl"), "rb") as f:
                mask_data = pickle.load(f)
            return {
                "meta": meta,
                "coord_list": coord_list,
                "input_latent_list": latent_list,
                "mask_list": [item[0] for item in mask_data],
                "mask_crop_box_list": [item[1] for item in mask_data],
                "fps": meta["fps"],
                "is_single_image": meta["is_single_image"],
                "extra_margin": meta.get("extra_margin", 10),
            }
        except Exception as e:
            print(f"[MuseTalk Cache] 加载缓存失败，将重新计算: {e}")
            return None

    def _save_preprocess_cache(self, face_path: str, coord_list, input_latent_list,
                                mask_data_pairs, fps, is_single_image, extra_margin, n_frames):
        """保存预处理缓存到磁盘"""
        import torch
        cache_dir = self._get_cache_dir(face_path)
        os.makedirs(cache_dir, exist_ok=True)
        try:
            with open(os.path.join(cache_dir, "coords.pkl"), "wb") as f:
                pickle.dump(coord_list, f)
            torch.save(input_latent_list, os.path.join(cache_dir, "latents.pt"))
            with open(os.path.join(cache_dir, "masks.pkl"), "wb") as f:
                pickle.dump(mask_data_pairs, f)
            meta = {
                "source_path": face_path,
                "hash": self._face_file_hash(face_path),
                "n_frames": n_frames,
                "fps": fps,
                "is_single_image": is_single_image,
                "extra_margin": extra_margin,
                "created_at": datetime.now().isoformat(),
            }
            with open(os.path.join(cache_dir, "meta.json"), "w") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            cache_size = sum(
                os.path.getsize(os.path.join(cache_dir, fn))
                for fn in os.listdir(cache_dir)
            )
            print(f"[MuseTalk Cache] 已保存缓存: {cache_dir} ({cache_size / 1024 / 1024:.1f} MB)")
        except Exception as e:
            print(f"[MuseTalk Cache] 保存缓存失败: {e}")

    def preprocess_face(self, face_path: str) -> dict:
        """对指定 face 文件执行完整预处理并缓存。返回状态 dict。"""
        import time as _time
        import torch

        abs_face = os.path.abspath(face_path)
        if not os.path.exists(abs_face):
            return {"status": "error", "message": f"文件不存在: {abs_face}"}

        cache_dir = self._get_cache_dir(abs_face)
        if os.path.exists(os.path.join(cache_dir, "meta.json")):
            with open(os.path.join(cache_dir, "meta.json"), "r") as f:
                meta = json.load(f)
            return {"status": "cached", "message": "缓存已存在", "meta": meta}

        t0 = _time.time()
        self._init_musetalk()
        m = self._musetalk_models
        device = m["device"]
        vae = m["vae"]
        get_landmark_and_bbox = m["get_landmark_and_bbox"]
        coord_placeholder = m["coord_placeholder"]
        fp = m["face_parsing"]
        get_image_prepare_material_fn = m["get_image_prepare_material"]

        frames, fps, is_single_image = self._read_video_frames(abs_face)
        if not frames or frames[0] is None:
            return {"status": "error", "message": "无法读取帧"}

        n_imgs = len(frames)
        extra_margin = 10

        tmp_dir = tempfile.mkdtemp()
        try:
            if is_single_image or n_imgs <= 4:
                tmp_paths = []
                for idx, frm in enumerate(frames):
                    p = os.path.join(tmp_dir, f"{idx:08d}.png")
                    cv2.imwrite(p, frm)
                    tmp_paths.append(p)
                coord_list, _ = get_landmark_and_bbox(tmp_paths, upperbondrange=0)
            else:
                detect_step = min(10, max(1, n_imgs // 20))
                key_indices = list(range(0, n_imgs, detect_step))
                if key_indices[-1] != n_imgs - 1:
                    key_indices.append(n_imgs - 1)
                key_paths = []
                for idx in key_indices:
                    p = os.path.join(tmp_dir, f"{idx:08d}.png")
                    cv2.imwrite(p, frames[idx])
                    key_paths.append(p)
                key_coords, _ = get_landmark_and_bbox(key_paths, upperbondrange=0)
                coord_list = [None] * n_imgs
                for ki, idx in enumerate(key_indices):
                    coord_list[idx] = key_coords[ki]
                for seg in range(len(key_indices) - 1):
                    i_s, i_e = key_indices[seg], key_indices[seg + 1]
                    c0, c1 = coord_list[i_s], coord_list[i_e]
                    if c0 == coord_placeholder or c1 == coord_placeholder:
                        fill = c0 if c0 != coord_placeholder else c1
                        for k in range(i_s, i_e + 1):
                            if coord_list[k] is None:
                                coord_list[k] = fill
                        continue
                    span = i_e - i_s
                    for k in range(i_s + 1, i_e):
                        t = (k - i_s) / span
                        coord_list[k] = tuple(int(a * (1 - t) + b * t) for a, b in zip(c0, c1))
                for k in range(n_imgs):
                    if coord_list[k] is None:
                        coord_list[k] = coord_list[k - 1] if k > 0 else coord_placeholder
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        input_latent_list = []
        for i in range(n_imgs):
            bbox = coord_list[i]
            if bbox == coord_placeholder:
                continue
            x1, y1, x2, y2 = bbox
            y2 = min(y2 + extra_margin, frames[i].shape[0])
            crop = frames[i][y1:y2, x1:x2]
            crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_LANCZOS4)
            input_latent_list.append(vae.get_latents_for_unet(crop))

        mask_data_pairs = []
        for i in range(n_imgs):
            bbox = coord_list[i]
            if bbox == coord_placeholder:
                mask_data_pairs.append((None, None))
                continue
            x1, y1, x2, y2 = bbox
            y2 = min(y2 + extra_margin, frames[i].shape[0])
            try:
                mask, crop_box = get_image_prepare_material_fn(
                    frames[i], [x1, y1, x2, y2], fp=fp, mode="jaw",
                )
                mask_data_pairs.append((mask, crop_box))
            except Exception:
                mask_data_pairs.append((None, None))

        self._save_preprocess_cache(
            abs_face, coord_list, input_latent_list,
            mask_data_pairs, fps, is_single_image, extra_margin, n_imgs,
        )

        elapsed = _time.time() - t0
        torch.cuda.empty_cache()
        gc.collect()

        return {
            "status": "ok",
            "message": f"预处理完成: {n_imgs} 帧, {len(input_latent_list)} 有效, 耗时 {elapsed:.1f}s",
            "n_frames": n_imgs,
            "n_valid": len(input_latent_list),
            "elapsed": round(elapsed, 1),
        }

    @staticmethod
    def list_cache_entries() -> List[dict]:
        """列出所有预处理缓存条目"""
        entries = []
        if not os.path.isdir(MUSETALK_CACHE_DIR):
            return entries
        for name in os.listdir(MUSETALK_CACHE_DIR):
            meta_path = os.path.join(MUSETALK_CACHE_DIR, name, "meta.json")
            if not os.path.exists(meta_path):
                continue
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                cache_dir = os.path.join(MUSETALK_CACHE_DIR, name)
                size = sum(
                    os.path.getsize(os.path.join(cache_dir, fn))
                    for fn in os.listdir(cache_dir)
                )
                entries.append({
                    "hash": name,
                    "source_path": meta.get("source_path", ""),
                    "n_frames": meta.get("n_frames", 0),
                    "fps": meta.get("fps", 0),
                    "is_single_image": meta.get("is_single_image", False),
                    "created_at": meta.get("created_at", ""),
                    "size_mb": round(size / 1024 / 1024, 1),
                })
            except Exception:
                continue
        return entries

    @staticmethod
    def clear_cache(cache_hash: str = None) -> dict:
        """清除指定或全部缓存"""
        if not os.path.isdir(MUSETALK_CACHE_DIR):
            return {"status": "ok", "message": "无缓存目录"}
        if cache_hash:
            target = os.path.join(MUSETALK_CACHE_DIR, cache_hash)
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
                return {"status": "ok", "message": f"已清除缓存: {cache_hash}"}
            return {"status": "error", "message": f"缓存不存在: {cache_hash}"}
        count = 0
        for name in os.listdir(MUSETALK_CACHE_DIR):
            p = os.path.join(MUSETALK_CACHE_DIR, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
                count += 1
        return {"status": "ok", "message": f"已清除 {count} 个缓存"}

    def run_musetalk(self, face_video, audio_path, output_path, task_id: str = ""):
        """使用 MuseTalk 生成高清口型同步视频（v5: 预处理缓存 + NVENC + 流水线并行）"""
        import torch
        import time as _time
        tmp = None
        ffmpeg_pipe = None
        compose_queue = None
        compose_thread = None
        # 与队列中「静默帧」占位 None 区分，仅供 finally 唤醒 compose 线程退出
        _compose_queue_done = object()
        try:
            t0 = _time.time()
            if self._gpu_inference_lock.locked():
                print(f"[MuseTalk] GPU 正忙，排队等待... ({_time.time()-t0:.1f}s)")
            self._gpu_inference_lock.acquire()
            print(f"[MuseTalk] GPU 锁已获取 ({_time.time()-t0:.1f}s)")
            self._init_musetalk()
            m = self._musetalk_models
            device = m["device"]
            vae, unet, pe = m["vae"], m["unet"], m["pe"]
            whisper_model = m["whisper"]
            mt_audio = m["audio_processor"]
            fp = m["face_parsing"]
            timesteps = m["timesteps"]
            weight_dtype = m["weight_dtype"]
            datagen_fn = m["datagen"]
            get_landmark_and_bbox = m["get_landmark_and_bbox"]
            coord_placeholder = m["coord_placeholder"]
            get_image_fn = m["get_image"]
            get_image_prepare_material_fn = m["get_image_prepare_material"]
            get_image_blending_fn = m["get_image_blending"]

            tmp = tempfile.mkdtemp()
            frames_dir = os.path.join(tmp, "frames")
            os.makedirs(frames_dir, exist_ok=True)

            abs_face = os.path.abspath(face_video)
            abs_audio = os.path.abspath(audio_path)
            abs_output = os.path.abspath(output_path)

            extra_margin = 10

            # ── 尝试加载预处理缓存 ──
            cache_data = self._load_preprocess_cache(abs_face, device)

            if cache_data is not None:
                print(f"[MuseTalk] 缓存命中! 跳过阶段 2 (DWPose + VAE + FaceParsing) ({_time.time()-t0:.1f}s)")
                coord_list = cache_data["coord_list"]
                input_latent_list = cache_data["input_latent_list"]
                pre_mask_list = cache_data["mask_list"]
                pre_mask_crop_box_list = cache_data["mask_crop_box_list"]
                fps = cache_data["fps"]
                is_single_image = cache_data["is_single_image"]
                extra_margin = cache_data["extra_margin"]
                frame_list, _, _ = self._read_video_frames(abs_face)
                if not frame_list or frame_list[0] is None:
                    print("[MuseTalk] 未能读取输入帧")
                    return False
                print(f"[MuseTalk] 从缓存加载: {len(coord_list)} coords, "
                      f"{len(input_latent_list)} latents, {len(pre_mask_list)} masks, "
                      f"帧重读 {len(frame_list)} 帧 ({_time.time()-t0:.1f}s)")
                has_precomputed_masks = True
            else:
                print(f"[MuseTalk] 缓存未命中，执行完整预处理 ({_time.time()-t0:.1f}s)")
                has_precomputed_masks = False
                pre_mask_list = None
                pre_mask_crop_box_list = None

                frame_list, fps, is_single_image = self._read_video_frames(abs_face)
                if not frame_list or frame_list[0] is None:
                    print("[MuseTalk] 未能读取输入帧")
                    return False
                if not is_single_image:
                    print(f"[MuseTalk] VideoCapture 读入 {len(frame_list)} 帧到内存 ({_time.time()-t0:.1f}s)")

                # ── 阶段 2/5：人脸检测与 VAE 编码 ──
                n_imgs = len(frame_list)
                if is_single_image:
                    print(f"[MuseTalk] 阶段2/5: 单图模式人脸检测... ({_time.time()-t0:.1f}s)")
                    tmp_img_path = os.path.join(frames_dir, "00000000.png")
                    cv2.imwrite(tmp_img_path, frame_list[0])
                    coord_list, _ = get_landmark_and_bbox([tmp_img_path], upperbondrange=0)
                    if not coord_list or coord_list[0] == coord_placeholder:
                        print("[MuseTalk] 未检测到有效人脸")
                        return False
                    bbox = coord_list[0]
                    x1, y1, x2, y2 = bbox
                    y2 = min(y2 + extra_margin, frame_list[0].shape[0])
                    crop = frame_list[0][y1:y2, x1:x2]
                    crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                    input_latent_list = [vae.get_latents_for_unet(crop)]
                    print(f"[MuseTalk] 单图模式：检测 1 帧 + VAE 编码 1 次 ({_time.time()-t0:.1f}s)")
                elif n_imgs <= 4:
                    print(f"[MuseTalk] 阶段2/5: 人脸检测（全量 {n_imgs} 帧）... ({_time.time()-t0:.1f}s)")
                    tmp_paths = []
                    for idx, frm in enumerate(frame_list):
                        p = os.path.join(frames_dir, f"{idx:08d}.png")
                        cv2.imwrite(p, frm)
                        tmp_paths.append(p)
                    coord_list, _ = get_landmark_and_bbox(tmp_paths, upperbondrange=0)
                    input_latent_list = []
                    for bbox, frame in zip(coord_list, frame_list):
                        if bbox == coord_placeholder:
                            continue
                        x1, y1, x2, y2 = bbox
                        y2 = min(y2 + extra_margin, frame.shape[0])
                        crop = frame[y1:y2, x1:x2]
                        crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                        input_latent_list.append(vae.get_latents_for_unet(crop))
                    print(f"[MuseTalk] 人脸检测完成, {len(input_latent_list)} 帧 ({_time.time()-t0:.1f}s)")
                else:
                    detect_step = min(10, max(1, n_imgs // 20))
                    key_indices = list(range(0, n_imgs, detect_step))
                    if key_indices[-1] != n_imgs - 1:
                        key_indices.append(n_imgs - 1)
                    key_paths = []
                    for idx in key_indices:
                        p = os.path.join(frames_dir, f"{idx:08d}.png")
                        cv2.imwrite(p, frame_list[idx])
                        key_paths.append(p)
                    print(f"[MuseTalk] 阶段2/5: 密集人脸检测 ({len(key_paths)}/{n_imgs} 帧, step={detect_step})... ({_time.time()-t0:.1f}s)")
                    key_coords, _ = get_landmark_and_bbox(key_paths, upperbondrange=0)

                    coord_list = [None] * n_imgs
                    for ki, idx in enumerate(key_indices):
                        coord_list[idx] = key_coords[ki]
                    for seg in range(len(key_indices) - 1):
                        i_start, i_end = key_indices[seg], key_indices[seg + 1]
                        c0, c1 = coord_list[i_start], coord_list[i_end]
                        if c0 == coord_placeholder or c1 == coord_placeholder:
                            fill = c0 if c0 != coord_placeholder else c1
                            for k in range(i_start, i_end + 1):
                                if coord_list[k] is None:
                                    coord_list[k] = fill
                            continue
                        span = i_end - i_start
                        for k in range(i_start + 1, i_end):
                            t = (k - i_start) / span
                            coord_list[k] = tuple(
                                int(a * (1 - t) + b * t) for a, b in zip(c0, c1)
                            )
                    for k in range(n_imgs):
                        if coord_list[k] is None:
                            coord_list[k] = coord_list[k - 1] if k > 0 else coord_placeholder
                    print(f"[MuseTalk] 密集检测 + 插值完成 ({_time.time()-t0:.1f}s)")

                    print(f"[MuseTalk] VAE 全帧编码 ({n_imgs} 帧)... ({_time.time()-t0:.1f}s)")
                    input_latent_list = []
                    for i in range(n_imgs):
                        bbox = coord_list[i]
                        if bbox == coord_placeholder:
                            continue
                        frame = frame_list[i]
                        x1, y1, x2, y2 = bbox
                        y2 = min(y2 + extra_margin, frame.shape[0])
                        crop = frame[y1:y2, x1:x2]
                        crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                        input_latent_list.append(vae.get_latents_for_unet(crop))
                    print(f"[MuseTalk] VAE 编码完成, {len(input_latent_list)} 帧 ({_time.time()-t0:.1f}s)")

                # 首次处理：计算 FaceParsing 并保存缓存
                mask_data_pairs = []
                n_imgs = len(frame_list)
                for i in range(n_imgs):
                    bbox = coord_list[i]
                    if bbox == coord_placeholder:
                        mask_data_pairs.append((None, None))
                        continue
                    x1, y1, x2, y2 = bbox
                    y2 = min(y2 + extra_margin, frame_list[i].shape[0])
                    try:
                        mask, crop_box = get_image_prepare_material_fn(
                            frame_list[i], [x1, y1, x2, y2], fp=fp, mode="jaw",
                        )
                        mask_data_pairs.append((mask, crop_box))
                    except Exception:
                        mask_data_pairs.append((None, None))
                print(f"[MuseTalk] FaceParsing 掩码全帧计算完成 ({_time.time()-t0:.1f}s)")

                pre_mask_list = [p[0] for p in mask_data_pairs]
                pre_mask_crop_box_list = [p[1] for p in mask_data_pairs]
                has_precomputed_masks = True

                self._save_preprocess_cache(
                    abs_face, coord_list, input_latent_list,
                    mask_data_pairs, fps, is_single_image, extra_margin, n_imgs,
                )
                del mask_data_pairs

            if not input_latent_list:
                print("[MuseTalk] 未检测到有效人脸")
                return False

            # ── 阶段 1/5：音频特征 ──
            print(f"[MuseTalk] 阶段1/5: 提取音频特征... ({_time.time()-t0:.1f}s)")
            whisper_feats, librosa_len = mt_audio.get_audio_feature(abs_audio)
            whisper_chunks = mt_audio.get_whisper_chunk(
                whisper_feats, device, weight_dtype, whisper_model, librosa_len, fps=fps,
            )
            del whisper_feats
            total_frames = len(whisper_chunks)
            print(f"[MuseTalk] 音频特征提取完成, {total_frames} chunks ({_time.time()-t0:.1f}s)")

            frame_list_cycle = frame_list + frame_list[::-1]
            coord_list_cycle = coord_list + coord_list[::-1]
            latent_list_cycle = input_latent_list + input_latent_list[::-1]

            if has_precomputed_masks:
                mask_list_cycle = pre_mask_list + pre_mask_list[::-1]
                mask_crop_box_list_cycle = pre_mask_crop_box_list + pre_mask_crop_box_list[::-1]
            else:
                mask_list_cycle = None
                mask_crop_box_list_cycle = None

            print(f"[MuseTalk] 预处理完成, {len(input_latent_list)} 有效帧 ({_time.time()-t0:.1f}s)")

            # ── 增量推理：检测静默帧 ──
            silent_mask = self._detect_silent_frames(whisper_chunks)
            n_silent = sum(silent_mask)
            n_active = total_frames - n_silent
            if n_silent > 0:
                print(f"[MuseTalk] 增量推理: {n_silent} 静默帧将跳过 UNet，仅推理 {n_active} 活跃帧")

            # ── 阶段 3/5：UNet 推理（流水线：边推理边送合成线程）──
            batch_size = config.musetalk_batch_size
            print(f"[MuseTalk] 阶段3/5: UNet 推理 + 流水线合成 (batch={batch_size})... ({_time.time()-t0:.1f}s)")

            active_indices = [i for i, s in enumerate(silent_mask) if not s]
            active_chunks = [whisper_chunks[i] for i in active_indices]
            active_latent_list = [latent_list_cycle[i % len(latent_list_cycle)] for i in active_indices]

            # 构建 frame_idx -> active_order 映射，用于流水线
            active_set = set(active_indices)

            # ── 阶段 4/5：合成线程（消费者）──
            first_frame = frame_list_cycle[0]
            frame_h, frame_w = first_frame.shape[:2]
            temp_vid = os.path.join(tmp, "temp.mp4")
            ffmpeg_pipe = subprocess.Popen(
                [
                    "ffmpeg", "-y", "-v", "warning",
                    "-f", "rawvideo", "-pix_fmt", "bgr24",
                    "-s", f"{frame_w}x{frame_h}",
                    "-r", str(fps), "-i", "-",
                    "-vcodec", "h264_nvenc", "-pix_fmt", "yuv420p",
                    "-qp", "18", "-preset", "p4", temp_vid,
                ],
                stdin=subprocess.PIPE,
            )

            compose_queue = queue.Queue(maxsize=64)
            compose_error = [None]

            def _compose_worker():
                """合成线程：从队列取帧，blending + 写入 FFmpeg 管道"""
                try:
                    last_combined = None
                    for frame_i in range(total_frames):
                        item = compose_queue.get(timeout=120)
                        if item is _compose_queue_done:
                            break
                        res_frame_or_none = item

                        cyc_idx = frame_i % len(coord_list_cycle)
                        bbox = coord_list_cycle[cyc_idx]
                        ori = frame_list_cycle[cyc_idx]
                        x1, y1, x2, y2 = bbox
                        y2 = min(y2 + extra_margin, ori.shape[0])
                        adj_box = [x1, y1, x2, y2]

                        if res_frame_or_none is not None:
                            try:
                                res_frame = cv2.resize(
                                    res_frame_or_none.astype(np.uint8), (x2 - x1, y2 - y1)
                                )
                            except Exception:
                                combined = last_combined if last_combined is not None else ori
                                ffmpeg_pipe.stdin.write(combined.tobytes())
                                continue

                            if mask_list_cycle is not None:
                                m_idx = cyc_idx
                                mask = mask_list_cycle[m_idx]
                                crop_box = mask_crop_box_list_cycle[m_idx]
                                if mask is not None:
                                    combined = get_image_blending_fn(
                                        ori, res_frame, adj_box, mask, crop_box,
                                    )
                                else:
                                    combined = get_image_fn(
                                        ori, res_frame, adj_box, mode="jaw", fp=fp,
                                    )
                            else:
                                combined = get_image_fn(
                                    ori, res_frame, adj_box, mode="jaw", fp=fp,
                                )
                            last_combined = combined
                        else:
                            combined = last_combined if last_combined is not None else ori

                        ffmpeg_pipe.stdin.write(combined.tobytes())
                except Exception as e:
                    compose_error[0] = e

            compose_thread = threading.Thread(target=_compose_worker, daemon=True)
            compose_thread.start()

            # ── UNet 推理（生产者）──
            gen = datagen_fn(
                active_chunks, active_latent_list,
                batch_size=batch_size, device=device,
            )

            active_cursor = 0
            frame_cursor = 0
            batch_count = 0
            total_batches = max(1, (n_active + batch_size - 1) // batch_size)

            active_res_buffer = {}

            with torch.no_grad():
                for whisper_batch, latent_batch in gen:
                    if task_id and task_id in cancelled_tasks:
                        print(f"[MuseTalk] 检测到任务取消，中止推理 (batch {batch_count}/{total_batches})")
                        raise Exception("任务已被用户取消")

                    audio_feat = pe(whisper_batch)
                    latent_batch = latent_batch.to(dtype=unet.model.dtype)
                    ts = timesteps.expand(latent_batch.shape[0])
                    pred = unet.model(
                        latent_batch, ts,
                        encoder_hidden_states=audio_feat,
                    ).sample
                    recon = vae.decode_latents(pred)

                    for res_f in recon:
                        if active_cursor < len(active_indices):
                            active_res_buffer[active_indices[active_cursor]] = res_f
                            active_cursor += 1

                    while frame_cursor < total_frames:
                        if frame_cursor in active_set and frame_cursor not in active_res_buffer:
                            break
                        res = active_res_buffer.pop(frame_cursor, None)
                        compose_queue.put(res)
                        frame_cursor += 1

                    batch_count += 1
                    if batch_count % 5 == 0 or batch_count == total_batches:
                        print(f"[MuseTalk] 推理进度: {batch_count}/{total_batches} batches ({_time.time()-t0:.1f}s)")

            while frame_cursor < total_frames:
                res = active_res_buffer.pop(frame_cursor, None)
                compose_queue.put(res)
                frame_cursor += 1

            del active_chunks, active_latent_list, gen, active_res_buffer
            torch.cuda.empty_cache()

            compose_thread.join()
            if compose_error[0] is not None:
                raise compose_error[0]

            ffmpeg_pipe.stdin.close()
            ffmpeg_pipe.wait()

            print(f"[MuseTalk] UNet 推理 + 帧合成 + 编码完成 ({_time.time()-t0:.1f}s)")

            # ── 阶段 5/5：混合音频 ──
            print(f"[MuseTalk] 阶段5/5: 混合音频... ({_time.time()-t0:.1f}s)")
            cmd_mux = f'ffmpeg -y -v warning -i "{abs_audio}" -i "{temp_vid}" "{abs_output}"'
            subprocess.run(cmd_mux, shell=True, check=True)

            shutil.rmtree(tmp, ignore_errors=True)
            tmp = None

            if os.path.exists(abs_output):
                elapsed = _time.time() - t0
                fps_actual = total_frames / max(elapsed, 0.01)
                cache_status = "cached" if cache_data is not None else "first_run"
                print(
                    f"[MuseTalk] 视频生成成功: {abs_output} — "
                    f"{total_frames} 帧, 总耗时 {elapsed:.1f}s, 实际 {fps_actual:.1f} fps "
                    f"[{cache_status}]"
                )
                return True
            return False

        except Exception as e:
            print(f"[MuseTalk] 推理异常: {e}")
            traceback.print_exc()
            return False
        finally:
            # 1) 清理 compose_thread：向队列发结束哨兵使线程退出
            if compose_queue is not None:
                try:
                    compose_queue.put_nowait(_compose_queue_done)
                except Exception:
                    pass
            if compose_thread is not None and compose_thread.is_alive():
                compose_thread.join(timeout=5)
                if compose_thread.is_alive():
                    print("[MuseTalk] 警告: compose_thread 未在 5s 内退出")
            # 2) 清理 FFmpeg 子进程
            if ffmpeg_pipe is not None:
                try:
                    if ffmpeg_pipe.stdin and not ffmpeg_pipe.stdin.closed:
                        ffmpeg_pipe.stdin.close()
                except Exception:
                    pass
                try:
                    ffmpeg_pipe.terminate()
                    ffmpeg_pipe.wait(timeout=5)
                except Exception:
                    try:
                        ffmpeg_pipe.kill()
                        ffmpeg_pipe.wait(timeout=3)
                    except Exception:
                        pass
            # 3) 释放 GPU 锁
            try:
                self._gpu_inference_lock.release()
                print("[MuseTalk] GPU 锁已释放")
            except RuntimeError:
                pass
            # 4) 清理临时目录
            if tmp and os.path.exists(tmp):
                shutil.rmtree(tmp, ignore_errors=True)
            # 5) 清理推理中间张量 + CUDA 显存
            try:
                import torch as _torch
                gc.collect()
                if _torch.cuda.is_available():
                    _torch.cuda.empty_cache()
                    alloc = _torch.cuda.memory_allocated() / (1024 ** 2)
                    resv = _torch.cuda.memory_reserved() / (1024 ** 2)
                    print(f"[MuseTalk Cleanup] allocated: {alloc:.0f}MB / reserved: {resv:.0f}MB")
            except Exception:
                pass
            print("[MuseTalk] 资源已清理 (线程/子进程/GPU/临时文件)")

    def resize_digital_human(self, input_video, output_video, size_ratio):
        """调整数字人大小，保持原始宽高比（竖屏保持竖屏，横屏保持横屏）"""
        try:
            w, h = self.get_video_dimensions(input_video)
            new_width = int(w * size_ratio)
            new_height = int(h * size_ratio)
            if new_width < 1:
                new_width = 1
            if new_height < 1:
                new_height = 1
            cmd = f'ffmpeg -i "{input_video}" -vf "scale={new_width}:{new_height}" -c:a copy -y "{output_video}"'
            subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e:
            print(f"❌❌❌❌ 数字人大小调整失败: {e}")
            return False
    
    def basic_segmentation(self, input_video, output_video, background_color="green", similarity=0.1, blend=0.2):
        """基础人像分割：绿幕 -> 透明背景"""
        try:
            color_map = {
                "green": "0x00FF00",
                "blue": "0x0000FF",
                "red": "0xFF0000"
            }
            color_value = color_map.get(background_color.lower(), "0x00FF00")

            cmd = (
                f'ffmpeg -i "{input_video}" '
                f'-vf "colorkey={color_value}:{similarity}:{blend},format=rgba" '
                f'-c:v libx264 -crf 18 -preset medium -pix_fmt yuva420p '
                f'-c:a aac -y "{output_video}"'
            )

            subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e:
            print(f"基础分割失败: {e}")
            return False

    def create_person_mask_video(
        self,
        input_video: str,
        output_mask_video: str,
        model_selection: int = 1,
        threshold: float = 0.5,
        blur_ksize: int = 11
    ) -> bool:
        """
        人像分割：生成 mask 视频（白=人像，黑=背景）。
        优化策略：
        - VIDEO 模式（时序平滑，减少闪烁）
        - 稀疏检测（每 N 帧推理，中间帧复用，说话视频轮廓变化极小）
        - FFmpeg 管道编码替代 cv2.VideoWriter
        - 预分配形态学核避免重复创建
        """
        import time as _time
        t0 = _time.time()
        cap = None
        ffpipe = None
        segmenter = None
        try:
            import mediapipe as mp

            cap = cv2.VideoCapture(input_video)
            if not cap.isOpened():
                print(f"[Mask] 无法打开视频: {input_video}")
                return False

            fps = cap.get(cv2.CAP_PROP_FPS)
            if not fps or fps <= 1e-2:
                fps = 25.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            os.makedirs(os.path.dirname(output_mask_video), exist_ok=True)

            blur_ksize = int(blur_ksize)
            if blur_ksize % 2 == 0:
                blur_ksize += 1
            blur_ksize = max(1, blur_ksize)
            thresh_val = int(threshold * 255)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

            detect_step = 3 if total > 30 else 1

            # FFmpeg 管道编码（比 cv2.VideoWriter + mp4v 快 5-10 倍）
            ffpipe = subprocess.Popen(
                [
                    "ffmpeg", "-y", "-v", "warning",
                    "-f", "rawvideo", "-pix_fmt", "bgr24",
                    "-s", f"{width}x{height}",
                    "-r", str(fps), "-i", "-",
                    "-vcodec", "libx264", "-crf", "23",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    output_mask_video,
                ],
                stdin=subprocess.PIPE,
            )

            use_new_api = not hasattr(mp, 'solutions')

            if use_new_api:
                from mediapipe.tasks.python import BaseOptions as MpBaseOptions
                from mediapipe.tasks.python.vision import (
                    ImageSegmenter, ImageSegmenterOptions, RunningMode,
                )
                model_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "assets", "mediapipe", "selfie_segmenter.tflite",
                )
                if not os.path.exists(model_path):
                    print(f"[Mask] 模型文件不存在: {model_path}，尝试下载...")
                    import urllib.request
                    os.makedirs(os.path.dirname(model_path), exist_ok=True)
                    urllib.request.urlretrieve(
                        "https://storage.googleapis.com/mediapipe-models/image_segmenter/"
                        "selfie_segmenter/float16/latest/selfie_segmenter.tflite",
                        model_path,
                    )

                options = ImageSegmenterOptions(
                    base_options=MpBaseOptions(model_asset_path=model_path),
                    running_mode=RunningMode.VIDEO,
                    output_confidence_masks=True,
                    output_category_mask=False,
                )
                segmenter = ImageSegmenter.create_from_options(options)
                print(f"[Mask] MediaPipe VIDEO 模式 (v{mp.__version__}), step={detect_step}, {total} 帧")

                frame_count = 0
                last_mask_bgr = None
                timestamp_ms = 0
                frame_interval_ms = int(1000 / fps)

                while True:
                    ok, frame_bgr = cap.read()
                    if not ok:
                        break

                    do_detect = (frame_count % detect_step == 0) or last_mask_bgr is None

                    if do_detect:
                        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                        result = segmenter.segment_for_video(mp_image, timestamp_ms)

                        if result.confidence_masks:
                            m = result.confidence_masks[0].numpy_view()
                            if m.ndim == 3:
                                m = m[:, :, 0]
                            if m.shape[:2] != (height, width):
                                m = cv2.resize(m, (width, height), interpolation=cv2.INTER_LINEAR)
                            m = (m * 255.0).clip(0, 255).astype(np.uint8)
                        else:
                            m = np.zeros((height, width), dtype=np.uint8)

                        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
                        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
                        if blur_ksize > 1:
                            m = cv2.GaussianBlur(m, (blur_ksize, blur_ksize), 0)
                        mask = np.where(m > thresh_val, m, 0).astype(np.uint8)
                        last_mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

                    ffpipe.stdin.write(last_mask_bgr.tobytes())
                    frame_count += 1
                    timestamp_ms += frame_interval_ms

                segmenter.close()
                segmenter = None
            else:
                mp_selfie = mp.solutions.selfie_segmentation
                with mp_selfie.SelfieSegmentation(model_selection=int(model_selection)) as seg:
                    frame_count = 0
                    last_mask_bgr = None
                    while True:
                        ok, frame_bgr = cap.read()
                        if not ok:
                            break
                        do_detect = (frame_count % detect_step == 0) or last_mask_bgr is None
                        if do_detect:
                            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                            res = seg.process(frame_rgb)
                            if res.segmentation_mask is None:
                                m = np.zeros((height, width), dtype=np.uint8)
                            else:
                                m = res.segmentation_mask
                                m = (m * 255.0).clip(0, 255).astype(np.uint8)
                            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
                            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
                            if blur_ksize > 1:
                                m = cv2.GaussianBlur(m, (blur_ksize, blur_ksize), 0)
                            mask = np.where(m > thresh_val, m, 0).astype(np.uint8)
                            last_mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                        ffpipe.stdin.write(last_mask_bgr.tobytes())
                        frame_count += 1

            cap.release()
            cap = None
            ffpipe.stdin.close()
            ffpipe.wait()
            ffpipe = None

            elapsed = _time.time() - t0
            det_count = (frame_count + detect_step - 1) // detect_step
            print(f"[Mask] 人像 mask 生成完成: {frame_count} 帧 "
                  f"(推理 {det_count} 帧, 复用 {frame_count - det_count} 帧, "
                  f"耗时 {elapsed:.1f}s, {frame_count/max(elapsed,0.01):.0f} fps)")

            if os.path.exists(output_mask_video) and os.path.getsize(output_mask_video) > 0:
                return True
            return False
        except Exception as e:
            print(f"[Mask] 通用人像 mask 生成失败: {e}")
            traceback.print_exc()
            return False
        finally:
            if segmenter is not None:
                try:
                    segmenter.close()
                except Exception:
                    pass
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            if ffpipe is not None:
                try:
                    ffpipe.stdin.close()
                except Exception:
                    pass
                try:
                    ffpipe.terminate()
                    ffpipe.wait(timeout=5)
                except Exception:
                    try:
                        ffpipe.kill()
                    except Exception:
                        pass
    
    def overlay_digital_human(self, background_video, digital_human_video, output_video, position="center", digital_human_mask_video: Optional[str] = None):
        """叠加数字人到背景视频（支持mask透明背景）"""
        try:
            position_map = {
                "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
                "top-left": "0:0",
                "top-right": "main_w-overlay_w:0",
                "bottom-left": "0:main_h-overlay_h",
                "bottom-right": "main_w-overlay_w:main_h-overlay_h"
            }
            
            overlay_position = position_map.get(position, "(main_w-overlay_w)/2:(main_h-overlay_h)/2")

            if digital_human_mask_video and os.path.exists(digital_human_mask_video):
                # 用外部 mask 生成 alpha：mask(白=前景) -> alphamerge -> overlay
                filter_complex = (
                    f'[1:v]format=rgba[fgsrc];'
                    f'[2:v]format=gray[mask];'
                    f'[fgsrc][mask]alphamerge[fg];'
                    f'[0:v][fg]overlay={overlay_position}'
                )
                cmd = (
                    f'ffmpeg -i "{background_video}" -i "{digital_human_video}" -i "{digital_human_mask_video}" '
                    f'-filter_complex "{filter_complex}" '
                    f'-c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -y "{output_video}"'
                )
            else:
                cmd = (
                    f'ffmpeg -i "{background_video}" -i "{digital_human_video}" '
                    f'-filter_complex "[1:v]format=rgba[fg];[0:v][fg]overlay={overlay_position}" '
                    f'-c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -y "{output_video}"'
                )
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(output_video):
                return True
            else:
                print(f"❌ 数字人叠加失败: {result.stderr}")
                return False
                    
        except Exception as e:
            print(f"❌ 数字人叠加异常: {e}")
            return False
    
    def add_audio_to_video(self, video_path, audio_path, output_path):
        """添加音频"""
        try:
            cmd = f'ffmpeg -i "{video_path}" -i "{audio_path}" -c:v copy -c:a aac -shortest -y "{output_path}"'
            subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e:
            print(f"❌❌❌❌ 音频添加失败: {e}")
            return False
    
    def add_ass_subtitles_to_video(self, input_video, subtitle_file, output_video):
        """添加ASS格式字幕到视频"""
        try:
            if not os.path.exists(input_video):
                print(f"❌ 输入视频文件不存在: {input_video}")
                return False
            
            if not os.path.exists(subtitle_file):
                print(f"❌ 字幕文件不存在: {subtitle_file}")
                return False
            
            cmd = [
                'ffmpeg', '-i', input_video,
                '-vf', f"ass={subtitle_file}",
                '-c:a', 'copy', '-y', output_video
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ ASS字幕添加成功")
                return True
            else:
                print(f"❌ ASS字幕添加失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ ASS字幕添加失败: {e}")
            return False
    
    def add_sound_effects(self, video_path, effects_config):
        """添加音效系统"""
        try:
            if not effects_config or not effects_config.get('enabled', False):
                return True
            
            if not os.path.exists(video_path):
                print("❌ 视频文件不存在")
                return False
            
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, "video_with_effects.mp4")
            final_audio_path = None
            
            try:
                original_audio_path = os.path.join(temp_dir, "original_audio.wav")
                extract_audio_cmd = f'ffmpeg -i "{video_path}" -vn -acodec pcm_s16le -ar 44100 -ac 2 -y "{original_audio_path}"'
                subprocess.run(extract_audio_cmd, shell=True, check=True)
                
                final_audio_path = self.audio_processor.process_sound_effects(
                    original_audio_path, effects_config, self.get_video_duration(video_path)
                )
                
                if not final_audio_path or not os.path.exists(final_audio_path):
                    print("❌ 音效处理失败")
                    return False
                
                merge_cmd = f'ffmpeg -i "{video_path}" -i "{final_audio_path}" -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 -shortest -y "{output_path}"'
                result = subprocess.run(merge_cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    shutil.copy2(output_path, video_path)
                    print("✅ 所有音效添加成功")
                    return True
                else:
                    print(f"❌ 音视频合并失败: {result.stderr}")
                    return False
                    
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                if final_audio_path:
                    audio_tmp = os.path.dirname(final_audio_path)
                    if audio_tmp and os.path.isdir(audio_tmp) and audio_tmp.startswith('/tmp/'):
                        shutil.rmtree(audio_tmp, ignore_errors=True)
                    
        except Exception as e:
            print(f"❌ 音效添加失败: {e}")
            return False
    
    def _process_parallel(self, settings, temp_dir, task_id):
        """并行处理视频生成的各个阶段"""
        no_face = not settings.get('face_video')
        quality_mode = settings.get('quality_mode', 'fast')

        executor = ThreadPoolExecutor(max_workers=3)
        has_timeout = False
        try:
            futures = {}
            
            futures['bg'] = executor.submit(
                self.create_background_video,
                settings['background_image'],
                self.audio_processor.get_audio_duration(settings['audio_path']),
                os.path.join(temp_dir, "background.mp4"),
                settings['welcome_text'],
                settings['topic_name'],
                settings['animation'],
                settings.get('animation_duration', 6.0),
                1920, 1080,
                settings.get('is_first_page', True)
            )
            
            dh_raw = os.path.join(temp_dir, "digital_human_raw.mp4")
            if not no_face:
                if quality_mode == 'hd':
                    futures['lipsync'] = executor.submit(
                        self.run_musetalk,
                        settings['face_video'],
                        settings['audio_path'],
                        dh_raw,
                        task_id,
                    )
                else:
                    futures['lipsync'] = executor.submit(
                        self.run_wav2lip,
                        settings['face_video'],
                        settings['audio_path'],
                        dh_raw,
                    )
            
            subtitle_path = os.path.join(temp_dir, "blue_karaoke_subtitles.ass")
            if settings['generate_subtitles']:
                futures['subtitle'] = executor.submit(
                    self.subtitle_service.create_karaoke_subtitles_from_audio,
                    settings['audio_path'],
                    subtitle_path
                )
            
            timeout = 1200 if quality_mode == 'hd' else 300
            results = {}
            has_timeout = False
            for name, future in futures.items():
                try:
                    results[name] = future.result(timeout=timeout)
                    tasks[task_id]['progress'] = f'{name}任务完成'
                except concurrent.futures.TimeoutError:
                    print(f"❌ 并行任务 {name} 超时 (>{timeout}s)，可能是 GPU 排队或推理卡死")
                    results[name] = None
                    has_timeout = True
                except Exception as e:
                    err_msg = str(e) or type(e).__name__
                    print(f"❌ 并行任务 {name} 失败: {err_msg}")
                    traceback.print_exc()
                    results[name] = None
            
            if no_face:
                results['lipsync'] = True

            return results, dh_raw, subtitle_path
        finally:
            if sys.version_info >= (3, 9):
                executor.shutdown(wait=not has_timeout, cancel_futures=True)
            else:
                executor.shutdown(wait=not has_timeout)
    
    def _check_cancelled(self, task_id: str):
        """检查任务是否已被取消，若已取消则抛出异常"""
        if task_id in cancelled_tasks:
            raise Exception("任务已被用户取消")

    def generate_video(self, settings: Dict[str, Any], task_id: str):
        """生成视频的主要逻辑（并行版本）"""
        tasks[task_id]['status'] = 'processing'
        tasks[task_id]['start_time'] = datetime.now().isoformat()

        quality_mode = settings.get('quality_mode', 'fast')
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            if quality_mode == 'hd' and settings.get('face_video'):
                tasks[task_id]['progress'] = '加载 MuseTalk 模型...'
                self._init_musetalk()

            self._check_cancelled(task_id)

            # 1. 并行处理多个任务
            tasks[task_id]['progress'] = '并行处理中...'
            parallel_results, dh_raw, subtitle_path = self._process_parallel(settings, temp_dir, task_id)
            
            if not parallel_results.get('lipsync', False):
                raise Exception("数字人生成失败")
            
            no_face = not settings.get('face_video')
            bg_video = os.path.join(temp_dir, "background.mp4")

            self._check_cancelled(task_id)

            if no_face:
                tasks[task_id]['progress'] = '添加音频(无数字人模式)...'
                video_with_audio = os.path.join(temp_dir, "with_audio.mp4")
                self.add_audio_to_video(bg_video, settings['audio_path'], video_with_audio)
            else:
                tasks[task_id]['progress'] = '调整数字人大小...'
                dh_resized = os.path.join(temp_dir, "digital_human_resized.mp4")
                self.resize_digital_human(dh_raw, dh_resized, settings['size'])
                
                tasks[task_id]['progress'] = '绿幕抠图处理...'
                dh_mask = os.path.join(temp_dir, "digital_human_mask.mp4")
                mask_ok = self.create_person_mask_video(
                    input_video=dh_resized,
                    output_mask_video=dh_mask,
                    model_selection=1,
                    threshold=0.6,
                    blur_ksize=21
                )
                if not mask_ok:
                    dh_transparent = os.path.join(temp_dir, "digital_human_transparent.mp4")
                    self.basic_segmentation(
                        input_video=dh_resized,
                        output_video=dh_transparent,
                        background_color="green",
                        similarity=0.08,
                        blend=0.15
                    )
                    dh_for_overlay = dh_transparent
                    dh_mask_for_overlay = None
                else:
                    dh_for_overlay = dh_resized
                    dh_mask_for_overlay = dh_mask
                
                self._check_cancelled(task_id)
                tasks[task_id]['progress'] = '叠加数字人...'
                video_with_dh = os.path.join(temp_dir, "with_dh.mp4")
                success = self.overlay_digital_human(
                    bg_video,
                    dh_for_overlay,
                    video_with_dh,
                    settings['position'],
                    digital_human_mask_video=dh_mask_for_overlay
                )
                if not success:
                    raise Exception("数字人叠加失败")
                
                tasks[task_id]['progress'] = '添加音频...'
                video_with_audio = os.path.join(temp_dir, "with_audio.mp4")
                self.add_audio_to_video(video_with_dh, settings['audio_path'], video_with_audio)
            
            # 3. 添加字幕
            final_output = os.path.join(self.output_dir, f"{settings['output_name']}_{task_id}.mp4")
            if subtitle_path and os.path.exists(subtitle_path):
                tasks[task_id]['progress'] = '添加字幕...'
                self.add_ass_subtitles_to_video(video_with_audio, subtitle_path, final_output)
            else:
                shutil.copy2(video_with_audio, final_output)
            
            # 4. 添加音效系统
            sound_effects_config = settings.get('sound_effects', {})
            print(f"🔊 音效配置状态: enabled={sound_effects_config.get('enabled')}")
            
            if sound_effects_config.get('enabled', False):
                tasks[task_id]['progress'] = '添加音效系统...'
                print("🎵 开始处理音效...")
                success = self.add_sound_effects(final_output, sound_effects_config)
                if success:
                    print("✅ 音效系统添加完成")
                else:
                    print("⚠️ 音效系统添加失败")
            else:
                print("🔇 音效系统未启用")
            
            # 清理临时文件
            shutil.rmtree(temp_dir)

            self._release_gpu_memory()
            
            if os.path.exists(final_output):
                tasks[task_id]['status'] = 'completed'
                tasks[task_id]['progress'] = '完成'
                tasks[task_id]['output_path'] = final_output
                tasks[task_id]['end_time'] = datetime.now().isoformat()
                
                self.show_completion_notification(final_output, task_id)
                return final_output
            else:
                tasks[task_id]['status'] = 'failed'
                tasks[task_id]['progress'] = '生成失败'
                tasks[task_id]['error'] = '视频文件未生成'
                return None
                
        except Exception as e:
            is_cancel = task_id in cancelled_tasks
            if is_cancel:
                print(f"[Cancel] 任务 {task_id} 已取消，清理资源中...")
                tasks[task_id]['status'] = 'cancelled'
                tasks[task_id]['progress'] = '已取消'
                tasks[task_id]['error'] = '任务已被用户取消'
            else:
                print(f"❌❌❌❌ 生成过程中出现错误: {e}")
                tasks[task_id]['status'] = 'failed'
                tasks[task_id]['progress'] = '生成失败'
                tasks[task_id]['error'] = str(e)
            tasks[task_id]['end_time'] = datetime.now().isoformat()
            cancelled_tasks.discard(task_id)

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            self._release_gpu_memory(scope="full")
            return None