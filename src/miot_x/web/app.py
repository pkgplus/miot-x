# -*- coding: utf-8 -*-
"""Starlette 统一 Web 应用工厂 — 组合 Web UI + REST API + MCP。"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .routes import all_api_routes

_LOGGER = logging.getLogger(__name__)
_STATIC_DIR = Path(__file__).parent / "static"


_xiaozhi_connected = False


def set_xiaozhi_status(connected: bool):
    global _xiaozhi_connected
    _xiaozhi_connected = connected


async def _status(request):
    """服务状态。"""
    from ..lib.proxy import _shared_proxy
    connected = _shared_proxy is not None and _shared_proxy.is_ready
    device_count = 0
    if _shared_proxy:
        try:
            devices = await _shared_proxy.get_devices()
            device_count = len(devices)
        except Exception:
            pass
    return JSONResponse({
        "connected": connected,
        "device_count": device_count,
        "xiaozhi_connected": _xiaozhi_connected,
    })


async def _xiaozhi_with_status(mcp_instance):
    """包装小智桥接，更新连接状态。"""
    from ..mcp.xiaozhi import xiaozhi_bridge
    set_xiaozhi_status(True)
    try:
        await xiaozhi_bridge(mcp_instance)
    finally:
        set_xiaozhi_status(False)


def create_app(enable_xiaozhi: bool = False, enable_mcp: bool = True):
    """创建统一 Starlette 应用。

    Args:
        enable_xiaozhi: 是否启用小智 WebSocket 桥接。
        enable_mcp: 是否挂载 MCP endpoint。
    """

    @asynccontextmanager
    async def lifespan(app):
        _LOGGER.info("miot-x Web 服务启动中...")

        # 尝试预连接 MIoT
        try:
            from ..lib.proxy import get_shared_proxy
            await get_shared_proxy()
            _LOGGER.info("MIoT 已连接")
        except Exception as e:
            _LOGGER.warning("MIoT 连接失败（将以离线模式运行）: %s", e)

        # 启动小智桥接
        xiaozhi_task = None
        if enable_xiaozhi:
            from ..mcp.xiaozhi import xiaozhi_bridge
            from ..mcp.server import mcp as mcp_instance
            xiaozhi_task = asyncio.create_task(_xiaozhi_with_status(mcp_instance))
            _LOGGER.info("小智桥接已启动")

        yield

        if xiaozhi_task:
            xiaozhi_task.cancel()

    # API routes
    api_routes = [
        Route("/status", _status, methods=["GET"]),
        *all_api_routes(),
    ]

    # 组合所有路由
    routes = [
        Mount("/api", routes=api_routes),
    ]

    # 挂载 MCP (FastMCP streamable-http)
    if enable_mcp:
        try:
            from ..mcp.server import mcp as mcp_instance
            mcp_app = mcp_instance.http_app(path="/mcp", transport="streamable-http")
            routes.append(Mount("/mcp", app=mcp_app))
            _LOGGER.info("MCP endpoint 已挂载 (/mcp)")
        except Exception as e:
            _LOGGER.warning("MCP 挂载失败: %s", e)

    # 静态文件 (Web UI)
    if _STATIC_DIR.exists():
        routes.append(Mount("/", app=StaticFiles(directory=str(_STATIC_DIR), html=True)))

    app = Starlette(routes=routes, lifespan=lifespan)
    return app
