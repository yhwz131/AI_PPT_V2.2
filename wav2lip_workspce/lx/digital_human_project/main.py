import os
import sys
import uvicorn
import webbrowser
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from api.routes import app

def main():
    print("🚀🚀🚀🚀 启动简体中文数字人视频生成器 FastAPI 服务...")
    
    # 获取配置
    host_ip = config.host_ip
    port = config.port
    
    print("=" * 60)
    print("🌐 网络连接信息:")
    print(f"📡 使用指定IP: {host_ip}")
    print(f"🔌 使用端口: {port}")
    print(f"💻 本机测试地址: http://127.0.0.1:{port}")
    print(f"🌍 局域网访问地址: http://{host_ip}:{port}")
    print(f"📚 交互式文档: http://{host_ip}:{port}/docs")
    print("=" * 60)
    
    # 检查FFmpeg
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg 已安装")
        else:
            print("⚠️ FFmpeg 可能未正确安装")
    except:
        print("❌ 未找到 FFmpeg，请确保已安装")
    
    # 检查依赖库
    try:
        import whisper
        print("✅ Whisper 已安装")
    except ImportError:
        print("⚠️ Whisper 未安装，字幕生成功能将不可用")
    
    try:
        from opencc import OpenCC
        print("✅ OpenCC 已安装")
    except ImportError:
        print("⚠️ OpenCC 未安装，将使用简单简繁转换")
    
    # 检查服务目录
    print(f"📁 输出目录: {os.path.abspath(config.output_dir)}")
    print(f"📁 上传目录: {os.path.abspath(config.upload_dir)}")
    print(f"📁 临时目录: {os.path.abspath(config.temp_dir)}")
    print("💡 服务启动中...")
    
    # 启动FastAPI服务
    uvicorn.run(
        app,
        host=host_ip,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    main()