"""
音频处理模块依赖项管理
"""

REQUIRED_PACKAGES = {
    'pydub': '用于音频处理',
    'ffmpeg': '音频编解码器（需单独安装）',
    'simpleaudio': '可选，用于音频播放'
}

def check_dependencies():
    """检查必要的依赖包是否已安装"""
    missing = []
    for package in ['pydub']:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("❌ 缺少必要的依赖包:")
        for pkg in missing:
            print(f"  - {pkg}: {REQUIRED_PACKAGES.get(pkg, '未知')}")
        print("\n安装命令:")
        print("pip install pydub")
        return False
    
    # 检查ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ FFmpeg未安装或不在PATH中")
        print("请从 https://ffmpeg.org/download.html 安装")
    
    return True