import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set
from datetime import datetime
import shutil

logger = logging.getLogger(__name__)


class FileCleanupService:
    """文件清理服务类"""

    def __init__(self, base_dir: str = None):
        """
        初始化清理服务

        参数:
            base_dir: 项目基础目录，如果为None则自动获取
        """
        if base_dir is None:
            # 获取项目根目录
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.base_dir = base_dir
        self.json_path = os.path.join(base_dir, "static", "data", "basic_information.json")

        # 初始化路径配置
        self.path_config = {
            'pdf': os.path.join(base_dir, "static", "file", "pdf"),
            'video_mergers': os.path.join(base_dir, "static", "video", "mergers"),
            'images': os.path.join(base_dir, "static", "file", "images"),
            'hls': os.path.join(base_dir, "static", "video", "hls"),
            'audio': os.path.join(base_dir, "static", "audio"),
            'video_temp': os.path.join(base_dir, "static", "video", "temp"),
            'uploads': os.path.join(base_dir, "static", "file", "uploads"),
            'bgm': os.path.join(base_dir, "static", "file", "bgm"),
        }

    def load_json_data(self) -> Dict:
        """加载JSON配置文件"""
        try:
            if not os.path.exists(self.json_path):
                logger.error(f"JSON配置文件不存在: {self.json_path}")
                return None

            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            logger.info(f"成功加载JSON数据，包含 {len(data.get('data', []))} 条记录")
            return data

        except Exception as e:
            logger.error(f"加载JSON数据失败: {e}")
            return None

    def extract_filenames_from_json(self, json_data: Dict) -> Dict[str, Set[str]]:
        """
        从JSON数据中提取所有引用的文件名

        返回:
            {
                'pdf': set(['file1', 'file2', ...]),
                'video': set(['file1', 'file2', ...]),
                'image_folders': set(['file1', 'file2', ...]),
                'hls_folders': set(['file1', 'file2', ...])
            }
        """
        if not json_data or 'data' not in json_data:
            return {'pdf': set(), 'video': set(), 'image_folders': set(), 'hls_folders': set()}

        pdf_names = set()
        video_names = set()
        image_folders = set()  # 图片文件夹名称
        hls_folders = set()  # HLS文件夹名称

        for item in json_data['data']:
            # 提取PDF文件名（不含扩展名）
            if 'pdf_path' in item and item['pdf_path']:
                try:
                    pdf_path = str(item['pdf_path'])
                    # 从路径中提取文件名
                    if '/' in pdf_path:
                        filename = pdf_path.split('/')[-1]
                    else:
                        filename = pdf_path

                    # 去除扩展名
                    name_without_ext = filename.split('.')[0]
                    pdf_names.add(name_without_ext)
                except Exception as e:
                    logger.warning(f"解析PDF路径失败: {item.get('pdf_path')}, 错误: {e}")

            # 提取视频文件名（不含扩展名）
            if 'video_path' in item and item['video_path']:
                try:
                    video_path = str(item['video_path'])
                    # 从路径中提取文件名
                    if '/' in video_path:
                        filename = video_path.split('/')[-1]
                    else:
                        filename = video_path

                    # 去除扩展名
                    name_without_ext = filename.split('.')[0]
                    video_names.add(name_without_ext)

                    # 视频文件对应的图片文件夹和HLS文件夹也视为被引用
                    image_folders.add(name_without_ext)
                    hls_folders.add(name_without_ext)
                except Exception as e:
                    logger.warning(f"解析视频路径失败: {item.get('video_path')}, 错误: {e}")

        logger.info(f"从JSON中提取: {len(pdf_names)} 个PDF文件, {len(video_names)} 个视频文件")

        return {
            'pdf': pdf_names,
            'video': video_names,
            'image_folders': image_folders,
            'hls_folders': hls_folders
        }

    def get_existing_files(self, directory: str, is_dir: bool = False) -> Set[str]:
        """
        获取指定目录下存在的文件或文件夹

        参数:
            directory: 目录路径
            is_dir: 是否获取文件夹（True获取文件夹，False获取文件）

        返回:
            文件名列表（不含扩展名或文件夹名）
        """
        if not os.path.exists(directory):
            logger.warning(f"目录不存在: {directory}")
            return set()

        existing_items = set()

        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)

                if is_dir:
                    # 获取文件夹
                    if os.path.isdir(item_path):
                        existing_items.add(item)
                else:
                    # 获取文件（去除扩展名）
                    if os.path.isfile(item_path):
                        # 去除扩展名
                        name_without_ext = os.path.splitext(item)[0]
                        existing_items.add(name_without_ext)

            logger.debug(f"目录 {directory} 下找到 {len(existing_items)} 个{'文件夹' if is_dir else '文件'}")
            return existing_items

        except Exception as e:
            logger.error(f"遍历目录失败 {directory}: {e}")
            return set()

    def get_all_files_with_extensions(self, directory: str, extensions: List[str] = None) -> Set[str]:
        """
        获取指定目录下指定扩展名的所有文件（不含扩展名）

        参数:
            directory: 目录路径
            extensions: 扩展名列表，如 ['.mp4', '.pdf']

        返回:
            文件名列表（不含扩展名）
        """
        if not os.path.exists(directory):
            logger.warning(f"目录不存在: {directory}")
            return set()

        files = set()

        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)

                if os.path.isfile(item_path):
                    if extensions:
                        if any(item.endswith(ext) for ext in extensions):
                            # 去除扩展名
                            name_without_ext = os.path.splitext(item)[0]
                            files.add(name_without_ext)
                    else:
                        # 没有指定扩展名，返回所有文件
                        name_without_ext = os.path.splitext(item)[0]
                        files.add(name_without_ext)

            return files

        except Exception as e:
            logger.error(f"获取文件列表失败 {directory}: {e}")
            return set()

    def cleanup_unreferenced_files(self) -> Dict[str, int]:
        """
        清理未引用的文件

        返回:
            清理统计信息
        """
        stats = {
            'pdf_deleted': 0,
            'video_deleted': 0,
            'image_folders_deleted': 0,
            'hls_folders_deleted': 0,
            'errors': 0
        }

        try:
            # 1. 加载JSON数据
            json_data = self.load_json_data()
            if not json_data:
                logger.error("无法加载JSON数据，清理终止")
                return stats

            # 2. 提取引用的文件名
            referenced = self.extract_filenames_from_json(json_data)
            referenced_pdf = referenced['pdf']
            referenced_video = referenced['video']
            referenced_image_folders = referenced['image_folders']
            referenced_hls_folders = referenced['hls_folders']

            logger.info(f"开始清理，共引用 {len(referenced_pdf)} 个PDF, {len(referenced_video)} 个视频")

            # 3. 清理PDF文件
            existing_pdf = self.get_all_files_with_extensions(self.path_config['pdf'], ['.pdf'])
            for pdf_name in existing_pdf:
                if pdf_name not in referenced_pdf:
                    try:
                        # 查找所有可能的PDF文件（包括不同扩展名大小写）
                        pdf_files = []
                        for file in os.listdir(self.path_config['pdf']):
                            if file.lower().endswith('.pdf'):
                                name_without_ext = os.path.splitext(file)[0]
                                if name_without_ext == pdf_name:
                                    pdf_files.append(file)

                        # 删除所有匹配的PDF文件
                        for pdf_file in pdf_files:
                            pdf_path = os.path.join(self.path_config['pdf'], pdf_file)
                            if os.path.exists(pdf_path):
                                os.remove(pdf_path)
                                stats['pdf_deleted'] += 1
                                logger.info(f"删除未引用PDF: {pdf_path}")
                    except Exception as e:
                        logger.error(f"删除PDF文件失败 {pdf_name}: {e}")
                        stats['errors'] += 1

            # 4. 清理视频文件
            existing_videos = self.get_all_files_with_extensions(self.path_config['video_mergers'],
                                                                 ['.mp4', '.avi', '.mov', '.mkv'])
            for video_name in existing_videos:
                if video_name not in referenced_video:
                    try:
                        # 查找所有可能的视频文件
                        video_files = []
                        video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
                        for file in os.listdir(self.path_config['video_mergers']):
                            for ext in video_extensions:
                                if file.lower().endswith(ext):
                                    name_without_ext = os.path.splitext(file)[0]
                                    if name_without_ext == video_name:
                                        video_files.append(file)
                                        break

                        # 删除所有匹配的视频文件
                        for video_file in video_files:
                            video_path = os.path.join(self.path_config['video_mergers'], video_file)
                            if os.path.exists(video_path):
                                os.remove(video_path)
                                stats['video_deleted'] += 1
                                logger.info(f"删除未引用视频: {video_path}")
                    except Exception as e:
                        logger.error(f"删除视频文件失败 {video_name}: {e}")
                        stats['errors'] += 1

            # 5. 清理图片文件夹
            existing_image_folders = self.get_existing_files(self.path_config['images'], is_dir=True)
            for folder_name in existing_image_folders:
                if folder_name not in referenced_image_folders:
                    try:
                        folder_path = os.path.join(self.path_config['images'], folder_name)
                        if os.path.exists(folder_path):
                            # 删除文件夹及其所有内容
                            shutil.rmtree(folder_path)
                            stats['image_folders_deleted'] += 1
                            logger.info(f"删除未引用图片文件夹: {folder_path}")
                    except Exception as e:
                        logger.error(f"删除图片文件夹失败 {folder_name}: {e}")
                        stats['errors'] += 1

            # 6. 清理HLS文件夹
            existing_hls_folders = self.get_existing_files(self.path_config['hls'], is_dir=True)
            for folder_name in existing_hls_folders:
                if folder_name not in referenced_hls_folders:
                    try:
                        folder_path = os.path.join(self.path_config['hls'], folder_name)
                        if os.path.exists(folder_path):
                            # 删除文件夹及其所有内容
                            shutil.rmtree(folder_path)
                            stats['hls_folders_deleted'] += 1
                            logger.info(f"删除未引用HLS文件夹: {folder_path}")
                    except Exception as e:
                        logger.error(f"删除HLS文件夹失败 {folder_name}: {e}")
                        stats['errors'] += 1

            # 7. 清理音频文件夹
            audio_deleted = self.cleanup_audio_folder()
            logger.info(f"清理音频文件夹，删除 {audio_deleted} 个文件/文件夹")

            # 8. 清理临时视频文件夹
            temp_video_deleted = self.cleanup_temp_video_folder()
            logger.info(f"清理临时视频文件夹，删除 {temp_video_deleted} 个文件/文件夹")

            # 9. 清理 PPT 原文件（uploads 目录全清）
            uploads_deleted = self._cleanup_directory(self.path_config['uploads'])
            logger.info(f"清理PPT上传目录，删除 {uploads_deleted} 个文件")

            # 10. 清理 BGM 上传文件（bgm 目录全清）
            bgm_deleted = self._cleanup_directory(self.path_config['bgm'])
            logger.info(f"清理BGM上传目录，删除 {bgm_deleted} 个文件")

            logger.info(f"清理完成: 删除 {stats['pdf_deleted']} PDF, {stats['video_deleted']} 视频, "
                        f"{stats['image_folders_deleted']} 图片文件夹, {stats['hls_folders_deleted']} HLS文件夹")

            return stats

        except Exception as e:
            logger.error(f"清理过程中发生错误: {e}")
            stats['errors'] += 1
            return stats

    def _cleanup_directory(self, directory: str) -> int:
        """清空指定目录下的所有文件（保留目录本身）"""
        deleted = 0
        if not os.path.exists(directory):
            return 0
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    deleted += 1
                except Exception as e:
                    logger.error(f"删除文件失败 {item_path}: {e}")
        except Exception as e:
            logger.error(f"清理目录失败 {directory}: {e}")
        return deleted

    def cleanup_audio_folder(self) -> int:
        """清理整个音频文件夹"""
        audio_dir = self.path_config['audio']
        deleted_count = 0

        if os.path.exists(audio_dir):
            try:
                for item in os.listdir(audio_dir):
                    item_path = os.path.join(audio_dir, item)
                    try:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"删除音频文件失败 {item_path}: {e}")

                logger.info(f"清理音频文件夹，删除 {deleted_count} 个文件/文件夹")
            except Exception as e:
                logger.error(f"清理音频文件夹失败: {e}")

        return deleted_count

    def cleanup_temp_video_folder(self) -> int:
        """清理临时视频文件夹"""
        temp_video_dir = self.path_config['video_temp']
        deleted_count = 0

        if os.path.exists(temp_video_dir):
            try:
                for item in os.listdir(temp_video_dir):
                    item_path = os.path.join(temp_video_dir, item)
                    try:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"删除临时视频文件失败 {item_path}: {e}")

                logger.info(f"清理临时视频文件夹，删除 {deleted_count} 个文件/文件夹")
            except Exception as e:
                logger.error(f"清理临时视频文件夹失败: {e}")

        return deleted_count

    def run_cleanup(self) -> Dict:
        """执行完整的清理流程"""
        start_time = datetime.now()
        logger.info("开始执行文件清理任务")

        stats = self.cleanup_unreferenced_files()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        result = {
            'status': 'success' if stats.get('errors', 0) == 0 else 'completed_with_errors',
            'stats': stats,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'message': f"清理完成，耗时 {duration:.2f} 秒"
        }

        if stats.get('errors', 0) > 0:
            result['message'] += f"，发生 {stats['errors']} 个错误"

        logger.info(f"清理任务完成: {result['message']}")
        return result