import os
import requests
import zipfile
import re
from pathlib import Path
from typing import List, Tuple, Optional
from urllib.parse import urlparse, unquote


class ZipProcessor:
    """
    ZIP文件处理类，用于下载、解压、重命名和清理ZIP文件
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        初始化ZIP处理器

        参数:
        - project_root: 项目根目录路径，如果为None则自动检测
        """
        if project_root is None:
            # 自动检测项目根目录（包含digital_human_interface的目录）
            current_path = Path(__file__).resolve().parent
            while current_path != current_path.parent:
                if "digital_human_interface" in current_path.name:
                    self.project_root = current_path
                    break
                current_path = current_path.parent
            else:
                self.project_root = Path(__file__).resolve().parent
        else:
            self.project_root = Path(project_root).resolve()

        print(f"项目根目录设置为: {self.project_root}")

    def ensure_absolute_path(self, path_str: str) -> Path:
        """
        确保路径为绝对路径

        参数:
        - path_str: 路径字符串，可以是相对路径或绝对路径

        返回:
        - 解析后的绝对路径对象
        """
        path = Path(path_str)
        if path.is_absolute():
            return path.resolve()

        # 如果是相对路径，则相对于项目根目录
        absolute_path = self.project_root / path
        absolute_path = absolute_path.resolve()

        print(f"路径转换: '{path_str}' -> '{absolute_path}'")
        return absolute_path

    def extract_number(self, filename: str) -> int:
        """
        从文件名中提取数字部分用于排序 - 修复版本
        现在会提取文件名中所有数字并组合成完整数字

        参数:
        - filename: 文件名

        返回:
        - 提取到的数字，如果没有数字则返回0
        """
        try:
            # 提取文件名中的所有数字[7](@ref)
            numbers = re.findall(r'\d+', str(filename))
            if numbers:
                # 将找到的所有数字组合起来[2](@ref)
                combined_number = int(''.join(numbers))
                return combined_number
            return 0
        except Exception as e:
            print(f"提取数字时出错 {filename}: {e}")
            return 0

    def natural_sort_key(self, filename: str) -> List:
        """
        自然排序键函数，确保数字按数值大小排序而不是字符串排序[6,7](@ref)

        参数:
        - filename: 文件名

        返回:
        - 用于自然排序的键列表
        """
        return [int(text) if text.isdigit() else text.lower()
                for text in re.split(r'(\d+)', str(filename))]

    def get_safe_filename(self, url: str) -> str:
        """
        从URL中安全地提取文件名

        参数:
        - url: 下载URL

        返回:
        - 安全的文件名
        """
        try:
            parsed_url = urlparse(url)
            path = unquote(parsed_url.path)
            filename = Path(path).name if path else "download_batch.zip"

            # 如果文件名无效，使用时间戳生成文件名
            if not filename or filename == "/":
                import time
                filename = f"download_batch_{int(time.time())}.zip"

            # 确保文件扩展名为.zip
            if not filename.endswith('.zip'):
                filename += '.zip'

            # 移除文件名中的非法字符
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            return filename

        except Exception as e:
            print(f"文件名提取失败，使用默认文件名: {e}")
            import time
            return f"download_batch_{int(time.time())}.zip"

    def download_zip_file(self, url: str, save_path: str) -> str:
        """
        从URL下载ZIP压缩包

        参数:
        - url: 下载URL
        - save_path: 保存路径

        返回:
        - 下载文件的完整路径，失败返回空字符串
        """
        try:
            save_path = Path(save_path)

            print(f"开始下载: {url}")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            # 确保保存目录存在
            save_path.parent.mkdir(parents=True, exist_ok=True)

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            percent = (downloaded_size / total_size) * 100
                            print(f"\r下载进度: {percent:.1f}%", end="", flush=True)

            print(f"\n下载完成，文件保存至: {save_path}")
            return str(save_path)

        except Exception as e:
            print(f"下载失败: {e}")
            return ""

    def extract_zip_file(self, zip_path: str, extract_to: str) -> str:
        """
        解压ZIP文件到指定目录 - 修复路径重复问题

        参数:
        - zip_path: ZIP文件路径
        - extract_to: 解压目标目录

        返回:
        - 解压目录路径，失败返回空字符串
        """
        try:
            # 检查文件是否为有效的ZIP格式
            if not zipfile.is_zipfile(zip_path):
                print("错误：文件不是有效的ZIP格式")
                return ""

            extract_to_path = Path(extract_to)

            # 关键修复：直接使用用户指定的解压目录，避免路径重复
            final_extract_path = extract_to_path

            print(f"开始解压: {zip_path}")
            final_extract_path.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                print(f"压缩包包含 {len(file_list)} 个文件/文件夹")

                # 解压所有文件到目标目录
                zip_ref.extractall(final_extract_path)

            print(f"解压完成，文件已解压到: {final_extract_path}")
            return str(final_extract_path)

        except Exception as e:
            print(f"解压过程中发生错误: {e}")
            return ""

    def rename_files_sequentially(self, directory: str, prefix: str = "audio", start_index: int = 1) -> bool:
        """
        将目录中的文件按照正确的数字顺序重新命名，并输出对照关系

        参数:
        - directory: 要重命名的目录路径
        - prefix: 新文件名的前缀，默认为"audio"
        - start_index: 起始索引，默认为1（从1开始编号）

        返回:
        - 重命名是否成功
        """
        try:
            directory_path = Path(directory)
            if not directory_path.exists():
                print(f"错误：目录不存在 {directory_path}")
                return False

            # 获取目录中的所有文件（排除子目录）
            files = [f for f in directory_path.iterdir() if f.is_file()]
            if not files:
                print("目录中没有文件可重命名")
                return True

            # 关键修复：使用自然排序确保数字按数值大小排序[6,7](@ref)
            files.sort(key=lambda x: self.natural_sort_key(x.name))

            # 调试信息：显示排序后的文件名
            print("排序后的文件列表:")
            for i, file_path in enumerate(files):
                print(f"  {i + 1}: {file_path.name}")

            print(f"开始重命名 {len(files)} 个文件...")
            print("文件名对照关系:")

            # 存储重命名操作，先收集所有操作再执行，避免冲突
            rename_operations = []

            # 收集所有重命名操作
            for index, file_path in enumerate(files, start=start_index):
                # 获取文件扩展名
                extension = file_path.suffix
                # 生成新文件名：前缀_索引.扩展名
                new_name = f"{prefix}_{index}{extension}"
                new_path = directory_path / new_name
                rename_operations.append((file_path, new_name, new_path))

                # 按照要求格式输出对照关系
                print(f"{file_path.name} -> {new_name}")

            # 执行重命名操作
            for file_path, new_name, new_path in rename_operations:
                # 如果目标文件已存在，先删除
                if new_path.exists():
                    new_path.unlink()
                # 执行重命名
                file_path.rename(new_path)

            print("文件重命名完成")
            return True

        except Exception as e:
            print(f"重命名过程中发生错误: {e}")
            return False

    def get_relative_file_paths(self, directory: str) -> List[str]:
        """
        获取目录中所有文件相对于项目根目录的路径列表

        参数:
        - directory: 目录路径

        返回:
        - 相对路径列表
        """
        try:
            directory_path = Path(directory)
            project_root = self.project_root.resolve()

            if not directory_path.exists():
                print(f"错误：目录不存在 {directory_path}")
                return []

            print(f"计算相对路径 - 项目根目录: {project_root}")
            print(f"计算相对路径 - 文件目录: {directory_path}")

            # 递归获取所有文件路径
            file_paths = []
            for file_path in directory_path.rglob('*'):
                if file_path.is_file():
                    file_paths.append(file_path)

            if not file_paths:
                print("目录中没有找到文件")
                return []

            # 按照正确的数字顺序排序
            file_paths.sort(key=lambda x: self.natural_sort_key(x.name))

            # 转换为相对路径
            relative_paths = []
            for file_path in file_paths:
                try:
                    abs_file_path = file_path.resolve()

                    # 确保文件在项目根目录下
                    if str(abs_file_path).startswith(str(project_root)):
                        relative_path = abs_file_path.relative_to(project_root)
                        # 转换为UNIX风格的路径（以/开头）
                        relative_path_str = '/' + str(relative_path).replace('\\', '/')
                        relative_paths.append(relative_path_str)
                        print(f"找到相对路径: {relative_path_str}")
                    else:
                        print(f"文件不在项目根目录下: {abs_file_path}")

                except Exception as e:
                    print(f"处理文件 {file_path} 时发生错误: {e}")
                    continue

            print(f"成功找到 {len(relative_paths)} 个文件的路径")
            return relative_paths

        except Exception as e:
            print(f"获取相对路径时发生错误: {e}")
            return []

    def delete_zip_file(self, zip_path: str) -> bool:
        """
        删除压缩包文件

        参数:
        - zip_path: ZIP文件路径

        返回:
        - 删除是否成功
        """
        try:
            zip_path = Path(zip_path)
            if zip_path.exists():
                zip_path.unlink()
                print(f"压缩包已删除: {zip_path}")
                return True
            else:
                print(f"文件不存在，无需删除: {zip_path}")
                return False
        except Exception as e:
            print(f"删除压缩包时发生错误: {e}")
            return False

    def process_zip_from_url(self, url: str, temp_path: str, save_path: str,
                             prefix: str = "audio", delete_after_extract: bool = True) -> Tuple[str, List[str]]:
        """
        完整的ZIP文件处理流程 - 修复版本

        参数:
        - url: 下载URL
        - temp_path: 临时存储ZIP文件的路径
        - save_path: 解压保存路径
        - prefix: 重命名前缀，默认为"audio"
        - delete_after_extract: 解压后是否删除ZIP文件

        返回:
        - (解压目录路径, 相对路径列表)
        """
        print("=" * 50)
        print("开始处理ZIP文件")
        print("=" * 50)

        # 使用安全的文件名提取方法
        zip_filename = self.get_safe_filename(url)
        print(f"解析的文件名: {zip_filename}")

        # 确保路径为绝对路径
        temp_path_abs = self.ensure_absolute_path(temp_path)
        save_path_abs = self.ensure_absolute_path(save_path)

        # 构建完整路径
        zip_path = temp_path_abs / zip_filename

        # 关键修复：直接使用用户指定的保存路径，不添加额外子目录
        extract_path = save_path_abs
        print(f"解压目录路径: {extract_path}")

        # 1. 下载ZIP文件
        downloaded_path = self.download_zip_file(url, zip_path)
        if not downloaded_path:
            return "", []

        # 2. 解压ZIP文件（使用修复后的方法）
        extract_path_str = self.extract_zip_file(downloaded_path, extract_path)
        if not extract_path_str:
            return "", []

        # 3. 重命名文件（从1开始编号，使用正确的排序）
        if not self.rename_files_sequentially(extract_path_str, prefix, start_index=1):
            print("警告：文件重命名失败，但继续处理")

        # 4. 删除压缩包（如果设置了删除标志）
        if delete_after_extract:
            self.delete_zip_file(downloaded_path)

        # 5. 获取相对路径列表
        relative_paths = self.get_relative_file_paths(extract_path_str)

        print("=" * 50)
        print("ZIP文件处理完成")
        print("=" * 50)

        return extract_path_str, relative_paths