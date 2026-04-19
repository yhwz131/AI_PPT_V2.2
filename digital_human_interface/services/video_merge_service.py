import os
import re
import subprocess
import glob
from pathlib import Path

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_BASE_DIR)
DEFAULT_BGM_PATH = os.getenv(
    "DEFAULT_BGM_PATH",
    os.path.join(_PROJECT_ROOT, "wav2lip_workspce", "lx", "测试", "assets", "sfx", "商务背景音乐.mp3")
)
BGM_VOLUME_RATIO = 0.15


class VideoMerger:
    """
    视频合并类 - 用于自动合并文件夹中的视频文件
    使用FFmpeg进行高效视频合并，支持按数字顺序排序
    """

    def __init__(self, video_folder, output_path, output_name):
        """
        初始化视频合并器

        Args:
            video_folder: 视频文件夹路径
            output_path: 合并视频保存路径
            output_name: 合并视频名称
        """
        self.video_folder = video_folder
        self.output_path = output_path
        self.output_name = output_name
        self.video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.ts', '.flv', '.wmv']

    def extract_number(self, filename):
        """
        从文件名中提取数字用于排序

        Args:
            filename: 文件名

        Returns:
            int: 提取的数字
        """
        # 使用正则表达式匹配文件名中的数字[5](@ref)
        numbers = re.findall(r'\d+', filename)
        if numbers:
            return int(numbers[0])
        else:
            # 如果文件名中没有数字，返回一个很大的数确保排在最后
            return float('inf')

    def get_sorted_video_files(self):
        """
        获取文件夹中所有视频文件并按数字顺序排序[4](@ref)

        Returns:
            list: 排序后的视频文件路径列表
        """
        video_files = []

        # 检查文件夹是否存在
        if not os.path.exists(self.video_folder):
            raise FileNotFoundError(f"视频文件夹不存在: {self.video_folder}")

        print(f"正在扫描文件夹: {self.video_folder}")

        # 使用glob匹配所有视频文件[1](@ref)
        for ext in self.video_extensions:
            pattern = os.path.join(self.video_folder, f'*{ext}')
            video_files.extend(glob.glob(pattern))

        # 如果没有找到视频文件，尝试使用os.listdir
        if not video_files:
            print("使用glob未找到文件，尝试使用os.listdir...")
            for filename in os.listdir(self.video_folder):
                if any(filename.lower().endswith(ext) for ext in self.video_extensions):
                    video_files.append(os.path.join(self.video_folder, filename))

        if not video_files:
            raise ValueError(f"在文件夹 {self.video_folder} 中未找到任何视频文件")

        print(f"找到 {len(video_files)} 个视频文件")

        # 按文件名中的数字排序[4](@ref)
        try:
            video_files.sort(key=lambda x: self.extract_number(os.path.basename(x)))
            print("视频文件已按数字顺序排序")
        except Exception as e:
            print(f"排序时出现错误: {e}")
            print("将按文件名自然排序")
            video_files.sort()

        # 显示排序后的文件列表
        for i, video_file in enumerate(video_files):
            print(f"{i + 1}. {os.path.basename(video_file)}")

        return video_files

    def check_ffmpeg_available(self):
        """
        检查FFmpeg是否可用

        Returns:
            bool: FFmpeg是否可用
        """
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError("FFmpeg未正确安装或未在系统路径中")
            print("FFmpeg已正确安装")
            return True
        except FileNotFoundError:
            raise RuntimeError("未找到FFmpeg，请确保已安装并添加到系统路径")

    def merge_videos(self):
        """
        合并视频文件的主方法[6](@ref)

        Returns:
            bool: 合并是否成功
            str: 成功或错误信息
        """
        try:
            # 检查FFmpeg是否可用
            self.check_ffmpeg_available()

            # 获取排序后的视频文件
            video_files = self.get_sorted_video_files()

            # 确保输出路径存在
            os.makedirs(self.output_path, exist_ok=True)

            # 构建完整的输出文件路径
            if not self.output_name.lower().endswith('.mp4'):
                self.output_name += '.mp4'
            output_file_path = os.path.join(self.output_path, self.output_name)

            # 创建临时文件列表[6](@ref)
            list_filename = os.path.join(self.output_path, "temp_file_list.txt")

            # 写入文件列表，确保路径格式正确
            with open(list_filename, 'w', encoding='utf-8') as f:
                for video_file in video_files:
                    # 使用正斜杠确保路径兼容性
                    file_path = video_file.replace('\\', '/')
                    f.write(f"file '{file_path}'\n")

            print(f"已创建文件列表: {list_filename}")
            print("开始合并视频...")

            # 构建FFmpeg命令[6](@ref)
            # -f concat: 使用concat协议合并文件
            # -safe 0: 允许非标准文件路径
            # -c copy: 直接复制流而不重新编码（快速且无损）
            ffmpeg_command = [
                'ffmpeg', '-f', 'concat', '-safe', '0',
                '-i', list_filename, '-c', 'copy', output_file_path, '-y'
            ]

            # 执行FFmpeg命令
            print("执行FFmpeg命令:", ' '.join(ffmpeg_command))

            # 使用utf-8编码来捕获FFmpeg的输出，避免编码错误
            result = subprocess.run(
                ffmpeg_command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'  # 忽略无法解码的字符
            )

            # 清理临时文件
            if os.path.exists(list_filename):
                os.remove(list_filename)
                print(f"已清理临时文件: {list_filename}")

            if result.returncode == 0:
                # 显示输出文件信息
                if os.path.exists(output_file_path):
                    file_size = os.path.getsize(output_file_path) / (1024 * 1024)  # 转换为MB
                    print(f"✓ 视频合并成功!")
                    print(f"输出文件: {output_file_path}")
                    print(f"文件大小: {file_size:.2f} MB")
                    return True, f"视频合并成功！文件保存至: {output_file_path}"
                else:
                    return False, "合并成功但输出文件未找到"
            else:
                # 输出错误信息，确保不会因为编码问题而崩溃
                error_msg = f"FFmpeg合并失败: {result.stderr[:500] if result.stderr else '未知错误'}"
                print(f"✗ {error_msg}")
                return False, error_msg

        except Exception as e:
            error_msg = f"合并过程中出现异常: {str(e)}"
            print(f"✗ {error_msg}")
            return False, error_msg

    def merge_with_progress(self):
        """
        带进度显示的合并方法（如果需要进度反馈可以调用此方法）

        Returns:
            bool: 合并是否成功
            str: 成功或错误信息
        """
        print("=" * 50)
        print("开始视频合并流程")
        print("=" * 50)

        success, message = self.merge_videos()

        print("=" * 50)
        if success:
            print("🎉 视频合并流程完成!")
        else:
            print("❌ 视频合并失败")

        return success, message


def mix_bgm(video_path: str, bgm_mode: str = "default", bgm_path: str = "",
            volume_ratio: float = BGM_VOLUME_RATIO) -> tuple[bool, str]:
    """
    将BGM循环混合到合并后的视频中。

    Args:
        video_path: 合并后的视频文件路径
        bgm_mode: "default" / "custom" / "none"
        bgm_path: 自定义BGM文件路径（bgm_mode="custom"时使用）
        volume_ratio: BGM音量比例（0.0~1.0）

    Returns:
        (success, message)
    """
    if bgm_mode == "none":
        return True, "BGM已禁用，跳过混合"

    if bgm_mode == "custom" and bgm_path:
        music_file = bgm_path
    else:
        music_file = DEFAULT_BGM_PATH

    if not os.path.exists(music_file):
        return False, f"BGM文件不存在: {music_file}"

    if not os.path.exists(video_path):
        return False, f"视频文件不存在: {video_path}"

    output_path = video_path.replace(".mp4", "_bgm.mp4")

    # -stream_loop -1: 无限循环BGM
    # amix duration=first: 以视频时长为准
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-stream_loop", "-1",
        "-i", music_file,
        "-filter_complex",
        f"[1:a]volume={volume_ratio}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[out]",
        "-map", "0:v",
        "-map", "[out]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-y",
        output_path,
    ]

    print(f"混合BGM命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if result.returncode != 0:
            return False, f"BGM混合失败: {result.stderr[:500] if result.stderr else '未知错误'}"

        # 替换原视频
        os.replace(output_path, video_path)
        file_size = os.path.getsize(video_path) / (1024 * 1024)
        print(f"✓ BGM混合完成，文件大小: {file_size:.2f} MB")
        return True, "BGM混合完成"
    except Exception as e:
        return False, f"BGM混合异常: {str(e)}"