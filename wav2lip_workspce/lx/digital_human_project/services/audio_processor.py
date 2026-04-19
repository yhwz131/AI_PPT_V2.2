import os
import tempfile
import subprocess
from pydub import AudioSegment
from typing import Optional, Dict

class AudioProcessor:
    def __init__(self):
        try:
            from pydub.generators import Sine
            self.can_generate_music = True
        except ImportError:
            self.can_generate_music = False
    
    def get_audio_duration(self, audio_path):
        """获取音频时长"""
        try:
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0
            print(f"音频时长: {duration:.2f}秒")
            return duration
        except Exception as e:
            print(f"获取音频时长失败: {e}")
            return 10
    
    def process_sound_effects(self, original_audio_path: str, effects_config: Dict, video_duration: float) -> Optional[str]:
        """处理所有音效混合"""
        try:
            # 加载主音频
            main_audio = AudioSegment.from_file(original_audio_path)
            mixed_audio = main_audio
            
            # 添加背景音乐
            if effects_config.get('background_music', {}).get('enabled', False):
                mixed_audio = self._add_background_music(mixed_audio, effects_config['background_music'], video_duration)
            
            # 添加转场音效
            if effects_config.get('transition_sounds', {}).get('enabled', False):
                mixed_audio = self._add_transition_sounds(mixed_audio, effects_config['transition_sounds'], video_duration)
            
            # 添加完成提示音
            if effects_config.get('final_notification', {}).get('enabled', False):
                mixed_audio = self._add_final_notification(mixed_audio, effects_config['final_notification'], video_duration)
            
            # 导出临时音频文件
            temp_dir = tempfile.mkdtemp()
            final_audio_path = os.path.join(temp_dir, "final_audio.wav")
            mixed_audio.export(final_audio_path, format="wav")
            
            return final_audio_path
            
        except Exception as e:
            print(f"❌ 音效处理失败: {e}")
            return None
    
    def _add_background_music(self, main_audio, settings, video_duration):
        """添加商务风格背景音乐"""
        try:
            music_file = settings.get("music_file")
            volume_ratio = settings.get("volume_ratio", 0.2)
            
            # 如果没有指定音乐文件，使用默认商务风格音乐
            if not music_file or not os.path.exists(music_file):
                if self.can_generate_music:
                    print("⚠️ 未指定背景音乐文件，使用默认商务风格")
                    music_file = self._create_corporate_background_music(video_duration)
                    if not music_file:
                        return main_audio
                else:
                    return main_audio
            
            # 加载背景音乐
            bg_music = AudioSegment.from_file(music_file)
            bg_music = bg_music - (20 * (1 - volume_ratio))
            
            # 循环背景音乐以匹配视频时长
            bg_duration = len(bg_music)
            main_duration = len(main_audio)
            
            if bg_duration < main_duration:
                loops = int(main_duration / bg_duration) + 1
                bg_music = bg_music * loops
            
            bg_music = bg_music[:main_duration]
            mixed = main_audio.overlay(bg_music)
            print("✅ 商务风格背景音乐添加成功")
            return mixed
            
        except Exception as e:
            print(f"❌ 背景音乐添加失败: {e}")
            return main_audio
    
    def _add_transition_sounds(self, main_audio, settings, video_duration):
        """添加转场音效"""
        try:
            sound_file = settings.get("sound_file")
            volume = settings.get("volume", -3)
            
            if not sound_file or not os.path.exists(sound_file):
                print("⚠️ 转场音效文件不存在，跳过")
                return main_audio
            
            transition_sound = AudioSegment.from_file(sound_file)
            transition_time = max(0, (video_duration - 0.5) * 1000)
            
            if volume != 0:
                transition_sound = transition_sound + volume
            
            available_time = video_duration * 1000 - transition_time
            if len(transition_sound) > available_time:
                transition_sound = transition_sound[:available_time]
            
            mixed_audio = main_audio.overlay(transition_sound, position=transition_time)
            print("✅ 转场音效添加成功（结束前0.5秒）")
            return mixed_audio
            
        except Exception as e:
            print(f"❌ 转场音效添加失败: {e}")
            return main_audio
    
    def _add_final_notification(self, main_audio, settings, video_duration):
        """添加完成提示音"""
        try:
            sound_file = settings.get("sound_file")
            start_before_end = settings.get("start_before_end", 1.0)
            volume = settings.get("volume", -5)
            fade_duration = settings.get("fade_duration", 0.3)
            
            if not sound_file or not os.path.exists(sound_file):
                print("⚠️ 完成提示音文件不存在，跳过")
                return main_audio
            
            notification_sound = AudioSegment.from_file(sound_file)
            notification_time = max(0, (video_duration - start_before_end) * 1000)
            
            if volume != 0:
                notification_sound = notification_sound + volume
            
            if fade_duration > 0:
                fade_ms = int(fade_duration * 1000)
                notification_sound = notification_sound.fade_in(fade_ms).fade_out(fade_ms)
            
            available_time = video_duration * 1000 - notification_time
            if len(notification_sound) > available_time:
                notification_sound = notification_sound[:available_time]
            
            mixed_audio = main_audio.overlay(notification_sound, position=notification_time)
            print("✅ 完成提示音添加成功（结束前1秒）")
            return mixed_audio
            
        except Exception as e:
            print(f"❌ 完成提示音添加失败: {e}")
            return main_audio
    
    def _create_corporate_background_music(self, duration):
        """创建默认商务风格背景音乐"""
        try:
            if not self.can_generate_music:
                return None
            
            from pydub.generators import Sine
            from pydub import AudioSegment
            
            duration_ms = int(duration * 1000)
            
            # 基础和弦
            chord1 = Sine(220).to_audio_segment(duration=4000)
            chord2 = Sine(261.63).to_audio_segment(duration=4000)
            chord3 = Sine(329.63).to_audio_segment(duration=4000)
            
            base_music = chord1.overlay(chord2).overlay(chord3)
            full_music = AudioSegment.silent(duration=500)
            
            while len(full_music) < duration_ms:
                full_music = full_music.append(base_music)
            
            full_music = full_music[:duration_ms]
            full_music = full_music.fade_in(3000).fade_out(4000)
            full_music = full_music - 20
            
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, "corporate_bg_music.wav")
            full_music.export(output_path, format="wav")
            
            return output_path
            
        except Exception as e:
            print(f"❌ 创建默认商务音乐失败: {e}")
            return None