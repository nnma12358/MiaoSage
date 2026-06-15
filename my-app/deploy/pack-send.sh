#!/bin/bash
# ============================================================
# 一键构建前端 + 打包 + 发送到 K1
# 用法: bash deploy/pack-send.sh root@192.168.x.x
# ============================================================
set -e
TARGET="${1:?用法: bash deploy/pack-send.sh root@192.168.x.x}"
BDIR="/opt/miao-xiu"

cd "$(dirname "$0")/.."

echo "=== [1/3] 构建前端 ==="
npm install --silent && npm run build

echo "=== [2/3] 打包 ==="
tar czf /tmp/miao-xiu.tar.gz \
    build/ \
    Dockerfile.k1 Dockerfile.yolo Dockerfile.asr Dockerfile.tts \
    docker-compose.k1.yml \
    yolov8n.onnx \
    server/yolo_server.py server/asr_server.py server/tts_server.py server/gateway_server.py \
    tokenizer*.whl 2>/dev/null || true
echo "  ✓ /tmp/miao-xiu.tar.gz ($(du -h /tmp/miao-xiu.tar.gz | cut -f1))"

echo "=== [3/3] 发送到 K1 ==="
ssh "$TARGET" "mkdir -p $BDIR"
scp /tmp/miao-xiu.tar.gz "$TARGET:$BDIR/"
ssh "$TARGET" "cd $BDIR && tar xzf miao-xiu.tar.gz && echo '✓ 解压完成'"

echo ""
echo "===== ✓ 发送完成 ====="
echo "  在 K1 上执行构建和启动:"
echo "    ssh $TARGET"
echo "    cd $BDIR"
echo "    docker compose -f docker-compose.k1.yml build"
echo "    docker compose -f docker-compose.k1.yml up -d"
