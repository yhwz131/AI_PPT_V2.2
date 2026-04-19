#!/usr/bin/env python3
"""
下载 PaddleOCR-VL-1.5-0.9B 模型，用于 doc_parser（与 pipeline 默认 model_name 一致）。
支持魔搭 ModelScope / HuggingFace 两种源。
"""
import os
import argparse


def download_from_modelscope(save_dir: str, model_id: str = "PaddlePaddle/PaddleOCR-VL-1.5"):
    """从魔搭 ModelScope 下载。"""
    from modelscope import snapshot_download
    os.makedirs(os.path.dirname(save_dir) or ".", exist_ok=True)
    path = snapshot_download(model_id, local_dir=save_dir)
    print(f"[ModelScope] 已下载到: {path}")
    return path


def download_from_huggingface(save_dir: str, model_id: str = "PaddlePaddle/PaddleOCR-VL-1.5"):
    """从 HuggingFace 下载。"""
    from huggingface_hub import snapshot_download
    os.makedirs(os.path.dirname(save_dir) or ".", exist_ok=True)
    path = snapshot_download(repo_id=model_id, local_dir=save_dir)
    print(f"[HuggingFace] 已下载到: {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description="下载 PaddleOCR-VL-1.5-0.9B 模型")
    parser.add_argument(
        "--source",
        choices=["modelscope", "huggingface"],
        default="modelscope",
        help="下载源：modelscope（魔搭）或 huggingface",
    )
    parser.add_argument(
        "--save_dir",
        type=str,
        default="./models/PaddleOCR-VL-1.5-0.9B",
        help="本地保存目录，建议与 pipeline 默认 model_name 对应",
    )
    args = parser.parse_args()

    model_id = "PaddlePaddle/PaddleOCR-VL-1.5"
    if args.source == "modelscope":
        download_from_modelscope(args.save_dir, model_id)
    else:
        download_from_huggingface(args.save_dir, model_id)

    print("下载完成。运行 doc_parser 时使用：")
    print(f"  --vl_rec_model_name PaddleOCR-VL-1.5-0.9B --vl_rec_model_dir {os.path.abspath(args.save_dir)}")


if __name__ == "__main__":
    main()
