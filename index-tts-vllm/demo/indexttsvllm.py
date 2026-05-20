import requests
import json
import argparse

# 创建命令行参数解析器
parser = argparse.ArgumentParser(description="IndexTTS VLLM 语音合成")
parser.add_argument("-texts", type=str, required=True,
                    help="要合成语音的文本列表，JSON数组格式。例如：'[\"你好\",\"世界\"]'")
parser.add_argument("-emo", type=int, default=1,
                    help="情感控制方法: 0=不使用情感, 1=使用情感向量(默认), 2=使用情感参考音频, 3=使用情感文本描述")
parser.add_argument("-emo_vec", type=str, default="[0,0,0,0,0,0,0,0]",
                    help="情感向量（8维数组），JSON格式。维度对应: [喜,怒,哀,惧,厌恶,低落,惊喜,平静]")
parser.add_argument("-spk_audio", type=str, required=True,
                    help="参考音色音频文件路径，用于提取说话人的音色特征")
parser.add_argument("-emo_ref", type=str, default=None,
                    help="情感参考音频文件路径（可选），当 emo=2 时使用")
parser.add_argument("-emo_text", type=str, default=None,
                    help="情感文本描述（可选），当 emo=3 时使用，例如：\"极度悲伤\"")
parser.add_argument("-max_text", type=int, default=120,
                    help="每句话最大处理的 token 数量，影响单句长度限制")
parser.add_argument("-output_dir", type=str, default=".",
                    help="输出目录，生成的音频文件将保存在此目录下")

args = parser.parse_args()

# TTS 服务器地址
url = "http://0.0.0.0:6006/batch_tts_url"

# 解析命令行传入的 JSON 格式参数
texts = json.loads(args.texts)        # 将 JSON 字符串解析为 Python 列表
emo_vec = json.loads(args.emo_vec)    # 将 JSON 字符串解析为 Python 列表

# 构建请求数据
data = {
    "texts": json.dumps(texts),                        # 文本列表（JSON数组）
    "emo_control_method": args.emo,                    # 情感控制方法（简写）
    "emo_vec": json.dumps(emo_vec),                   # 情感向量（JSON数组）
    "max_text_tokens_per_sentence": args.max_text      # 最大token数（简写）
}

# 打开参考音色音频文件，以二进制形式读取
files = {}
with open(args.spk_audio, "rb") as f:
    files["spk_audio_file"] = f

    # 发送 POST 请求到 TTS 服务器
    response = requests.post(url, data=data, files=files)

# 解析服务器返回的 JSON 响应
result = response.json()
print(f"响应: {result}")

# 遍历每个音频结果，下载生成的音频文件
for idx, item in enumerate(result.get("results", [])):
    # 检查该音频是否生成失败
    if item.get("status") == "failed":
        print(f"音频 {idx} 生成失败: {item.get('error')}")
        continue

    # 获取该音频的下载链接
    download_url = item.get("download_url")
    audio_path = item.get("audio_path")

    print(f"正在下载音频 {idx}: {download_url}")

    # 通过下载链接获取音频内容
    audio_response = requests.get(download_url)

    # 保存音频文件到指定目录
    output_file = f"{args.output_dir}/output_{idx}.wav"
    with open(output_file, "wb") as f:
        f.write(audio_response.content)
    print(f"音频已保存: {output_file}")