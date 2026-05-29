# -*- coding: utf-8 -*-
"""miot-skill 配置常量。"""
import os
from pathlib import Path

# 缓存目录
CACHE_DIR = Path(os.getenv("MIOT_CACHE_DIR", os.path.expanduser("~/.miot-mcp")))
# Token 持久化文件
AUTH_FILE = CACHE_DIR / "auth.json"
# 设备/场景缓存
DEVICES_FILE = CACHE_DIR / "devices.json"
SCENES_FILE = CACHE_DIR / "scenes.json"

# OAuth 回调地址（本地 loopback）
OAUTH_REDIRECT_URI = "https://127.0.0.1"
# 小米云区域（cn = 中国大陆）
CLOUD_SERVER = os.getenv("MIOT_CLOUD_SERVER", "cn")
