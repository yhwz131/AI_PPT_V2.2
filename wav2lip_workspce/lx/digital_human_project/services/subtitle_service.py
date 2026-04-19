import os
import re
from typing import List, Dict, Any, Optional
import subprocess
from datetime import datetime

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from opencc import OpenCC
    OPENCC_AVAILABLE = True
except ImportError:
    OPENCC_AVAILABLE = False

class SubtitleService:
    def __init__(self):
        self.whisper_model = None
        self.model_size = None
        
        if OPENCC_AVAILABLE:
            self.cc = OpenCC('t2s')
        else:
            self.cc = None
    
    def load_whisper_model(self, model_size="large-v3"):
        """加载Whisper模型"""
        if not WHISPER_AVAILABLE:
            return False
        try:
            if self.whisper_model is None or self.model_size != model_size:
                print(f"正在加载Whisper {model_size}模型...")
                self.whisper_model = whisper.load_model(model_size)
                self.model_size = model_size
                print("Whisper模型加载完成")
            return True
        except Exception as e:
            print(f"加载Whisper模型失败: {e}")
            if model_size != "small":
                return self.load_whisper_model("small")
            return False
    
    def format_time(self, seconds):
        """格式化时间为SRT格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def format_ass_time(self, seconds):
        """ASS格式时间戳"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        hundredths = int((seconds - int(seconds)) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{hundredths:02d}"

        
    
    def _calculate_dynamic_font_size(self, audio_path):
        """根据音频/视频特性计算动态字体大小"""
        try:
            from services.audio_processor import AudioProcessor
            audio_processor = AudioProcessor()
            
            # 获取音频时长
            duration = audio_processor.get_audio_duration(audio_path)
            
            # 基础字体大小
            base_size = 60
            
            # 根据音频时长调整字体大小
            if duration <= 30:  # 短音频
                font_size = base_size * 1.5  # 90
            elif duration <= 120:  # 中等长度音频
                font_size = base_size * 1.2  # 72
            else:  # 长音频
                font_size = base_size  # 60
            
            # 确保字体大小在合理范围内
            font_size = min(max(font_size, 50), 100)
            
            print(f"🔧 动态计算字体大小: 音频时长={duration:.1f}秒 -> 字体大小={font_size}")
            return font_size
            
        except Exception as e:
            print(f"⚠️ 动态字体大小计算失败，使用默认值90: {e}")
            return 90
    
    def create_karaoke_subtitles_from_audio(self, audio_path, subtitle_path):
        """改进版：解决长句子不分割的问题，支持动态字体大小"""
        try:
            if not WHISPER_AVAILABLE:
                print("❌ Whisper不可用，无法生成卡拉OK字幕")
                print("💡 请安装: pip install openai-whisper")
                return False
            
            if not os.path.exists(audio_path):
                print(f"❌ 音频文件不存在: {audio_path}")
                return False
            
            print(f"🔍 字幕生成调试:")
            print(f"   音频文件: {audio_path}")
            print(f"   输出字幕: {subtitle_path}")
            
            if not self.load_whisper_model("large-v3"):
                return False
            
            print("开始生成改进版电视风格卡拉OK字幕（支持长句分割和动态字体大小）...")
            
            # 转录音频
            result = self.whisper_model.transcribe(
                audio_path, 
                language='zh',
                task='transcribe',
                word_timestamps=True,
                best_of=3,
                beam_size=3,
                temperature=0.0,
                no_speech_threshold=0.5,
                logprob_threshold=-0.5,
                condition_on_previous_text=False
            )
            
            if not result or 'segments' not in result:
                return False
            
            # 获取音频时长
            from services.audio_processor import AudioProcessor
            audio_processor = AudioProcessor()
            audio_duration = audio_processor.get_audio_duration(audio_path)
            
            # 修复时间轴对齐
            segments = self._fix_timestamp_alignment(result['segments'], audio_duration)
            segments = self._smart_split_long_segments(segments)
            
            # 获取字体大小
            font_size = self._calculate_dynamic_font_size(audio_path)
            
            # 生成ASS字幕，传入字体大小参数
            ass_content = self._generate_improved_karaoke_ass(segments, audio_duration, font_size)
            
            with open(subtitle_path.replace('.srt', '.ass'), 'w', encoding='utf-8') as f:
                f.write(ass_content)
            
            print(f"✅ 改进版电视风格卡拉OK字幕生成成功（字体大小: {font_size}）")
            return True
            
        except Exception as e:
            print(f"❌ 改进版字幕生成失败: {e}")
            return False
    
    def _smart_split_long_segments(self, segments):
        """智能分割过长的字幕段"""
        import re
        
        new_segments = []
        
        for segment in segments:
            text = segment.get('text', '').strip()
            start_time = segment.get('start', 0)
            end_time = segment.get('end', 0)
            duration = end_time - start_time
            
            if not text or duration <= 0:
                continue
            
            if len(text) > 30:
                print(f"🔍 发现长句子需要分割: {text[:50]}...")
                sub_texts = self._intelligent_text_split(text)
                
                if len(sub_texts) > 1:
                    for i, sub_text in enumerate(sub_texts):
                        if not sub_text.strip():
                            continue
                        
                        char_ratio = len(sub_text) / len(text)
                        sub_duration = duration * char_ratio
                        sub_start = start_time + sum(len(sub_texts[j]) for j in range(i)) * duration / len(text)
                        sub_end = sub_start + sub_duration
                        
                        new_segments.append({
                            'text': sub_text.strip(),
                            'start': sub_start,
                            'end': sub_end
                        })
                    print(f"  分割为 {len(sub_texts)} 个小段")
                    continue
            
            new_segments.append(segment)
        
        return new_segments
    
    def _intelligent_text_split(self, text):
        """智能文本分割算法"""
        import re
        
        text = text.strip()
        if not text:
            return []
        
        sentence_pattern = r'([。！？；]+)'
        temp_text = re.sub(sentence_pattern, r'\1<SPLIT>', text)
        sentences = [s.strip() for s in temp_text.split('<SPLIT>') if s.strip()]
        
        result = []
        for sentence in sentences:
            if len(sentence) <= 20:
                result.append(sentence)
            else:
                parts = re.split(r'[，、；,]+', sentence)
                current_part = ""
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    if current_part:
                        combined = current_part + "，" + part
                        if len(combined) > 25:
                            result.append(current_part + "，")
                            current_part = part
                        else:
                            current_part = combined
                    else:
                        current_part = part
                
                if current_part:
                    result.append(current_part)
        
        if not result:
            result = [text]
        
        return result
    
    def _generate_improved_karaoke_ass(self, segments, audio_duration, font_size=90):
        """生成改进的卡拉OK ASS字幕格式，支持动态字体大小"""
        try:
            # 动态生成ASS样式，使用传入的字体大小
            ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TVStyle,Microsoft YaHei,{font_size},&H00FFFFFF,&H00FFAA66,&H00000000,&H99000000,0,0,0,0,100,100,0,0,1,3,2,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            
            events = []
            
            for i, segment in enumerate(segments):
                start_time = segment.get('start', 0)
                end_time = segment.get('end', 0)
                text = segment.get('text', '').strip()
                
                if not text:
                    continue
                
                text = self._optimize_chinese_punctuation(text)
                # 修改这里：改为电视风格效果
                karaoke_text = self._create_blue_karaoke_effect(text, start_time, end_time)
                start_str = self.format_ass_time(start_time)
                end_str = self.format_ass_time(end_time)
                events.append(f"Dialogue: 0,{start_str},{end_str},TVStyle,,0,0,0,,{karaoke_text}")
            
            if not events:
                default_start = self.format_ass_time(0)
                default_end = self.format_ass_time(audio_duration)
                default_text = "欢迎来到AI知识讲堂"
                # 修改这里：改为电视风格效果
                karaoke_text = self._create_blue_karaoke_effect(default_text, 0, audio_duration)
                events.append(f"Dialogue: 0,{default_start},{default_end},TVStyle,,0,0,0,,{karaoke_text}")
            
            return ass_header + '\n'.join(events)
            
        except Exception as e:
            print(f"❌ 生成ASS字幕失败: {e}")
            return self._generate_basic_ass_template(font_size)
    
    def _generate_basic_ass_template(self, font_size=90):
        """生成基本的ASS字幕模板"""
        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TVStyle,Microsoft YaHei,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,0,0,0,0,100,100,0,0,1,3,2,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,TVStyle,,0,0,0,,{{\\k100}}{{\\c&HFFFFFF&}}欢迎来到{{\\k100}}{{\\c&HFFFFFF&}}{{\\c&HFFFFFF\\t(100,\\c&HFFFFFF)}}AI知识讲堂
"""
    
    def _create_blue_karaoke_effect(self, text, start_time, end_time):
        """简化：仅使用标准卡拉OK标记"""
        text = self._optimize_chinese_punctuation(text.strip())
        if not text:
            return ""
        
        duration = min(end_time - start_time, 8.0)  # 避免过长
        return self._create_karaoke_segment(text, duration)
    
    def _create_karaoke_segment(self, text, duration):
        """生成只含\k标记的卡拉OK片段"""
        chars = list(text)
        if not chars:
            return ""
        
        char_duration = duration / len(chars)
        karaoke_parts = []
        for char in chars:
            karaoke_parts.append(f"{{\\k{int(char_duration*100)}}}{char}")
        return ''.join(karaoke_parts)
    
    def _improved_smart_split(self, text):
        """改进的文本分割算法"""
        import re
        
        text = text.strip()
        split_points = ['。', '！', '？', '；', '……']
        
        for split_char in split_points:
            if split_char in text:
                text = text.replace(split_char, f"{split_char}<SENTENCE_SPLIT>")
        
        sentence_parts = [part.strip() for part in text.split('<SENTENCE_SPLIT>') if part.strip()]
        segments = []
        
        for sentence in sentence_parts:
            if len(sentence) <= 20:
                segments.append(sentence)
            else:
                sub_parts = re.split(r'[，；、]', sentence)
                current_part = ""
                for part in sub_parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    if current_part and len(current_part + "，" + part) > 25:
                        segments.append(current_part + "，")
                        current_part = part
                    else:
                        if current_part:
                            current_part += "，" + part
                        else:
                            current_part = part
                
                if current_part:
                    segments.append(current_part)
        
        return segments
    
    def _fix_timestamp_alignment(self, segments, audio_duration):
        """修复时间戳对齐"""
        if not segments:
            return segments
        
        total_duration = segments[-1]['end'] - segments[0]['start']
        if total_duration < 0.1:
            return segments
        
        if segments[0]['start'] > 0.1:
            shift_time = segments[0]['start']
            for segment in segments:
                segment['start'] = max(0, segment['start'] - shift_time)
                segment['end'] = max(0, segment['end'] - shift_time)
        
        if segments[-1]['end'] > audio_duration:
            scale_factor = audio_duration / segments[-1]['end']
            for segment in segments:
                segment['start'] = segment['start'] * scale_factor
                segment['end'] = segment['end'] * scale_factor
        
        return segments
    
    def _optimize_chinese_punctuation(self, text):
        """优化中文标点符号"""
        import re
        text = re.sub(r'\s*,\s*', '，', text)
        text = re.sub(r'\s*\.\s*', '。', text)
        text = re.sub(r'\s*\?\s*', '？', text)
        text = re.sub(r'\s*!\s*', '！', text)
        text = re.sub(r'\s*;\s*', '；', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text