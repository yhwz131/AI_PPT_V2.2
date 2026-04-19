import gc
import os
import sys
# 获取当前脚本所在目录的父目录（即 index-tts-vllm/）
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 将父目录加入Python搜索路径
sys.path.append(parent_dir)
import asyncio
import io
import traceback
from fastapi import FastAPI, Request, Response, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
import argparse
import json
import time
import soundfile as sf
from typing import List, Optional, Union
from urllib.parse import quote
from loguru import logger
import glob
from datetime import datetime, timedelta
import zipfile
from indextts.infer_vllm_v2 import IndexTTS2
import torch
import re
from dotenv import load_dotenv


#载入环境变量（优先从 server 目录加载 .env）
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    load_dotenv(_env_path, override=True)
else:
    load_dotenv(override=True)
EXPIRE_DAYS = int(os.getenv("EXPIRE_DAYS", 7))
LOG_ROTATION_SIZE = os.getenv("LOG_ROTATION_SIZE", "10 MB")
LOG_RETENTION_COUNT = int(os.getenv("LOG_RETENTION_COUNT", 10))
logger.add("logs/api_server_v2.log", rotation=LOG_ROTATION_SIZE, retention=LOG_RETENTION_COUNT, level="DEBUG", enqueue=True)
# 新增：从环境变量读取配置
REF_AUDIO_ROOT_PATH = os.getenv("REF_AUDIO_ROOT_PATH")
ALLOWED_AUDIO_EXTENSIONS = os.getenv("ALLOWED_AUDIO_EXTENSIONS", ".wav,.mp3").split(",")
# 校验环境变量是否配置
if not REF_AUDIO_ROOT_PATH:
    raise ValueError("环境变量 REF_AUDIO_ROOT_PATH 未配置，请检查.env文件")
if not os.path.isdir(REF_AUDIO_ROOT_PATH):
    raise ValueError(f"REF_AUDIO_ROOT_PATH 路径不存在：{REF_AUDIO_ROOT_PATH}")
#端口
PORT=int(os.getenv("PORT",6006))

DEFAULT_OUTPUT_PATH = None
tts = None

# 新增：安全拼接参考音频路径的函数
def safe_join_ref_audio(relative_path: str) -> str:
    """
    安全拼接参考音频路径，防止路径穿越攻击：
    1. 禁止传入绝对路径
    2. 解析为规范路径后校验是否在根目录内
    3. 校验文件后缀合法性
    """
    # 1. 禁止绝对路径
    if os.path.isabs(relative_path):
        raise HTTPException(
            status_code=400,
            detail="禁止传入绝对路径，请使用REF_AUDIO_ROOT_PATH下的相对路径"
        )
    
    # 2. 拼接并规范化路径（消除../等穿越符号）
    full_path = os.path.abspath(os.path.join(REF_AUDIO_ROOT_PATH, relative_path))
    
    # 3. 校验路径是否在根目录内（防止路径穿越）
    if not full_path.startswith(os.path.abspath(REF_AUDIO_ROOT_PATH)):
        raise HTTPException(
            status_code=403,
            detail="路径非法，禁止访问根目录外的文件"
        )
    
    # 4. 校验文件后缀
    file_ext = os.path.splitext(full_path)[1].lower()
    if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"文件格式不支持，仅允许：{','.join(ALLOWED_AUDIO_EXTENSIONS)}"
        )
    
    # 5. 校验文件是否存在
    if not os.path.exists(full_path):
        raise HTTPException(
            status_code=404,
            detail=f"参考音频文件不存在：{full_path}"
        )
    
    return full_path

# 新增：临时保存上传的音频文件
def save_uploaded_audio(upload_file: UploadFile, save_dir: str = REF_AUDIO_ROOT_PATH) -> str:
    """
    保存上传的音频文件到指定目录，返回文件完整路径
    """
    if not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)
    
    # 校验文件后缀
    file_ext = os.path.splitext(upload_file.filename)[1].lower()
    if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"上传文件格式不支持，仅允许：{','.join(ALLOWED_AUDIO_EXTENSIONS)}"
        )
    
    # 生成唯一文件名（避免覆盖）
    filename = f"upload_{int(time.time())}_{upload_file.filename}"
    full_path = os.path.join(save_dir, filename)
    
    # 保存文件
    with open(full_path, "wb") as f:
        f.write(upload_file.file.read())
    
    return full_path

@asynccontextmanager
async def lifespan(app: FastAPI):
    global tts
    tts = IndexTTS2(
        model_dir=args.model_dir,
        is_fp16=args.is_fp16,
        gpu_memory_utilization=args.gpu_memory_utilization,
        qwenemo_gpu_memory_utilization=args.qwenemo_gpu_memory_utilization,
    )
    global DEFAULT_OUTPUT_PATH
    DEFAULT_OUTPUT_PATH = args.default_output_path
    if not os.path.exists(DEFAULT_OUTPUT_PATH):
        os.makedirs(DEFAULT_OUTPUT_PATH, exist_ok=True)
    # 修复：过期文件清理逻辑（核心修改部分）
    expire_days = EXPIRE_DAYS
    expire_time = datetime.now() - timedelta(days=expire_days)
    expire_timestamp = int(expire_time.timestamp())
    
    # 1. 清理批量音频文件（tts_batch_output_*）
    for wav_file in glob.glob(os.path.join(DEFAULT_OUTPUT_PATH, "tts_batch_output_*.wav")):
        try:
            # 提取文件名（去掉路径和后缀）
            filename = os.path.splitext(os.path.basename(wav_file))[0]
            # 拆分并安全提取timestamp（兼容批量文件名格式）
            parts = filename.split("_")
            if len(parts) >= 4 and parts[3].isdigit():
                file_timestamp = int(parts[3])
                if file_timestamp < expire_timestamp:
                    os.remove(wav_file)
                    logger.info(f"清理过期批量音频文件：{wav_file}")
            else:
                logger.warning(f"文件名格式异常，跳过清理：{wav_file}")
        except Exception as e:
            logger.error(f"清理批量音频文件失败：{wav_file}，错误：{str(e)}")
    
    # 2. 清理单个音频文件（tts_output_*）
    for wav_file in glob.glob(os.path.join(DEFAULT_OUTPUT_PATH, "tts_output_*.wav")):
        try:
            filename = os.path.splitext(os.path.basename(wav_file))[0]
            parts = filename.split("_")
            if len(parts) >= 3 and parts[2].isdigit():
                file_timestamp = int(parts[2])
                if file_timestamp < expire_timestamp:
                    os.remove(wav_file)
                    logger.info(f"清理过期单个音频文件：{wav_file}")
            else:
                logger.warning(f"文件名格式异常，跳过清理：{wav_file}")
        except Exception as e:
            logger.error(f"清理单个音频文件失败：{wav_file}，错误：{str(e)}")
    
    # 3. 清理过期压缩包
    for zip_file in glob.glob(os.path.join(DEFAULT_OUTPUT_PATH, "tts_batch_*.zip")):
        try:
            filename = os.path.splitext(os.path.basename(zip_file))[0]
            parts = filename.split("_")
            if len(parts) >= 3 and parts[2].isdigit():
                file_timestamp = int(parts[2])
                if file_timestamp < expire_timestamp:
                    os.remove(zip_file)
                    logger.info(f"清理过期压缩包：{zip_file}")
            else:
                logger.warning(f"压缩包文件名格式异常，跳过清理：{zip_file}")
        except Exception as e:
            logger.error(f"清理压缩包失败：{zip_file}，错误：{str(e)}")
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_TTS_PATHS = {"/tts_url", "/batch_tts_url"}

class CudaCacheCleanupMiddleware(BaseHTTPMiddleware):
    """在 TTS 推理请求结束后释放 PyTorch CUDA 缓存，防止显存碎片堆积"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path in _TTS_PATHS:
            gc.collect()
            torch.cuda.empty_cache()
        return response

app.add_middleware(CudaCacheCleanupMiddleware)

# 新增文本预处理函数
def preprocess_tts_text(text: str) -> str:
    """
    标准化TTS输入文本：
    1. 将连字符 `-` 替换为英文发音 "hyphen"（或空字符，根据需求）；
    2. 英文单词按音节/空格切分，降低口胡概率；
    3. 英文单词强制小写+重音标记（可选）。
    """
    # 1. 处理连字符 `-`：按需选择以下一种策略
    # 策略A：读成英文"hyphen"（适合需要明确念出符号的场景）
    #text = re.sub(r'-', ' hyphen ', text)
    # 策略B：直接删除（适合仅作为分隔符、无需念出的场景）
    #text = re.sub(r'-', '', text)
    # 策略C：替换为英文半角空格（适合英文单词连字符，如 "state-of-the-art"）
    text = re.sub(r'(\w)-(\w)', r'\1 \2', text)

    # 2. 英文单词优化：降低长单词口胡概率
    # 2.1 英文单词与中文之间加空格，避免模型混淆
    text = re.sub(r'([a-zA-Z])([\u4e00-\u9fa5])', r'\1 \2', text)
    text = re.sub(r'([\u4e00-\u9fa5])([a-zA-Z])', r'\1 \2', text)
    # 2.2 长英文单词按音节切分（简单版：每4个字母加空格，可根据需求细化）
    def split_long_word(match):
        word = match.group(0)
        if len(word) > 8:  # 仅处理长度>8的英文单词
            return ' '.join([word[i:i+4] for i in range(0, len(word), 4)])
        return word
    text = re.sub(r'[a-zA-Z]+', split_long_word, text)
    
    # 3. 可选：英文全部小写（避免模型对大小写敏感）
    text = re.sub(r'[A-Z]+', lambda m: m.group(0).lower(), text)
    
    return text.strip()

@app.get("/health")
async def health_check():
    if tts is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "message": "TTS model not initialized"
            }
        )
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "message": "Service is running",
            "timestamp": time.time(),
            "default_output_path": DEFAULT_OUTPUT_PATH
        }
    )

# --------------------- 新增：单音频文件下载接口 ---------------------
@app.get("/download_audio", responses={
    200: {"content": {"audio/wav": {}}},
    404: {"content": {"application/json": {}}},
    500: {"content": {"application/json": {}}}
})
async def download_audio(file_path: str):
    """
    下载单个生成的音频文件
    :param file_path: 音频文件的完整路径（需urlencode转义特殊字符）
    """
    try:
        # 校验文件是否存在
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"文件不存在：{file_path}")
        # 提取文件名（用于下载时的显示名称）
        file_name = os.path.basename(file_path)
        # 返回文件响应（自动触发下载）
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="audio/wav"
        )
    except HTTPException as e:
        raise e
    except Exception as ex:
        tb_str = ''.join(traceback.format_exception(type(ex), ex, ex.__traceback__))
        raise HTTPException(status_code=500, detail=f"下载失败：{tb_str}")

# --------------------- 新增：批量音频压缩包下载接口 ---------------------
@app.get("/download_batch_zip", responses={
    200: {"content": {"application/zip": {}}},
    404: {"content": {"application/json": {}}},
    500: {"content": {"application/json": {}}}
})
async def download_batch_zip(timestamp: int, output_path: str = DEFAULT_OUTPUT_PATH):
    """
    下载指定时间戳的批量音频压缩包（timestamp为批量生成时的统一时间戳）
    :param timestamp: 批量生成时的时间戳（int类型，来自batch_tts_api_url返回的timestamp）
    :param output_path: 批量音频的存储路径（默认使用DEFAULT_OUTPUT_PATH）
    """
    try:
        # 筛选该时间戳下的所有音频文件
        batch_files = [
            os.path.join(output_path, f)
            for f in os.listdir(output_path)
            if f.startswith(f"tts_batch_output_{timestamp}_") and f.endswith(".wav")
        ]
        if not batch_files:
            raise HTTPException(status_code=404, detail=f"未找到时间戳{timestamp}对应的批量音频文件")
        
        # 生成压缩包文件名
        zip_filename = f"tts_batch_{timestamp}.zip"
        zip_file_path = os.path.join(output_path, zip_filename)
        
        # 创建压缩包（覆盖已存在的同名压缩包）
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in batch_files:
                # 压缩包内保留原文件名，不嵌套目录
                zipf.write(file_path, os.path.basename(file_path))
        
        # 返回压缩包下载响应
        return FileResponse(
            path=zip_file_path,
            filename=zip_filename,
            media_type="application/zip"
        )
    except HTTPException as e:
        raise e
    except Exception as ex:
        tb_str = ''.join(traceback.format_exception(type(ex), ex, ex.__traceback__))
        raise HTTPException(status_code=500, detail=f"压缩/下载失败：{tb_str}")
    
# 改造：批量TTS接口（接收form-data）
@app.post("/batch_tts_url", responses={
    200: {"content": {"application/json": {}}},
    500: {"content": {"application/json": {}}}
})
async def batch_tts_api_url(
    # 核心文本列表（JSON字符串格式传递）
    texts: str = Form(...),
    # 其他参数
    emo_control_method: int = Form(0),
    # 二选一：参考音频路径 或 上传参考音频文件
    spk_audio_relative: Optional[str] = Form(None),
    spk_audio_file: Optional[UploadFile] = File(None),
    # 情感参考音频（二选一）
    emo_ref_relative: Optional[str] = Form(None),
    emo_ref_file: Optional[UploadFile] = File(None),
    # 其他可选参数
    emo_weight: float = Form(1.0),
    emo_vec: str = Form(json.dumps([0]*8)),  # JSON字符串传递列表
    emo_text: Optional[str] = Form(None),
    emo_random: bool = Form(False),
    max_text_tokens_per_sentence: int = Form(120),
    custom_output_path: Optional[str] = Form(DEFAULT_OUTPUT_PATH)
):
    try:
        # 1. 解析文本列表（form-data中传递JSON字符串）
        try:
            texts_list = json.loads(texts)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "texts参数必须是合法的JSON数组字符串"}
            )
        if not texts_list or not isinstance(texts_list, list):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "texts必须是非空列表"}
            )
        
        # 2. 处理参考音频（路径/上传文件二选一）
        if spk_audio_relative and spk_audio_file:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "只能选择spk_audio_relative或spk_audio_file其中一个"}
            )
        if not spk_audio_relative and not spk_audio_file:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "必须提供spk_audio_relative或spk_audio_file"}
            )
        # 2.1 处理说话人参考音频
        if spk_audio_relative:
            spk_audio_path = safe_join_ref_audio(spk_audio_relative)
        else:
            spk_audio_path = save_uploaded_audio(spk_audio_file)
        
        # 2.2 处理情感参考音频
        emo_ref_path = None
        if emo_ref_relative or emo_ref_file:
            if emo_ref_relative and emo_ref_file:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "error": "只能选择emo_ref_relative或emo_ref_file其中一个"}
                )
            if emo_ref_relative:
                emo_ref_path = safe_join_ref_audio(emo_ref_relative)
            else:
                emo_ref_path = save_uploaded_audio(emo_ref_file)
        
        # 3. 解析情感向量（JSON字符串转列表）
        try:
            emo_vec_list = json.loads(emo_vec)
            if not isinstance(emo_vec_list, list) or len(emo_vec_list) != 8:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "error": "emo_vec必须是长度为8的JSON数组字符串"}
                )
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "emo_vec必须是合法的JSON数组字符串"}
            )
        
        # 4. 处理其他参数
        if type(emo_control_method) is not int:
            emo_control_method = emo_control_method.value
        if emo_control_method == 0:
            emo_ref_path = None
            emo_weight = 1.0
        if emo_control_method == 1:
            emo_weight = emo_weight
        vec = None
        if emo_control_method == 2:
            vec = emo_vec_list
            vec_sum = sum(vec)
            if vec_sum > 1.5:
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "error": "情感向量之和不能超过1.5，请调整后重试。"}
                )

        # 5. 确保自定义输出路径存在
        custom_output_path = custom_output_path or DEFAULT_OUTPUT_PATH
        os.makedirs(custom_output_path, exist_ok=True)
        timestamp = int(time.time())  # 统一时间戳，便于批量文件归类

        # 6. 循环处理每条文本，生成独立音频文件
        batch_results = []
        idx = 1
        for idx, text in enumerate(texts_list):
            try:
                # 文本预处理
                processed_text = preprocess_tts_text(text)
                # 生成独立的文件名（包含索引，避免重复）
                audio_filename = f"tts_batch_output_{timestamp}_{idx}.wav"
                full_output_path = os.path.join(custom_output_path, audio_filename)
                
                # 调用TTS模型生成音频
                sr = await tts.infer(
                    spk_audio_prompt=spk_audio_path,
                    text=processed_text,
                    output_path=full_output_path,
                    emo_audio_prompt=emo_ref_path,
                    emo_alpha=emo_weight,
                    emo_vector=vec,
                    use_emo_text=(emo_control_method==3),
                    emo_text=emo_text,
                    use_random=emo_random,
                    max_text_tokens_per_sentence=int(max_text_tokens_per_sentence),
                )
                encoded_file_path = quote(full_output_path)
                download_url = f"http://{args.host}:{args.port}/download_audio?file_path={encoded_file_path}"

                # 记录该音频的结果
                batch_results.append({
                    "index": idx,          # 文本列表中的索引
                    "text": text,          # 对应文本
                    "audio_path": full_output_path,  # 音频文件路径
                    "sample_rate": sr,      # 采样率
                    "download_url": download_url  # 新增下载链接
                })
                logger.info(f"批量TTS完成：索引{idx}，文件路径{full_output_path}")

            except Exception as sub_ex:
                # 单个文本处理失败，不中断整体流程
                tb_str = ''.join(traceback.format_exception(type(sub_ex), sub_ex, sub_ex.__traceback__))
                batch_results.append({
                    "index": idx,
                    "text": text,
                    "status": "failed",
                    "error": tb_str
                })
                logger.error(f"批量TTS失败：索引{idx}，错误{tb_str}")
        
        # 生成批量下载链接
        batch_zip_url = f"http://{args.host}:{args.port}/download_batch_zip?timestamp={timestamp}&output_path={quote(custom_output_path)}"
        
        # 返回批量处理结果
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "batch_count": len(texts_list),
                "success_count": len([r for r in batch_results if r.get("status") != "failed"]),
                "timestamp": timestamp,
                "batch_zip_url": batch_zip_url,
                "results": batch_results
            }
        )

    except Exception as ex:
        tb_str = ''.join(traceback.format_exception(type(ex), ex, ex.__traceback__))
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": tb_str
            }
        )

# 改造：单文本TTS接口（接收form-data）
@app.post("/tts_url", responses={
    200: {"content": {"application/octet-stream": {}}},
    500: {"content": {"application/json": {}}}
})
async def tts_api_url(
    # 核心参数
    text: str = Form(...),
    emo_control_method: int = Form(0),
    # 参考音频（二选一）
    spk_audio_relative: Optional[str] = Form(None),
    spk_audio_file: Optional[UploadFile] = File(None),
    # 情感参考音频（二选一）
    emo_ref_relative: Optional[str] = Form(None),
    emo_ref_file: Optional[UploadFile] = File(None),
    # 其他可选参数
    emo_weight: float = Form(1.0),
    emo_vec: str = Form(json.dumps([0]*8)),  # JSON字符串传递列表
    emo_text: Optional[str] = Form(None),
    emo_random: bool = Form(False),
    max_text_tokens_per_sentence: int = Form(120),
    custom_output_path: Optional[str] = Form(DEFAULT_OUTPUT_PATH)
):
    try:
        # 1. 处理参考音频（路径/上传文件二选一）
        if spk_audio_relative and spk_audio_file:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "只能选择spk_audio_relative或spk_audio_file其中一个"}
            )
        if not spk_audio_relative and not spk_audio_file:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "必须提供spk_audio_relative或spk_audio_file"}
            )
        # 1.1 说话人参考音频
        if spk_audio_relative:
            spk_audio_path = safe_join_ref_audio(spk_audio_relative)
        else:
            spk_audio_path = save_uploaded_audio(spk_audio_file)
        
        # 1.2 情感参考音频
        emo_ref_path = None
        if emo_ref_relative or emo_ref_file:
            if emo_ref_relative and emo_ref_file:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "error": "只能选择emo_ref_relative或emo_ref_file其中一个"}
                )
            if emo_ref_relative:
                emo_ref_path = safe_join_ref_audio(emo_ref_relative)
            else:
                emo_ref_path = save_uploaded_audio(emo_ref_file)
        
        # 2. 解析情感向量
        try:
            emo_vec_list = json.loads(emo_vec)
            if not isinstance(emo_vec_list, list) or len(emo_vec_list) != 8:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "error": "emo_vec必须是长度为8的JSON数组字符串"}
                )
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": "emo_vec必须是合法的JSON数组字符串"}
            )
        
        # 3. 处理其他参数
        if type(emo_control_method) is not int:
            emo_control_method = emo_control_method.value
        if emo_control_method == 0:
            emo_ref_path = None
            emo_weight = 1.0
        if emo_control_method == 1:
            emo_weight = emo_weight
        vec = None
        if emo_control_method == 2:
            vec = emo_vec_list
            vec_sum = sum(vec)
            if vec_sum > 1.5:
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "error": "情感向量之和不能超过1.5，请调整后重试。"}
                )

        # 4. 文本预处理
        processed_text = preprocess_tts_text(text)
        
        # 5. 生成音频文件
        custom_output_path = custom_output_path or DEFAULT_OUTPUT_PATH
        audio_filename = f"tts_output_{int(time.time())}.wav"
        full_output_path = os.path.join(custom_output_path, audio_filename)
        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
        
        sr = await tts.infer(
            spk_audio_prompt=spk_audio_path,
            text=processed_text,
            output_path=full_output_path,
            emo_audio_prompt=emo_ref_path, 
            emo_alpha=emo_weight,
            emo_vector=vec,
            use_emo_text=(emo_control_method==3), 
            emo_text=emo_text,
            use_random=emo_random,
            max_text_tokens_per_sentence=int(max_text_tokens_per_sentence)
        )
        
        # 6. 读取音频并返回二进制流
        wav, sr = sf.read(full_output_path)
        with io.BytesIO() as wav_buffer:
            sf.write(wav_buffer, wav, sr, format='WAV')
            wav_bytes = wav_buffer.getvalue()

        return Response(content=wav_bytes, media_type="audio/wav")
    
    except Exception as ex:
        tb_str = ''.join(traceback.format_exception(type(ex), ex, ex.__traceback__))
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(tb_str)
            }
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _server_dir = os.path.dirname(os.path.abspath(__file__))
    _project_dir = os.path.dirname(_server_dir)
    parser.add_argument("--host", type=str, default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 6006)))
    parser.add_argument("--model_dir", type=str, default=os.getenv("MODEL_DIR", os.path.join(_project_dir, "checkpoints", "IndexTTS-2-vLLM")), help="Model checkpoints directory")
    parser.add_argument("--is_fp16", action="store_true", default=os.getenv("IS_FP16", "False").lower() == "true", help="Fp16 infer")
    parser.add_argument("--gpu_memory_utilization", type=float, default=float(os.getenv("GPU_MEMORY_UTILIZATION", 0.15)))
    parser.add_argument("--qwenemo_gpu_memory_utilization", type=float, default=float(os.getenv("QWENEMO_GPU_MEMORY_UTILIZATION", 0.10)))
    parser.add_argument("--verbose", action="store_true", default=False, help="Enable verbose mode")
    parser.add_argument("--default_output_path", type=str, default=os.getenv("DEFAULT_OUTPUT_PATH", os.path.join(_project_dir, "outputs")), 
                        help="Default output directory for TTS audio files")
    args = parser.parse_args()
    
    if not os.path.exists("outputs"):
        os.makedirs("outputs")

    uvicorn.run(app=app, host=args.host, port=args.port)