from config.config import get_settings
from services.conversion_service import ConversionService

# 全局任务存储
conversion_tasks = {}


def get_conversion_service():
    # 调用 get_settings() 函数获取 Settings 实例
    settings_instance = get_settings()  # 注意：这里必须加括号！

    # 添加调试信息
    print(f"get_conversion_service: settings_instance 类型 = {type(settings_instance)}")

    # 创建 ConversionService 实例
    service = ConversionService(settings_instance, conversion_tasks)
    return service