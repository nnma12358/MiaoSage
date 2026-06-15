#!/bin/bash
# ============================================================
# 一键构建前端 + 打包 + 发送到 K1（支持双模式）
# 用法: bash deploy/pack-send.sh root@192.168.x.x [static|docker]
# ============================================================
set -e
TARGET="${1:?用法: bash deploy/pack-send.sh root@192.168.x.x [static|docker]}"
MODE="${2:-docker}"
BDIR="/opt/miao-xiu"

cd "$(dirname "$0")/.."

echo "=== [1/3] 构建前端 ==="
npm install --silent && npm run build

echo "=== [2/3] 打包 ($MODE) ==="
if [ "$MODE" = "static" ]; then
    tar czf /tmp/miao-xiu.tar.gz \
        build/ \
        yolov8n.onnx \
        server/board_server.py server/perf.py server/requirements.txt
else
    tar czf /tmp/miao-xiu.tar.gz \
        build/ \
        Dockerfile.k1 Dockerfile.yolo Dockerfile.asr Dockerfile.tts \
        docker-compose.k1.yml \
        yolov8n.onnx \
        server/yolo_server.py server/asr_server.py server/tts_server.py server/gateway_server.py \
        tokenizer*.whl 2>/dev/null || true
fi
echo "  ✓ /tmp/miao-xiu.tar.gz ($(du -h /tmp/miao-xiu.tar.gz | cut -f1))"

echo "=== [3/3] 发送到 K1 ==="
ssh "$TARGET" "mkdir -p $BDIR"
scp /tmp/miao-xiu.tar.gz "$TARGET:$BDIR/"
ssh "$TARGET" "cd $BDIR && tar xzf miao-xiu.tar.gz && echo '✓ 解压完成'"

echo ""
if [ "$MODE" = "static" ]; then
    echo "===== ✓ 发送完成 (静态模式) ====="
    echo "  在 K1 上启动:"
    echo "    ssh $TARGET"
    echo "    cd $BDIR"
    echo "    pip install --break-system-packages -r server/requirements.txt"
    echo "    python3 server/board_server.py --port 443"
else
    echo "===== ✓ 发送完成 (Docker 模式) ====="
    echo "  在 K1 上构建启动:"
    echo "    ssh $TARGET"
    echo "    cd $BDIR"
    echo "    docker compose -f docker-compose.k1.yml up -d --build"
fi
