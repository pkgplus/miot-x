#!/bin/bash
# miot-skill 首次扫码登录
# 用法: ./scripts/login.sh

set -e
cd "$(dirname "$0")/.."

echo "🔐 miot-skill 首次登录"
echo "======================"
echo ""

source venv/bin/activate 2>/dev/null || {
    echo "❌ 请先创建 venv: python3 -m venv venv && source venv/bin/activate && pip install -e ."
    exit 1
}

python -m miot_skill login
