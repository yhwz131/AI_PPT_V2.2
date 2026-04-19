#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PaddleOCR-VL API Service
纯净的 API 服务，输入 PDF/图片，输出 JSON 格式的解析结果
"""

import os
import io
import re
import json
import base64
from pathlib import Path
from typing import Dict, List, Any
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv
import sys
# 允许跨域 1. 导入 CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware

# 获取当前文件的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
print("当前路径：", current_dir)
# 添加 until 目录到 Python 路径
until_dir = os.path.join(current_dir, "until")
sys.path.insert(0, until_dir)

# 直接导入（去掉点号）
from get_voice_content import get_ppt_voice_content

load_dotenv(override=True)

try:
    import html2text
except ImportError:
    raise ImportError("请安装 html2text: pip install html2text")

try:
    from paddleocr import PaddleOCRVL
except ImportError:
    raise ImportError("请安装 paddleocr: pip install paddleocr")

# ============ 配置 ============
_PADDLEOCR_DIR = os.path.dirname(os.path.abspath(__file__))

# 定义ppocrvl模型路径
VL_MODEL_DIR = Path(os.getenv(
    "VL_MODEL_DIR",
    os.path.join(_PADDLEOCR_DIR, "models", "PaddleOCR-VL-0.9B")
))

# 定义ppocrvl的布局模型路径
LAYOUT_MODEL_DIR = Path(os.getenv(
    "LAYOUT_MODEL_DIR",
    os.path.join(_PADDLEOCR_DIR, "models", "PaddleOCR-VL-0.9B", "PP-DocLayoutV2")
))

# 定义uploadurl
UPLOAD_BASE_URL = os.getenv("UPLOAD_BASE_URL", "127.0.0.1")

# 定义upload路径
UPLOAD_BASE_DIR = Path(os.getenv(
    "UPLOAD_BASE_DIR",
    os.path.join(_PADDLEOCR_DIR, "output")
))

GPU_ID = os.getenv("GPU_ID", "0")
PORT = int(os.getenv("PORT", "8802"))
# 监听 0.0.0.0 才能被外网访问；127.0.0.1 仅本机
HOST = os.getenv("HOST", "0.0.0.0")
# ===============================

os.environ["CUDA_VISIBLE_DEVICES"] = GPU_ID

app = FastAPI(title="PaddleOCR-VL API", version="1.0.0")

# 2. 定义允许访问的源列表
_cors_env = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8802",
    "http://localhost:8802",
    "http://127.0.0.1:9088",
    "http://localhost:9088",
]

# 3. 添加 CORS 中间件到应用
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许的源列表
    allow_credentials=True,  # 允许携带凭证（如 cookies）
    allow_methods=["*"],  # 允许所有 HTTP 方法 (GET, POST, PUT, DELETE 等)
    allow_headers=["*"],  # 允许所有 HTTP 头
    # expose_headers=["*"]
)

# 全局 pipeline 实例
pipeline = None


def pil_to_base64(img, fmt="PNG") -> str:
    """PIL Image 转 base64"""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def convert_html_to_markdown(md_text: str) -> str:
    """将 HTML 格式的图片和表格转换为 Markdown 格式"""
    # 转换图片去掉图片部分【不需要】
    img_pattern = r'<div[^>]*>\s*<img\s+src="([^"]+)"[^>]*>\s*</div>'
    md_text = re.sub(img_pattern, '', md_text)
    # 转换表格
    if '<table' in md_text:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0

        table_pattern = r'<table[^>]*>.*?</table>'
        tables = re.findall(table_pattern, md_text, re.DOTALL)

        for table_html in tables:
            table_md = h.handle(table_html).strip()
            md_text = md_text.replace(table_html, table_md)

    return md_text


# 辅助函数将其markdown分割成每一页
def parse_markdown_by_pageindex(markdown_content: str) -> List[Dict[str, any]]:
    """
    解析包含<!-- pageindex 页数-->标记的Markdown内容，
    将其分割为多个页面

    Args:
        markdown_content: 包含页面标记的Markdown字符串

    Returns:
        包含页面索引和内容的字典列表
        [{"pageindex": 0, "md_content": "页面内容"}, ...]
    """

    # 正则表达式匹配页面标记
    page_pattern = r'<!--\s*pageindex\s+(\d+)\s*-->'

    # 查找所有的页面标记位置
    page_markers = list(re.finditer(page_pattern, markdown_content))

    if not page_markers:
        # 如果没有找到页面标记，返回整个内容作为一个页面
        return [{"pageindex": 0, "md_content": markdown_content}]

    result = []

    # 提取每个页面的内容
    for i, marker in enumerate(page_markers):
        page_number = int(marker.group(1))
        start_pos = marker.end()  # 当前页面标记结束的位置

        # 计算当前页面的结束位置
        if i < len(page_markers) - 1:
            # 如果不是最后一个页面，结束位置是下一个页面标记的开始
            end_pos = page_markers[i + 1].start()
        else:
            # 如果是最后一个页面，结束位置是内容的末尾
            end_pos = len(markdown_content)

        # 提取页面内容
        page_content = markdown_content[start_pos:end_pos].strip()

        result.append({
            "pageindex": page_number,
            "md_content": page_content
        })

    return result


def process_file(file_path: str, style: str = "normal") -> Dict[str, Any]:
    """处理文件并返回 JSON 结果"""
    outputs = pipeline.predict(input=file_path)

    model_output_list = []

    for page_idx, res in enumerate(outputs):
        md_dict = res.markdown
        md_text_original = f'\n<!-- pageindex {page_idx}-->\n' + md_dict["markdown_texts"]
        # 收集原始 markdown
        model_output_list.append(md_text_original)

    # 合并并转换 markdown
    combined_md = "\n\n".join(model_output_list)
    md_content_converted = convert_html_to_markdown(combined_md)
    # 将其分割每一页
    page_contents = parse_markdown_by_pageindex(md_content_converted)
    # 形成口播文案
    ppt_list = get_ppt_voice_content(md_content_converted, style=style)['ppts_list']
    # 组装最终输出
    return {
        "backend": "paddleocr-vl",
        "version": "0.9B",
        "file_name": Path(file_path).stem,
        "md_content": md_content_converted,
        "page_contents": page_contents,
        "ppt_list": ppt_list
    }


@app.on_event("startup")
async def startup_event():
    """启动时初始化 pipeline"""
    global pipeline

    vl_dir = Path(VL_MODEL_DIR)
    layout_dir = Path(LAYOUT_MODEL_DIR)

    if not vl_dir.exists():
        raise FileNotFoundError(f"VL model not found: {vl_dir}")
    if not layout_dir.exists():
        raise FileNotFoundError(f"Layout model not found: {layout_dir}")

    pipeline = PaddleOCRVL(
        vl_rec_model_dir=str(vl_dir),
        layout_detection_model_dir=str(layout_dir)
    )
    print(f"[OK] Pipeline initialized on GPU {GPU_ID}")


@app.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
    style: str = Form("normal")
):
    """
    解析文档（PDF 或图片）

    Args:
        file: PDF 或图片文件
        style: 文案风格 (brief/normal/professional)
    """
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        result = process_file(temp_path, style=style)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "gpu": GPU_ID}


if __name__ == "__main__":
    print(f"[OK] 监听 {HOST}:{PORT} (HOST=0.0.0.0 时可供外网访问)")
    uvicorn.run(app, host=HOST, port=PORT)