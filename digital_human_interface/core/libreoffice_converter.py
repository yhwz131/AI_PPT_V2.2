import os
import sys
import asyncio
import subprocess
import platform
import logging
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# 设置日志
logger = logging.getLogger(__name__)


class LibreOfficeConverter:
    """
    LibreOffice 文档转换器
    支持跨平台运行（Windows, Linux, macOS）
    提供PPT/Word/Excel等文档到PDF/图片的转换功能
    修复：Windows路径空格问题和PPT多页导出问题
    """

    def __init__(self, libreoffice_path: str = None):
        """
        初始化转换器

        Args:
            libreoffice_path: 可选的LibreOffice可执行文件路径，如果为None则自动检测
        """
        self.logger = logger
        self.system_type = platform.system().lower()
        self.libreoffice_path = libreoffice_path or self._find_libreoffice()

        if self.libreoffice_path:
            self.logger.info(f"找到LibreOffice: {self.libreoffice_path} (系统: {self.system_type})")
        else:
            self.logger.warning("未找到LibreOffice，文档转换功能将不可用")

        # 设置平台特定的参数
        self._setup_platform_specific_settings()

        # 创建线程池执行器
        self.thread_pool = ThreadPoolExecutor(max_workers=2)

    def _setup_platform_specific_settings(self):
        """设置平台特定的配置"""
        if self.system_type == "windows":
            self.default_timeout = 120
            # Windows下始终使用shell=False，避免路径分割问题
            self.use_shell = False
        else:
            self.default_timeout = 90
            self.use_shell = False

    def _find_libreoffice(self) -> Optional[str]:
        """自动查找系统中安装的LibreOffice"""
        if self.system_type == "windows":
            possible_paths = [
                "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
                "soffice.exe",
            ]
        elif self.system_type == "darwin":
            possible_paths = [
                "/Applications/LibreOffice.app/Contents/MacOS/soffice",
                "/usr/local/bin/soffice",
                "soffice",
            ]
        else:
            possible_paths = [
                "/usr/lib/libreoffice/program/soffice",
                "/usr/bin/soffice",
                "soffice",
            ]

        for path in possible_paths:
            if self._check_path_valid(path):
                return path
        return None

    def _check_path_valid(self, path: str) -> bool:
        """检查路径是否有效"""
        if not path:
            return False

        if not os.path.isabs(path):
            try:
                if self.system_type == "windows":
                    result = subprocess.run(["where", path], capture_output=True, text=True, timeout=5)
                else:
                    result = subprocess.run(["which", path], capture_output=True, text=True, timeout=5)

                if result.returncode == 0:
                    found_path = result.stdout.strip().split('\n')[0]
                    return os.path.exists(found_path)
            except:
                return False
        else:
            return os.path.exists(path)

        return False

    def _prepare_command(self, args: List[str]) -> List[str]:
        """
        准备命令参数列表
        修复：正确处理Windows路径中的空格，不使用shell模式
        """
        if not self.libreoffice_path:
            raise Exception("LibreOffice路径未设置")

        # 直接使用路径，不添加引号（因为使用shell=False）
        cmd = [self.libreoffice_path]
        cmd.extend(args)
        return cmd

    def _run_command(self, cmd, timeout=30):
        """同步执行命令"""
        try:
            # 记录日志时确保所有元素都是字符串
            self.logger.info(f"执行命令: {' '.join(str(arg) for arg in cmd)}")
            result = subprocess.run(
                cmd,  # subprocess.run 可以处理 Path 对象，但记录日志时需要字符串
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout
            )
            self.logger.info(f"命令执行完成，返回码: {result.returncode}")
            if result.stdout:
                self.logger.debug(f"命令输出: {result.stdout.decode('utf-8', errors='ignore')}")
            if result.stderr:
                self.logger.debug(f"命令错误: {result.stderr.decode('utf-8', errors='ignore')}")
            return result
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"命令执行超时: {e}")
            raise
        except Exception as e:
            self.logger.error(f"命令执行异常: {e}")
            raise

    async def convert_to_pdf(self, input_file: str, output_dir: str, timeout: int = None) -> str:
        """将文档转换为PDF格式"""
        if timeout is None:
            timeout = self.default_timeout

        try:
            # 确保输入文件是绝对路径
            if not os.path.isabs(input_file):
                input_file = os.path.abspath(input_file)

            # 确保输出目录是绝对路径
            if not os.path.isabs(output_dir):
                output_dir = os.path.abspath(output_dir)

            self.logger.info(f"开始PDF转换: {input_file} -> {output_dir}")

            # 验证输入文件
            if not os.path.exists(input_file):
                error_msg = f"输入文件不存在: {input_file}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)

            # 在线程池中执行同步转换
            loop = asyncio.get_event_loop()
            pdf_path = await loop.run_in_executor(
                self.thread_pool,
                self._convert_to_pdf_sync,
                input_file,
                output_dir,
                timeout
            )

            if not os.path.exists(pdf_path):
                error_msg = f"PDF文件未生成: {pdf_path}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            self.logger.info(f"PDF转换成功: {pdf_path}")
            return pdf_path

        except Exception as e:
            self.logger.error(f"PDF转换异常: {str(e)}", exc_info=True)
            raise

    def _convert_to_pdf_sync(self, input_file: str, output_dir: str, timeout: int) -> str:
        """同步方式将文档转换为PDF"""
        param_combinations = [
            ['--headless', '--nologo', '--norestore', '--nodefault', '--nofirststartwizard'],
            ['--headless', '--nologo'],
            ['--headless'],
            [],
        ]

        last_error = None

        for i, params in enumerate(param_combinations):
            try:
                self.logger.info(f"尝试PDF转换参数组合 {i + 1}/{len(param_combinations)}: {params}")

                # 构建命令参数
                cmd_args = params + [
                    '--convert-to', 'pdf',
                    '--outdir', output_dir,
                    input_file
                ]

                cmd = self._prepare_command(cmd_args)
                result = self._run_command(cmd, timeout)

                self.logger.info(f"PDF转换命令返回码: {result.returncode}")
                if result.stdout:
                    self.logger.info(f"PDF转换命令输出: {result.stdout}")
                if result.stderr:
                    self.logger.warning(f"PDF转换命令错误: {result.stderr}")

                if result.returncode == 0:
                    # 查找生成的PDF文件
                    pdf_path = self._find_output_file(input_file, output_dir, "pdf")
                    if pdf_path:
                        return pdf_path
                    else:
                        last_error = Exception(f"PDF文件未生成在目录: {output_dir}")
                        continue
                else:
                    last_error = Exception(f"PDF转换失败，返回码: {result.returncode}")
                    continue

            except subprocess.TimeoutExpired:
                last_error = Exception(f"PDF转换超时（{timeout}秒）")
                continue
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        else:
            raise Exception("所有PDF转换尝试都失败")

    async def convert_to_images(self, input_file: str, output_dir: str,
                                image_format: str = "png", timeout: int = None) -> List[str]:
        """
        将文档转换为图片序列

        Args:
            input_file: 输入文件路径
            output_dir: 输出目录路径
            image_format: 图片格式（png, jpg等）
            timeout: 超时时间（秒）

        Returns:
            生成的图片文件路径列表
        """
        if timeout is None:
            timeout = self.default_timeout

        try:
            # 确保输入文件是绝对路径
            if not os.path.isabs(input_file):
                input_file = os.path.abspath(input_file)

            # 确保输出目录是绝对路径
            if not os.path.isabs(output_dir):
                output_dir = os.path.abspath(output_dir)

            self.logger.info(f"开始图片转换: {input_file} -> {output_dir}, 格式: {image_format}")

            # 验证输入文件
            if not os.path.exists(input_file):
                error_msg = f"输入文件不存在: {input_file}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)

            # 在线程池中执行同步转换
            loop = asyncio.get_event_loop()
            image_paths = await loop.run_in_executor(
                self.thread_pool,
                self._convert_to_images_sync,
                input_file,
                output_dir,
                image_format,
                timeout
            )

            if not image_paths:
                error_msg = "未生成任何图片文件"
                self.logger.error(error_msg)
                raise Exception(error_msg)

            self.logger.info(f"图片转换成功，生成 {len(image_paths)} 张图片")
            return image_paths

        except Exception as e:
            self.logger.error(f"图片转换异常: {str(e)}", exc_info=True)
            raise

    def _convert_to_images_sync(self, input_file: str, output_dir: str,
                                image_format: str, timeout: int) -> List[str]:
        """
        同步方式将文档转换为图片序列
        """
        # 获取文件扩展名以确定文档类型
        file_ext = Path(input_file).suffix.lower()

        # 根据文件类型选择不同的转换策略
        if file_ext in ['.ppt', '.pptx', '.odp']:
            # 演示文稿文件，需要特殊处理以确保导出所有幻灯片
            return self._convert_presentation_to_images(input_file, output_dir, image_format, timeout)
        else:
            # 其他类型文件使用标准转换
            return self._convert_standard_to_images(input_file, output_dir, image_format, timeout)

    def _convert_presentation_to_images(self, input_file: str, output_dir: str,
                                        image_format: str, timeout: int) -> List[str]:
        """
        专门处理演示文稿（PPT/PPTX）转换为图片
        确保导出所有幻灯片
        """
        self.logger.info("检测到演示文稿文件，使用特殊转换方法确保导出所有幻灯片")

        # 尝试不同的转换策略
        strategies = [
            self._try_presentation_conversion_strategy1,  # 基础方法
            self._try_presentation_conversion_strategy2,  # 使用独立用户配置
            self._try_presentation_conversion_strategy3,  # 使用过滤器选项
            self._try_presentation_conversion_fallback,  # 备用方案
        ]

        last_error = None

        for i, strategy in enumerate(strategies):
            try:
                self.logger.info(f"尝试演示文稿转换策略 {i + 1}/{len(strategies)}")
                image_paths = strategy(input_file, output_dir, image_format, timeout)

                # 检查是否生成了多张图片
                if image_paths and len(image_paths) > 1:
                    self.logger.info(f"策略 {i + 1} 成功，生成 {len(image_paths)} 张图片")
                    return image_paths
                elif image_paths and len(image_paths) == 1:
                    self.logger.warning(f"策略 {i + 1} 仅生成1张图片，尝试下一个策略")
                    last_error = Exception(f"策略 {i + 1} 仅生成1张图片")
                    continue
                else:
                    last_error = Exception(f"策略 {i + 1} 未生成任何图片")
                    continue
            except Exception as e:
                last_error = e
                self.logger.warning(f"策略 {i + 1} 失败: {e}")
                continue

        if last_error:
            raise last_error
        else:
            raise Exception("所有演示文稿转换策略都失败，无法导出所有幻灯片")

    def _try_presentation_conversion_strategy1(self, input_file: str, output_dir: str,
                                               image_format: str, timeout: int) -> List[str]:
        """
        策略1：基础转换方法
        """
        cmd_args = [
            '--headless',
            '--nologo',
            '--norestore',
            '--invisible',
            '--convert-to', f'{image_format}',
            '--outdir', output_dir,
            input_file
        ]

        cmd = self._prepare_command(cmd_args)
        result = self._run_command(cmd, timeout)

        self.logger.info(f"策略1返回码: {result.returncode}")
        if result.stdout:
            self.logger.info(f"策略1输出: {result.stdout}")
        if result.stderr:
            self.logger.warning(f"策略1错误: {result.stderr}")

        if result.returncode == 0:
            image_files = self._find_all_image_files(output_dir, image_format, input_file)
            return image_files
        else:
            raise Exception(f"策略1失败，返回码: {result.returncode}")

    def _try_presentation_conversion_strategy2(self, input_file: str, output_dir: str,
                                               image_format: str, timeout: int) -> List[str]:
        """
        策略2：使用独立用户配置避免冲突
        """
        # 生成唯一的用户配置目录
        user_install_dir = os.path.join(output_dir, ".libreoffice_temp")
        os.makedirs(user_install_dir, exist_ok=True)

        cmd_args = [
            '--headless',
            '--nologo',
            '--norestore',
            '--invisible',
            '--nodefault',
            '--nofirststartwizard',
            f'-env:UserInstallation=file:///{user_install_dir.replace(os.sep, "/")}',
            '--convert-to', f'{image_format}',
            '--outdir', output_dir,
            input_file
        ]

        cmd = self._prepare_command(cmd_args)
        result = self._run_command(cmd, timeout)

        # 清理临时目录
        try:
            shutil.rmtree(user_install_dir, ignore_errors=True)
        except:
            pass

        self.logger.info(f"策略2返回码: {result.returncode}")

        if result.returncode == 0:
            image_files = self._find_all_image_files(output_dir, image_format, input_file)
            return image_files
        else:
            raise Exception(f"策略2失败，返回码: {result.returncode}")

    def _try_presentation_conversion_strategy3(self, input_file: str, output_dir: str,
                                               image_format: str, timeout: int) -> List[str]:
        """
        策略3：使用Impress专用过滤器
        """
        # 为演示文稿使用专门的过滤器
        filter_name = "impress_png_Export" if image_format.lower() == "png" else f"impress_{image_format}_Export"

        cmd_args = [
            '--headless',
            '--nologo',
            '--invisible',
            '--convert-to', f'{image_format}:{filter_name}',
            '--outdir', output_dir,
            input_file
        ]

        cmd = self._prepare_command(cmd_args)
        result = self._run_command(cmd, timeout * 2)  # 给更多时间

        self.logger.info(f"策略3返回码: {result.returncode}")
        if result.stdout:
            self.logger.info(f"策略3输出: {result.stdout}")
        if result.stderr:
            self.logger.warning(f"策略3错误: {result.stderr}")

        if result.returncode == 0:
            image_files = self._find_all_image_files(output_dir, image_format, input_file)
            return image_files
        else:
            raise Exception(f"策略3失败，返回码: {result.returncode}")

    def _try_presentation_conversion_fallback(self, input_file: str, output_dir: str,
                                              image_format: str, timeout: int) -> List[str]:
        """
        备用策略：先转换为PDF，再将PDF转换为图片
        """
        self.logger.info("使用备用策略: PPT->PDF->图片")

        # 创建临时目录存储PDF
        with tempfile.TemporaryDirectory() as temp_pdf_dir:
            try:
                # 第一步：转换为PDF
                pdf_path = self._convert_to_pdf_sync(input_file, temp_pdf_dir, timeout)
                self.logger.info(f"备用策略：PPT转PDF成功: {pdf_path}")

                # 第二步：将PDF转换为图片
                pdf_image_files = self._convert_pdf_to_images(pdf_path, output_dir, image_format, timeout)
                if pdf_image_files:
                    self.logger.info(f"备用策略成功，生成 {len(pdf_image_files)} 张图片")
                    return pdf_image_files
                else:
                    raise Exception("备用策略未生成任何图片")
            except Exception as e:
                self.logger.warning(f"备用策略失败: {e}")
                raise

    def _convert_pdf_to_images(self, pdf_file: str, output_dir: str,
                               image_format: str, timeout: int) -> List[str]:
        """将PDF文件转换为图片"""
        cmd_args = [
            '--headless',
            '--nologo',
            '--norestore',
            '--convert-to', image_format,
            '--outdir', output_dir,
            pdf_file
        ]

        cmd = self._prepare_command(cmd_args)
        result = self._run_command(cmd, timeout)

        if result.returncode == 0:
            return self._find_all_image_files(output_dir, image_format, pdf_file)
        else:
            raise Exception(f"PDF转图片失败，返回码: {result.returncode}")

    def _convert_standard_to_images(self, input_file: str, output_dir: str,
                                    image_format: str, timeout: int) -> List[str]:
        """标准文件转换方法"""
        param_combinations = [
            ['--headless', '--nologo', '--norestore', '--nodefault', '--nofirststartwizard'],
            ['--headless', '--nologo'],
            ['--headless'],
            [],
        ]

        last_error = None

        for i, params in enumerate(param_combinations):
            try:
                self.logger.info(f"尝试标准转换参数组合 {i + 1}/{len(param_combinations)}: {params}")

                cmd_args = params + [
                    '--convert-to', image_format,
                    '--outdir', output_dir,
                    input_file
                ]

                cmd = self._prepare_command(cmd_args)
                result = self._run_command(cmd, timeout)

                self.logger.info(f"标准转换返回码: {result.returncode}")

                if result.returncode == 0:
                    image_files = self._find_all_image_files(output_dir, image_format, input_file)
                    if image_files:
                        return image_files
                    else:
                        last_error = Exception("未生成任何图片文件")
                        continue
                else:
                    last_error = Exception(f"标准转换失败，返回码: {result.returncode}")
                    continue

            except subprocess.TimeoutExpired:
                last_error = Exception(f"标准转换超时（{timeout}秒）")
                continue
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        else:
            raise Exception("所有标准转换尝试都失败")

    def _find_all_image_files(self, output_dir: str, image_format: str, input_file: str = None) -> List[str]:
        """
        查找输出目录中的所有图片文件，并按页码排序
        """
        # 构建基础文件名（用于匹配）
        base_name = ""
        if input_file:
            base_name = Path(input_file).stem.lower()

        # 查找所有匹配格式的文件
        pattern = f"*.{image_format.lower()}"
        image_files = list(Path(output_dir).glob(pattern))

        if not image_files:
            return []

        # 过滤出与输入文件相关的图片
        filtered_files = []
        for file in image_files:
            file_name = file.stem.lower()
            # 匹配规则：包含基础文件名或包含页码
            if base_name and (base_name in file_name or self._is_paged_file(file_name, base_name)):
                filtered_files.append(file)
            elif not base_name:
                filtered_files.append(file)

        # 如果过滤后为空，使用原始列表
        if not filtered_files:
            filtered_files = image_files

        # 按文件名排序
        filtered_files.sort(key=lambda x: self._extract_page_number(x.name))

        # 转换为绝对路径
        result = [str(f.absolute()) for f in filtered_files]

        self.logger.info(f"找到 {len(result)} 张图片文件")
        return result

    def _is_paged_file(self, filename: str, base_name: str) -> bool:
        """检查是否为分页文件"""
        # 移除基础文件名部分，检查剩余部分是否为数字
        remaining = filename.replace(base_name, '').strip('-_')
        return remaining.isdigit()

    def _extract_page_number(self, filename: str) -> int:
        """
        从文件名中提取页码
        """
        try:
            # 移除扩展名
            name_without_ext = Path(filename).stem

            # 尝试提取数字
            import re
            match = re.search(r'(\d+)$', name_without_ext)
            if match:
                return int(match.group(1))

            match = re.search(r'-(\d+)', name_without_ext)
            if match:
                return int(match.group(1))

            match = re.search(r'_(\d+)', name_without_ext)
            if match:
                return int(match.group(1))

            if name_without_ext.isdigit():
                return int(name_without_ext)

            return 0
        except:
            return 0

    def _find_output_file(self, input_file: str, output_dir: str, output_format: str) -> Optional[str]:
        """查找输出文件"""
        input_path = Path(input_file)

        # 首先尝试预期的文件名
        expected_file = os.path.join(output_dir, input_path.stem + "." + output_format)
        if os.path.exists(expected_file):
            return expected_file

        # 查找所有匹配格式的文件
        pattern = f"*.{output_format}"
        matching_files = list(Path(output_dir).glob(pattern))

        if matching_files:
            # 返回最新修改的文件
            matching_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            return str(matching_files[0])

        return None

    def test_connection(self) -> bool:
        """测试LibreOffice连接"""
        if not self.libreoffice_path:
            return False

        try:
            cmd = self._prepare_command(['--version'])
            result = self._run_command(cmd, 30)
            return result.returncode == 0
        except:
            return False

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "libreoffice_path": self.libreoffice_path,
            "libreoffice_found": bool(self.libreoffice_path),
        }

    def __del__(self):
        """析构函数，清理线程池"""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=False)


# 创建全局转换器实例
converter = LibreOfficeConverter()


# 导出工具函数
def test_libreoffice_connection() -> bool:
    """测试LibreOffice连接"""
    return converter.test_connection()


def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    return converter.get_system_info()