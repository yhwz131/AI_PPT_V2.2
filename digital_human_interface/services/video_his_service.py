import os
import subprocess
import re
from typing import Optional, Dict
import logging
from pathlib import Path


class SimpleHLSSlicer:
    """
    精简版HLS视频切片器 - 返回以/static开头的路径
    """

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        """
        初始化HLS切片器

        Args:
            ffmpeg_path: FFmpeg可执行文件路径
        """
        self.ffmpeg_path = ffmpeg_path
        self.logger = self._setup_logger()

        # 验证工具是否可用
        self._verify_tools()

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _verify_tools(self) -> None:
        """验证FFmpeg是否可用"""
        try:
            subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                check=True
            )
            self.logger.info("FFmpeg可用")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("FFmpeg未找到或不可用")

    def slice_to_hls(
            self,
            video_path: str,
            output_dir: str,
            segment_duration: int = 10,
            quality: str = "medium",
            audio_quality: str = "128k",
            delete_existing: bool = False
    ) -> str:
        """
        将视频切片为HLS格式，返回以/static开头的播放列表路径

        Args:
            video_path: 输入视频文件路径
            output_dir: 输出目录路径
            segment_duration: 每个切片的时长（秒）
            quality: 视频质量（low, medium, high）
            audio_quality: 音频质量（如"128k"）
            delete_existing: 是否删除已存在的输出目录

        Returns:
            以/static开头的播放列表路径

        Raises:
            FileNotFoundError: 视频文件不存在时抛出
            RuntimeError: 切片失败时抛出
        """
        try:
            # 验证输入文件
            if not os.path.isfile(video_path):
                raise FileNotFoundError(f"视频文件不存在: {video_path}")

            # 创建输出目录
            output_path = Path(output_dir)
            if delete_existing and output_path.exists():
                import shutil
                shutil.rmtree(output_path)
                self.logger.info(f"已清理输出目录: {output_path}")

            output_path.mkdir(parents=True, exist_ok=True)

            # 构建输出路径
            playlist_path = output_path / "playlist.m3u8"
            segment_pattern = output_path / "segment_%03d.ts"

            self.logger.info(f"开始HLS转换...")
            self.logger.info(f"输入视频: {video_path}")
            self.logger.info(f"输出目录: {output_dir}")
            self.logger.info(f"切片时长: {segment_duration}秒")

            # 构建FFmpeg命令
            quality_params = self._get_quality_params(quality)

            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-c:v", "libx264",
                "-preset", quality_params["preset"],
                "-crf", str(quality_params["crf"]),
                "-c:a", "aac",
                "-b:a", audio_quality,
                "-f", "hls",
                "-hls_time", str(segment_duration),
                "-hls_list_size", "0",
                "-hls_segment_filename", str(segment_pattern),
                "-hls_playlist_type", "vod",
                "-y",
                str(playlist_path)
            ]

            # 添加码率控制
            if "bitrate" in quality_params:
                cmd.insert(8, quality_params["bufsize"])
                cmd.insert(8, "-bufsize")
                cmd.insert(8, quality_params["maxrate"])
                cmd.insert(8, "-maxrate")
                cmd.insert(8, quality_params["bitrate"])
                cmd.insert(8, "-b:v")

            self.logger.debug(f"FFmpeg命令: {' '.join(cmd)}")

            # 执行转换
            try:
                # 使用subprocess运行命令
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=False,
                    bufsize=1,
                    universal_newlines=False
                )

                # 读取并显示进度信息
                while True:
                    output = process.stderr.readline()
                    if output == b'' and process.poll() is not None:
                        break
                    if output:
                        try:
                            line = output.decode('utf-8', errors='ignore')
                            if "time=" in line:
                                time_match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
                                if time_match:
                                    self.logger.info(f"转换进度: {time_match.group(1)}")
                        except:
                            pass

                process.wait()

                if process.returncode != 0:
                    raise RuntimeError(f"FFmpeg返回错误码: {process.returncode}")

            except Exception as e:
                self.logger.error(f"执行FFmpeg命令失败: {e}")
                raise

            # 验证结果
            if not playlist_path.exists():
                raise RuntimeError(f"播放列表未生成: {playlist_path}")

            # 检查ts文件数量
            ts_files = list(output_path.glob("segment_*.ts"))
            if len(ts_files) == 0:
                ts_files = list(output_path.glob("*.ts"))

            self.logger.info(f"HLS切片完成!")
            self.logger.info(f"播放列表: {playlist_path.name}")
            self.logger.info(f"生成的ts切片数量: {len(ts_files)}")

            # 返回以/static开头的路径
            static_path = self._get_static_path(str(playlist_path))
            return static_path

        except Exception as e:
            self.logger.error(f"HLS切片失败: {e}")
            raise

    def simple_slice(
            self,
            video_path: str,
            output_dir: str,
            segment_duration: int = 10
    ) -> str:
        """
        最简单的HLS切片方法

        Args:
            video_path: 输入视频文件路径
            output_dir: 输出目录路径
            segment_duration: 每个切片的时长（秒）

        Returns:
            以/static开头的播放列表路径
        """
        try:
            # 验证输入文件
            if not os.path.isfile(video_path):
                raise FileNotFoundError(f"视频文件不存在: {video_path}")

            # 创建输出目录
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            playlist_path = output_path / "playlist.m3u8"
            segment_pattern = output_path / "segment_%03d.ts"

            self.logger.info(f"开始HLS转换（简单模式）...")

            # 构建最简单的命令
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-f", "hls",
                "-hls_time", str(segment_duration),
                "-hls_list_size", "0",
                "-hls_segment_filename", str(segment_pattern),
                "-hls_playlist_type", "vod",
                "-y",
                str(playlist_path)
            ]

            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=False,
                check=True
            )

            if playlist_path.exists():
                # 检查ts文件
                ts_files = list(output_path.glob("segment_*.ts"))
                self.logger.info(f"播放列表生成成功: {playlist_path.name}")
                self.logger.info(f"生成的ts切片数量: {len(ts_files)}")

                # 返回以/static开头的路径
                static_path = self._get_static_path(str(playlist_path))
                return static_path
            else:
                raise RuntimeError("播放列表未生成")

        except subprocess.CalledProcessError as e:
            error_output = e.stderr.decode('utf-8', errors='ignore') if e.stderr else "未知错误"
            self.logger.error(f"FFmpeg执行失败: {error_output}")
            raise RuntimeError(f"HLS切片失败: {error_output}")
        except Exception as e:
            self.logger.error(f"HLS切片失败: {e}")
            raise

    def _get_static_path(self, absolute_path: str) -> str:
        """
        获取以/static开头的路径

        Args:
            absolute_path: 绝对路径

        Returns:
            以/static开头的路径
        """
        # 将路径中的反斜杠替换为正斜杠
        normalized_path = absolute_path.replace('\\', '/')

        # 查找"/static"在路径中的位置
        static_index = normalized_path.find('/static')

        if static_index >= 0:
            # 找到/static，截取从该位置开始的子串
            static_path = normalized_path[static_index:]

            # 确保路径以/static开头
            if not static_path.startswith('/static'):
                static_path = '/static' + static_path

            return static_path
        else:
            # 如果没有找到/static，尝试查找"static"
            static_index = normalized_path.find('static/')
            if static_index > 0:
                # 获取从static开始的路径
                static_path = normalized_path[static_index - 1:]  # 包含前导斜杠

                # 确保路径以/static开头
                if not static_path.startswith('/static'):
                    static_path = '/static' + static_path

                return static_path
            else:
                # 如果都找不到，返回相对路径
                self.logger.warning(f"无法从路径中提取/static部分: {absolute_path}")
                return normalized_path

    def _get_quality_params(self, quality: str) -> Dict:
        """根据质量设置获取参数"""
        quality_levels = {
            "low": {
                "preset": "ultrafast",
                "crf": 28,
                "bitrate": "800k",
                "maxrate": "1000k",
                "bufsize": "1600k"
            },
            "medium": {
                "preset": "fast",
                "crf": 23,
                "bitrate": "2000k",
                "maxrate": "2500k",
                "bufsize": "4000k"
            },
            "high": {
                "preset": "medium",
                "crf": 18,
                "bitrate": "5000k",
                "maxrate": "6000k",
                "bufsize": "10000k"
            }
        }

        return quality_levels.get(quality, quality_levels["medium"])

    def list_output_files(self, output_dir: str) -> list:
        """
        列出输出目录中的所有文件

        Args:
            output_dir: 输出目录路径

        Returns:
            文件列表
        """
        output_path = Path(output_dir)
        if not output_path.exists():
            return []

        files = []
        for file in output_path.iterdir():
            if file.is_file():
                files.append({
                    "name": file.name,
                    "size": file.stat().st_size,
                    "path": str(file)
                })

        # 按文件名排序
        files.sort(key=lambda x: x["name"])
        return files