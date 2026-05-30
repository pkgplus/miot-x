# -*- coding: utf-8 -*-
"""家庭相关 API routes。"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ...lib.config import get_selected_home_ids, save_selected_home_ids
from ...lib.proxy import get_shared_proxy


async def _get_proxy_or_error():
    try:
        return await get_shared_proxy(), None
    except Exception as e:
        return None, JSONResponse({"error": f"未连接: {e}"}, status_code=503)


async def list_homes(request: Request):
    proxy, err = await _get_proxy_or_error()
    if err:
        return err
    homes = await proxy.get_homes()
    selected = get_selected_home_ids()
    result = []
    for home in homes.values():
        room_count = len(home.room_list) if home.room_list else 0
        result.append({
            "home_id": home.home_id,
            "name": home.home_name,
            "room_count": room_count,
        })
    return JSONResponse({"homes": result, "selected": selected})


async def select_homes(request: Request):
    body = await request.json()
    home_ids = body.get("home_ids")
    save_selected_home_ids(home_ids if home_ids else None)
    return JSONResponse({"success": True})


routes = [
    Route("/homes", list_homes, methods=["GET"]),
    Route("/homes/select", select_homes, methods=["POST"]),
]
