import time
import traceback
import hashlib
import html
import json
import os
import re
import asyncio
from pathlib import Path
from typing import Dict, Tuple, Any, List, AsyncGenerator, Optional
from datetime import datetime
from services.video_his_service import SimpleHLSSlicer
import httpx
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, UploadFile, Form, File, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from config.config import Settings
from services.extract_compressed_file_service import ZipProcessor
from services.json_info_service import JsonDataManager
from services.pdf_image_service import convert_and_get_urls
from services.video_merge_service import VideoMerger, mix_bgm

settings = Settings()

router = APIRouter(
    prefix="/my_digital_human",
    tags=["数字人管理"],
    responses={
        404: {"description": "接口不存在"},
        500: {"description": "服务器内部错误"}
    }
)

# ========== 常量定义 ==========
# 数字人位置存储字典（兼容旧前端中文键名 + 新前端英文值）
location_dir = {
    "浮层-左下": "bottom-left",
    "浮层-左上": "top-left",
    "浮层-右下": "bottom-right",
    "浮层-右上": "top-right",
    "浮层-中央": "center",
    "无数字人": "none",
    "bottom-left": "bottom-left",
    "top-left": "top-left",
    "bottom-right": "bottom-right",
    "top-right": "top-right",
    "center": "center",
    "none": "none",
}

# 音频生成url
audio_url="http://127.0.0.1:6006/batch_tts_url"
# 数字人生成url
digital_human_url="http://127.0.0.1:5000/generate/upload"

# ========== SSE事件类型定义 ==========
class SSEMessage:
    """SSE消息类型"""

    @staticmethod
    def format(event: str, data: Any) -> bytes:
        """格式化SSE消息为字节流"""
        message = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        return message.encode('utf-8')

    @staticmethod
    def progress_stage(
        stage: str,
        message: str,
        progress: int = 0,
        current: int = 0,
        total: int = 0,
        current_stage_progress: int = 0  # 新增参数：当前阶段内部进度
    ) -> bytes:
        """进度阶段消息"""
        return SSEMessage.format("progress", {
            "stage": stage,
            "message": message,
            "progress": progress,
            "current": current,
            "total": total,
            "current_stage_progress": current_stage_progress  # 新增字段
        })

    @staticmethod
    def error(message: str) -> bytes:
        """错误消息"""
        return SSEMessage.format("error", {"message": message})

    @staticmethod
    def success(data: Any) -> bytes:
        """成功消息"""
        return SSEMessage.format("success", data)

    @staticmethod
    def video_result(result: Dict[str, Any]) -> bytes:
        """单个视频结果"""
        return SSEMessage.format("video_result", result)

    @staticmethod
    def connected(task_id: str) -> bytes:
        """连接确认消息"""
        return SSEMessage.format("connected", {"task_id": task_id})

    @staticmethod
    def end() -> bytes:
        """结束消息"""
        return b"event: end\ndata: {}\n\n"

    @staticmethod
    def heartbeat() -> bytes:
        """心跳消息，防止代理/浏览器超时"""
        return b": heartbeat\n\n"


# ========== 任务事件队列（SSE拆分用） ==========
task_event_queues: Dict[str, asyncio.Queue] = {}
# 事件历史缓存，用于断线重连时回放
task_event_history: Dict[str, List[bytes]] = {}
# 任务是否仍在运行
task_running: Dict[str, bool] = {}

# ========== 任务状态存储 ==========
task_status_store = {}
TASK_EXPIRY_HOURS = 24


# ========== 辅助函数 ==========
def generate_task_id() -> str:
    """生成唯一的任务ID"""
    timestamp = int(time.time() * 1000)
    random_str = hashlib.md5(str(timestamp).encode()).hexdigest()[:8]
    return f"task_{timestamp}_{random_str}"


def cleanup_old_tasks():
    """清理过期任务"""
    now = time.time()
    expired_tasks = []

    for task_id, task_data in task_status_store.items():
        created_at = task_data.get("created_at", 0)
        # 如果任务创建时间超过24小时，标记为过期
        if now - created_at > TASK_EXPIRY_HOURS * 3600:
            expired_tasks.append(task_id)

    for task_id in expired_tasks:
        del task_status_store[task_id]
        task_event_history.pop(task_id, None)
        task_event_queues.pop(task_id, None)
        task_running.pop(task_id, None)
        print(f"已清理过期任务: {task_id}")


def update_task_status(task_id: str, status_updates: Dict[str, Any]):
    """更新任务状态"""
    if task_id not in task_status_store:
        task_status_store[task_id] = {
            "created_at": time.time(),
            "updated_at": time.time(),
            "status": "pending"
        }

    task_status_store[task_id].update(status_updates)
    task_status_store[task_id]["updated_at"] = time.time()


def _cleanup_temp_files(data: Dict[str, Any]):
    """生成完成后清理临时文件（PPT原文件 + BGM上传文件）"""
    try:
        # 1. 清理 PPT 原文件：从 pdf_path 推导 uploads 路径
        pdf_path = data.get("pdf_path", "")
        if pdf_path:
            pdf_basename = os.path.basename(pdf_path)
            file_uuid = os.path.splitext(pdf_basename)[0]
            uploads_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "static", "file", "uploads"
            )
            if os.path.isdir(uploads_dir):
                import glob as _glob
                for f in _glob.glob(os.path.join(uploads_dir, f"{file_uuid}.*")):
                    try:
                        os.remove(f)
                        print(f"已清理PPT临时文件: {f}")
                    except Exception as e:
                        print(f"清理PPT临时文件失败: {f}, {e}")

        # 2. 清理 BGM 上传文件
        bgm_path = data.get("bgm_path", "")
        if bgm_path and os.path.isfile(bgm_path):
            try:
                os.remove(bgm_path)
                print(f"已清理BGM临时文件: {bgm_path}")
            except Exception as e:
                print(f"清理BGM临时文件失败: {bgm_path}, {e}")
    except Exception as e:
        print(f"清理临时文件时出错: {e}")


# ========== 核心数字人生成逻辑 ==========
async def track_digital_human_generation(
        data: Dict[str, Any],
        task_id: str
) -> AsyncGenerator[bytes, None]:
    """
    跟踪数字人生成进度，并生成SSE事件流

    在每个功能点完成后实时发送状态信息，确保前端能获取最新进度

    Args:
        data: 数字人生成数据
        task_id: 任务ID

    Yields:
        SSE格式的事件消息（字节流）
    """
    # 用于记录打开的文件句柄，确保最终能关闭
    open_files = []

    try:
        # 初始化任务状态
        update_task_status(task_id, {
            "status": "running",
            "progress": 0,
            "current_stage": "开始处理",
            "results": [],
            "message": "开始数字人生成任务"
        })

        # 发送连接确认消息
        yield SSEMessage.connected(task_id)
        print(f"任务开始，任务ID: {task_id}")

        # 阶段1: 解析讲稿内容
        # 预留最低进度：解析阶段结束前至少推进到此值，防止后续比例计算导致进度回退
        STAGE1_MIN_PROGRESS = 10
        try:
            yield SSEMessage.progress_stage(
                "parse_script",
                "开始解析讲稿内容...",
                progress=0,
                current_stage_progress=0
            )
            print("开始解析讲稿内容")

            update_task_status(task_id, {
                "current_stage": "parse_script",
                "message": "开始解析讲稿内容"
            })

            # 处理HTML转义字符
            unescaped_content = html.unescape(data["scriptContent"])
            soup = BeautifulSoup(unescaped_content, "lxml")
            texts = []  # 存储口播文案
            content_lis = []  # 存储基本信息

            yield SSEMessage.progress_stage(
                "parse_script",
                "正在解析HTML内容...",
                progress=3,
                current_stage_progress=30
            )
            print("正在解析HTML内容")

            for item in soup.select("div"):
                h3_elements = item.select("h3")
                p_elements = item.select("p")
                if h3_elements and p_elements:
                    title = str(h3_elements[0].text).replace("标题: ", '')
                    text = str(p_elements[0].text).replace("内容: ", '')
                    texts.append(text)
                    content_lis.append(title)

            if not texts or not content_lis:
                h3_all = soup.find_all("h3")
                p_all = soup.find_all("p")
                for h3_el, p_el in zip(h3_all, p_all):
                    title = str(h3_el.get_text()).replace("标题: ", '').replace("标题:", '')
                    text = str(p_el.get_text()).replace("内容: ", '').replace("内容:", '')
                    if title.strip() and text.strip():
                        content_lis.append(title.strip())
                        texts.append(text.strip())

            if not texts or not content_lis:
                raise ValueError("解析讲稿内容为空，请检查HTML结构")

            yield SSEMessage.progress_stage(
                "parse_script",
                "讲稿解析完成",
                progress=6,
                current_stage_progress=60
            )
            print("讲稿解析完成")

            # 基于文本字数的加权时间预估
            total_segments = len(texts)
            total_chars = sum(len(t) for t in texts)
            estimated_audio_duration = total_chars * 0.05

            stage1_time = 1   # 文档解析
            stage2_time = 2   # 准备文件
            stage3_time = max(3, int(estimated_audio_duration * 0.3))
            stage4_time = 1   # 处理音频
            stage5_time = max(10, int(estimated_audio_duration * 12))
            stage6_time = 1   # 视频合并
            stage7_time = 3   # 视频切片

            total_time = (
                    stage1_time + stage2_time + stage3_time +
                    stage4_time + stage5_time + stage6_time + stage7_time
            )
            _min, _sec = divmod(total_time, 60)
            time_str = f"{_min}分{_sec}秒" if _min > 0 else f"{_sec}秒"

            # 剩余可分配进度 = 100 - STAGE1_MIN_PROGRESS
            remaining_progress = 100 - STAGE1_MIN_PROGRESS
            remaining_time = stage2_time + stage3_time + stage4_time + stage5_time + stage6_time + stage7_time
            if remaining_time <= 0:
                remaining_time = 1

            stage2_progress = max(1, int((stage2_time / remaining_time) * remaining_progress))
            stage3_progress = max(1, int((stage3_time / remaining_time) * remaining_progress))
            stage4_progress = max(1, int((stage4_time / remaining_time) * remaining_progress))
            stage5_progress = max(1, int((stage5_time / remaining_time) * remaining_progress))
            stage6_progress = max(1, int((stage6_time / remaining_time) * remaining_progress))
            stage7_progress = max(1, int((stage7_time / remaining_time) * remaining_progress))

            # 累计进度从 STAGE1_MIN_PROGRESS 开始，保证只增不减
            accumulated_progress = STAGE1_MIN_PROGRESS

            yield SSEMessage.progress_stage(
                "parse_script",
                f"预估总时间: {time_str}, 总段数: {total_segments}, 总字数: {total_chars}",
                progress=accumulated_progress,
                current_stage_progress=100
            )
            print(f"预估总时间: {time_str}, 总段数: {total_segments}, 总字数: {total_chars}")

            update_task_status(task_id, {
                "progress": accumulated_progress,
                "message": f"讲稿解析完成，共{total_segments}段/{total_chars}字，预估: {time_str}",
                "time_estimation": {
                    "total_segments": total_segments,
                    "total_chars": total_chars,
                    "total_time_seconds": total_time,
                    "estimated_audio_duration": round(estimated_audio_duration, 1),
                    "stage3_time": stage3_time,
                    "stage5_time": stage5_time,
                }
            })

        except Exception as e:
            error_msg = "讲稿解析失败，请检查内容格式"
            print(f"讲稿解析失败: {str(e)}")
            traceback.print_exc()

            yield SSEMessage.error(error_msg)
            update_task_status(task_id, {
                "status": "failed",
                "error": error_msg,
                "progress": 100
            })
            return

        # 阶段2: 准备文件路径
        try:
            # 发送开始准备文件消息
            yield SSEMessage.progress_stage(
                "prepare_files",
                "开始准备相关文件...",
                progress=accumulated_progress,
                current_stage_progress=0
            )
            print("开始准备文件路径")

            update_task_status(task_id, {
                "current_stage": "prepare_files",
                "message": "开始准备相关文件"
            })

            # 获取音频文件路径
            human_data = data.get("human", {})
            audio_path = human_data.get("audio", "")
            if not audio_path:
                raise ValueError("数字人音频路径为空")

            spk_audio_path = get_file_path(audio_path)

            # 检查文件是否存在
            if not os.path.exists(spk_audio_path):
                raise FileNotFoundError("音频文件不存在")

            # 发送音频文件准备消息
            yield SSEMessage.progress_stage(
                "prepare_files",
                "音频文件准备完成",
                progress=accumulated_progress,
                current_stage_progress=33
            )
            print("音频文件路径准备完成")

            # 获取PDF文件路径
            pdf_path = data.get("pdf_path", "")
            if not pdf_path:
                raise ValueError("PDF路径为空")

            pdf_full_path = get_file_path(pdf_path)

            # 检查PDF文件是否存在
            if not os.path.exists(pdf_full_path):
                raise FileNotFoundError("PDF文件不存在")

            print("PDF文件路径准备完成")

            # 提取文件名
            file_name = os.path.basename(pdf_path)
            if "." in file_name:
                name_only = file_name[:file_name.index(".")]
            else:
                name_only = file_name

            print("文件准备完成")

            # 发送文件准备完成的状态信息
            yield SSEMessage.progress_stage(
                "prepare_files",
                "所有文件准备完成",
                progress=accumulated_progress + stage2_progress,
                current_stage_progress=100
            )
            print("文件准备完成")

            accumulated_progress += stage2_progress

            update_task_status(task_id, {
                "progress": accumulated_progress,
                "message": "文件准备完成"
            })

        except Exception as e:
            error_msg = "文件准备失败，请检查文件路径"
            print(f"文件准备失败: {str(e)}")
            traceback.print_exc()

            yield SSEMessage.error(error_msg)
            update_task_status(task_id, {
                "status": "failed",
                "error": error_msg,
                "progress": 100
            })
            return

        # 阶段3: 音频生成
        try:
            # 发送开始音频生成消息
            yield SSEMessage.progress_stage(
                "audio_generation",
                "开始生成音频文件...",
                progress=accumulated_progress,
                current_stage_progress=0
            )
            print("开始生成音频文件")

            update_task_status(task_id, {
                "current_stage": "audio_generation",
                "message": "开始生成音频文件"
            })

            # 发送音频生成进行中消息
            yield SSEMessage.progress_stage(
                "audio_generation",
                "正在处理音频生成...",
                progress=accumulated_progress,
                current_stage_progress=30
            )
            print(f"正在处理{len(texts)}段文本的音频生成")

            # 使用异步HTTP客户端替换同步requests
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 调用音频生成函数
                print(f"调用音频生成，文本数量: {len(texts)}")

                # 注意：这里假设audio_generation是异步函数
                # 如果audio_generation是同步的，可以这样调用：
                # audio_response = await asyncio.to_thread(audio_generation, texts, spk_audio_path)
                emo_kwargs = {}
                raw_emo = data.get("emo_control_method", 0)
                emo_map = {"natural": 0, "vector": 2, "text": 3}
                if isinstance(raw_emo, str) and raw_emo in emo_map:
                    emo_method = emo_map[raw_emo]
                else:
                    emo_method = int(raw_emo) if raw_emo else 0
                if emo_method:
                    emo_kwargs["emo_control_method"] = emo_method
                    if emo_method == 2:
                        emo_kwargs["emo_vec"] = data.get("emo_vec", "")
                    elif emo_method == 3:
                        emo_kwargs["emo_text"] = data.get("emo_text", "")
                audio_response = await asyncio.to_thread(
                    audio_generation, texts, spk_audio_path, **emo_kwargs
                )

            if not audio_response.get("success"):
                error_msg = "音频生成失败"
                print(f"音频生成失败: {audio_response.get('error', '未知错误')}")

                yield SSEMessage.error(error_msg)
                update_task_status(task_id, {
                    "status": "failed",
                    "error": error_msg,
                    "progress": 100
                })
                return

            print("音频生成成功")

            # 发送音频生成完成的状态信息
            yield SSEMessage.progress_stage(
                "audio_generation",
                "音频生成完成",
                progress=accumulated_progress + stage3_progress,
                current_stage_progress=100
            )
            print("音频生成完成")

            accumulated_progress += stage3_progress

            update_task_status(task_id, {
                "progress": accumulated_progress,
                "message": "音频生成完成"
            })

        except Exception as e:
            error_msg = "音频生成过程出错"
            print(f"音频生成过程出错: {str(e)}")
            traceback.print_exc()

            yield SSEMessage.error(error_msg)
            update_task_status(task_id, {
                "status": "failed",
                "error": error_msg,
                "progress": 100
            })
            return

        # 阶段4: 处理音频压缩包
        try:
            # 发送开始处理音频压缩包消息
            yield SSEMessage.progress_stage(
                "process_audio",
                "开始处理音频文件...",
                progress=accumulated_progress,
                current_stage_progress=0
            )
            print("开始处理音频压缩包")

            update_task_status(task_id, {
                "current_stage": "process_audio",
                "message": "开始处理音频文件"
            })

            # 创建ZIP处理器实例
            project_root = Path(__file__).resolve().parent.parent
            processor = ZipProcessor(str(project_root))

            # 发送下载压缩包消息
            yield SSEMessage.progress_stage(
                "process_audio",
                "正在处理音频文件...",
                progress=accumulated_progress,
                current_stage_progress=25
            )
            print("正在下载音频压缩包")

            # 使用异步方式处理ZIP包
            result = await asyncio.to_thread(
                processor.process_zip_from_url,
                url=audio_response["batch_zip_url"],
                temp_path=os.path.join("C:", "zip", "down"),  # 使用os.path.join确保路径正确
                save_path=os.path.join("static", "audio", name_only),
                prefix="audio",
                delete_after_extract=True
            )

            if not result:
                error_msg = "音频压缩包处理失败"
                print(f"音频压缩包处理失败")

                yield SSEMessage.error(error_msg)
                update_task_status(task_id, {
                    "status": "failed",
                    "error": error_msg,
                    "progress": 100
                })
                return

            extract_path, relative_paths = result

            print(f"音频处理完成，共{len(relative_paths)}个音频文件")

            # 发送音频处理完成的状态信息
            yield SSEMessage.progress_stage(
                "process_audio",
                "音频处理完成",
                progress=accumulated_progress + stage4_progress,
                current_stage_progress=100
            )
            print("音频处理完成")

            accumulated_progress += stage4_progress

            update_task_status(task_id, {
                "progress": accumulated_progress,
                "message": "音频处理完成"
            })

        except Exception as e:
            error_msg = "音频处理失败"
            print(f"音频处理失败: {str(e)}")
            traceback.print_exc()

            yield SSEMessage.error(error_msg)
            update_task_status(task_id, {
                "status": "failed",
                "error": error_msg,
                "progress": 100
            })
            return

        # 阶段5: 数字人视频生成
        try:
            # 获取模板位置
            position = location_dir.get(data.get("template", ""), "bottom-left")
            no_digital_human = (position == "none")

            face_video = None
            if not no_digital_human:
                video_path = human_data.get("video", "")
                if not video_path:
                    raise ValueError("数字人视频路径为空")
                face_video = get_file_path(video_path)
                if not os.path.exists(face_video):
                    raise FileNotFoundError("数字人视频文件不存在")

            total_videos = len(content_lis)

            # 确保音频文件数量与内容数量匹配
            if len(relative_paths) != total_videos:
                print(f"警告: 音频文件数量({len(relative_paths)})与内容数量({total_videos})不匹配")

            total_video_time = stage5_time
            _vmin, _vsec = divmod(total_video_time, 60)
            video_time_str = f"{_vmin}分{_vsec}秒" if _vmin > 0 else f"{_vsec}秒"

            yield SSEMessage.progress_stage(
                "video_generation_start",
                f"开始生成数字人视频，共{total_videos}个视频，预估: {video_time_str}",
                progress=accumulated_progress,
                current=0,
                total=total_videos,
                current_stage_progress=0
            )
            print(f"开始生成数字人视频，共{total_videos}个视频，预估: {video_time_str}")

            update_task_status(task_id, {
                "current_stage": "video_generation_start",
                "message": f"开始生成数字人视频，共{total_videos}个视频"
            })

            # 转换PDF为图片
            # 发送开始PDF转换消息
            yield SSEMessage.progress_stage(
                "convert_pdf",
                "正在准备背景图片...",
                progress=accumulated_progress,
                current_stage_progress=0
            )
            print("开始转换PDF为图片")

            update_task_status(task_id, {
                "current_stage": "convert_pdf",
                "message": "正在准备背景图片"
            })

            # 调用PDF转图片服务
            urls = await asyncio.to_thread(
                convert_and_get_urls,
                pdf_path=pdf_full_path,
                output_folder=os.path.join("static", "file", "images", name_only),
                zoom=2.5,
                prefix="slide_"
            )

            if not urls:
                raise ValueError("PDF转换失败，未生成任何图片")

            print(f"PDF转换完成，共{len(urls)}张图片")

            # 发送PDF转换完成的状态信息
            yield SSEMessage.progress_stage(
                "convert_pdf",
                "背景图片准备完成",
                progress=accumulated_progress,
                current_stage_progress=100
            )
            print("PDF转换完成")

            update_task_status(task_id, {
                "progress": accumulated_progress,
                "message": "背景图片准备完成"
            })

            # 逐个生成视频（优化：复用HTTP连接 + 异步轮询 + Wav2Lip模型预加载）
            completed_count = 0
            failed_count = 0
            video_results = []

            remaining_video_time = stage5_progress - int(stage5_progress * 0.1)
            single_video_progress = remaining_video_time // total_videos if total_videos > 0 else 0
            num_videos = min(len(urls), len(content_lis), len(relative_paths))

            folder_path = get_file_path(os.path.join("static", "video", "temp", name_only))
            os.makedirs(folder_path, exist_ok=True)

            async with httpx.AsyncClient(timeout=300.0) as client:
                for i in range(num_videos):
                    video_start_progress = accumulated_progress
                    current_stage_progress = (i / num_videos) * 100 if num_videos > 0 else 0

                    yield SSEMessage.progress_stage(
                        "video_generation",
                        f"正在生成第 {i + 1} 个视频...",
                        progress=video_start_progress,
                        current=i + 1,
                        total=num_videos,
                        current_stage_progress=current_stage_progress
                    )
                    print(f"开始生成第 {i + 1}/{num_videos} 个视频")

                    update_task_status(task_id, {
                        "current_stage": "video_generation",
                        "message": f"正在生成第 {i + 1} 个视频",
                        "progress": video_start_progress,
                        "animation_duration": 8.0,
                    })

                    try:
                        bg_path = get_file_path(urls[i])
                        audio_path = get_file_path(relative_paths[i])
                        if not os.path.exists(bg_path):
                            raise FileNotFoundError("背景图片不存在")
                        if not os.path.exists(audio_path):
                            raise FileNotFoundError("音频文件不存在")

                        bg_file = open(bg_path, "rb")
                        audio_file = open(audio_path, "rb")
                        open_files.extend([(None, bg_file, None), (None, audio_file, None)])

                        files = {
                            "background_image": ("img1.png", bg_file, "image/png"),
                            "audio_path": ("1.wav", audio_file, "audio/wav"),
                        }
                        if not no_digital_human and face_video:
                            face_file = open(face_video, "rb")
                            open_files.append((None, face_file, None))
                            files["face_video"] = ("video_file.mp4", face_file, "video/mp4")
                        submit_data = {
                            "position": position,
                            "topic_name": content_lis[i],
                            "animation_duration": 6.0,
                            "welcome_text": data.get("welcome_text", "欢迎来到AI PPT 数字人讲解平台"),
                        }
                        submit_data["bgm_enabled"] = "false"

                        yield SSEMessage.progress_stage(
                            "video_generation",
                            f"正在处理第 {i + 1} 个视频...",
                            progress=video_start_progress,
                            current=i + 1,
                            total=num_videos,
                            current_stage_progress=current_stage_progress + 10
                        )

                        try:
                            resp = await client.post(digital_human_url, files=files, data=submit_data)
                        finally:
                            for fh in [bg_file, audio_file]:
                                try:
                                    fh.close()
                                except Exception:
                                    pass
                            if "face_video" in files:
                                try:
                                    files["face_video"][1].close()
                                except Exception:
                                    pass

                        if resp.status_code == 202:
                            task_id_inner = resp.json().get("task_id")

                            if task_id_inner:
                                result_json = await poll_task_status_async(client, task_id_inner)

                                if (result_json.get("status_code") == 500 or
                                        result_json.get("message") == "视频生成失败" or
                                        result_json.get("error") == "数字人生成失败"):
                                    failed_count += 1
                                    yield SSEMessage.video_result({
                                        "video_index": i + 1,
                                        "status": "failed",
                                        "error": "视频生成失败",
                                        "error_details": result_json,
                                        "content": content_lis[i]
                                    })
                                    accumulated_progress += single_video_progress // 2
                                    yield SSEMessage.progress_stage(
                                        "video_generation",
                                        f"第 {i + 1} 个视频生成失败",
                                        progress=accumulated_progress,
                                        current=i + 1,
                                        total=num_videos,
                                        current_stage_progress=current_stage_progress + 50
                                    )
                                    print(f"第 {i + 1} 个视频生成失败: {result_json.get('error', result_json.get('message', '未知错误'))}")
                                    continue

                                elif result_json.get("status_code") == 200:
                                    video_url = result_json.get("download_url", "")
                                    if not video_url:
                                        raise ValueError("视频URL为空")

                                    save_path = os.path.join(folder_path, f"video_{i + 1}.mp4")
                                    video_response = await client.get(video_url, timeout=60.0)
                                    if video_response.status_code == 200:
                                        with open(save_path, "wb") as f:
                                            f.write(video_response.content)
                                    else:
                                        raise ValueError(f"下载视频失败，状态码: {video_response.status_code}")

                                    video_result = {
                                        "video_index": i + 1,
                                        "status": "completed",
                                        "save_path": save_path,
                                        "relative_path": os.path.join("/static", "video", "temp", name_only,
                                                                      f"video_{i + 1}.mp4"),
                                        "content": content_lis[i],
                                        "created_at": datetime.now().isoformat()
                                    }
                                    video_results.append(video_result)
                                    completed_count += 1
                                    accumulated_progress += single_video_progress

                                    yield SSEMessage.video_result(video_result)
                                    yield SSEMessage.progress_stage(
                                        "video_generation",
                                        f"第 {i + 1} 个视频生成完成",
                                        progress=accumulated_progress,
                                        current=i + 1,
                                        total=num_videos,
                                        current_stage_progress=current_stage_progress + 100
                                    )
                                    print(f"第 {i + 1} 个视频生成成功")
                                else:
                                    failed_count += 1
                                    yield SSEMessage.video_result({
                                        "video_index": i + 1,
                                        "status": "failed",
                                        "error": "视频处理失败",
                                        "error_details": result_json,
                                        "content": content_lis[i]
                                    })
                                    accumulated_progress += single_video_progress // 2
                            else:
                                failed_count += 1
                                yield SSEMessage.video_result({
                                    "video_index": i + 1,
                                    "status": "failed",
                                    "error": "未获取到任务ID",
                                    "content": content_lis[i]
                                })
                                accumulated_progress += single_video_progress // 3
                        else:
                            failed_count += 1
                            yield SSEMessage.video_result({
                                "video_index": i + 1,
                                "status": "failed",
                                "error": f"上传失败，状态码: {resp.status_code}",
                                "content": content_lis[i]
                            })
                            accumulated_progress += single_video_progress // 4

                    except Exception as e:
                        failed_count += 1
                        yield SSEMessage.video_result({
                            "video_index": i + 1,
                            "status": "failed",
                            "error": f"视频生成异常: {str(e)}",
                            "content": content_lis[i]
                        })
                        accumulated_progress += single_video_progress // 5
                        print(f"第 {i + 1} 个视频生成异常: {str(e)}")
                        traceback.print_exc()

            # 视频生成阶段完成
            print(f"视频生成阶段完成! 成功: {completed_count}, 失败: {failed_count}")

            # 发送视频生成阶段完成的状态信息
            yield SSEMessage.progress_stage(
                "video_generation_complete",
                f"视频生成阶段完成! 成功: {completed_count}, 失败: {failed_count}",
                progress=accumulated_progress,
                current=completed_count,
                total=total_videos,
                current_stage_progress=100
            )

            # 阶段6: 视频合并
            if completed_count > 0:  # 只要有成功生成的视频就尝试合并
                # 合并视频
                pdf_path = data["pdf_path"]
                # 先提取完整文件名，再分离名称和扩展名
                full_name = os.path.basename(pdf_path)
                name_only, ext_only = os.path.splitext(full_name)
                file_name = data["file_name"]
                video_folder = get_file_path(os.path.join("static", "video", "temp", name_only))
                output_path = get_file_path(os.path.join("static", "video", "mergers"))
                output_name = f"{file_name}.mp4"

                # 确保输出目录存在
                os.makedirs(output_path, exist_ok=True)

                # 发送视频合并开始的状态信息
                yield SSEMessage.progress_stage(
                    "video_merge",
                    "开始合并视频...",
                    progress=accumulated_progress,
                    current_stage_progress=0
                )
                print("开始合并视频")

                update_task_status(task_id, {
                    "current_stage": "video_merge",
                    "message": "开始合并视频"
                })

                # 创建视频合并器实例
                merger = VideoMerger(video_folder, output_path, output_name)

                # 发送视频合并进行中消息
                yield SSEMessage.progress_stage(
                    "video_merge",
                    "正在合并视频文件...",
                    progress=accumulated_progress,
                    current_stage_progress=50
                )

                # 使用异步方式合并视频
                success, message = await asyncio.to_thread(merger.merge_with_progress)

                if success:
                    accumulated_progress += stage6_progress

                    # 获取合并后的视频路径
                    merged_video_path = os.path.join(output_path, output_name)

                    if not os.path.exists(merged_video_path):
                        raise FileNotFoundError("合并后的视频不存在")

                    print("视频合并成功")

                    # 发送视频合并完成的状态信息
                    yield SSEMessage.progress_stage(
                        "video_merge_complete",
                        "视频合并完成",
                        progress=accumulated_progress,
                        current_stage_progress=100
                    )
                    print("视频合并完成")

                    # 阶段6.5：BGM混合（合并后统一添加，循环播放）
                    bgm_mode = data.get("bgm_mode", "default")
                    if bgm_mode != "none":
                        yield SSEMessage.progress_stage(
                            "bgm_mixing",
                            "正在添加背景音乐...",
                            progress=accumulated_progress,
                            current_stage_progress=0
                        )
                        print(f"开始混合BGM (mode={bgm_mode})")

                        bgm_ok, bgm_msg = await asyncio.to_thread(
                            mix_bgm,
                            merged_video_path,
                            bgm_mode,
                            data.get("bgm_path", ""),
                        )

                        if bgm_ok:
                            yield SSEMessage.progress_stage(
                                "bgm_mixing_complete",
                                "背景音乐添加完成",
                                progress=accumulated_progress,
                                current_stage_progress=100
                            )
                            print(f"BGM混合完成: {bgm_msg}")
                        else:
                            yield SSEMessage.progress_stage(
                                "bgm_mixing_warning",
                                f"背景音乐添加失败: {bgm_msg}，继续处理",
                                progress=accumulated_progress,
                                current_stage_progress=100
                            )
                            print(f"BGM混合失败(非致命): {bgm_msg}")

                    # 阶段7：视频切片（转换为HLS格式）
                    # 发送开始视频切片消息
                    yield SSEMessage.progress_stage(
                        "video_conversion",
                        "开始视频切片转换...",
                        progress=accumulated_progress,
                        current_stage_progress=0
                    )
                    print("开始视频切片转换")

                    update_task_status(task_id, {
                        "current_stage": "video_conversion",
                        "message": "开始视频切片转换"
                    })

                    # 准备切片参数
                    input_video_path = merged_video_path

                    # 生成切片输出目录
                    output_dir = get_file_path(os.path.join("static", "video", "hls", f"{name_only}"))

                    # 确保输出目录存在
                    os.makedirs(output_dir, exist_ok=True)

                    print("开始视频切片")

                    # 发送切片进行中消息
                    yield SSEMessage.progress_stage(
                        "video_conversion",
                        "正在处理视频切片...",
                        progress=accumulated_progress,
                        current_stage_progress=20
                    )

                    # 使用SimpleHLSSlicer进行本地切片，替换原有的HTTP调用
                    try:
                        # 创建HLS切片器实例
                        slicer = SimpleHLSSlicer()

                        # 切片视频，返回playlist.m3u8的相对路径
                        playlist_relative_path = slicer.simple_slice(
                            video_path=input_video_path,
                            output_dir=output_dir,
                            segment_duration=10  # 分段时长设为10秒
                        )

                        accumulated_progress = 100

                        yield SSEMessage.progress_stage(
                            "video_conversion_completed",
                            "视频切片转换完成",
                            progress=100,
                            current_stage_progress=100
                        )
                        print(f"HLS切片完成! 播放列表相对路径: {playlist_relative_path}")

                        # 存储最终的数据到json文件 basic_information
                        sample_data = {
                            "file_name": data["file_name"],
                            "content_text": texts,
                            "img_lis": urls,
                            "pdf_path": data["pdf_path"],
                            "video_path": os.path.join("/static", "video", "mergers", output_name),
                            "m3u8_url": playlist_relative_path,  # 使用切片器返回的路径
                            "output_dir": output_dir,
                        }

                        # 保存数据到JSON文件
                        json_manager = JsonDataManager(
                            get_file_path(os.path.join('static', 'data', 'basic_information.json'))
                        )
                        await asyncio.to_thread(json_manager.add_data, sample_data)

                        # 构建最终结果
                        final_result = {
                            "success": True,
                            "task_id": task_id,
                            "total_videos": total_videos,
                            "completed": completed_count,
                            "failed": failed_count,
                            "video_results": video_results,
                            "relative_paths": relative_paths,
                            "completed_at": datetime.now().isoformat(),
                            "video_path": os.path.join("/static", "video", "mergers", output_name),
                            "hls_info": {
                                "m3u8_url": playlist_relative_path,
                                "output_dir": output_dir,
                                "segment_duration": 10,
                                "status": "completed"
                            },
                            "time_estimation": {
                                "total_segments": total_segments,
                                "total_time_seconds": total_time,
                                "actual_progress": accumulated_progress
                            }
                        }

                        # 发送成功消息
                        yield SSEMessage.success(final_result)

                        # 更新任务状态
                        update_task_status(task_id, {
                            "status": "completed",
                            "progress": accumulated_progress,
                            "results": final_result,
                            "message": "视频生成和切片完成",
                            "completed_at": time.time()
                        })

                        print("数字人生成任务完成")
                        return

                    except Exception as e:
                        # 切片失败但视频本身已生成成功
                        error_msg = f"视频切片失败: {str(e)}"
                        print(f"视频切片失败: {str(e)}")
                        traceback.print_exc()

                        accumulated_progress += stage7_progress // 2

                        yield SSEMessage.progress(accumulated_progress, "video_conversion", f"警告: {error_msg}，视频仍可下载")

                        final_result = {
                            "success": True,
                            "task_id": task_id,
                            "total_videos": total_videos,
                            "completed": completed_count,
                            "failed": failed_count,
                            "video_results": video_results,
                            "relative_paths": relative_paths,
                            "completed_at": datetime.now().isoformat(),
                            "video_path": os.path.join("/static", "video", "mergers", output_name),
                            "hls_info": {
                                "error": error_msg,
                                "status": "failed"
                            },
                            "note": "视频生成完成，但切片失败"
                        }

                        yield SSEMessage.success(final_result)

                        # 更新任务状态
                        update_task_status(task_id, {
                            "status": "completed",
                            "progress": accumulated_progress,
                            "results": final_result,
                            "message": "视频生成完成，但切片失败",
                            "completed_at": time.time()
                        })
                        return

                else:
                    # 视频合并失败
                    error_msg = "视频合并失败"
                    print(f"视频合并失败")

                    yield SSEMessage.error(error_msg)

                    update_task_status(task_id, {
                        "status": "failed",
                        "progress": accumulated_progress,
                        "error": error_msg,
                        "message": "视频生成完成，但合并失败",
                        "failed_at": time.time()
                    })
                    return
            else:
                # 没有成功生成的视频
                error_msg = "没有成功生成的视频，无法继续后续处理"
                print(f"没有成功生成的视频，无法继续后续处理")

                yield SSEMessage.error(error_msg)

                update_task_status(task_id, {
                    "status": "failed",
                    "progress": accumulated_progress,
                    "error": error_msg,
                    "message": error_msg,
                    "failed_at": time.time()
                })
                return

        except Exception as e:
            error_msg = "视频生成过程出错"
            print(f"视频生成过程出错: {str(e)}")
            traceback.print_exc()

            yield SSEMessage.error(error_msg)

            # 更新任务状态为失败
            update_task_status(task_id, {
                "status": "failed",
                "error": error_msg,
                "failed_at": time.time(),
                "progress": accumulated_progress
            })
            return

    except Exception as e:
        error_msg = "数字人生成任务失败"
        print(f"数字人生成任务失败: {str(e)}")
        traceback.print_exc()

        yield SSEMessage.error(error_msg)

        # 更新任务状态
        if task_id in task_status_store:
            update_task_status(task_id, {
                "status": "failed",
                "error": error_msg,
                "failed_at": time.time()
            })

    finally:
        # 确保所有打开的文件都被关闭
        for file in open_files:
            if hasattr(file, 'close') and not file.closed:
                try:
                    file.close()
                except:
                    pass

        # 清理临时文件（PPT 原文件 + BGM）
        _cleanup_temp_files(data)

        # 清理过期任务
        cleanup_old_tasks()


# ========== 接口定义 ==========
@router.post("/digital_character_generation_stream")
async def digital_character_generation_stream(request: Request):
    """
    数字人生成接口，返回SSE流式响应

    客户端可以通过EventSource连接此接口接收实时进度
    支持POST方法，接收JSON数据

    Request Body:
        {
            "scriptContent": "HTML格式的讲稿内容",
            "template": "浮层-左下",
            "human": {
                "name": "数字人名称",
                "avatar": "/static/path/to/avatar.jpg",
                "audio": "/static/path/to/audio.wav",
                "video": "/static/path/to/video.mp4"
            },
            "file_name": "文件名",
            "pdf_path": "/static/path/to/pdf.pdf"
        }

    Returns:
        StreamingResponse: SSE流式响应
    """
    try:
        # 解析请求体
        try:
            data = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"请求体解析失败: {str(e)}")

        # 验证必要字段
        required_fields = ["scriptContent", "human", "pdf_path"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必要字段: {field}")

        # 生成唯一任务ID
        task_id = generate_task_id()

        print(f"📥 收到数字人生成请求，任务ID: {task_id}")
        print(f"📋 请求数据: {json.dumps(data, ensure_ascii=False, indent=2)}")

        # 异步生成SSE事件流
        async def event_generator():
            try:
                # 跟踪生成进度并发送事件
                async for event in track_digital_human_generation(data, task_id):
                    yield event

                # 发送结束标记
                yield SSEMessage.end()

            except Exception as e:
                error_msg = f"SSE流生成异常: {str(e)}"
                print(f"❌ {error_msg}")
                traceback.print_exc()

                yield SSEMessage.error(error_msg)
                yield SSEMessage.end()

        # 返回StreamingResponse
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用nginx缓冲
                "Access-Control-Allow-Origin": "*",  # CORS支持
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Accept"
            }
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"数字角色生成过程中发生错误: {str(e)}")


# ========== 新增：SSE拆分接口 ==========
@router.post("/tasks", summary="创建数字人生成任务")
async def create_generation_task(request: Request):
    """
    创建数字人生成任务，返回task_id。
    客户端随后使用 GET /tasks/{task_id}/stream 订阅SSE事件流。
    """
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"请求体解析失败: {str(e)}")

    required_fields = ["scriptContent", "human", "pdf_path"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"缺少必要字段: {field}")

    task_id = generate_task_id()
    queue: asyncio.Queue = asyncio.Queue()
    task_event_queues[task_id] = queue
    task_event_history[task_id] = []
    task_running[task_id] = True

    async def _run_generation():
        try:
            async for event in track_digital_human_generation(data, task_id):
                task_event_history.setdefault(task_id, []).append(event)
                await queue.put(event)
            end_evt = SSEMessage.end()
            task_event_history.setdefault(task_id, []).append(end_evt)
            await queue.put(end_evt)
        except Exception as e:
            err_evt = SSEMessage.error(f"生成异常: {str(e)}")
            end_evt = SSEMessage.end()
            task_event_history.setdefault(task_id, []).extend([err_evt, end_evt])
            await queue.put(err_evt)
            await queue.put(end_evt)
        finally:
            task_running[task_id] = False
            await queue.put(None)

    asyncio.create_task(_run_generation())

    return {"code": 200, "message": "任务已创建", "data": {"task_id": task_id}}


@router.get("/tasks/{task_id}/stream", summary="订阅任务SSE事件流")
async def stream_generation_task(task_id: str, request: Request):
    """
    通过GET请求订阅任务的SSE事件流。
    支持断线重连：已完成的任务会回放全部历史事件。
    """
    history = task_event_history.get(task_id)
    is_running = task_running.get(task_id, False)
    queue = task_event_queues.get(task_id)

    if history is None and queue is None:
        raise HTTPException(status_code=404, detail="任务不存在或已结束")

    async def event_generator():
        already_sent = 0
        if history:
            already_sent = len(history)
            for evt in history:
                yield evt

        if not is_running:
            return

        if queue is None:
            return

        skipped = 0
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    yield SSEMessage.heartbeat()
                    continue
                if event is None:
                    break
                if skipped < already_sent:
                    skipped += 1
                    continue
                yield event
        finally:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


# ========== 新增：任务状态查询接口 ==========
@router.get("/task_status/{task_id}")
async def get_task_status(task_id: str):
    """
    查询数字人生成任务状态

    Args:
        task_id: 任务ID

    Returns:
        任务状态信息
    """
    if task_id not in task_status_store:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {"code": 200, "message": "查询成功", "data": task_status_store[task_id]}


# ========== 新增：任务列表查询接口 ==========
@router.get("/tasks")
async def get_tasks(status: Optional[str] = None, limit: int = 50):
    """
    查询所有任务列表，支持按状态过滤

    Args:
        status: 任务状态过滤（running, completed, failed, pending）
        limit: 返回数量限制

    Returns:
        任务列表
    """
    # 清理过期任务
    cleanup_old_tasks()

    tasks = list(task_status_store.items())

    # 按状态过滤
    if status:
        tasks = [(task_id, task_data) for task_id, task_data in tasks if task_data.get("status") == status]

    # 按更新时间排序（最新的在前）
    tasks.sort(key=lambda x: x[1].get("updated_at", 0), reverse=True)

    # 限制数量
    tasks = tasks[:limit]

    return {
        "total": len(tasks),
        "tasks": [{"task_id": task_id, **task_data} for task_id, task_data in tasks]
    }


# ========== 保留原有接口（兼容性） ==========
@router.post("/digital_character_generation", summary="数字人生成（传统响应）", response_model=Dict[str, Any])
async def digital_character_generation(data: Dict[str, Any]):
    """
    数字人生成接口（传统同步响应，保持向后兼容）

    注意：此接口会阻塞直到所有视频生成完成

    Request Body:
        同 digital_character_generation_stream 接口

    Returns:
        生成结果
    """
    try:
        # 生成任务ID
        task_id = generate_task_id()

        # 收集所有事件结果
        final_result = None

        # 异步迭代生成器，收集结果
        async for event_bytes in track_digital_human_generation(data, task_id):
            # 解码事件
            event_str = event_bytes.decode('utf-8')

            # 提取事件类型和数据
            lines = event_str.strip().split('\n')
            event_type = None
            event_data = None

            for line in lines:
                if line.startswith('event:'):
                    event_type = line[6:].strip()
                elif line.startswith('data:'):
                    try:
                        event_data = json.loads(line[5:].strip())
                    except:
                        event_data = line[5:].strip()

            # 如果是成功事件，保存结果
            if event_type == 'success' and event_data:
                final_result = event_data

        if final_result and final_result.get("success"):
            return final_result
        else:
            return {"success": False, "error": "数字人生成失败", "task_id": task_id}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"数字角色生成过程中发生错误: {str(e)}")


# ========== 音频生成函数 ==========
def audio_generation(texts: List[str], audio_file_path: str,
                     emo_control_method: int = 0,
                     emo_vec: str = None,
                     emo_text: str = None):
    """
    音频生成

    Args:
        texts: 口播文案列表
        audio_file_path: 音频样本文件路径
        emo_control_method: 情感控制模式 (0=无, 2=向量, 3=文本)
        emo_vec: 8维情感向量 JSON 字符串
        emo_text: 情感描述文本
    """
    audio_file_path = str(audio_file_path) if hasattr(audio_file_path, '__fspath__') else audio_file_path

    url = audio_url

    try:
        with open(audio_file_path, 'rb') as audio_file:
            files = {
                'spk_audio_file': (os.path.basename(audio_file_path), audio_file, 'audio/wav')
            }

            data = {
                'texts': json.dumps(texts, ensure_ascii=False),
                'emo_control_method': str(emo_control_method),
            }
            if emo_vec and emo_control_method == 2:
                # 将逗号分隔的字符串转为 JSON 数组格式: "0,1.2,0" → "[0.0, 1.2, 0.0]"
                if not emo_vec.strip().startswith('['):
                    emo_vec = json.dumps([float(v.strip()) for v in emo_vec.split(',')])
                data['emo_vec'] = emo_vec
            if emo_text and emo_control_method == 3:
                data['emo_text'] = emo_text

            response = requests.post(
                url,
                data=data,
                files=files,
                timeout=600
            )

        # 检查响应状态
        if response.status_code == 200:
            try:
                response_data = response.json()
                batch_zip_url = response_data.get("batch_zip_url")
                if batch_zip_url:
                    return {"success": True, "batch_zip_url": batch_zip_url}
                else:
                    return {"success": False, "error": "服务器响应格式错误，缺少batch_zip_url字段"}
            except json.JSONDecodeError as e:
                return {"success": False, "error": f"服务器响应格式错误: {str(e)}"}
        else:
            return {"success": False, "error": f"服务请求失败: {response.status_code}, {response.text}"}

    except requests.exceptions.Timeout:
        return {"success": False, "error": "请求超时，请稍后重试"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "无法连接到音频生成服务，请检查网络连接"}
    except Exception as e:
        return {"success": False, "error": f"发生未知错误: {str(e)}"}


# ========== 轮询任务状态 ==========
async def poll_task_status_async(client: httpx.AsyncClient, task_id: str,
                                  max_attempts: int = 150, interval: float = 2):
    """
    异步轮询任务状态（使用复用的 httpx 客户端）
    """
    status_url = f"http://127.0.0.1:5000/status/{task_id}"
    for attempt in range(1, max_attempts + 1):
        try:
            status_resp = await client.get(status_url)
            if status_resp.status_code == 200:
                return status_resp.json()
            elif status_resp.status_code == 500:
                return status_resp.json()
        except Exception as e:
            print(f"[async poll] attempt {attempt} error: {e}")
        if attempt < max_attempts:
            await asyncio.sleep(interval)
    return {"error": "轮询超时", "task_id": task_id}


# ========== 辅助函数 ==========
def get_file_path(relative_path):
    """
    根据相对路径获取文件的完整路径

    Args:
        relative_path: 相对于项目根目录的文件路径

    Returns:
        完整的文件路径字符串
    """
    # 获取当前脚本所在目录（项目根目录）
    project_root = Path(__file__).resolve().parent.parent

    # 移除路径开头的斜杠，然后使用正确的路径拼接
    if relative_path.startswith('/') or relative_path.startswith('\\'):
        relative_path = relative_path[1:]

    full_path = project_root / relative_path

    return str(full_path)


def sanitize_filename(name: str) -> str:
    """
    清理文件名，确保安全

    Args:
        name: 原始文件名

    Returns:
        清理后的安全文件名
    """
    # 移除非法字符，只保留字母、数字、中文、下划线、短横线和空格
    sanitized = re.sub(r'[^\w\s\u4e00-\u9fff\-]', '', name)
    # 将空格替换为下划线
    sanitized = sanitized.replace(' ', '_')
    # 移除开头和结尾的特殊字符
    sanitized = sanitized.strip('_-.')

    # 如果清理后为空，则使用默认名称
    if not sanitized:
        sanitized = "digital_human"

    return sanitized


def get_file_extension(filename: str) -> str:
    """
    获取文件扩展名

    Args:
        filename: 文件名

    Returns:
        文件扩展名（小写，包含点号）
    """
    return os.path.splitext(filename)[1].lower()


def get_safe_filename(base_name: str, file_extension: str, save_path: Path) -> Tuple[Path, str, bool]:
    """
    根据文件覆盖策略获取安全的文件名

    Args:
        base_name: 基础文件名
        file_extension: 文件扩展名
        save_path: 保存目录

    Returns:
        (文件路径, 最终文件名, 是否被重命名)
    """
    # 构建基础文件名
    base_filename = f"{base_name}{file_extension}"
    file_path = save_path / base_filename

    # 检查文件是否已存在
    if not file_path.exists():
        return file_path, base_filename, False

    # 文件已存在，根据策略处理
    if settings.FILE_OVERWRITE_POLICY == "overwrite":
        # 覆盖策略：直接使用原文件名
        return file_path, base_filename, False

    elif settings.FILE_OVERWRITE_POLICY == "reject":
        # 拒绝策略：抛出异常
        raise HTTPException(
            status_code=400,
            detail=f"文件 '{base_filename}' 已存在，拒绝上传"
        )

    elif settings.FILE_OVERWRITE_POLICY == "rename":
        # 重命名策略：添加数字后缀
        counter = 1
        while True:
            new_filename = f"{base_name}_{counter}{file_extension}"
            new_file_path = save_path / new_filename
            if not new_file_path.exists():
                return new_file_path, new_filename, True
            counter += 1

    # 默认使用重命名策略
    counter = 1
    while True:
        new_filename = f"{base_name}_{counter}{file_extension}"
        new_file_path = save_path / new_filename
        if not new_file_path.exists():
            return new_file_path, new_filename, True


def validate_file_type(filename: str, allowed_extensions: list) -> bool:
    """
    验证文件类型

    Args:
        filename: 文件名
        allowed_extensions: 允许的文件扩展名列表

    Returns:
        是否通过验证
    """
    ext = get_file_extension(filename)
    return ext in allowed_extensions


def validate_file_size(file: UploadFile, max_size: int) -> bool:
    """
    验证文件大小

    Args:
        file: 上传的文件对象
        max_size: 最大允许大小（字节）

    Returns:
        是否通过验证
    """
    # 移动文件指针到末尾获取文件大小
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)  # 重置指针

    return file_size <= max_size


def save_upload_file(upload_file: UploadFile, save_path: Path) -> Dict[str, str]:
    """
    保存上传的文件

    Args:
        upload_file: 上传的文件对象
        save_path: 保存路径

    Returns:
        包含文件信息的字典
    """
    try:
        # 计算文件MD5
        md5_hash = hashlib.md5()

        with save_path.open("wb") as buffer:
            # 分块读取文件并计算MD5
            for chunk in iter(lambda: upload_file.file.read(8192), b''):
                if not chunk:
                    break
                buffer.write(chunk)
                md5_hash.update(chunk)

        file_md5 = md5_hash.hexdigest()

        return {
            "file_path": str(save_path),
            "file_size": save_path.stat().st_size,
            "file_md5": file_md5,
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"文件保存失败: {str(e)}"
        )


# ========== 数字人上传接口 ==========
@router.post("/digital-human/upload", summary="上传自定义数字人数据", response_model=Dict[str, Any])
async def upload_digital_human(
        name: str = Form(..., description="数字人名称，将作为文件名"),
        brief: str = Form(..., description="数字人简介"),
        avatar: UploadFile = File(..., description="头像图片文件"),
        audio: UploadFile = File(..., description="音频文件"),
        video: UploadFile = File(..., description="视频文件")
):
    """
    上传数字人数据

    接收文本数据和文件，按指定规则存储到对应目录
    所有文件统一使用name作为文件名（不带时间戳和随机数）

    Returns:
        上传结果和文件路径信息
    """
    try:
        # 验证必填字段
        if not name or not name.strip():
            raise HTTPException(
                status_code=400,
                detail="name字段不能为空"
            )

        # 清理文件名，确保安全
        safe_name = sanitize_filename(name)

        # 验证文件类型
        if not validate_file_type(avatar.filename, settings.ALLOWED_IMAGE_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail=f"头像文件格式不支持，请使用: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS)}"
            )

        if not validate_file_type(audio.filename, settings.ALLOWED_AUDIO_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail=f"音频文件格式不支持，请使用: {', '.join(settings.ALLOWED_AUDIO_EXTENSIONS)}"
            )

        if not validate_file_type(video.filename, settings.ALLOWED_VIDEO_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail=f"视频文件格式不支持，请使用: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}"
            )

        # 验证文件大小
        if not validate_file_size(avatar, settings.MAX_IMAGE_SIZE):
            raise HTTPException(
                status_code=400,
                detail=f"头像文件大小超过限制: {settings.MAX_IMAGE_SIZE / 1024 / 1024}MB"
            )

        if not validate_file_size(audio, settings.MAX_AUDIO_SIZE):
            raise HTTPException(
                status_code=400,
                detail=f"音频文件大小超过限制: {settings.MAX_AUDIO_SIZE / 1024 / 1024}MB"
            )

        if not validate_file_size(video, settings.MAX_VIDEO_SIZE):
            raise HTTPException(
                status_code=400,
                detail=f"视频文件大小超过限制: {settings.MAX_VIDEO_SIZE / 1024 / 1024}MB"
            )

        # 获取文件扩展名
        avatar_ext = get_file_extension(avatar.filename)
        audio_ext = get_file_extension(audio.filename)
        video_ext = get_file_extension(video.filename)

        # 根据策略获取最终文件名
        avatar_path, avatar_filename, avatar_renamed = get_safe_filename(
            safe_name, avatar_ext, settings.upload_image_folder_absolute
        )
        audio_path, audio_filename, audio_renamed = get_safe_filename(
            safe_name, audio_ext, settings.upload_audio_folder_absolute
        )
        video_path, video_filename, video_renamed = get_safe_filename(
            safe_name, video_ext, settings.upload_video_folder_absolute
        )

        # 检查是否有文件被重命名
        renamed_files = []
        if avatar_renamed:
            renamed_files.append(f"头像文件被重命名为: {avatar_filename}")
        if audio_renamed:
            renamed_files.append(f"音频文件被重命名为: {audio_filename}")
        if video_renamed:
            renamed_files.append(f"视频文件被重命名为: {video_filename}")

        # 保存文件
        avatar_info = save_upload_file(avatar, avatar_path)
        audio_info = save_upload_file(audio, audio_path)
        video_info = save_upload_file(video, video_path)

        # 保存数据到json文件
        new_data = {
            "name": name,
            "brief": brief,
            "image": f"/static/Digital_human/Customized_digital_human/image/{avatar_filename}",
            "audio": f"/static/Digital_human/Customized_digital_human/audio/{audio_filename}",
            "video": f"/static/Digital_human/Customized_digital_human/video/{video_filename}",
        }
        file_path = 'static/Digital_human/Customized_digital_human.json'

        try:
            # 检查文件是否存在且不为空
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                # 文件存在且不为空，读取现有数据
                with open(file_path, 'r', encoding='utf-8') as file:
                    try:
                        existing_data = json.load(file)
                        print("✓ 成功读取现有JSON数据")
                    except json.JSONDecodeError:
                        # 如果JSON格式错误，创建新的数据结构
                        print("JSON文件格式错误，将创建新的数据结构")
                        existing_data = {"data": []}
            else:
                # 文件不存在或为空，创建新的数据结构
                print("文件不存在或为空，将创建新的数据结构")
                existing_data = {"data": []}

            # 确保数据结构正确
            if "data" not in existing_data:
                existing_data["data"] = []

            # 检查是否已存在相同name的数据
            existing_names = [item.get("name") for item in existing_data["data"] if item.get("name")]
            if new_data.get("name") in existing_names:
                print(f"名称 '{new_data.get('name')}' 已存在，将更新数据")
                # 找到并更新现有数据
                for i, item in enumerate(existing_data["data"]):
                    if item.get("name") == new_data.get("name"):
                        existing_data["data"][i] = new_data
                        break
            else:
                # 在数据末尾添加新数据
                existing_data["data"].append(new_data)
                print(f"新数据已添加到JSON文件")

            # 将更新后的数据写回文件
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(existing_data, file, ensure_ascii=False, indent=4)

            print("数据已成功写入文件")

        except Exception as e:
            print(f"❌ 操作失败: {e}")

        return JSONResponse(
            status_code=200,
            content={"code": 200, "message": "添加成功！", "data": new_data}
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"服务器内部错误: {str(e)}"
        )


@router.delete("/digital-human/{digital_human_name}", summary="删除指定名称的数字人文件", response_model=Dict[str, Any])
async def delete_digital_human(digital_human_name: str):
    """
    删除指定名称的数字人文件

    删除指定名称的所有相关文件（图片、音频、视频）
    """
    try:
        # 清理名称
        safe_name = sanitize_filename(digital_human_name)

        deleted_files = []

        # 遍历三个目录，删除匹配的文件
        for folder_name, folder_path in [
            ("image", settings.upload_image_folder_absolute),
            ("audio", settings.upload_audio_folder_absolute),
            ("video", settings.upload_video_folder_absolute)
        ]:
            if folder_path.exists():
                for file in folder_path.iterdir():
                    if file.is_file():
                        # 检查文件名是否以指定名称开头
                        if file.stem.startswith(safe_name):
                            try:
                                file.unlink()  # 删除文件
                                deleted_files.append(str(file.relative_to(settings.BASE_DIR)))
                                print(f"已删除文件: {file}")
                            except Exception as e:
                                print(f"删除文件失败: {file}, 错误: {e}")

        if deleted_files:
            return {
                "code": 200,
                "message": f"成功删除 {len(deleted_files)} 个文件",
                "data": {"status": "success", "deleted_files": deleted_files}
            }
        else:
            return {
                "code": 200,
                "message": f"未找到名称为 '{digital_human_name}' 的文件",
                "data": {"status": "warning"}
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除文件失败: {str(e)}"
        )