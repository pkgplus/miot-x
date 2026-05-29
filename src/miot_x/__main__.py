# -*- coding: utf-8 -*-
"""miot-x — 小米米家智能家居控制工具。

用法:
    python -m miot_x                   # 默认 stdio 模式
    python -m miot_x --http-port 8300  # HTTP MCP server
    python -m miot_x --xiaozhi         # 小智 WebSocket 桥接
    python -m miot_x --http-port 8300 --xiaozhi  # 全部启用

管理命令:
    python -m miot_x login     # 扫码登录
    python -m miot_x homes     # 重新选择家庭
    python -m miot_x test      # 测试连接
"""
import asyncio
import re
import sys

import qrcode

from .mcp import server_main


async def login():
    """OAuth 扫码登录 — 终端显示二维码。"""
    from .lib.auth import MIoTAuth

    auth = MIoTAuth()
    auth_url, state = await auth.gen_oauth_url()

    qr = qrcode.QRCode()
    qr.add_data(auth_url)
    qr.print_ascii()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║               🔐 米家授权登录                            ║
╚══════════════════════════════════════════════════════════╝

📱 用手机米家 App 扫描上方二维码授权

如果扫码失败，也可复制以下链接在浏览器中打开:
{auth_url}

扫码授权后，浏览器会跳转到 127.0.0.1（打不开是正常的），
把浏览器地址栏的 👉 完整 URL 👈 粘贴到这里:
""")

    callback_url = input("📋 回调 URL: ").strip()
    code_match = re.search(r'[?&]code=([^&]+)', callback_url)
    if not code_match:
        print("❌ URL 中未找到授权码 (code)")
        return

    code = code_match.group(1)
    try:
        oauth_info = await auth.exchange_code(code)
        print(f"""
✅ 登录成功!
   UID: {oauth_info.user_info.uid if oauth_info.user_info else 'N/A'}
   昵称: {oauth_info.user_info.nickname if oauth_info.user_info else 'N/A'}
   Token 已保存: ~/.miot-x/auth.json
""")
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        return

    await select_homes()


async def select_homes():
    """选择要控制的家庭。"""
    from .lib.proxy import MiotProxy
    from .lib.config import save_selected_home_ids

    print("🏠 正在获取家庭列表...")
    proxy = MiotProxy()
    await proxy.init()
    homes = await proxy.get_homes()
    await proxy.deinit()

    if not homes:
        print("⚠️  未找到任何家庭")
        return

    home_list = list(homes.values())
    print("\n可用家庭:")
    for i, home in enumerate(home_list, 1):
        room_count = len(home.room_list) if home.room_list else 0
        print(f"  [{i}] {home.home_name}（{room_count} 个房间）")
    print(f"  [0] 全部家庭")

    choice = input("\n请选择家庭编号（多个用逗号分隔，直接回车选全部）: ").strip()

    if not choice or choice == "0":
        save_selected_home_ids(None)
        print("✅ 已选择: 全部家庭")
    else:
        selected_ids = []
        selected_names = []
        for part in choice.split(","):
            try:
                idx = int(part.strip()) - 1
                if 0 <= idx < len(home_list):
                    selected_ids.append(home_list[idx].home_id)
                    selected_names.append(home_list[idx].home_name)
            except ValueError:
                continue
        if selected_ids:
            save_selected_home_ids(selected_ids)
            print(f"✅ 已选择: {', '.join(selected_names)}")
        else:
            save_selected_home_ids(None)
            print("✅ 已选择: 全部家庭")


async def test():
    """测试设备连接。"""
    from .lib.proxy import MiotProxy

    proxy = MiotProxy()
    await proxy.init()
    devices = await proxy.get_devices()
    scenes = await proxy.get_scenes()
    print(f"✅ 连接成功: {len(devices)} 设备, {len(scenes)} 场景")
    await proxy.deinit()


CLI_COMMANDS = {"devices", "device", "on", "off", "toggle", "get", "set", "action", "scenes", "scene", "status"}


def main():
    enable_xiaozhi = False
    http_port = 0
    http_host = "127.0.0.1"
    positional = []

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--xiaozhi":
            enable_xiaozhi = True
        elif a == "--http-port":
            i += 1
            if i < len(args):
                http_port = int(args[i])
        elif a == "--http-host":
            i += 1
            if i < len(args):
                http_host = args[i]
        else:
            positional.append(a)
        i += 1

    cmd = positional[0] if positional else "run"

    if cmd == "login":
        asyncio.run(login())
    elif cmd == "test":
        asyncio.run(test())
    elif cmd == "homes":
        asyncio.run(select_homes())
    elif cmd in CLI_COMMANDS:
        from .cli import cli_main
        cli_main(positional)
    else:
        asyncio.run(server_main(
            http_port=http_port,
            http_host=http_host,
            enable_xiaozhi=enable_xiaozhi,
        ))


if __name__ == "__main__":
    main()
