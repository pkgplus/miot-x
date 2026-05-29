# miot-x

> 基于小米官方 [miot_kit](https://github.com/XiaoMi/xiaomi-miloco) SDK 的米家智能家居控制工具 — 让 AI 直接操控你的米家设备。提供 MCP Server、CLI 命令、Agent Skill 及小智 WebSocket 桥接，**单进程搞定全部**，纯 Python，ARM64 可用，零 GPU 依赖。

## 特性

- 🏠 **官方 SDK 直连** — 基于小米官方 miot_kit，复用 OAuth + AES 加密协议，稳定可靠
- 📱 **终端扫码登录** — 运行即显示二维码，手机米家一扫授权，token 自动刷新
- 🔧 **多种接入方式** — 默认 stdio、`--http-port` HTTP MCP、`--xiaozhi` WebSocket 桥接，可任意组合
- 🔍 **模糊匹配** — 设备/场景名称智能搜索，说「台灯」就能找到
- 🌐 **小智内置桥接** — `--xiaozhi` 参数直接启用，无需额外进程，断线自动重连
- 🤖 **Agent Skill** — 内置 MCP 和 CLI 两种 Skill，AI 开箱即用
- 🐍 **全异步** — aiohttp 驱动，无同步阻塞，ARM64 / x64 通吃
- ⚡ **单进程架构** — HTTP MCP + 小智桥接合二为一，不再需要 mcp_pipe 子进程

## 快速开始

### 1. 获取 miot_kit

```bash
git clone --depth 1 https://github.com/XiaoMi/xiaomi-miloco.git ~/src/xiaomi-miloco
```

### 2. 安装

```bash
git clone https://github.com/pkgplus/miot-x.git
cd miot-x
python3 -m venv venv && source venv/bin/activate
pip install -e ~/src/xiaomi-miloco/miot_kit
pip install -e .
```

### 3. 扫码登录

```bash
python -m miot_x login
```

终端会显示二维码，用手机米家 App 扫码授权。授权后浏览器会跳转到 `127.0.0.1`（打不开是正常的），把地址栏的完整 URL 粘贴回终端即可。

登录成功后会自动提示选择家庭（支持多选或全部）。选择后只会操作对应家庭的设备和场景。随时可通过以下命令重新选择：

```bash
python -m miot_x homes
```

### 4. 使用

```bash
# 测试连接
python -m miot_x test

# 默认 stdio 模式（兼容旧版）
python -m miot_x

# 一体化模式：HTTP MCP（给 Hermes/Claude Code）+ 小智桥接
python -m miot_x --http-port 8300 --xiaozhi

# 仅 HTTP MCP
python -m miot_x --http-port 8300

# 仅小智桥接
python -m miot_x --xiaozhi
```

## 运行模式

| 参数 | 说明 | 适用场景 |
|------|------|----------|
| (无参数) | stdio MCP Server | 兼容旧版，Claude Code 直连 |
| `--http-port PORT` | HTTP MCP Server (streamable-http) | Hermes Agent 等 HTTP 客户端 |
| `--xiaozhi` | 小智 WebSocket 桥接 | 小智平台远程控制 |
| `--http-port PORT --xiaozhi` | **一体化模式（推荐）** | **单进程同时服务本地和小智** |

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

## CLI 命令

除了 MCP 模式，还提供独立 CLI 命令用于调试或 Agent Skill 调用：

```bash
python -m miot_x homes                      # 选择/切换家庭
python -m miot_x devices [--room 房间名]   # 设备列表
python -m miot_x device <设备名>            # 设备详情
python -m miot_x on <设备名>                # 打开
python -m miot_x off <设备名>               # 关闭
python -m miot_x toggle <设备名>            # 切换
python -m miot_x get <设备名> <siid> <piid> # 读属性
python -m miot_x set <设备名> <siid> <piid> <value>  # 写属性
python -m miot_x action <设备名> <siid> <aiid> [--args ...]  # 执行动作
python -m miot_x scenes                     # 场景列表
python -m miot_x scene <场景名>             # 执行场景
python -m miot_x status                     # 连接状态
```

所有命令输出 JSON 格式，设备名/场景名支持模糊匹配。

## Agent Skills

项目内置两种 Agent Skill，位于 `skills/` 目录：

| Skill | 路径 | 调用方式 | 适用场景 |
|-------|------|----------|----------|
| **miot-mcp** | `skills/miot-mcp/` | MCP 工具调用 | Claude Code、Hermes、小智等 MCP 环境 |
| **miot-cli** | `skills/miot-cli/` | Bash 执行 CLI 命令 | 无 MCP 环境时的回退方案 |

**MCP 版本**（推荐）：Server 长驻，连接复用，响应快。适合已配置 MCP Server 的环境。

**CLI 版本**：每次通过 Bash 执行独立命令，无需 MCP Server 运行。适合调试或无法注册 MCP 的场景。

### 安装 Skill

将 `skills/miot-mcp/` 或 `skills/miot-cli/` 复制到你的 Agent 项目 skills 目录即可。

## 注册到 Claude Code

在项目 `.claude/settings.json` 中添加 MCP Server：

```json
{
  "mcpServers": {
    "miot-x": {
      "type": "stdio",
      "command": "/path/to/miot-x/venv/bin/python",
      "args": ["-m", "miot_x"]
    }
  }
}
```

## 注册到 Hermes Agent

**推荐使用 HTTP 模式**（单进程，无需子进程）：

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  miot:
    transport: streamable-http
    url: http://127.0.0.1:8300
    timeout: 30
```

配合 systemd 开机自启：

```bash
# 复制 service 文件
sudo cp miot-x.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now miot-x.service
```

> 旧版 stdio 模式仍然支持，但会额外启动一个子进程。推荐升级到 HTTP 模式。

## 小智平台

**内置桥接**（v1.1+），无需 mcp_pipe：

```bash
# 设置小智 MCP 端点
export MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=***

# 启动（单进程：HTTP MCP + 小智桥接）
python -m miot_x --http-port 8300 --xiaozhi
```

特性：
- WebSocket 断线自动重连（指数退避，最大 10 分钟）
- 与 HTTP MCP 共享同一进程，零额外开销
- 兼容 `MCP_ENDPOINT` 和 `XIAOZHI_MCP_URL` 环境变量

> ⚠️ `mcp_pipe.py` 已废弃，功能已集成到 `--xiaozhi` 参数中。如需独立桥接仍可使用。

## 部署（systemd 开机自启）

```bash
# 1. 创建 .env 文件
cat > .env << EOF
MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=你的token
EOF

# 2. 安装 service
sudo cp miot-x.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now miot-x.service

# 3. 验证
systemctl status miot-x.service
```

## 架构

```
                    ┌──────────────────┐
    Hermes ──HTTP──►│                  │
                    │   miot_x     │──WS──► 小智平台
  Claude Code ──stdio──►  (单进程)     │
                    │                  │──HTTPS──► 小米 IoT 云
                    └──────────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
          proxy.py    auth.py    miot_kit
         (设备控制)   (OAuth)   (小米SDK)
```

单进程架构：HTTP MCP、小智 WebSocket 桥接、设备控制全部在同一个进程中运行。

## 项目结构

```
miot-x/
├── src/miot_x/
│   ├── __main__.py         # 入口分发 + 参数解析
│   ├── lib/                # 核心库：设备控制、认证、配置
│   │   ├── config.py       #   配置常量 + 家庭选择
│   │   ├── auth.py         #   OAuth 认证 + token 管理
│   │   └── proxy.py        #   设备/场景控制代理
│   ├── mcp/                # MCP 协议层
│   │   ├── server.py       #   FastMCP 工具注册 + stdio/HTTP
│   │   └── xiaozhi.py      #   小智 WebSocket 桥接
│   └── cli/                # CLI 命令层
│       └── commands.py     #   所有子命令实现
├── skills/                 # Agent Skills
│   ├── miot-mcp/           #   MCP 版 Skill
│   └── miot-cli/           #   CLI 版 Skill
├── mcp_config.json         # MCP Server 配置
├── miot-x.service        # systemd service 文件
└── pyproject.toml
```

## License

MIT
