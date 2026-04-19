import os
import subprocess
import platform

def get_video_duration(video_path):
    """获取视频时长"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 
            video_path
        ], capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return 0

def open_file_in_explorer(file_path):
    """在文件管理器中打开文件所在文件夹"""
    try:
        folder_path = os.path.dirname(file_path)
        system = platform.system()
        
        if system == "Windows":
            os.startfile(folder_path)
        elif system == "Darwin":
            subprocess.run(["open", folder_path])
        elif system == "Linux":
            subprocess.run(["xdg-open", folder_path])
        else:
            print(f"💡 提示: 文件已保存到: {folder_path}")
            
    except Exception as e:
        print(f"⚠️ 无法打开文件管理器: {e}")
        print(f"💡 请手动访问文件夹: {os.path.dirname(file_path)}")

def check_ffmpeg():
    """检查FFmpeg是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False