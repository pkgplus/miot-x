# -*- coding: utf-8 -*-
"""MCP Server — FastMCP 入口，注册米家设备控制工具。

支持三种模式（可组合）：
    stdio       — 默认，MCP stdio 协议
    --http-port — 启动 HTTP MCP server（给 Hermes 等本地客户端）
    --xiaozhi   — 启动小智 WebSocket 桥接
"""
import asyncio
import json
import logging
import os
import sys
from typing import Optional

import websockets
from fastmcp import FastMCP
from miot.types import MIoTDeviceInfo

from .proxy import MiotProxy

_LOGGER = logging.getLogger(__name__)

# 全局代理实例
_proxy: Optional[MiotProxy] = None
# 设备缓存
_devices: dict[str, MIoTDeviceInfo] = {}

# FastMCP 实例
mcp = FastMCP(
    name="miot-skill",
    instructions="Xiaomi Mijia Smart Home MCP Server — 控制米家智能设备",
)


# ── 初始化 ────────────────────────────────────────

async def _ensure_proxy():
    global _proxy, _devices
    if _proxy is not None:
        return
    _proxy = MiotProxy()
    await _proxy.init()
    _devices = await _proxy.get_devices()
    _LOGGER.info("已连接，设备数: %d", len(_devices))


def _find_device(name_or_id: str) -> MIoTDeviceInfo | None:
    """按名称或 ID 查找设备（模糊匹配）。"""
    if not name_or_id:
        return None
    # 精确匹配 did
    if name_or_id in _devices:
        return _devices[name_or_id]
    # 模糊匹配名称
    for d in _devices.values():
        if name_or_id.lower() in d.name.lower():
            return d
    # 包含匹配 device_class
    for d in _devices.values():
        cls = d.model.split(".")[1] if "." in d.model else ""
        if name_or_id.lower() in cls.lower():
            return d
    return None


# ── 设备列表 ───────────────────────────────────────

@mcp.tool()
async def list_devices(room: str = "", refresh: bool = False) -> dict:
    """获取所有米家设备列表。

    Args:
        room: 可选，按房间名筛选。
        refresh: 强制刷新。

    Returns:
        {"total": N, "devices": [{did, name, model, online, room}, ...]}
    """
    global _devices
    await _ensure_proxy()

    if refresh:
        _devices = await _proxy.get_devices()

    # 获取房间信息
    homes = await _proxy.get_homes()
    room_map = {}
    for home in homes.values():
        for rid, rinfo in home.room_list.items():
            room_map[rid] = rinfo.room_name

    result = []
    for did, dev in _devices.items():
        dev_room = ""
        for home in homes.values():
            for rid, rinfo in home.room_list.items():
                if did in rinfo.dids:
                    dev_room = rinfo.room_name
                    break
        if room and room not in dev_room:
            continue
        result.append({
            "did": dev.did,
            "name": dev.name,
            "model": dev.model,
            "online": dev.online,
            "room": dev_room,
        })

    return {"total": len(result), "devices": result}


@mcp.tool()
async def get_device(device_name: str) -> dict:
    """获取指定设备的详细信息，含 SPEC 定义。

    Args:
        device_name: 设备名称或 did（支持模糊匹配）。
    """
    await _ensure_proxy()
    dev = _find_device(device_name)
    if not dev:
        return {"error": f"未找到设备: {device_name}"}

    # 获取 spec
    spec = None
    if _proxy._client and _proxy._client.spec_parser:
        try:
            spec_raw = await _proxy._client.spec_parser.parse_async(dev.model)
            if spec_raw:
                spec = {
                    "type": spec_raw.type,
                    "services": [
                        {
                            "iid": s.iid,
                            "name": s.description,
                            "properties": [
                                {"iid": p.iid, "name": p.description, "format": p.format,
                                 "access": p.access}
                                for p in s.properties
                            ],
                            "actions": [
                                {"iid": a.iid, "name": a.description,
                                 "in": [ai.description for ai in a.in_def]}
                                for a in s.actions
                            ],
                        }
                        for s in spec_raw.services
                    ],
                }
        except Exception:
            pass

    return {
        "did": dev.did,
        "name": dev.name,
        "model": dev.model,
        "online": dev.online,
        "lan_status": dev.lan_status,
        "local_ip": dev.local_ip,
        "spec": spec,
        "raw": dev.model_dump() if hasattr(dev, "model_dump") else {},
    }


# ── 设备控制 ───────────────────────────────────────

@mcp.tool()
async def device_on(device_name: str) -> dict:
    """打开指定设备（通用开关 siid=2, piid=1）。

    Args:
        device_name: 设备名称或 did（支持模糊匹配）。
    """
    await _ensure_proxy()
    dev = _find_device(device_name)
    if not dev:
        return {"error": f"未找到设备: {device_name}"}
    result = await _proxy.set_prop(dev.did, siid=2, piid=1, value=True)
    return {"did": dev.did, "name": dev.name, "result": result}


@mcp.tool()
async def device_off(device_name: str) -> dict:
    """关闭指定设备（通用开关 siid=2, piid=1）。

    Args:
        device_name: 设备名称或 did（支持模糊匹配）。
    """
    await _ensure_proxy()
    dev = _find_device(device_name)
    if not dev:
        return {"error": f"未找到设备: {device_name}"}
    result = await _proxy.set_prop(dev.did, siid=2, piid=1, value=False)
    return {"did": dev.did, "name": dev.name, "result": result}


@mcp.tool()
async def device_toggle(device_name: str) -> dict:
    """切换设备开关状态（先读后写）。

    Args:
        device_name: 设备名称或 did（支持模糊匹配）。
    """
    await _ensure_proxy()
    dev = _find_device(device_name)
    if not dev:
        return {"error": f"未找到设备: {device_name}"}
    current = await _proxy.get_prop(dev.did, siid=2, piid=1)
    new_val = not current if isinstance(current, bool) else True
    result = await _proxy.set_prop(dev.did, siid=2, piid=1, value=new_val)
    return {"did": dev.did, "name": dev.name, "from": current, "to": new_val, "result": result}


# ── 属性读写 ───────────────────────────────────────

@mcp.tool()
async def get_prop(device_name: str, siid: int, piid: int) -> dict:
    """读取设备属性。

    Args:
        device_name: 设备名称或 did。
        siid: 服务实例 ID。
        piid: 属性实例 ID。
    """
    await _ensure_proxy()
    dev = _find_device(device_name)
    if not dev:
        return {"error": f"未找到设备: {device_name}"}
    value = await _proxy.get_prop(dev.did, siid=siid, piid=piid)
    return {"did": dev.did, "name": dev.name, "siid": siid, "piid": piid, "value": value}


@mcp.tool()
async def set_prop(device_name: str, siid: int, piid: int, value) -> dict:
    """设置设备属性。

    Args:
        device_name: 设备名称或 did。
        siid: 服务实例 ID。
        piid: 属性实例 ID。
        value: 属性值（bool/int/float/str）。
    """
    await _ensure_proxy()
    dev = _find_device(device_name)
    if not dev:
        return {"error": f"未找到设备: {device_name}"}
    result = await _proxy.set_prop(dev.did, siid=siid, piid=piid, value=value)
    return {"did": dev.did, "name": dev.name, "siid": siid, "piid": piid, "value": value, "result": result}


@mcp.tool()
async def device_action(device_name: str, siid: int, aiid: int, in_list: list = None) -> dict:
    """执行设备动作。

    Args:
        device_name: 设备名称或 did。
        siid: 服务实例 ID。
        aiid: 动作实例 ID。
        in_list: 动作输入参数列表。
    """
    await _ensure_proxy()
    dev = _find_device(device_name)
    if not dev:
        return {"error": f"未找到设备: {device_name}"}
    result = await _proxy.action(dev.did, siid=siid, aiid=aiid, in_list=in_list)
    return {"did": dev.did, "name": dev.name, "siid": siid, "aiid": aiid, "result": result}


# ── 场景 ───────────────────────────────────────────

@mcp.tool()
async def list_scenes(refresh: bool = False) -> dict:
    """获取手动场景列表。

    Args:
        refresh: 强制刷新。
    """
    await _ensure_proxy()
    scenes = await _proxy.get_scenes()
    result = [
        {"scene_id": s.scene_id, "name": s.scene_name, "home_id": s.home_id}
        for s in scenes.values()
    ]
    return {"total": len(result), "scenes": result}


@mcp.tool()
async def execute_scene(scene_name: str) -> dict:
    """执行指定场景（按名称模糊匹配）。

    Args:
        scene_name: 场景名称（支持模糊匹配）。
    """
    await _ensure_proxy()
    scenes = await _proxy.get_scenes()
    for s in scenes.values():
        if scene_name.lower() in s.scene_name.lower():
            ok = await _proxy.run_scene(s)
            return {"scene_id": s.scene_id, "name": s.scene_name, "success": ok}
    return {"error": f"未找到场景: {scene_name}"}


# ── 服务状态 ───────────────────────────────────────

@mcp.tool()
async def get_service_status() -> dict:
    """获取 MCP 服务连接状态。"""
    try:
        await _ensure_proxy()
        return {
            "connected": True,
            "device_count": len(_devices),
            "ready": _proxy.is_ready if _proxy else False,
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


# ── 工具注册表（用于小智桥接） ─────────────────────


async def _get_tools_registry() -> dict:
    """返回 {tool_name: async_function} 映射。"""
    tools = await mcp.list_tools()
    return {t.name: t.fn for t in tools}


async def _handle_xiaozhi_message(msg_raw: str, tools_registry: dict) -> str:
    """处理来自小智 WebSocket 的 MCP JSON-RPC 消息。

    支持的方法：
        - initialize, notifications/initialized
        - tools/list
        - tools/call
    """
    try:
        msg = json.loads(msg_raw)
    except json.JSONDecodeError:
        return json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})

    req_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    if method == "initialize":
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "miot-skill", "version": "1.0.0"},
            },
        })

    if method == "notifications/initialized":
        return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}})

    if method == "tools/list":
        tools = [
            {"name": name, "description": getattr(fn, "__doc__", "") or "",
             "inputSchema": {"type": "object", "properties": {}}}
            for name, fn in tools_registry.items()
        ]
        return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}})

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        fn = tools_registry.get(tool_name)
        if not fn:
            return json.dumps({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
            })
        try:
            result = await fn(**arguments)
            return json.dumps({
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
            })
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32603, "message": str(e)},
            })

    # 未知方法
    return json.dumps({
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    })


# ── 小智 WebSocket 桥接 ────────────────────────────

async def xiaozhi_bridge():
    """连接小智平台 WebSocket，双向桥接 MCP 消息。

    环境变量:
        MCP_ENDPOINT 或 XIAOZHI_MCP_URL — 小智 WebSocket 端点
    """
    url = os.environ.get("MCP_ENDPOINT") or os.environ.get("XIAOZHI_MCP_URL")
    if not url:
        _LOGGER.warning("小智桥接: 未设置 MCP_ENDPOINT，跳过")
        return

    tools_registry = await _get_tools_registry()
    _LOGGER.info("小智桥接: 已注册 %d 个工具，连接 %s...", len(tools_registry), url[:60])

    backoff = 1
    while True:
        try:
            if backoff > 1:
                _LOGGER.info("小智桥接: 等待 %ds 后重连...", backoff)
                await asyncio.sleep(backoff)

            async with websockets.connect(url) as ws:
                _LOGGER.info("小智桥接: 已连接")
                backoff = 1
                async for raw_msg in ws:
                    if isinstance(raw_msg, bytes):
                        raw_msg = raw_msg.decode("utf-8")
                    resp = await _handle_xiaozhi_message(raw_msg, tools_registry)
                    await ws.send(resp)
        except Exception as e:
            _LOGGER.warning("小智桥接: 连接断开 (%s)，将重连...", e)
            backoff = min(backoff * 2, 600)


# ── 入口 ───────────────────────────────────────────

async def main(
    http_port: int = 0,
    http_host: str = "127.0.0.1",
    enable_xiaozhi: bool = False,
):
    """启动 MCP server。

    Args:
        http_port: HTTP MCP server 端口（0=不启动）。
        http_host: HTTP server 绑定地址。
        enable_xiaozhi: 是否启用小智 WebSocket 桥接。
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        await _ensure_proxy()
        _LOGGER.info("MCP server 启动中...")
    except Exception as e:
        _LOGGER.warning("设备连接失败（将以离线模式启动）: %s", e)

    tasks = []

    if enable_xiaozhi:
        tasks.append(xiaozhi_bridge())

    if http_port > 0:
        _LOGGER.info("HTTP MCP server: http://%s:%d", http_host, http_port)
        tasks.append(mcp.run_http_async(
            host=http_host,
            port=http_port,
            transport="http",
            show_banner=False,
        ))

    if tasks:
        await asyncio.gather(*tasks)
    else:
        # 默认 stdio 模式
        await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
