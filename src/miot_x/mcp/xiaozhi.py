# -*- coding: utf-8 -*-
"""小智平台 WebSocket 桥接 — 将 MCP 工具暴露给小智。"""
import asyncio
import json
import logging
import os

import websockets

_LOGGER = logging.getLogger(__name__)


async def _handle_message(msg_raw: str, tools_registry: dict) -> str:
    """处理来自小智 WebSocket 的 MCP JSON-RPC 消息。"""
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
                "serverInfo": {"name": "miot-x", "version": "1.0.0"},
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

    return json.dumps({
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    })


async def xiaozhi_bridge(mcp_instance):
    """连接小智平台 WebSocket，双向桥接 MCP 消息。

    Args:
        mcp_instance: FastMCP 实例，用于获取工具注册表。
    """
    url = os.environ.get("MCP_ENDPOINT") or os.environ.get("XIAOZHI_MCP_URL")
    if not url:
        _LOGGER.warning("小智桥接: 未设置 MCP_ENDPOINT，跳过")
        return

    tools = await mcp_instance.list_tools()
    tools_registry = {t.name: t.fn for t in tools}
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
                    resp = await _handle_message(raw_msg, tools_registry)
                    await ws.send(resp)
        except Exception as e:
            _LOGGER.warning("小智桥接: 连接断开 (%s)，将重连...", e)
            backoff = min(backoff * 2, 600)
