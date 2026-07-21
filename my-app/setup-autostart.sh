#!/bin/bash
# ============================================================
# 苗绣·识裳 — 开机自启安装脚本
# ============================================================
# 用法:
#   K1 板:  bash setup-autostart.sh k1
#   PC端:   bash setup-autostart.sh pc
# ============================================================
set -e

PROFILE="$1"
if [ -z "$PROFILE" ]; then
    echo "用法: bash setup-autostart.sh <k1|pc>"
    exit 1
fi

# 自动检测 compose 文件路径（脚本所在目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.swarm.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "错误: 找不到 $COMPOSE_FILE"
    exit 1
fi

# ---- 检测 docker / docker compose 路径 ----
DOCKER_BIN=$(which docker)
if [ -z "$DOCKER_BIN" ]; then
    echo "错误: 未找到 docker，请先安装 Docker"
    exit 1
fi

# 优先使用 docker compose (v20+)，其次 docker-compose (v1)
COMPOSE_CMD=""
if $DOCKER_BIN compose version &>/dev/null; then
    COMPOSE_CMD="$DOCKER_BIN compose"
elif which docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "错误: 未找到 docker compose 或 docker-compose"
    exit 1
fi
echo "  Docker: $DOCKER_BIN"
echo "  Compose: $COMPOSE_CMD"

# 预检 compose 文件
if ! $COMPOSE_CMD -f "$COMPOSE_FILE" config --quiet &>/dev/null; then
    echo "警告: compose 文件校验失败，尝试继续..."
fi

echo "============================================"
echo "  苗绣·识裳 — 开机自启安装"
echo "  模式: $PROFILE"
echo "  Compose: $COMPOSE_FILE"
echo "============================================"

if [ "$PROFILE" = "k1" ]; then
    SERVICE_NAME="miao-k1"
    PROFILE_ARG="--profile k1"
    DESCRIPTION="苗绣·识裳 K1 板端服务 (YOLO + ASR + Gateway)"

    cat > /tmp/miao-k1.service << 'SERVICE_EOF'
[Unit]
Description=SERVICE_DESC
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=SERVICE_DIR
ExecStartPre=/bin/sleep 10
ExecStart=SERVICE_COMPOSE_CMD -f SERVICE_COMPOSE PROFILE_ARG up -d
ExecStop=SERVICE_COMPOSE_CMD -f SERVICE_COMPOSE PROFILE_ARG down
ExecReload=SERVICE_COMPOSE_CMD -f SERVICE_COMPOSE PROFILE_ARG up -d --force-recreate
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
SERVICE_EOF

    sed -i "s|SERVICE_DESC|$DESCRIPTION|" /tmp/miao-k1.service
    sed -i "s|SERVICE_DIR|$SCRIPT_DIR|" /tmp/miao-k1.service
    sed -i "s|SERVICE_COMPOSE_CMD|$COMPOSE_CMD|" /tmp/miao-k1.service
    sed -i "s|SERVICE_COMPOSE|$COMPOSE_FILE|" /tmp/miao-k1.service
    sed -i "s|PROFILE_ARG|$PROFILE_ARG|" /tmp/miao-k1.service

    sudo cp /tmp/miao-k1.service /etc/systemd/system/miao-k1.service
    sudo systemctl daemon-reload
    sudo systemctl enable miao-k1.service
    echo "✓ K1 自启服务已安装: systemctl enable miao-k1"
    echo "  手动启动: sudo systemctl start miao-k1"
    echo "  查看状态: sudo systemctl status miao-k1"
    echo "  查看日志: sudo journalctl -u miao-k1 -f"

elif [ "$PROFILE" = "pc" ]; then
    SERVICE_NAME="miao-tts"
    PROFILE_ARG="--profile pc"
    DESCRIPTION="苗绣·识裳 PC端 TTS 服务 (MeloTTS)"

    cat > /tmp/miao-tts.service << 'SERVICE_EOF'
[Unit]
Description=SERVICE_DESC
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=SERVICE_DIR
ExecStartPre=/bin/sleep 5
ExecStart=SERVICE_COMPOSE_CMD -f SERVICE_COMPOSE PROFILE_ARG up -d
ExecStop=SERVICE_COMPOSE_CMD -f SERVICE_COMPOSE PROFILE_ARG down
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
SERVICE_EOF

    sed -i "s|SERVICE_DESC|$DESCRIPTION|" /tmp/miao-tts.service
    sed -i "s|SERVICE_DIR|$SCRIPT_DIR|" /tmp/miao-tts.service
    sed -i "s|SERVICE_COMPOSE_CMD|$COMPOSE_CMD|" /tmp/miao-tts.service
    sed -i "s|SERVICE_COMPOSE|$COMPOSE_FILE|" /tmp/miao-tts.service
    sed -i "s|PROFILE_ARG|$PROFILE_ARG|" /tmp/miao-tts.service

    sudo cp /tmp/miao-tts.service /etc/systemd/system/miao-tts.service
    sudo systemctl daemon-reload
    sudo systemctl enable miao-tts.service
    echo "✓ PC TTS 自启服务已安装: systemctl enable miao-tts"
    echo "  手动启动: sudo systemctl start miao-tts"

else
    echo "错误: 无效模式 '$PROFILE'，请使用 k1 或 pc"
    exit 1
fi
