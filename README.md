# miot-skill

> 小米米家智能家居 MCP Server — 基于小米官方 [miot_kit](https://github.com/XiaoMi/xiaomi-miloco) SDK，纯 Python，ARM64 可用，零 GPU 依赖。

## 特性

- 🏠 **小米云直连** — 复用 miloco 的 OAuth ClientID + AES 加密协议，稳定可靠
- 📱 **终端扫码登录** — 运行即显示二维码，手机米家一扫授权，token 自动刷新
- 🔧 **11 个 MCP 工具** — 设备列表、开关控制、属性读写、场景执行
- 🔍 **模糊匹配** — 设备/场景名称智能搜索，说「台灯」就能找到
- 🌐 **小智适配** — 内置 `mcp_config.json`，支持远程 SSE/HTTP 注册
- 🐍 **全异步** — aiohttp 驱动，无同步阻塞，ARM64 / x64 通吃

## 快速开始

### 1. 获取 miot_kit

```bash
git clone --depth 1 https://github.com/XiaoMi/xiaomi-miloco.git ~/src/xiaomi-miloco
```

### 2. 安装

```bash
git clone https://github.com/pkgplus/miot-skill.git
cd miot-skill
python3 -m venv venv && source venv/bin/activate
pip install -e ~/src/xiaomi-miloco/miot_kit
pip install -e .
```

### 3. 扫码登录

```bash
python -m miot_skill login
```

终端会显示二维码，用手机米家 App 扫码授权。授权后浏览器会跳转到 `127.0.0.1`（打不开是正常的），把地址栏的完整 URL 粘贴回终端即可。

### 4. 使用

```bash
# 测试连接
python -m miot_skill test

# 启动 MCP 服务
python -m miot_skill
```

## MCP 工具

| 工具 | 说明 |
|------|------|
| `list_devices` | 设备列表，支持按房间筛选 |
| `get_device` | 设备详情 + SPEC 定义（siid/piid） |
| `device_on` | 打开设备 |
| `device_off` | 关闭设备 |
| `device_toggle` | 切换开关（先读后写） |
| `get_prop` | 读取属性（siid/piid） |
| `set_prop` | 设置属性（siid/piid/value） |
| `device_action` | 执行动作（siid/aiid） |
| `list_scenes` | 场景列表 |
| `execute_scene` | 执行场景（名称模糊匹配） |
| `get_service_status` | 服务连接状态 |

## 注册到 Hermes Agent

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  miot:
    command: /path/to/miot-skill/venv/bin/python
    args: [-m, miot_skill]
    timeout: 30
```

```bash
hermes mcp test miot
```

## 小智平台

通过 `mcp_pipe.py` 将本地 MCP Server 桥接到小智 WebSocket：

```bash
# 设置小智 MCP 端点
export MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=XXXXX

# 启动桥接（自动读取 mcp_config.json 中已启用的 server）
python mcp_pipe.py

# 或指定单个 server
python mcp_pipe.py miot-skill
```

特性：
- WebSocket 断线自动重连（指数退避）
- 支持 stdio / sse / http 三种传输类型
- 多 server 并行桥接

## 架构

```
   ┌─────────────────┐
   │  小智平台         │  WebSocket
   │  api.xiaozhi.me  │
   └────┬────────────┘
        │ ws://
   ┌────▼────────────┐
   │  mcp_pipe.py     │  WebSocket ↔ stdio 桥接
   │                  │  自动重连 + 多 server
   └────┬────────────┘
        │ stdio
   ┌────▼────────────┐
   │  miot_skill      │  11 工具
   │  server.py       │  FastMCP
   └────┬────────────┘
        │
   ┌────▼────────────┐
   │  miot_skill      │  token 刷新
   │  proxy.py        │  设备控制
   └────┬────────────┘
        │
   ┌────▼────────────┐
   │  miot_kit        │  OAuth2 / AES+RSA
   │  (小米官方 SDK)   │  全异步 aiohttp
   └────┬────────────┘
        │ HTTPS
   ┌────▼────────────┐
   │  mico.api.       │
   │  mijia.tech      │
   └─────────────────┘
```

## License

MIT
