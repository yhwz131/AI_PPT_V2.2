import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, List, Set, Any, AsyncGenerator, Optional

from pydantic import BaseModel

from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.types import Scope, Receive, Send
from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File, Depends, BackgroundTasks, WebSocket, \
    WebSocketDisconnect
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import httpx
from urllib.parse import unquote, urlparse

# 导入配置和核心功能
from config import get_settings
from config.config import validate_ffmpeg_available
from core.dependencies import get_conversion_service
from routers import files, conversion, my_digital_human
from routers.conversion import get_file_service
from routers.files import preview
from routers.sse_monitor import SSEMonitorMiddleware
from routers.video import router_video

# 导入自定义服务
from services.cleanup_service import FileCleanupService
from services.scheduler_service import TaskScheduler
from services.conversion_service import ConversionService
from services.file_service import FileService


# ============ 首先确保必要的目录存在 ============
def ensure_directories():
    """
    确保所有必要的目录都存在
    在应用启动前创建所有需要的目录，避免运行时出现FileNotFoundError
    """
    directories = [
        "logs",  # 日志目录
        "static/css",  # CSS目录
        "static/js",  # JavaScript目录
        "templates",  # 模板目录
        "static/data",  # JSON数据目录
        "static/file/pdf",  # PDF文件目录
        "static/video/mergers",  # 合并视频目录
        "static/file/images",  # 图片目录
        "static/video/hls",  # HLS视频目录
        "static/audio",  # 音频目录
        "static/video/temp",  # 临时视频目录
        "static/swagger",  # Swagger UI静态文件目录
    ]

    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"已创建目录: {directory}")


# 在应用启动前调用目录创建函数
ensure_directories()


# ============ 自定义日志处理器（用于WebSocket推送） ============
class WebSocketLogHandler(logging.Handler):
    """
    自定义日志处理器，用于将日志推送到WebSocket连接
    继承自logging.Handler，重写emit方法实现日志的实时推送
    修改：设置处理器级别为INFO，确保只捕获INFO及以上级别的日志
    """

    def __init__(self, websocket_manager):
        """
        初始化WebSocket日志处理器

        参数:
            websocket_manager: WebSocket连接管理器实例
        """
        super().__init__()
        self.websocket_manager = websocket_manager
        # 设置日志格式
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        # 设置处理器级别为INFO，确保只捕获INFO及以上级别的日志
        self.setLevel(logging.INFO)

    def emit(self, record):
        """
        发送日志记录到所有WebSocket连接
        修改：只发送INFO及以上级别的日志，不包括DEBUG

        参数:
            record: 日志记录对象
        """
        try:
            # 只处理INFO及以上级别的日志
            if record.levelno >= logging.INFO:
                log_entry = self.format(record)
                # 异步发送到所有WebSocket连接
                asyncio.create_task(self.websocket_manager.broadcast({
                    "type": "log",
                    "timestamp": datetime.now().isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": log_entry
                }))
        except Exception:
            # 如果发送失败，调用父类的错误处理方法
            self.handleError(record)


# ============ WebSocket连接管理器 ============
class ConnectionManager:
    """
    WebSocket连接管理器
    管理所有WebSocket连接，包括连接、断开、消息发送等功能
    """

    def __init__(self):
        """
        初始化连接管理器
        """
        # 活跃的连接集合
        self.active_connections: List[WebSocket] = []
        # 连接ID计数器
        self.connection_counter = 0
        # 连接信息字典
        self.connections_info: Dict[int, Dict] = {}

    async def connect(self, websocket: WebSocket, client_info: Dict = None):
        """
        接受WebSocket连接

        参数:
            websocket: WebSocket连接对象
            client_info: 客户端信息字典

        返回:
            conn_id: 连接ID
        """
        await websocket.accept()
        self.active_connections.append(websocket)

        # 生成连接ID
        conn_id = self.connection_counter
        self.connection_counter += 1

        # 保存连接信息
        self.connections_info[conn_id] = {
            "id": conn_id,
            "websocket": websocket,
            "connected_at": datetime.now().isoformat(),
            "info": client_info or {},
            "last_activity": datetime.now().isoformat()
        }

        logger.info(f"WebSocket客户端连接: ID={conn_id}, 总数={len(self.active_connections)}")

        # 发送欢迎消息
        await self.send_personal_message({
            "type": "system",
            "message": f"连接成功! 您的连接ID: {conn_id}",
            "timestamp": datetime.now().isoformat()
        }, websocket)

        return conn_id

    def disconnect(self, websocket: WebSocket):
        """
        断开WebSocket连接

        参数:
            websocket: 要断开的WebSocket连接对象
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

            # 从连接信息中移除
            conn_id = None
            for cid, info in self.connections_info.items():
                if info["websocket"] == websocket:
                    conn_id = cid
                    break

            if conn_id is not None:
                del self.connections_info[conn_id]
                logger.info(f"WebSocket客户端断开: ID={conn_id}, 剩余={len(self.active_connections)}")

    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """
        向指定客户端发送消息

        参数:
            message: 消息字典
            websocket: 目标WebSocket连接对象
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict):
        """
        向所有客户端广播消息

        参数:
            message: 要广播的消息字典
        """
        if not self.active_connections:
            return

        # 收集断开连接的客户端
        disconnected = []

        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        # 清理断开连接的客户端
        for websocket in disconnected:
            self.disconnect(websocket)

    async def send_command_result(self, command: str, result: Dict):
        """
        发送命令执行结果到所有客户端

        参数:
            command: 命令名称
            result: 命令执行结果字典
        """
        await self.broadcast({
            "type": "command_result",
            "command": command,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })

    def get_connection_stats(self):
        """
        获取连接统计信息

        返回:
            包含连接统计信息的字典
        """
        return {
            "total_connections": len(self.active_connections),
            "connections_info": [
                {
                    "id": info["id"],
                    "connected_at": info["connected_at"],
                    "last_activity": info["last_activity"],
                    "info": info["info"]
                }
                for info in self.connections_info.values()
            ]
        }


# ============ 初始化 ============
# 创建WebSocket管理器
websocket_manager = ConnectionManager()

# 配置日志
LOG_DIR = "logs"
LOG_FILE = "file_cleanup.log"
log_file_path = Path(LOG_DIR) / LOG_FILE

# 创建主日志记录器
logger = logging.getLogger(__name__)
# 修改：设置主日志记录器为INFO级别，确保只捕获INFO及以上级别的日志
logger.setLevel(logging.INFO)

# 文件处理器 - 将日志写入文件
file_handler = logging.FileHandler(log_file_path, encoding='utf-8', mode='a')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
# 设置文件处理器级别为INFO，记录INFO及以上级别的日志
file_handler.setLevel(logging.INFO)

# 控制台处理器 - 将日志输出到控制台
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
))
# 设置控制台处理器级别为INFO，控制台只输出INFO及以上级别的日志
console_handler.setLevel(logging.INFO)

# WebSocket处理器 - 将日志推送到WebSocket连接
websocket_handler = WebSocketLogHandler(websocket_manager)

# 添加所有处理器到日志记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.addHandler(websocket_handler)

# 修改：为根日志记录器也配置处理器，确保所有模块的日志都能被捕获
root_logger = logging.getLogger()
# 设置根日志记录器为INFO级别，确保只捕获INFO及以上级别的日志
root_logger.setLevel(logging.INFO)

# 为根日志记录器添加控制台处理器
root_console_handler = logging.StreamHandler()
root_console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
# 设置根控制台处理器级别为INFO
root_console_handler.setLevel(logging.INFO)
root_logger.addHandler(root_console_handler)

# 为根日志记录器添加WebSocket处理器，确保第三方库的日志也能推送到前端
root_websocket_handler = WebSocketLogHandler(websocket_manager)
root_logger.addHandler(root_websocket_handler)

# 全局变量 - 用于在整个应用中共享服务实例
cleanup_service = None  # 文件清理服务实例
task_scheduler = None  # 定时任务调度器实例

# 获取应用配置
settings = get_settings()

# 初始化Jinja2模板引擎
templates = Jinja2Templates(directory="templates")


# ============ 全局异常处理 ============
async def exception_not_found(request, exc):
    """404异常处理函数"""
    detail = getattr(exc, 'detail', None) or "没有定义这个请求地址"
    return JSONResponse({
        "code": exc.status_code,
        "error": detail
    }, status_code=exc.status_code)


# 配置异常处理器字典
exception_handlers = {
    404: exception_not_found
}


# ============ 应用生命周期管理 ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理上下文管理器
    负责应用启动时的初始化和关闭时的清理工作

    参数:
        app: FastAPI应用实例
    """
    global cleanup_service, task_scheduler

    # ============ 应用启动时的初始化 ============
    logger.info("初始化文件清理服务和定时任务调度器...")

    try:
        # 初始化文件清理服务
        cleanup_service = FileCleanupService()
        logger.info("文件清理服务初始化完成")

        # 初始化定时任务调度器
        task_scheduler = TaskScheduler()
        logger.info("定时任务调度器初始化完成")

        # 添加每日8点的清理任务
        success = task_scheduler.add_daily_job(
            job_id="daily_file_cleanup",
            func=cleanup_service.run_cleanup,
            hour=8,
            minute=0
        )

        if success:
            logger.info("每日清理任务添加成功")

            # 启动调度器
            if task_scheduler.start():
                logger.info("服务初始化完成，定时任务已启动")
                logger.info(f"每日清理任务设置在 08:00 执行")
            else:
                logger.error("定时任务调度器启动失败")
        else:
            logger.error("添加每日清理任务失败")

    except Exception as e:
        logger.error(f"服务初始化失败: {e}", exc_info=True)
        raise

    # ============ 应用运行期间 ============
    yield

    # ============ 应用关闭时的清理 ============
    logger.info("关闭定时任务调度器...")
    try:
        if task_scheduler:
            task_scheduler.shutdown()
        logger.info("定时任务调度器已关闭")
    except Exception as e:
        logger.error(f"关闭调度器失败: {e}")

    logger.info("应用关闭完成")


# ============ 创建主应用 ============
app = FastAPI(
    title="AI数字人PPT视频讲解",
    description="基于数字人的视频讲解服务，提供PPT转视频、数字人讲解等功能",
    version=settings.__class__.__version__ if hasattr(settings.__class__, '__version__') else "1.0.0",
    # 关闭默认的Swagger UI路由（避免和自定义路由冲突）
    docs_url=None,
    # 关闭默认的ReDoc路由（可选，根据需求决定是否保留）
    redoc_url=None,
    exception_handlers=exception_handlers,  # 自定义异常处理器
    lifespan=lifespan  # 添加生命周期管理
)

# ============ CORS配置 ============
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 添加SSE监控中间件 ============
app.add_middleware(SSEMonitorMiddleware)


# ============ 自定义静态文件处理器 ============
class CORSStaticFiles(StaticFiles):
    """
    自定义静态文件处理器，添加CORS头到静态文件响应
    继承自StaticFiles，重写__call__方法以添加CORS头
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("method") == "OPTIONS":
            response = Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Max-Age": "86400",
                },
            )
            await response(scope, receive, send)
            return

        request_path = scope.get("path", "")
        is_json = request_path.endswith(".json")

        async def send_with_cors_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers[b"access-control-allow-origin"] = b"*"
                headers[b"access-control-allow-methods"] = b"GET, OPTIONS"
                headers[b"access-control-allow-headers"] = b"*"
                headers[b"access-control-expose-headers"] = b"Content-Length, Content-Range"
                if is_json:
                    headers[b"cache-control"] = b"no-cache, no-store, must-revalidate"
                    headers.pop(b"etag", None)
                message["headers"] = [(k, v) for k, v in headers.items()]
            await send(message)

        await super().__call__(scope, receive, send_with_cors_headers)


# ============ 挂载静态文件目录 ============
app.mount("/static", CORSStaticFiles(directory="static"), name="static")

# ============ 注册路由 ============
# 注册视频相关路由
app.include_router(router_video)

# 注册文件管理路由
app.include_router(files.router)

# 注册转换服务路由
app.include_router(conversion.router)

# 注册数字人相关路由
app.include_router(my_digital_human.router)


# ============ 自定义Swagger UI路由 ============
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """
    自定义Swagger UI页面

    返回:
        HTMLResponse: Swagger UI HTML页面
    """
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,  # 指向FastAPI自动生成的openapi.json
        title=f"{app.title} - Swagger UI",  # Swagger页面标题
        # 配置本地swagger资源路径
        swagger_js_url="/static/swagger/swagger-ui-bundle.min.js",
        swagger_css_url="/static/swagger/swagger-ui.min.css"
    )


# ============ 控制台监控相关路由 ============
@app.get("/console", response_class=HTMLResponse)
async def get_console_dashboard(request: Request):
    """
    控制台监控面板页面

    参数:
        request: 请求对象

    返回:
        HTMLResponse: 控制台监控面板HTML页面
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "实时控制台监控面板",
            "services_available": True,
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )


@app.get("/api/system/info")
async def get_system_info():
    """
    获取系统信息

    返回:
        JSONResponse: 包含系统信息的JSON响应
    """
    import platform
    import psutil

    try:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # 内存使用情况
        memory = psutil.virtual_memory()

        # 磁盘使用情况
        disk = psutil.disk_usage(".")

        return {
            "status": "success",
            "system": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "hostname": platform.node(),
                "processor": platform.processor(),
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": cpu_percent,
                "memory_total": memory.total,
                "memory_used": memory.used,
                "memory_percent": memory.percent,
                "disk_total": disk.total,
                "disk_used": disk.used,
                "disk_percent": disk.percent,
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取系统信息失败: {str(e)}"
        }


@app.get("/api/connections")
async def get_connections():
    """
    获取WebSocket连接信息

    返回:
        JSONResponse: 包含连接信息的JSON响应
    """
    return {
        "status": "success",
        "connections": websocket_manager.get_connection_stats(),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/logs/recent")
async def get_recent_logs(limit: int = 100):
    """
    获取最近的日志

    参数:
        limit: 返回的日志行数限制

    返回:
        JSONResponse: 包含日志的JSON响应
    """
    try:
        log_lines = []
        if log_file_path.exists():
            with open(log_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-limit:]  # 获取最后limit行
                for line in lines:
                    log_lines.append(line.strip())

        return {
            "status": "success",
            "logs": log_lines,
            "count": len(log_lines),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"读取日志失败: {str(e)}"
        }


@app.post("/api/commands/test-log")
async def test_log(message: str = "测试日志消息", level: str = "INFO"):
    """
    测试日志功能
    修改：只测试INFO及以上级别的日志，不测试DEBUG级别

    参数:
        message: 日志消息内容
        level: 日志级别

    返回:
        JSONResponse: 操作结果
    """
    log_levels = {
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    level_num = log_levels.get(level.upper(), logging.INFO)

    # 记录不同级别的日志
    if level_num == logging.INFO:
        logger.info(f"测试INFO日志: {message}")
    elif level_num == logging.WARNING:
        logger.warning(f"测试WARNING日志: {message}")
    elif level_num == logging.ERROR:
        logger.error(f"测试ERROR日志: {message}")
    elif level_num == logging.CRITICAL:
        logger.critical(f"测试CRITICAL日志: {message}")

    # 测试根日志记录器的输出
    root_logger = logging.getLogger()
    root_logger.log(level_num, f"测试根日志记录器 {level} 日志: {message}")

    return {
        "status": "success",
        "message": f"测试日志已发送，级别: {level}",
        "timestamp": datetime.now().isoformat()
    }


# ============ WebSocket路由 ============
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket端点，处理实时通信

    参数:
        websocket: WebSocket连接对象
    """
    # 连接客户端
    conn_id = await websocket_manager.connect(websocket, {
        "client": websocket.client.host if websocket.client else "unknown",
        "user_agent": websocket.headers.get("user-agent", "unknown")
    })

    try:
        # 保持连接并接收消息
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()

            # 更新最后活动时间
            if conn_id in websocket_manager.connections_info:
                websocket_manager.connections_info[conn_id]["last_activity"] = datetime.now().isoformat()

            # 处理不同类型的消息
            message_type = data.get("type", "")

            if message_type == "ping":
                # 心跳检测
                await websocket_manager.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

            elif message_type == "command":
                # 执行命令
                command = data.get("command", "")
                if command == "get_stats":
                    # 获取系统统计
                    import psutil
                    stats = {
                        "cpu": psutil.cpu_percent(),
                        "memory": psutil.virtual_memory().percent,
                        "connections": websocket_manager.get_connection_stats()
                    }

                    await websocket_manager.send_personal_message({
                        "type": "stats",
                        "stats": stats,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)

            # 记录客户端活动
            logger.info(f"WebSocket客户端 {conn_id} 活动: {data}")

    except WebSocketDisconnect:
        # 客户端断开连接
        websocket_manager.disconnect(websocket)
    except Exception as e:
        # 其他异常
        logger.error(f"WebSocket错误: {e}")
        websocket_manager.disconnect(websocket)


# ============ 应用启动事件 ============
@app.on_event("startup")
async def startup_event():
    """
    应用启动事件处理函数
    在应用启动后执行，用于初始化额外的服务和验证
    """
    logger.info("视频转换服务启动中...")
    logger.info(f"服务地址: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"上传目录: {settings.upload_folder_absolute}")
    logger.info(f"转换目录: {settings.converted_folder_absolute}")

    # 验证FFmpeg是否可用
    if validate_ffmpeg_available():
        logger.info("FFmpeg验证成功")
    else:
        logger.warning("FFmpeg未找到，请确保已安装FFmpeg")

    # 记录所有级别的测试日志（不包括DEBUG），验证日志系统正常工作
    logger.info("测试INFO级别日志输出")
    logger.warning("测试WARNING级别日志输出")
    logger.error("测试ERROR级别日志输出")
    logger.critical("测试CRITICAL级别日志输出")

    logger.info("控制台监控面板已启用，访问地址: /console")
    logger.info("日志级别: INFO及以上级别 - INFO, WARNING, ERROR, CRITICAL")


# ============ 清理服务相关路由 ============
@app.get("/")
async def root():
    """
    根路径，返回服务状态

    返回:
        JSONResponse: 服务状态信息
    """
    return {
        "service": "AI数字人PPT视频讲解",
        "status": "运行中",
        "description": "基于数字人的视频讲解服务",
        "console": "/console",
        "docs": "/docs",
        "cleanup_service": "已启用",
        "log_level": "INFO及以上级别 (INFO, WARNING, ERROR, CRITICAL)",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/cleanup/run")
async def run_cleanup_now(background_tasks: BackgroundTasks):
    """
    立即执行文件清理任务（异步）

    参数:
        background_tasks: FastAPI后台任务管理器

    返回:
        JSONResponse: 操作结果
    """
    if not cleanup_service:
        raise HTTPException(status_code=500, detail="清理服务未初始化")

    async def cleanup_task():
        """
        后台清理任务函数
        """
        try:
            logger.info("手动触发清理任务开始...")
            result = cleanup_service.run_cleanup()
            logger.info(f"手动触发清理任务完成: {result}")

            # 通过WebSocket发送结果到所有客户端
            await websocket_manager.send_command_result("cleanup", result)
        except Exception as e:
            logger.error(f"手动清理任务执行失败: {e}", exc_info=True)

    # 将清理任务添加到后台执行
    background_tasks.add_task(cleanup_task)

    return {
        "status": "success",
        "message": "文件清理任务已在后台启动",
        "next_step": "请查看日志文件获取清理结果",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/cleanup/run-sync")
async def run_cleanup_sync():
    """
    同步执行文件清理任务（立即返回结果）

    返回:
        JSONResponse: 清理任务执行结果
    """
    if not cleanup_service:
        raise HTTPException(status_code=500, detail="清理服务未初始化")

    try:
        logger.info("同步执行清理任务开始...")
        result = cleanup_service.run_cleanup()
        logger.info("同步执行清理任务完成")
        return result
    except Exception as e:
        logger.error(f"执行清理任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清理任务执行失败: {str(e)}")


@app.get("/api/scheduler/jobs")
async def get_scheduled_jobs():
    """
    获取所有定时任务信息

    返回:
        JSONResponse: 包含定时任务信息的JSON响应
    """
    if not task_scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")

    jobs = task_scheduler.list_jobs()
    logger.info(f"获取定时任务列表: {len(jobs)} 个任务")
    return {
        "total": len(jobs),
        "jobs": jobs,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/scheduler/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    """
    暂停指定定时任务

    参数:
        job_id: 任务ID

    返回:
        JSONResponse: 操作结果
    """
    if not task_scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")

    success = task_scheduler.pause_job(job_id)

    if success:
        logger.info(f"定时任务 {job_id} 已暂停")
        return {"status": "success", "message": f"任务 {job_id} 已暂停"}
    else:
        logger.warning(f"暂停定时任务 {job_id} 失败: 任务不存在")
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在或暂停失败")


@app.post("/api/scheduler/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """
    恢复指定定时任务

    参数:
        job_id: 任务ID

    返回:
        JSONResponse: 操作结果
    """
    if not task_scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")

    success = task_scheduler.resume_job(job_id)

    if success:
        logger.info(f"定时任务 {job_id} 已恢复")
        return {"status": "success", "message": f"任务 {job_id} 已恢复"}
    else:
        logger.warning(f"恢复定时任务 {job_id} 失败: 任务不存在")
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在或恢复失败")


@app.delete("/api/scheduler/jobs/{job_id}")
async def remove_job(job_id: str):
    """
    移除指定定时任务

    参数:
        job_id: 任务ID

    返回:
        JSONResponse: 操作结果
    """
    if not task_scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")

    success = task_scheduler.remove_job(job_id)

    if success:
        logger.info(f"定时任务 {job_id} 已移除")
        return {"status": "success", "message": f"任务 {job_id} 已移除"}
    else:
        logger.warning(f"移除定时任务 {job_id} 失败: 任务不存在")
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在或移除失败")


@app.post("/api/scheduler/jobs/daily-cleanup")
async def add_daily_cleanup_job(hour: int = 8, minute: int = 0):
    """
    添加或更新每日清理任务

    参数:
        hour: 执行小时 (0-23)
        minute: 执行分钟 (0-59)

    返回:
        JSONResponse: 操作结果
    """
    if not task_scheduler or not cleanup_service:
        raise HTTPException(status_code=500, detail="服务未初始化")

    # 验证时间参数
    if hour < 0 or hour > 23:
        logger.warning(f"无效的小时参数: {hour}")
        raise HTTPException(status_code=400, detail="hour 参数必须在 0-23 之间")
    if minute < 0 or minute > 59:
        logger.warning(f"无效的分钟参数: {minute}")
        raise HTTPException(status_code=400, detail="minute 参数必须在 0-59 之间")

    # 添加每日任务
    success = task_scheduler.add_daily_job(
        job_id="daily_file_cleanup",
        func=cleanup_service.run_cleanup,
        hour=hour,
        minute=minute
    )

    if success:
        logger.info(f"已更新每日清理任务执行时间: {hour:02d}:{minute:02d}")
        return {
            "status": "success",
            "message": f"每日清理任务已设置为 {hour:02d}:{minute:02d} 执行",
            "timestamp": datetime.now().isoformat()
        }
    else:
        logger.error("添加定时任务失败")
        raise HTTPException(status_code=500, detail="添加定时任务失败")


@app.get("/api/health")
async def health_check():
    """
    健康检查接口

    返回:
        JSONResponse: 服务健康状态
    """
    logger.info("健康检查请求")
    status = {
        "service": "running",
        "cleanup_service": "initialized" if cleanup_service else "not_initialized",
        "scheduler": "running" if task_scheduler and task_scheduler.scheduler.running else "stopped",
        "scheduled_jobs": len(task_scheduler.list_jobs()) if task_scheduler else 0,
        "websocket_connections": len(websocket_manager.active_connections),
        "log_level": "INFO及以上级别 (INFO, WARNING, ERROR, CRITICAL)",
        "timestamp": datetime.now().isoformat()
    }

    return JSONResponse(content=status)


# ============ GPU 监控 API ============
@app.get("/api/system/gpu")
async def get_gpu_info():
    """获取 GPU 信息及进程列表（通过 nvidia-smi）"""
    import subprocess
    try:
        # 查询 GPU 基础指标
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return {"status": "error", "message": "nvidia-smi 执行失败", "gpus": []}

        # 查询 GPU uuid → index 映射
        uuid_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        uuid_to_idx = {}
        for line in uuid_result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 2:
                uuid_to_idx[parts[1]] = int(parts[0])

        # 查询各 GPU 上的进程
        proc_result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        procs_by_gpu: dict = {}
        for line in proc_result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpu_uuid = parts[0]
                gpu_idx = uuid_to_idx.get(gpu_uuid)
                if gpu_idx is None:
                    continue
                procs_by_gpu.setdefault(gpu_idx, []).append({
                    "pid": int(parts[1]),
                    "name": parts[2],
                    "memory_used": int(parts[3]) if parts[3].isdigit() else 0,
                })

        gpus = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                idx = int(parts[0])
                gpus.append({
                    "index": idx,
                    "name": parts[1],
                    "memory_total": int(parts[2]),
                    "memory_used": int(parts[3]),
                    "memory_free": int(parts[4]),
                    "utilization": int(parts[5]),
                    "temperature": int(parts[6]),
                    "processes": procs_by_gpu.get(idx, []),
                })
        return {"status": "success", "gpus": gpus}
    except FileNotFoundError:
        return {"status": "error", "message": "nvidia-smi 未安装", "gpus": []}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "nvidia-smi 超时", "gpus": []}
    except Exception as e:
        return {"status": "error", "message": str(e), "gpus": []}


# ============ 服务状态 API ============
@app.get("/api/system/services")
async def get_services_status():
    """检查各微服务端口是否可达"""
    import socket

    services = [
        {"name": "PaddleOCR", "port": 8802},
        {"name": "IndexTTS", "port": 6006},
        {"name": "Wav2Lip", "port": 5000},
        {"name": "DigitalHuman", "port": 9088},
    ]

    results = []
    for svc in services:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            err = sock.connect_ex(("127.0.0.1", svc["port"]))
            sock.close()
            results.append({**svc, "status": "running" if err == 0 else "stopped"})
        except Exception:
            results.append({**svc, "status": "stopped"})

    return {"status": "success", "services": results}


# ============ 管理员认证 ============
ADMIN_USERNAME = "root"
ADMIN_PASSWORD = "toor"
admin_tokens: Set[str] = set()


def verify_admin_token(request: Request):
    """验证管理员 token"""
    token = request.headers.get("X-Admin-Token", "")
    if token not in admin_tokens:
        raise HTTPException(status_code=401, detail="未授权，请先登录管理控制台")


# ============ 日志文件读取 API ============
LOG_FILE_MAP = {
    "digital": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "digital.log"),
    "tts": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "tts.log"),
    "wav2lip": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "wav2lip.log"),
    "paddleocr": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "paddleocr.log"),
    "cleanup": os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "file_cleanup.log"),
}


@app.get("/api/admin/logs/{service_name}")
async def get_service_logs(service_name: str, request: Request, lines: int = 100):
    """读取指定服务的日志文件尾部（需管理员认证）"""
    verify_admin_token(request)

    if service_name not in LOG_FILE_MAP:
        raise HTTPException(status_code=404, detail=f"未知服务: {service_name}，可选: {', '.join(LOG_FILE_MAP.keys())}")

    log_path = LOG_FILE_MAP[service_name]
    if not os.path.exists(log_path):
        return {"status": "success", "service": service_name, "lines": [], "total": 0}

    try:
        from collections import deque
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            tail = deque(f, maxlen=min(lines, 1000))
        return {"status": "success", "service": service_name, "lines": list(tail), "total": len(tail)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")


# ============ 服务启停 API ============
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "start_all.sh")
SERVICE_NAMES = {"paddleocr", "tts", "wav2lip", "digital"}
ALLOWED_ACTIONS = {"start", "stop", "restart"}


@app.post("/api/admin/services/{action}")
async def control_service(action: str, request: Request):
    """启停微服务（需管理员认证）"""
    verify_admin_token(request)

    body = await request.json()
    service = body.get("service", "")

    if action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"无效操作: {action}，可选: start, stop, restart")
    if service not in SERVICE_NAMES:
        raise HTTPException(status_code=400, detail=f"未知服务: {service}，可选: {', '.join(SERVICE_NAMES)}")

    # digital 服务只允许 restart
    if service == "digital" and action != "restart":
        raise HTTPException(status_code=400, detail="DigitalHuman 服务仅允许重启操作，不能单独启动或停止")

    if not os.path.exists(SCRIPT_PATH):
        raise HTTPException(status_code=500, detail="启动脚本不存在")

    import subprocess, re

    # digital restart 需要特殊处理：当前进程会被 stop 杀掉，
    # 所以必须用 detached 进程执行，先返回响应再被杀
    if service == "digital" and action == "restart":
        logger.info("管理员重启 DigitalHuman 服务（detached）")
        subprocess.Popen(
            ["bash", "-c", f"sleep 1 && bash {SCRIPT_PATH} restart digital"],
            stdout=open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "digital_restart.log"), "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "TERM": "dumb"}
        )
        return {"status": "success", "message": "DigitalHuman 正在重启，页面将在数秒后恢复"}

    try:
        logger.info(f"管理员执行服务操作: {action} {service}")
        result = subprocess.run(
            ["bash", SCRIPT_PATH, action, service],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "TERM": "dumb"}
        )
        clean_output = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout + result.stderr)

        if result.returncode == 0:
            logger.info(f"服务操作成功: {action} {service}")
            return {"status": "success", "message": f"{service} {action} 成功", "output": clean_output.strip()}
        else:
            logger.error(f"服务操作失败: {action} {service}, exit={result.returncode}")
            return {"status": "error", "message": f"{service} {action} 失败 (exit {result.returncode})", "output": clean_output.strip()}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="操作超时 (120s)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


# ============ 管理员 API ============
@app.post("/api/admin/login")
async def admin_login(request: Request):
    """管理员登录"""
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        import secrets
        token = secrets.token_hex(16)
        admin_tokens.add(token)
        logger.info(f"管理员登录成功")
        return {"status": "success", "token": token}
    else:
        logger.warning(f"管理员登录失败: {username}")
        raise HTTPException(status_code=401, detail="用户名或密码错误")


def _resolve_path(p: str, base_dir: str) -> str:
    """把 JSON 里的相对路径转为绝对路径"""
    if not p:
        return ""
    return p if os.path.isabs(p) else os.path.join(base_dir, p.lstrip("/"))


def _job_uuid_from_item(item: Dict[str, Any]) -> str:
    """从 pdf_path 或 m3u8_url 提取任务 UUID，用于定位 images 目录。"""
    pdf = item.get("pdf_path") or ""
    if pdf:
        return os.path.splitext(os.path.basename(pdf))[0]
    m3u8 = (item.get("m3u8_url") or "").replace("\\", "/")
    parts = [x for x in m3u8.split("/") if x]
    try:
        i = parts.index("hls")
        if i + 1 < len(parts):
            return parts[i + 1]
    except ValueError:
        pass
    return ""


def _collect_paths_for_item(item: Dict[str, Any], base_dir: str) -> List[str]:
    """收集一条记录关联的所有磁盘路径。"""
    paths: List[str] = []
    for key in ("pdf_path", "video_path"):
        v = item.get(key, "")
        if v:
            paths.append(_resolve_path(v, base_dir))
    m3u8 = item.get("m3u8_url", "")
    if m3u8:
        paths.append(os.path.dirname(_resolve_path(m3u8, base_dir)))
    od = item.get("output_dir", "")
    if od:
        paths.append(_resolve_path(od, base_dir))
    job_uuid = _job_uuid_from_item(item)
    if job_uuid:
        paths.append(os.path.join(base_dir, "static", "file", "images", job_uuid))
    return paths


def _paths_still_referenced(
    candidate_paths: List[str],
    remaining_items: List[Dict[str, Any]],
    base_dir: str,
) -> set:
    """返回 candidate_paths 中仍被 remaining_items 引用的绝对路径集合。"""
    ref_set: set = set()
    for it in remaining_items:
        for p in _collect_paths_for_item(it, base_dir):
            rp = os.path.normpath(p)
            ref_set.add(rp)
    return {os.path.normpath(p) for p in candidate_paths if os.path.normpath(p) in ref_set}


def _delete_paths_on_disk(paths: List[str], skip: set = None) -> List[str]:
    import shutil
    deleted: List[str] = []
    skip = skip or set()
    for p in paths:
        if not p or not os.path.exists(p):
            continue
        if os.path.normpath(p) in skip:
            logger.info(f"跳过删除（仍被其它记录引用）: {p}")
            continue
        try:
            if os.path.isfile(p):
                os.remove(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)
            deleted.append(p)
        except Exception as e:
            logger.error(f"删除文件失败 {p}: {e}")
    return deleted


class AdminDeleteVideoBody(BaseModel):
    """用 index 定位要删除的记录，pdf_path 做校验防止并发竞态。"""
    index: int
    pdf_path: Optional[str] = None
    file_name: Optional[str] = None


@app.get("/api/admin/videos")
async def admin_list_videos(request: Request):
    """获取视频列表（管理员），每条记录带 index 标识"""
    verify_admin_token(request)

    json_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static", "data", "basic_information.json"
    )
    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            videos = data.get("data", [])
        else:
            videos = []
        enriched = [{**v, "_index": i} for i, v in enumerate(videos)]
        return {"status": "success", "count": len(enriched), "videos": enriched}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取视频列表失败: {str(e)}")


@app.post("/api/admin/videos/delete")
async def admin_delete_video(body: AdminDeleteVideoBody, request: Request):
    """按 index 删除单条记录；pdf_path / file_name 做二次校验防止并发竞态。
    删文件前检查该路径是否仍被其它记录引用，若有则跳过。"""
    verify_admin_token(request)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "static", "data", "basic_information.json")

    try:
        from services.json_info_service import JsonDataManager
        json_manager = JsonDataManager(json_path)
        data_list = json_manager.data.get("data", [])

        idx = body.index
        if idx < 0 or idx >= len(data_list):
            raise HTTPException(status_code=404, detail=f"索引 {idx} 超出范围（共 {len(data_list)} 条），请刷新列表重试")

        item = data_list[idx]

        if body.pdf_path:
            expected = (body.pdf_path or "").replace("\\", "/").strip().strip("/")
            actual = (item.get("pdf_path") or "").replace("\\", "/").strip().strip("/")
            if expected and actual and expected != actual:
                raise HTTPException(status_code=409, detail="pdf_path 与记录不匹配，列表可能已变动，请刷新后重试")

        if body.file_name and item.get("file_name") != body.file_name:
            raise HTTPException(status_code=409, detail="file_name 与记录不匹配，列表可能已变动，请刷新后重试")

        candidate_paths = _collect_paths_for_item(item, base_dir)

        remaining = data_list[:idx] + data_list[idx + 1:]
        still_used = _paths_still_referenced(candidate_paths, remaining, base_dir)

        deleted_files = _delete_paths_on_disk(candidate_paths, skip=still_used)

        del data_list[idx]
        json_manager.data["data"] = data_list
        json_manager._save_json()

        label = item.get("file_name") or f"index={idx}"
        skipped = len(still_used)
        msg = f"已删除记录「{label}」，清理 {len(deleted_files)} 个路径"
        if skipped:
            msg += f"，跳过 {skipped} 个仍被引用的路径"
        logger.info(f"管理员删除: index={idx}, {label!r}, 删除={len(deleted_files)}, 跳过={skipped}")
        return {
            "status": "success",
            "message": msg,
            "deleted_files": deleted_files,
            "skipped_files": list(still_used),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除视频失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除视频失败: {str(e)}")


# ============ 全局错误处理 ============
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    全局异常处理器

    参数:
        request: 请求对象
        exc: 异常对象

    返回:
        JSONResponse: 错误响应
    """
    logger.error(f"全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "服务器内部错误",
            "detail": str(exc)
        }
    )


# ============ 获取日志级别配置 ============
@app.get("/api/logs/level")
async def get_log_level():
    """
    获取当前日志级别配置

    返回:
        JSONResponse: 日志级别配置信息
    """
    levels = {
        "root_logger": root_logger.getEffectiveLevel(),
        "main_logger": logger.getEffectiveLevel(),
        "file_handler": file_handler.level,
        "console_handler": console_handler.level,
        "websocket_handler": websocket_handler.level
    }

    # 将数字级别转换为名称
    level_names = {}
    for key, level in levels.items():
        level_names[key] = logging.getLevelName(level)

    return {
        "status": "success",
        "levels": level_names,
        "timestamp": datetime.now().isoformat()
    }


# ============ 设置日志级别 ============
@app.post("/api/logs/level/{level_name}")
async def set_log_level(level_name: str):
    """
    设置日志级别

    参数:
        level_name: 日志级别名称 (INFO, WARNING, ERROR, CRITICAL)

    返回:
        JSONResponse: 操作结果
    """
    level_mapping = {
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    if level_name.upper() not in level_mapping:
        logger.warning(f"无效的日志级别: {level_name}")
        raise HTTPException(status_code=400, detail="无效的日志级别，必须是: INFO, WARNING, ERROR, CRITICAL")

    new_level = level_mapping[level_name.upper()]

    # 设置所有记录器和处理器的级别
    root_logger.setLevel(new_level)
    logger.setLevel(new_level)
    file_handler.setLevel(new_level)
    console_handler.setLevel(new_level)
    websocket_handler.setLevel(new_level)

    logger.info(f"日志级别已设置为: {level_name}")

    return {
        "status": "success",
        "message": f"日志级别已设置为 {level_name}",
        "timestamp": datetime.now().isoformat()
    }


# ============ 应用启动 ============
if __name__ == "__main__":
    """
    应用主入口
    当直接运行此脚本时启动FastAPI应用
    """
    import uvicorn

    # 显示启动信息横幅
    logger.info("=" * 60)
    logger.info("启动AI数字人PPT视频讲解服务...")
    logger.info(f"访问地址: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"控制台面板: http://{settings.HOST}:{settings.PORT}/console")
    logger.info(f"API文档: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info(f"日志文件: {log_file_path.absolute()}")
    logger.info(f"日志级别: INFO及以上级别 (INFO, WARNING, ERROR, CRITICAL)")
    logger.info("=" * 60)

    # 启动FastAPI应用
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1,
        log_level="info",  # 设置为info级别，确保只输出INFO及以上级别的日志
        http="h11",  # 强制使用HTTP/1.1，避免h2协议的Content-Length校验
    )