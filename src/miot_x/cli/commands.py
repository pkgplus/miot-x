# -*- coding: utf-8 -*-
"""miot-x CLI — 供 Agent 通过 Bash 调用的设备控制命令。

用法:
    python -m miot_x devices [--room ROOM] [--refresh]
    python -m miot_x device <name>
    python -m miot_x on <name>
    python -m miot_x off <name>
    python -m miot_x toggle <name>
    python -m miot_x get <name> <siid> <piid>
    python -m miot_x set <name> <siid> <piid> <value>
    python -m miot_x action <name> <siid> <aiid> [--args ARG1,ARG2,...]
    python -m miot_x scenes
    python -m miot_x scene <name>
    python -m miot_x status
"""
import argparse
import asyncio
import json
import sys

from ..lib.proxy import MiotProxy


async def _get_proxy():
    proxy = MiotProxy()
    await proxy.init()
    return proxy


def _json_out(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


async def cmd_devices(args):
    proxy = await _get_proxy()
    devices = await proxy.get_devices()
    homes = await proxy.get_homes()

    room_map = {}
    device_rooms = {}
    for home in homes.values():
        for rid, rinfo in home.room_list.items():
            room_map[rid] = rinfo.room_name
            for did in rinfo.dids:
                device_rooms[did] = rinfo.room_name

    result = []
    for did, dev in devices.items():
        dev_room = device_rooms.get(did, "")
        if args.room and args.room not in dev_room:
            continue
        result.append({
            "did": dev.did,
            "name": dev.name,
            "model": dev.model,
            "online": dev.online,
            "room": dev_room,
        })

    _json_out({"total": len(result), "devices": result})
    await proxy.deinit()


async def cmd_device(args):
    proxy = await _get_proxy()
    devices = await proxy.get_devices()
    dev = _find_device(devices, args.name)
    if not dev:
        _json_out({"error": f"未找到设备: {args.name}"})
        await proxy.deinit()
        return

    spec = None
    if proxy._client and proxy._client.spec_parser:
        try:
            spec_raw = await proxy._client.spec_parser.parse_async(dev.model)
            if spec_raw:
                spec = {
                    "type": spec_raw.type,
                    "services": [
                        {
                            "iid": s.iid,
                            "name": s.description,
                            "properties": [
                                {"iid": p.iid, "name": p.description, "format": p.format, "access": p.access}
                                for p in s.properties
                            ],
                            "actions": [
                                {"iid": a.iid, "name": a.description, "in": [ai.description for ai in a.in_def]}
                                for a in s.actions
                            ],
                        }
                        for s in spec_raw.services
                    ],
                }
        except Exception:
            pass

    _json_out({
        "did": dev.did,
        "name": dev.name,
        "model": dev.model,
        "online": dev.online,
        "spec": spec,
    })
    await proxy.deinit()


async def cmd_on(args):
    proxy = await _get_proxy()
    devices = await proxy.get_devices()
    dev = _find_device(devices, args.name)
    if not dev:
        _json_out({"error": f"未找到设备: {args.name}"})
        await proxy.deinit()
        return
    result = await proxy.set_prop(dev.did, siid=2, piid=1, value=True)
    _json_out({"did": dev.did, "name": dev.name, "action": "on", "result": result})
    await proxy.deinit()


async def cmd_off(args):
    proxy = await _get_proxy()
    devices = await proxy.get_devices()
    dev = _find_device(devices, args.name)
    if not dev:
        _json_out({"error": f"未找到设备: {args.name}"})
        await proxy.deinit()
        return
    result = await proxy.set_prop(dev.did, siid=2, piid=1, value=False)
    _json_out({"did": dev.did, "name": dev.name, "action": "off", "result": result})
    await proxy.deinit()


async def cmd_toggle(args):
    proxy = await _get_proxy()
    devices = await proxy.get_devices()
    dev = _find_device(devices, args.name)
    if not dev:
        _json_out({"error": f"未找到设备: {args.name}"})
        await proxy.deinit()
        return
    current = await proxy.get_prop(dev.did, siid=2, piid=1)
    new_val = not current if isinstance(current, bool) else True
    result = await proxy.set_prop(dev.did, siid=2, piid=1, value=new_val)
    _json_out({"did": dev.did, "name": dev.name, "from": current, "to": new_val, "result": result})
    await proxy.deinit()


async def cmd_get_prop(args):
    proxy = await _get_proxy()
    devices = await proxy.get_devices()
    dev = _find_device(devices, args.name)
    if not dev:
        _json_out({"error": f"未找到设备: {args.name}"})
        await proxy.deinit()
        return
    value = await proxy.get_prop(dev.did, siid=args.siid, piid=args.piid)
    _json_out({"did": dev.did, "name": dev.name, "siid": args.siid, "piid": args.piid, "value": value})
    await proxy.deinit()


async def cmd_set_prop(args):
    proxy = await _get_proxy()
    devices = await proxy.get_devices()
    dev = _find_device(devices, args.name)
    if not dev:
        _json_out({"error": f"未找到设备: {args.name}"})
        await proxy.deinit()
        return
    value = _parse_value(args.value)
    result = await proxy.set_prop(dev.did, siid=args.siid, piid=args.piid, value=value)
    _json_out({"did": dev.did, "name": dev.name, "siid": args.siid, "piid": args.piid, "value": value, "result": result})
    await proxy.deinit()


async def cmd_action(args):
    proxy = await _get_proxy()
    devices = await proxy.get_devices()
    dev = _find_device(devices, args.name)
    if not dev:
        _json_out({"error": f"未找到设备: {args.name}"})
        await proxy.deinit()
        return
    in_list = [_parse_value(v) for v in args.args.split(",")] if args.args else []
    result = await proxy.action(dev.did, siid=args.siid, aiid=args.aiid, in_list=in_list)
    _json_out({"did": dev.did, "name": dev.name, "siid": args.siid, "aiid": args.aiid, "result": result})
    await proxy.deinit()


async def cmd_scenes(args):
    proxy = await _get_proxy()
    scenes = await proxy.get_scenes()
    result = [
        {"scene_id": s.scene_id, "name": s.scene_name, "home_id": s.home_id}
        for s in scenes.values()
    ]
    _json_out({"total": len(result), "scenes": result})
    await proxy.deinit()


async def cmd_scene(args):
    proxy = await _get_proxy()
    scenes = await proxy.get_scenes()
    for s in scenes.values():
        if args.name.lower() in s.scene_name.lower():
            ok = await proxy.run_scene(s)
            _json_out({"scene_id": s.scene_id, "name": s.scene_name, "success": ok})
            await proxy.deinit()
            return
    _json_out({"error": f"未找到场景: {args.name}"})
    await proxy.deinit()


async def cmd_status(args):
    try:
        proxy = await _get_proxy()
        devices = await proxy.get_devices()
        _json_out({"connected": True, "device_count": len(devices)})
        await proxy.deinit()
    except Exception as e:
        _json_out({"connected": False, "error": str(e)})


def _find_device(devices, name_or_id):
    if name_or_id in devices:
        return devices[name_or_id]
    for d in devices.values():
        if name_or_id.lower() in d.name.lower():
            return d
    for d in devices.values():
        cls = d.model.split(".")[1] if "." in d.model else ""
        if name_or_id.lower() in cls.lower():
            return d
    return None


def _parse_value(v):
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def build_parser():
    parser = argparse.ArgumentParser(prog="miot-x", description="小米米家智能家居 CLI")
    sub = parser.add_subparsers(dest="command")

    p_devices = sub.add_parser("devices", help="列出所有设备")
    p_devices.add_argument("--room", default="", help="按房间筛选")
    p_devices.add_argument("--refresh", action="store_true", help="强制刷新")

    p_device = sub.add_parser("device", help="设备详情+SPEC")
    p_device.add_argument("name", help="设备名称(模糊匹配)")

    p_on = sub.add_parser("on", help="打开设备")
    p_on.add_argument("name", help="设备名称")

    p_off = sub.add_parser("off", help="关闭设备")
    p_off.add_argument("name", help="设备名称")

    p_toggle = sub.add_parser("toggle", help="切换设备开关")
    p_toggle.add_argument("name", help="设备名称")

    p_get = sub.add_parser("get", help="读取属性")
    p_get.add_argument("name", help="设备名称")
    p_get.add_argument("siid", type=int, help="服务 ID")
    p_get.add_argument("piid", type=int, help="属性 ID")

    p_set = sub.add_parser("set", help="设置属性")
    p_set.add_argument("name", help="设备名称")
    p_set.add_argument("siid", type=int, help="服务 ID")
    p_set.add_argument("piid", type=int, help="属性 ID")
    p_set.add_argument("value", help="属性值")

    p_action = sub.add_parser("action", help="执行设备动作")
    p_action.add_argument("name", help="设备名称")
    p_action.add_argument("siid", type=int, help="服务 ID")
    p_action.add_argument("aiid", type=int, help="动作 ID")
    p_action.add_argument("--args", default="", help="参数列表(逗号分隔)")

    sub.add_parser("scenes", help="列出场景")

    p_scene = sub.add_parser("scene", help="执行场景")
    p_scene.add_argument("name", help="场景名称(模糊匹配)")

    sub.add_parser("status", help="服务连接状态")

    return parser


def cli_main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "devices": cmd_devices,
        "device": cmd_device,
        "on": cmd_on,
        "off": cmd_off,
        "toggle": cmd_toggle,
        "get": cmd_get_prop,
        "set": cmd_set_prop,
        "action": cmd_action,
        "scenes": cmd_scenes,
        "scene": cmd_scene,
        "status": cmd_status,
    }

    if not args.command or args.command not in dispatch:
        parser.print_help()
        sys.exit(1)

    asyncio.run(dispatch[args.command](args))
