# -*- coding: utf-8 -*-
"""设备相关 API routes。"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ...lib.proxy import get_shared_proxy


async def _get_proxy_or_error():
    try:
        return await get_shared_proxy(), None
    except Exception as e:
        return None, JSONResponse({"error": f"未连接: {e}"}, status_code=503)


async def list_devices(request: Request):
    room = request.query_params.get("room", "")
    refresh = request.query_params.get("refresh", "").lower() == "true"
    proxy, err = await _get_proxy_or_error()
    if err:
        return err

    devices = await proxy.get_devices()
    if refresh:
        devices = await proxy.get_devices()

    homes = await proxy.get_homes()
    result = []
    for did, dev in devices.items():
        dev_room = ""
        for home in homes.values():
            if home.room_list:
                for rinfo in home.room_list.values():
                    if did in rinfo.dids:
                        dev_room = rinfo.room_name
                        break
        if room and room not in dev_room:
            continue
        result.append({
            "did": dev.did, "name": dev.name, "model": dev.model,
            "online": dev.online, "room": dev_room,
        })

    return JSONResponse({"total": len(result), "devices": result})


async def get_device(request: Request):
    did = request.path_params["did"]
    proxy, err = await _get_proxy_or_error()
    if err:
        return err
    devices = await proxy.get_devices()
    dev = devices.get(did)
    if not dev:
        return JSONResponse({"error": f"未找到设备: {did}"}, status_code=404)

    import logging
    _log = logging.getLogger(__name__)
    spec = None
    spec_parser = None
    try:
        spec_parser = proxy._client.spec_parser if proxy._client else None
    except Exception as e:
        _log.warning("spec_parser access failed: %s", e)
    if spec_parser:
        try:
            urn = dev.urn if hasattr(dev, 'urn') and dev.urn else dev.model
            _log.info("parsing spec for urn=%s", urn)
            spec_raw = await spec_parser.parse_async(urn)
            if spec_raw:
                spec = {
                    "urn": spec_raw.urn,
                    "name": spec_raw.description_trans or spec_raw.description,
                    "services": [
                        {
                            "iid": s.iid, "name": s.description_trans or s.description,
                            "properties": [
                                {
                                    "iid": p.iid,
                                    "name": p.description_trans or p.description,
                                    "format": p.format,
                                    "access": list(p.access) if p.access else [],
                                    "range": [p.value_range.min_, p.value_range.max_, p.value_range.step] if p.value_range else None,
                                    "value_list": [{"value": v.value, "description": v.description} for v in p.value_list] if p.value_list else None,
                                    "unit": p.unit,
                                }
                                for p in s.properties
                            ],
                            "actions": [
                                {"iid": a.iid, "name": a.description_trans or a.description}
                                for a in s.actions
                            ],
                        }
                        for s in spec_raw.services
                    ],
                }
        except Exception as e:
            _log.error("spec parse error: %s", e)

    # 提取子设备名称（双键开关等的通道别名）
    sub_devices = {}
    try:
        raw = dev.model_dump() if hasattr(dev, 'model_dump') else {}
        for k, v in raw.get('sub_devices', {}).items():
            sub_devices[k] = {'name': v.get('name', ''), 'did': v.get('did', '')}
    except Exception:
        pass

    return JSONResponse({
        "did": dev.did, "name": dev.name, "model": dev.model,
        "online": dev.online, "spec": spec, "sub_devices": sub_devices,
    })


async def device_on(request: Request):
    did = request.path_params["did"]
    proxy, err = await _get_proxy_or_error()
    if err:
        return err
    result = await proxy.set_prop(did, siid=2, piid=1, value=True)
    return JSONResponse({"did": did, "action": "on", "result": result})


async def device_off(request: Request):
    did = request.path_params["did"]
    proxy, err = await _get_proxy_or_error()
    if err:
        return err
    result = await proxy.set_prop(did, siid=2, piid=1, value=False)
    return JSONResponse({"did": did, "action": "off", "result": result})


async def device_prop(request: Request):
    did = request.path_params["did"]
    body = await request.json()
    siid, piid, value = body["siid"], body["piid"], body["value"]
    proxy, err = await _get_proxy_or_error()
    if err:
        return err
    result = await proxy.set_prop(did, siid=siid, piid=piid, value=value)
    return JSONResponse({"did": did, "siid": siid, "piid": piid, "value": value, "result": result})


async def device_action(request: Request):
    did = request.path_params["did"]
    body = await request.json()
    siid, aiid = body["siid"], body["aiid"]
    in_list = body.get("in_list", [])
    proxy, err = await _get_proxy_or_error()
    if err:
        return err
    result = await proxy.action(did, siid=siid, aiid=aiid, in_list=in_list)
    return JSONResponse({"did": did, "siid": siid, "aiid": aiid, "result": result})


async def get_prop_value(request: Request):
    did = request.path_params["did"]
    siid = int(request.path_params["siid"])
    piid = int(request.path_params["piid"])
    proxy, err = await _get_proxy_or_error()
    if err:
        return err
    try:
        value = await proxy.get_prop(did, siid=siid, piid=piid)
        return JSONResponse({"did": did, "siid": siid, "piid": piid, "value": value})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


routes = [
    Route("/devices", list_devices, methods=["GET"]),
    Route("/devices/{did}", get_device, methods=["GET"]),
    Route("/devices/{did}/on", device_on, methods=["POST"]),
    Route("/devices/{did}/off", device_off, methods=["POST"]),
    Route("/devices/{did}/prop", device_prop, methods=["POST"]),
    Route("/devices/{did}/prop/{siid}/{piid}", get_prop_value, methods=["GET"]),
    Route("/devices/{did}/action", device_action, methods=["POST"]),
]
