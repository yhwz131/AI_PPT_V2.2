import os
import tempfile
import subprocess
import shutil
import cv2
import numpy as np
import platform
from datetime import datetime
from typing import Dict, Any, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import config
from models import tasks
from services.audio_processor import AudioProcessor
from services.subtitle_service import SubtitleService

class VideoGenerator:
    def __init__(self):
        self.output_dir = config.output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.audio_processor = AudioProcessor()
        self.subtitle_service = SubtitleService()
        
        self.preset_sounds = {
            "notifications": {
                "completion_bell": os.path.join(config.sound_effects_dir, "notifications/completion_bell.wav"),
                "success_chime": os.path.join(config.sound_effects_dir, "notifications/success_chime.wav")
            },
            "transitions": {
                "swipe": os.path.join(config.sound_effects_dir, "transitions/swipe.wav"),
                "whoosh": os.path.join(config.sound_effects_dir, "transitions/whoosh.wav")
            },
            "background": {
                "corporate": os.path.join(config.sound_effects_dir, "background/corporate.mp3"),
                "professional": os.path.join(config.sound_effects_dir, "background/professional.mp3")
            }
        }
    
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
    
    def create_background_video(self, image_path, duration, output_path, welcome_text, topic_name, animation, animation_duration=6.0):
        """创建背景视频"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                print(f"❌ 无法读取图片: {image_path}")
                return False
                
            original_height, original_width = img.shape[:2]
            target_width, target_height = 1920, 1080
            
            scale_x = target_width / original_width
            scale_y = target_height / original_height
            scale = max(scale_x, scale_y)
            
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            
            scaled_img_path = os.path.join(os.path.dirname(output_path), "scaled_image.jpg")
            resize_cmd = f'ffmpeg -i "{image_path}" -vf "scale={new_width}:{new_height}" -y "{scaled_img_path}"'
            subprocess.run(resize_cmd, shell=True, check=True)
            
            font_path = self._get_ubuntu_font()
            
            if font_path and os.path.exists(scaled_img_path):
                temp_bg_path = os.path.join(os.path.dirname(output_path), "temp_bg.mp4")
                
                bg_cmd = (
                    f'ffmpeg -f lavfi -i color=color=darkgreen:size=1920x1080:duration={duration} '
                    f'-vf "drawtext=text=\'{welcome_text}\':fontcolor=white:fontsize=80:'
                    f'fontfile={font_path}:x=(w-text_w)/2:y=(h-text_h)/2-100,'
                    f'drawtext=text=\'主题：{topic_name}\':fontcolor=yellow:fontsize=72:'
                    f'fontfile={font_path}:x=(w-text_w)/2:y=(h-text_h)/2+40" '
                    f'-c:v libx264 -pix_fmt yuv420p -y "{temp_bg_path}"'
                )
                subprocess.run(bg_cmd, shell=True, check=True)
                
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
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', output_path
                ]
                subprocess.run(cmd, check=True)
                
                if os.path.exists(temp_bg_path):
                    os.remove(temp_bg_path)
                if os.path.exists(scaled_img_path):
                    os.remove(scaled_img_path)
            else:
                cmd = (
                    f'ffmpeg -f lavfi -i color=color=darkgreen:size=1920x1080:duration={duration} '
                    f'-vf "drawtext=text=\'{welcome_text}\':fontcolor=white:fontsize=60:'
                    f'x=(w-text_w)/2:y=(h-text_h)/2-100,'
                    f'drawtext=text=\'{topic_name}\':fontcolor=yellow:fontsize=72:'
                    f'x=(w-text_w)/2:y=(h-text_h)/2" '
                    f'-c:v libx264 -pix_fmt yuv420p -y "{output_path}"'
                )
                subprocess.run(cmd, shell=True, check=True)
            
            return True
        except Exception as e:
            print(f"❌❌❌❌ 背景视频创建失败: {e}")
            return False
    
    def run_wav2lip(self, face_video, audio_path, output_path):
        """运行Wav2Lip"""
        try:
            if not os.path.exists(config.wav2lip_checkpoint):
                print("❌❌❌❌ Wav2Lip模型文件不存在")
                return False
            
            original_dir = os.getcwd()
            os.chdir(config.wav2lip_dir)
            
            cmd = [
                "python", "inference.py",
                "--checkpoint_path", config.wav2lip_checkpoint,
                "--face", os.path.abspath(face_video),
                "--audio", os.path.abspath(audio_path),
                "--outfile", os.path.abspath(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=500)
            os.chdir(original_dir)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return True
            else:
                print("❌❌❌❌ Wav2Lip失败")
                return False
        except Exception as e:
            print(f"❌❌❌❌ Wav2Lip异常: {e}")
            return False
    
    def resize_digital_human(self, input_video, output_video, size_ratio):
        """调整数字人大小"""
        try:
            new_width = int(1920 * size_ratio)
            new_height = int(new_width * 9 / 16)
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
                f'-c:v libx264 -pix_fmt yuva420p '
                f'-c:a aac -y "{output_video}"'
            )

            subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e:
            print(f"基础分割失败: {e}")
            return False
    
    def overlay_digital_human(self, background_video, digital_human_video, output_video, position="center"):
        """叠加数字人到背景视频"""
        try:
            position_map = {
                "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
                "top-left": "0:0",
                "top-right": "main_w-overlay_w:0",
                "bottom-left": "0:main_h-overlay_h",
                "bottom-right": "main_w-overlay_w:main_h-overlay_h"
            }
            
            overlay_position = position_map.get(position, "(main_w-overlay_w)/2:(main_h-overlay_h)/2")
            
            cmd = f'ffmpeg -i "{background_video}" -i "{digital_human_video}" -filter_complex "[1:v]format=rgba,alphaextract[alpha];[1:v][alpha]alphamerge[fg];[0:v][fg]overlay={overlay_position}" -c:v libx264 -pix_fmt yuv420p -c:a aac -y "{output_video}"'
            
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
                    
        except Exception as e:
            print(f"❌ 音效添加失败: {e}")
            return False
    
    def _process_parallel(self, settings, temp_dir, task_id):
        """并行处理视频生成的各个阶段"""
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            
            # 并行任务1：生成背景视频
            futures['bg'] = executor.submit(
                self.create_background_video,
                settings['background_image'],
                self.audio_processor.get_audio_duration(settings['audio_path']),
                os.path.join(temp_dir, "background.mp4"),
                settings['welcome_text'],
                settings['topic_name'],
                settings['animation'],
                settings.get('animation_duration', 6.0)
            )
            
            # 并行任务2：生成数字人视频
            dh_raw = os.path.join(temp_dir, "digital_human_raw.mp4")
            futures['wav2lip'] = executor.submit(
                self.run_wav2lip,
                settings['face_video'],
                settings['audio_path'],
                dh_raw
            )
            
            # 并行任务3：生成字幕
            subtitle_path = os.path.join(temp_dir, "blue_karaoke_subtitles.ass")
            if settings['generate_subtitles']:
                futures['subtitle'] = executor.submit(
                    self.subtitle_service.create_karaoke_subtitles_from_audio,
                    settings['audio_path'],
                    subtitle_path
                )
            
            # 等待所有并行任务完成
            results = {}
            for name, future in futures.items():
                try:
                    results[name] = future.result(timeout=300)
                    tasks[task_id]['progress'] = f'{name}任务完成'
                except Exception as e:
                    print(f"❌ 并行任务 {name} 失败: {e}")
                    results[name] = None
            
            return results, dh_raw, subtitle_path
    
    def generate_video(self, settings: Dict[str, Any], task_id: str):
        """生成视频的主要逻辑（并行版本）"""
        tasks[task_id]['status'] = 'processing'
        tasks[task_id]['start_time'] = datetime.now().isoformat()
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            # 1. 并行处理多个任务
            tasks[task_id]['progress'] = '并行处理中...'
            parallel_results, dh_raw, subtitle_path = self._process_parallel(settings, temp_dir, task_id)
            
            if not parallel_results.get('wav2lip', False):
                raise Exception("数字人生成失败")
            
            # 2. 串行处理依赖任务
            tasks[task_id]['progress'] = '调整数字人大小...'
            dh_resized = os.path.join(temp_dir, "digital_human_resized.mp4")
            self.resize_digital_human(dh_raw, dh_resized, settings['size'])
            
            tasks[task_id]['progress'] = '绿幕抠图处理...'
            dh_transparent = os.path.join(temp_dir, "digital_human_transparent.mp4")
            self.basic_segmentation(
                input_video=dh_resized,
                output_video=dh_transparent,
                background_color="green",
                similarity=0.08,
                blend=0.15
            )
            
            tasks[task_id]['progress'] = '叠加数字人...'
            video_with_dh = os.path.join(temp_dir, "with_dh.mp4")
            success = self.overlay_digital_human(
                os.path.join(temp_dir, "background.mp4"),
                dh_transparent,
                video_with_dh,
                settings['position']
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
            print(f"❌❌❌❌ 生成过程中出现错误: {e}")
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['progress'] = '生成失败'
            tasks[task_id]['error'] = str(e)
            
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return None