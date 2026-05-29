# -*- coding: utf-8 -*-
"""OAuth2 认证模块 — 生成 QR 登录 URL，交换授权码换取 token。"""
import asyncio
import json
import logging
from pathlib import Path
from uuid import uuid4

from miot.cloud import MIoTOAuth2Client
from miot.types import MIoTOauthInfo

from .config import OAUTH_REDIRECT_URI, CLOUD_SERVER, AUTH_FILE

_LOGGER = logging.getLogger(__name__)

UUID_FILE = AUTH_FILE.parent / "uuid.txt"


class MIoTAuth:
    """米家 OAuth 认证管理器。"""

    def __init__(self, cache_dir: Path = None):
        self._cache_dir = cache_dir or AUTH_FILE.parent
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._client: MIoTOAuth2Client | None = None

        # 复用已保存的 uuid（保证 device_id 一致）
        if UUID_FILE.exists():
            self._uuid = UUID_FILE.read_text().strip()
        else:
            self._uuid = uuid4().hex
            UUID_FILE.write_text(self._uuid)

    # ── OAuth URL 生成 ──────────────────────────────

    async def gen_oauth_url(self) -> tuple[str, str]:
        """生成 OAuth 授权 URL。

        Returns:
            (auth_url, state): 授权 URL 和 state 校验值。
        """
        self._client = MIoTOAuth2Client(
            redirect_uri=OAUTH_REDIRECT_URI,
            cloud_server=CLOUD_SERVER,
            uuid=self._uuid,
        )
        auth_url = self._client.gen_auth_url()
        return auth_url, self._client.state

    # ── Code 换 Token ───────────────────────────────

    async def exchange_code(self, code: str) -> MIoTOauthInfo:
        """用授权码换取 access token。

        Returns:
            MIoTOauthInfo: 包含 access_token, refresh_token, expires_ts。
        """
        if not self._client:
            self._client = MIoTOAuth2Client(
                redirect_uri=OAUTH_REDIRECT_URI,
                cloud_server=CLOUD_SERVER,
                uuid=self._uuid,
            )
        oauth_info = await self._client.get_access_token_async(code=code)
        self.save(oauth_info)
        await self._client.deinit_async()
        self._client = None
        return oauth_info

    # ── Token 持久化 ────────────────────────────────

    def save(self, oauth_info: MIoTOauthInfo) -> None:
        """保存 token 到磁盘。"""
        data = {
            "access_token": oauth_info.access_token,
            "refresh_token": oauth_info.refresh_token,
            "expires_ts": oauth_info.expires_ts,
        }
        AUTH_FILE.write_text(json.dumps(data, indent=2))
        _LOGGER.info("token 已保存: %s", AUTH_FILE)

    @staticmethod
    def load() -> MIoTOauthInfo | None:
        """从磁盘加载 token。"""
        if not AUTH_FILE.exists():
            return None
        try:
            data = json.loads(AUTH_FILE.read_text())
            return MIoTOauthInfo(**data)
        except Exception as e:
            _LOGGER.warning("加载 token 失败: %s", e)
            return None

    @staticmethod
    def clear() -> None:
        """清除已保存的 token。"""
        for f in [AUTH_FILE, UUID_FILE]:
            if f.exists():
                f.unlink()
        _LOGGER.info("认证信息已清除")
