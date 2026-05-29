# -*- coding: utf-8 -*-
"""小智 MCP 适配 — 解析 mcp_config.json，管理远程注册。
环境变量:
    XIAOZHI_MCP_URL  小智 MCP WebSocket 地址
                     格式: wss://api.xiaozhi.me/mcp/?token=XXXXX
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

_LOGGER = logging.getLogger(__name__)


class XiaozhiConfig:
    """小智 MCP 注册配置。"""

    def __init__(self, config_path: Path = None):
        self._config_path = config_path or Path(
            os.getenv("XIAOZHI_CONFIG", "mcp_config.json")
        )
        self._data: dict = {}

    def load(self) -> dict:
        """加载 mcp_config.json。"""
        path = self._config_path
        if not path.exists():
            _LOGGER.warning("配置文件不存在: %s", path)
            return {}
        with open(path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        return self._data

    @property
    def servers(self) -> dict:
        if not self._data:
            self.load()
        return self._data.get("mcpServers", {})

    @property
    def enabled_servers(self) -> dict:
        return {
            name: cfg
            for name, cfg in self.servers.items()
            if not (cfg or {}).get("disabled", False)
        }

    @staticmethod
    def get_mcp_url() -> Optional[str]:
        """获取小智 MCP 地址（含 token）。
        格式: wss://api.xiaozhi.me/mcp/?token=XXXXX
        """
        return os.getenv("XIAOZHI_MCP_URL")

    def build_server_command(self, name: str) -> tuple[list[str], dict]:
        servers = self.servers
        if name not in servers:
            raise RuntimeError(f"未知 server: {name}")

        entry = servers[name]
        if entry.get("disabled"):
            raise RuntimeError(f"Server '{name}' 已禁用")

        typ = (entry.get("type") or "stdio").lower()
        env = os.environ.copy()
        for k, v in (entry.get("env") or {}).items():
            env[str(k)] = str(v)

        if typ == "stdio":
            cmd = entry.get("command")
            args = entry.get("args") or []
            if not cmd:
                raise RuntimeError(f"Server '{name}' 缺少 'command'")
            return [cmd, *args], env

        if typ in ("sse", "http", "streamablehttp"):
            url = entry.get("url", "")
            url = url.replace("${XIAOZHI_MCP_URL}", os.getenv("XIAOZHI_MCP_URL", ""))
            cmd = [os.sys.executable, "-m", "miot_mcp.server"]
            return cmd, env

        raise RuntimeError(f"不支持的 server 类型: {typ}")

    def to_json(self) -> str:
        return json.dumps(self._data, indent=2, ensure_ascii=False)
