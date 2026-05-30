# -*- coding: utf-8 -*-
"""认证相关 API routes。"""
import asyncio
import json
import logging
import time

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ...lib.auth import MIoTAuth
from ...lib.config import AUTH_FILE
from ...lib.proxy import reset_shared_proxy
from ..oauth_callback import start_callback_server, stop_callback_server

_LOGGER = logging.getLogger(__name__)

_callback_state = {
    "future": None,
    "runner": None,
}


async def auth_status(request: Request):
    """获取登录状态。"""
    if not AUTH_FILE.exists():
        return JSONResponse({"logged_in": False})
    try:
        data = json.loads(AUTH_FILE.read_text())
        expires_ts = data.get("expires_ts", 0)
        logged_in = bool(data.get("access_token")) and expires_ts > time.time()
        return JSONResponse({"logged_in": logged_in, "expires_ts": expires_ts})
    except Exception:
        return JSONResponse({"logged_in": False})


async def auth_start(request: Request):
    """启动 OAuth 登录流程。"""
    auth = MIoTAuth()
    auth_url, state = await auth.gen_oauth_url()

    # 尝试启动 :443 回调服务器
    code_future, runner = await start_callback_server()
    _callback_state["future"] = code_future
    _callback_state["runner"] = runner

    auto_callback = code_future is not None

    if auto_callback:
        asyncio.create_task(_wait_and_exchange(auth, code_future, runner))

    return JSONResponse({
        "auth_url": auth_url,
        "auto_callback": auto_callback,
    })


async def _wait_and_exchange(auth: MIoTAuth, code_future: asyncio.Future, runner):
    """等待回调 code 并换取 token。"""
    try:
        code = await asyncio.wait_for(code_future, timeout=120)
        await auth.exchange_code(code)
        await reset_shared_proxy()
        _LOGGER.info("OAuth 登录成功（自动回调）")
    except asyncio.TimeoutError:
        _LOGGER.warning("OAuth 回调超时")
    except Exception as e:
        _LOGGER.error("OAuth token 交换失败: %s", e)
    finally:
        await stop_callback_server(runner)
        _callback_state["future"] = None
        _callback_state["runner"] = None


async def auth_callback(request: Request):
    """手动提交 OAuth code（fallback 模式）。"""
    body = await request.json()
    code = body.get("code", "").strip()
    if not code:
        return JSONResponse({"success": False, "error": "missing code"}, status_code=400)

    try:
        auth = MIoTAuth()
        await auth.gen_oauth_url()
        await auth.exchange_code(code)
        await reset_shared_proxy()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def auth_logout(request: Request):
    """登出（清除 token）。"""
    MIoTAuth.clear()
    return JSONResponse({"success": True})


routes = [
    Route("/auth/status", auth_status, methods=["GET"]),
    Route("/auth/start", auth_start, methods=["POST"]),
    Route("/auth/callback", auth_callback, methods=["POST"]),
    Route("/auth/logout", auth_logout, methods=["POST"]),
]
