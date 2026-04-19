#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PaddleOCR-VL API 测试脚本
通过调用接口测试4个关键功能
"""

import requests
import json
import base64
from pathlib import Path

# ============ 配置 ============
import os
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
API_URL = os.getenv("API_URL", "http://127.0.0.1:8802")
TEST_PDF = os.getenv("TEST_PDF", os.path.join(_SCRIPT_DIR, "data", "test.pdf"))
TEST_IMAGE = os.getenv("TEST_IMAGE", os.path.join(_SCRIPT_DIR, "data", "test.jpg"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(_SCRIPT_DIR, "output", "test1"))
# ===============================

def get_api():
    """测试API的4个关键功能"""
    
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("PaddleOCR-VL API 测试")
    print("=" * 60)
    
    # 先检查健康状态
    print("\n检查服务状态...")
    try:
        health = requests.get(f"{API_URL}/health", timeout=5)
        print(f"✓ 服务正常: {health.json()}")
    except Exception as e:
        print(f"✗ 服务未启动: {e}")
        return
    
    # 测试 PDF
    print(f"\n处理PDF文件: {TEST_PDF}")
    if not Path(TEST_PDF).exists():
        print(f"✗ 文件不存在: {TEST_PDF}")
        return
    
    with open(TEST_PDF, "rb") as f:
        files = {"file": (Path(TEST_PDF).name, f, "application/pdf")}
        response = requests.post(f"{API_URL}/parse", files=files)
    
    if response.status_code != 200:
        print(f"✗ API调用失败: {response.text}")
        return
    
    result = response.json()

    
    # 1. 保存md_content
    md_content = result["md_content"]
    md_file = output_dir / "md_content.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"文件:{result['file_name']}")
    print(f"✓ 1. Markdown已保存: {md_file}")
    print(f"   预览(前200字符): {md_content[:200]}...")
    print(result['ppt_list'])
    

    

if __name__ == "__main__":
    get_api()