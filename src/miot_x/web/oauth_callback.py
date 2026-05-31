# -*- coding: utf-8 -*-
"""OAuth 回调 — HTTPS :443 常驻服务，随 serve 启动。"""
import asyncio
import datetime
import ipaddress
import logging
import ssl
import tempfile

from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

_LOGGER = logging.getLogger(__name__)

SUCCESS_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>登录成功</title></head>
<body style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:system-ui;background:#F5F5F5;">
<div style="text-align:center;background:white;padding:40px;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
<h2 style="margin-bottom:8px;">✅ 登录成功</h2>
<p style="color:#999;font-size:14px;">窗口将自动关闭，请返回 miot-x</p>
<script>
try { if (window.opener) { window.opener.postMessage({type:'miot-x-login-success'}, '*'); } } catch(e) {}
setTimeout(function(){ try { window.close(); } catch(e) {} }, 1500);
</script>
</div>
</body></html>"""

FAIL_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>登录失败</title></head>
<body style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:system-ui;background:#F5F5F5;">
<div style="text-align:center;background:white;padding:40px;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
<h2 style="margin-bottom:8px;">❌ 登录失败</h2>
<p style="color:#999;font-size:14px;">%s</p>
</div>
</body></html>"""

# 全局状态：443 是否可用
_callback_available = False
_runner = None


def is_callback_available() -> bool:
    return _callback_available


def _generate_self_signed_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    key_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
    cert_file.close()
    key_file.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_file.close()
    return cert_file.name, key_file.name


async def start_persistent_callback_server():
    """启动常驻 HTTPS :443 服务，收到 OAuth 回调自动换 token。"""
    global _callback_available, _runner

    async def handle_callback(request):
        code = request.query.get("code")
        if not code:
            return web.Response(text=FAIL_HTML % "未收到授权码", content_type="text/html", status=400)

        try:
            from ..lib.auth import MIoTAuth
            from ..lib.proxy import reset_shared_proxy
            auth = MIoTAuth()
            # gen_oauth_url 需要先调用来初始化 client（获取 device_id）
            await auth.gen_oauth_url()
            await auth.exchange_code(code)
            # 重置 proxy 以便下次请求时用新 token 重建连接
            await reset_shared_proxy()
            _LOGGER.info("OAuth 登录成功（:443 常驻回调）")
            return web.Response(text=SUCCESS_HTML, content_type="text/html")
        except Exception as e:
            _LOGGER.error("OAuth token 交换失败: %s", e)
            return web.Response(text=FAIL_HTML % str(e), content_type="text/html", status=500)

    app = web.Application()
    app.router.add_get("/", handle_callback)

    cert_path, key_path = _generate_self_signed_cert()
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(cert_path, key_path)

    _runner = web.AppRunner(app)
    await _runner.setup()
    try:
        site = web.TCPSite(_runner, "127.0.0.1", 443, ssl_context=ssl_ctx)
        await site.start()
        _callback_available = True
        _LOGGER.info("OAuth 回调服务常驻启动 (https://127.0.0.1:443)")
    except OSError as e:
        _LOGGER.warning("无法绑定 443 端口: %s（登录将使用手动模式）", e)
        await _runner.cleanup()
        _runner = None
        _callback_available = False


async def stop_persistent_callback_server():
    global _callback_available, _runner
    if _runner:
        await _runner.cleanup()
        _runner = None
    _callback_available = False
