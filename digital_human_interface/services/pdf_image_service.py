import os
import fitz  # PyMuPDF
from pathlib import Path
from typing import List
import re


def get_project_root() -> Path:
    """
    获取项目根目录

    返回:
        Path: 项目根目录路径
    """
    current_path = Path(__file__).resolve().parent
    # 向上查找包含项目标识的目录
    while current_path != current_path.parent:
        if "digital_human_interface" in current_path.name:
            return current_path
        current_path = current_path.parent
    return Path(__file__).resolve().parent


def ensure_absolute_path(path_str: str, base_path: Path = None) -> Path:
    """
    确保路径为绝对路径

    参数:
        path_str (str): 输入路径字符串
        base_path (Path): 基础路径，用于相对路径转换

    返回:
        Path: 绝对路径
    """
    if not path_str:
        raise ValueError("路径字符串不能为空")

    # 处理以"/"开头的相对路径（项目相对路径）
    if path_str.startswith('/') or path_str.startswith('\\'):
        # 这是相对于项目根目录的路径
        project_root = get_project_root()
        # 去掉开头的斜杠
        clean_path = path_str.lstrip('/\\')
        absolute_path = project_root / clean_path
    else:
        path = Path(path_str)
        # 如果已经是绝对路径，直接返回
        if path.is_absolute():
            absolute_path = path
        else:
            # 如果指定了基础路径，基于基础路径转换
            if base_path:
                absolute_path = base_path / path
            else:
                # 如果没有指定基础路径，使用当前工作目录
                absolute_path = Path.cwd() / path

    return absolute_path.resolve()


def pdf_to_images_pymupdf(pdf_path: str, output_folder: str = None,
                          zoom: float = 2.0, prefix: str = "page_") -> List[str]:
    """
    使用PyMuPDF将PDF转换为图片，并返回图片相对路径列表

    参数:
        pdf_path (str): PDF文件的路径（相对或绝对路径）
        output_folder (str): 输出图片的文件夹路径。如果为None，则在与PDF同目录下创建"[PDF文件名]_images"文件夹
        zoom (float): 缩放因子，控制图片质量。值越大，图片质量越高（默认2.0）
        prefix (str): 输出图片文件名的前缀（默认"page_")

    返回:
        List[str]: 包含所有生成的图片相对路径（相对于输出文件夹）的列表

    异常:
        FileNotFoundError: 如果指定的PDF文件不存在
        ValueError: 如果PDF文件无法打开或处理
    """

    print(f"原始PDF路径: {pdf_path}")
    print(f"原始输出文件夹: {output_folder}")

    # 转换PDF路径为绝对路径
    # pdf_absolute_path = ensure_absolute_path(pdf_path)
    pdf_absolute_path = pdf_path
    print(f"PDF绝对路径: {pdf_absolute_path}")

    # 验证PDF文件是否存在
    # if not pdf_absolute_path.exists():
    #     # 尝试另一种路径格式
    #     if pdf_path.startswith('/'):
    #         # 尝试去掉开头的斜杠
    #         alt_path = pdf_path.lstrip('/')
    #         pdf_absolute_path = ensure_absolute_path(alt_path)
    #         print(f"尝试替代PDF路径: {pdf_absolute_path}")
    #
    #     if not pdf_absolute_path.exists():
    #         # 列出目录内容以帮助调试
    #         parent_dir = pdf_absolute_path.parent
    #         print(f"PDF父目录: {parent_dir}")
    #         if parent_dir.exists():
    #             files = list(parent_dir.glob("*.pdf"))
    #             print(f"该目录下的PDF文件: {[f.name for f in files]}")
    #
    #         raise FileNotFoundError(f"PDF文件不存在: {pdf_absolute_path}")

    # 如果未指定输出文件夹，则在与PDF同目录下创建默认文件夹
    if output_folder is None:
        pdf_parent = pdf_absolute_path.parent
        pdf_name = pdf_absolute_path.stem
        output_absolute_path = pdf_parent / f"{pdf_name}_images"
    else:
        # 转换输出文件夹路径为绝对路径
        output_absolute_path = ensure_absolute_path(output_folder)

    # 创建输出文件夹（如果不存在）
    output_absolute_path.mkdir(parents=True, exist_ok=True)
    print(f"输出文件夹: {output_absolute_path}")

    # 记录保存的图片路径
    image_paths = []

    try:
        # 打开PDF文件
        pdf_document = fitz.open(str(pdf_absolute_path))
        total_pages = len(pdf_document)
        print(f"PDF总页数: {total_pages}")

        # 遍历每一页
        for page_num in range(total_pages):
            # 获取页面对象
            page = pdf_document.load_page(page_num)

            # 设置缩放矩阵
            mat = fitz.Matrix(zoom, zoom)

            # 渲染页面为图像
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # 构建图片文件名和完整路径
            page_num_str = str(page_num + 1).zfill(3)
            image_filename = f"{prefix}{page_num_str}.png"
            image_absolute_path = output_absolute_path / image_filename

            # 保存图像为PNG格式
            pix.save(str(image_absolute_path))

            # 记录相对路径（相对于输出文件夹）
            image_paths.append(image_filename)

            # 显示进度信息
            progress = (page_num + 1) / total_pages * 100
            print(f"进度: {page_num + 1}/{total_pages} ({progress:.1f}%) - 已保存: {image_filename}")

        # 关闭PDF文档
        pdf_document.close()

        print(f"转换完成！共 {total_pages} 页")
        print(f"生成的图片数量: {len(image_paths)}")

        return image_paths

    except Exception as e:
        # 捕获并处理异常
        raise ValueError(f"PDF处理失败: {str(e)}")


def get_all_images_from_folder(folder_path: str, sort_by_number: bool = True) -> List[str]:
    """
    获取文件夹中所有图片文件的相对路径（相对于该文件夹）

    参数:
        folder_path (str): 文件夹路径
        sort_by_number (bool): 是否按文件名中的数字排序（默认True）

    返回:
        List[str]: 图片文件相对路径列表
    """

    # 转换文件夹路径为绝对路径
    folder_absolute_path = ensure_absolute_path(folder_path)
    print(f"图片文件夹绝对路径: {folder_absolute_path}")

    # 验证文件夹是否存在
    if not folder_absolute_path.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_absolute_path}")

    # 支持的图片格式
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}

    # 获取所有图片文件
    image_files = []
    for file in folder_absolute_path.iterdir():
        # 检查是否为文件且为图片格式
        if file.is_file():
            ext = file.suffix.lower()
            if ext in image_extensions:
                # 只保存文件名（相对路径）
                image_files.append(file.name)

    # 排序（如果需要）
    if sort_by_number and image_files:
        # 提取文件名中的数字进行排序
        def extract_number(filename):
            # 查找文件名中的所有数字
            numbers = re.findall(r'\d+', filename)
            return int(numbers[0]) if numbers else 0

        image_files.sort(key=extract_number)

    return image_files


def get_relative_paths(image_filenames: List[str], pdf_path: str, output_folder: str = None) -> List[str]:
    """
    获取图片相对于项目根目录的路径

    参数:
        image_filenames (List[str]): 图片文件名列表
        pdf_path (str): PDF文件路径（用于确定默认输出文件夹）
        output_folder (str): 输出文件夹路径

    返回:
        List[str]: 相对于项目根目录的路径列表
    """

    # 确定输出文件夹的绝对路径
    pdf_absolute_path = ensure_absolute_path(pdf_path)
    if output_folder is None:
        pdf_parent = pdf_absolute_path.parent
        pdf_name = pdf_absolute_path.stem
        output_absolute_path = pdf_parent / f"{pdf_name}_images"
    else:
        output_absolute_path = ensure_absolute_path(output_folder)

    # 获取项目根目录
    project_root = get_project_root()

    relative_paths = []
    for image_filename in image_filenames:
        image_absolute_path = output_absolute_path / image_filename

        # 计算相对于项目根目录的路径
        try:
            relative_path = image_absolute_path.relative_to(project_root)
            # 转换为使用正斜杠的格式
            relative_path_str = '/' + str(relative_path).replace('\\', '/')
            relative_paths.append(relative_path_str)
        except ValueError:
            # 如果图片路径不在项目根目录下，使用绝对路径
            print(f"警告: 图片 {image_filename} 不在项目根目录下")
            relative_paths.append(str(image_absolute_path))

    return relative_paths


def convert_and_get_urls(pdf_path: str, output_folder: str = None,
                         zoom: float = 2.0, prefix: str = "page_") -> List[str]:
    """
    转换PDF为图片并返回可用于web访问的URL路径

    参数:
        pdf_path (str): PDF文件路径
        output_folder (str): 输出文件夹
        zoom (float): 缩放因子
        prefix (str): 文件名前缀

    返回:
        List[str]: URL路径列表
    """
    # 转换PDF为图片
    image_filenames = pdf_to_images_pymupdf(pdf_path, output_folder, zoom, prefix)

    # 获取相对于项目根目录的路径
    relative_paths = get_relative_paths(image_filenames, pdf_path, output_folder)

    return relative_paths
