# -*- coding: utf-8 -*-
"""场景相关 API routes。"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ...lib.proxy import get_shared_proxy


async def _get_proxy_or_error():
    try:
        return await get_shared_proxy(), None
    except Exception as e:
        return None, JSONResponse({"error": f"未连接: {e}"}, status_code=503)


async def list_scenes(request: Request):
    proxy, err = await _get_proxy_or_error()
    if err:
        return err
    scenes = await proxy.get_scenes()
    result = [
        {"scene_id": s.scene_id, "name": s.scene_name, "home_id": s.home_id}
        for s in scenes.values()
    ]
    return JSONResponse({"total": len(result), "scenes": result})


async def run_scene(request: Request):
    scene_id = request.path_params["scene_id"]
    proxy, err = await _get_proxy_or_error()
    if err:
        return err
    scenes = await proxy.get_scenes()
    for s in scenes.values():
        if s.scene_id == scene_id:
            ok = await proxy.run_scene(s)
            return JSONResponse({"scene_id": s.scene_id, "name": s.scene_name, "success": ok})
    return JSONResponse({"error": f"未找到场景: {scene_id}"}, status_code=404)


routes = [
    Route("/scenes", list_scenes, methods=["GET"]),
    Route("/scenes/{scene_id}/run", run_scene, methods=["POST"]),
]
