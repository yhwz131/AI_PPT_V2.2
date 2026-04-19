import time
from typing import Callable
from fastapi import Request, Response
from sse_starlette.sse import logger
from starlette.middleware.base import BaseHTTPMiddleware


class SSEMonitorMiddleware(BaseHTTPMiddleware):
    """
    SSE监控中间件
    监控SSE连接和请求
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 记录SSE相关请求
        if "/sse/" in str(request.url):
            client_id = request.path_params.get("client_id", "unknown")
            start_time = time.time()

            try:
                response = await call_next(request)
                elapsed = time.time() - start_time

                # 记录SSE连接成功
                logger.info(f"SSE连接成功: {client_id}, 耗时: {elapsed:.2f}s")

                return response
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"SSE连接失败: {client_id}, 耗时: {elapsed:.2f}s, 错误: {e}")
                raise

        # 处理数字人生成请求
        if "/digital_character_generation" in str(request.url):
            client_id = request.headers.get("Client-ID", "unknown")
            start_time = time.time()

            try:
                response = await call_next(request)
                elapsed = time.time() - start_time

                # 记录请求处理时间
                logger.info(f"数字人生成请求: {client_id}, 耗时: {elapsed:.2f}s")

                return response
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"数字人生成请求失败: {client_id}, 耗时: {elapsed:.2f}s, 错误: {e}")
                raise

        # 其他请求正常处理
        return await call_next(request)