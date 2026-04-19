"""
视频转换核心功能模块
基于配置文件的实现
"""
import os
import re
import subprocess
from datetime import datetime
from typing import Dict, Any

# 导入配置
from config import get_settings

# 全局任务存储
conversion_tasks: Dict[str, 'ConversionTask'] = {}


class ConversionTask:
    """
    转换任务类

    Attributes:
        task_id: 任务ID
        input_file: 输入文件路径
        output_dir: 输出目录
        status: 任务状态
        progress: 进度百分比
        message: 状态消息
    """

    def __init__(self, task_id: str, input_file: str, output_dir: str):
        self.task_id = task_id
        self.input_file = input_file
        self.output_dir = output_dir
        self.status = "waiting"  # waiting, processing, completed, error, cancelled
        self.progress = 0
        self.message = ""
        self.start_time = None
        self.end_time = None
        self.total_duration = 0
        self.current_time = 0
        self.speed = "0.0x"
        self.m3u8_file = ""
        self.settings = get_settings()


def get_video_duration(input_file: str) -> Dict[str, Any]:
    """
    获取视频时长信息

    Args:
        input_file: 输入文件路径

    Returns:
        Dict: 包含成功状态、时长和消息的字典
    """
    settings = get_settings()
    try:
        probe_cmd = [
            settings.FFPROBE_PATH, '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_file
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return {
            "success": True,
            "duration": duration,
            "message": f"成功获取视频时长: {duration:.2f}秒"
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "duration": None,
            "message": f"FFprobe执行失败: {e}"
        }
    except Exception as e:
        return {
            "success": False,
            "duration": None,
            "message": f"获取视频时长时发生错误: {e}"
        }


def convert_mp4_to_hls_async(task_id: str, input_file: str, output_dir: str):
    """
    异步将视频转换为HLS格式

    Args:
        task_id: 任务ID
        input_file: 输入文件路径
        output_dir: 输出目录
    """
    settings = get_settings()
    task = conversion_tasks[task_id]
    task.status = "processing"
    task.start_time = datetime.now()

    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 设置输出的m3u8文件和TS切片路径模板
        m3u8_file = os.path.join(output_dir, "playlist.m3u8")
        segment_pattern = os.path.join(output_dir, "segment_%03d.ts")
        task.m3u8_file = m3u8_file

        # 构建FFmpeg命令 - 使用配置文件中的参数
        command = [
            settings.FFMPEG_PATH,
            '-i', input_file,
            '-c:v', settings.VIDEO_CODEC,
            '-c:a', settings.AUDIO_CODEC,
            '-b:v', settings.VIDEO_BITRATE,
            '-maxrate', settings.MAXRATE,
            '-bufsize', settings.BUFSIZE,
            '-hls_time', str(settings.SEGMENT_TIME),
            '-hls_list_size', '0',
            '-f', 'hls',
            '-hls_segment_filename', segment_pattern,
            '-y',  # 覆盖输出文件
            m3u8_file
        ]

        # 获取视频总时长
        task.message = "正在获取视频信息..."
        duration_result = get_video_duration(input_file)

        if duration_result["success"] and duration_result["duration"]:
            task.total_duration = duration_result["duration"]
            task.message = f"视频总时长: {task.total_duration:.2f}秒"
        else:
            task.total_duration = 0
            task.message = "无法获取视频时长，将显示简易进度"

        # 执行FFmpeg命令并实时捕获输出
        process = subprocess.Popen(
            command,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            encoding='utf-8',
            errors='ignore'
        )

        # 正则表达式匹配时间信息
        duration_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
        speed_pattern = re.compile(r'speed=([\d.]+)x')

        # 实时处理输出并更新进度
        task.message = "开始转换视频..."
        while True:
            if task.status == "cancelled":
                process.terminate()
                task.message = "转换任务已被取消"
                break

            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break

            if not line:
                continue

            # 解析时间信息
            match = duration_pattern.search(line)
            if match and task.total_duration > 0:
                hours, minutes, seconds = map(float, match.groups())
                task.current_time = hours * 3600 + minutes * 60 + seconds
                task.progress = min(100, (task.current_time / task.total_duration) * 100)

                speed_match = speed_pattern.search(line)
                if speed_match:
                    task.speed = f"{speed_match.group(1)}x"

                task.message = f"转换进度: {task.progress:.1f}% | 速度: {task.speed}"

            elif not task.total_duration and "time=" in line:
                task.progress = min(task.progress + 0.5, 99.9)
                task.message = f"转换中... {task.progress:.1f}%"

        # 等待进程结束
        return_code = process.wait()
        task.end_time = datetime.now()

        if task.status == "cancelled":
            return

        if return_code == 0:
            task.status = "completed"
            task.progress = 100

            if os.path.exists(m3u8_file):
                file_size = os.path.getsize(m3u8_file) / 1024
                ts_files = [f for f in os.listdir(output_dir) if f.endswith('.ts')]
                task.message = f"转换成功！M3U8文件大小: {file_size:.2f} KB, 生成 {len(ts_files)} 个TS切片"
            else:
                task.status = "error"
                task.message = "转换完成但未找到输出文件"

        else:
            task.status = "error"
            task.message = f"转换失败！FFmpeg返回码: {return_code}"

    except Exception as e:
        task.status = "error"
        task.message = f"转换过程中发生错误: {str(e)}"