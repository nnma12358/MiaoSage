#!/bin/bash
# ============================================================
# 苗绣·识裳 — K1 一键部署（支持静态 / Docker 双模式）
# ============================================================
# 用法：
#   bash deploy/deploy-k1-docker.sh root@192.168.x.x [static|docker]
#
#   static — 单进程直接运行 (board_server.py + pip install)
#   docker — 4 容器架构 (gateway + yolo + asr + tts)
#
# 前置：
#   - yolov8n.onnx 在项目根目录
#   - Docker 模式需 K1 已安装 Docker + docker compose
#   - Docker 模式需 tokenizer*.whl 在项目根目录（TTS 容器）
#   - /home/bainbu/spacemit-demo/examples/NLP 存在（ASR/TTS）
# ============================================================
set -e

MODE="${2:-docker}"
TARGET="${1:-}"
[ -z "$TARGET" ] && { echo "用法: $0 root@192.168.x.x [static|docker]"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BDIR="/opt/miao-xiu"

cd "$PROJECT_DIR"

case "$MODE" in
  static)  MODE_LABEL="静态部署 (单进程)";;
  docker)  MODE_LABEL="Docker 多容器";;
  *)       echo "未知模式: $MODE (可选 static|docker)"; exit 1;;
esac

echo "========================================="
echo "  苗绣·识裳 — K1 部署"
echo "  目标: $TARGET"
echo "  模式: $MODE_LABEL"
echo "========================================="

# ====== [公共步骤] 构建前端 ======
echo "[1] PC 构建前端..."
npm install --silent && npm run build
[ -f build/index.html ] || { echo "❌ build 失败"; exit 1; }
echo "  ✓ 前端已构建"

# ====== [公共步骤] 检查模型 ======
echo "[2] 检查模型文件..."
[ -f yolov8n.onnx ] || { echo "❌ 请将 yolov8n.onnx 放到项目根目录"; exit 1; }
echo "  ✓ yolov8n.onnx ($(du -h yolov8n.onnx | cut -f1))"

# ====== [公共步骤] 传输文件 ======
echo "[3] 传输文件到 K1..."
ssh "$TARGET" "mkdir -p $BDIR/server $BDIR/deploy" 2>/dev/null || true
rsync -avz --delete build/ "$TARGET:$BDIR/build/" 2>/dev/null || \
    scp -r build "$TARGET:$BDIR/"

scp yolov8n.onnx "$TARGET:$BDIR/"

if [ "$MODE" = "static" ]; then
    # ==================== 静态部署 ====================
    echo "=== 静态部署模式 ==="
    scp server/board_server.py server/perf.py server/requirements.txt "$TARGET:$BDIR/server/"
    echo "  ✓ 文件已传输"
    echo ""
    echo "[4] K1 安装依赖并启动..."
    ssh "$TARGET" "
        cd $BDIR
        echo '--- 安装 Python 依赖 ---'
        pip install --break-system-packages -r server/requirements.txt
        echo '--- 安装 spacemit-ort ---'
        pip install --break-system-packages --index-url https://git.spacemit.com/api/v4/projects/33/packages/pypi/simple spacemit-ort
        echo '--- 停止旧进程 ---'
        pkill -f board_server.py 2>/dev/null || true
        echo '--- 启动服务 (HTTPS 443) ---'
        nohup python3 -m uvicorn server.board_server:app --host 0.0.0.0 --port 443 \
            --ssl-keyfile /app/certs/key.pem --ssl-certfile /app/certs/cert.pem \
            --workers 1 --log-level info > /tmp/miao-xiu.log 2>&1 &
        sleep 5
        echo '--- 健康检查 ---'
        curl -sk https://127.0.0.1:443/health | python3 -m json.tool 2>/dev/null || echo '⏳ 启动中...'
    "
    echo ""
    echo "===== ✓ 静态部署完成 ====="
    echo "  HTTPS:  https://${TARGET#*@}"
    echo "  日志:   ssh $TARGET 'tail -f /tmp/miao-xiu.log'"
    echo "  停止:   ssh $TARGET 'pkill -f board_server.py'"

else
    # ==================== Docker 部署 ====================
    echo "=== Docker 多容器模式 ==="
    scp Dockerfile.yolo Dockerfile.asr Dockerfile.tts Dockerfile.k1 \
        docker-compose.k1.yml "$TARGET:$BDIR/"
    scp server/yolo_server.py server/asr_server.py \
        server/tts_server.py server/gateway_server.py "$TARGET:$BDIR/server/"
    if ls tokenizer*.whl 1>/dev/null 2>&1; then
        scp tokenizer*.whl "$TARGET:$BDIR/"
        echo "  ✓ tokenizer wheel 已传输"
    else
        echo "  ⚠ 未找到 tokenizer*.whl，TTS 容器构建可能失败"
    fi
    echo "  ✓ 文件已传输"

    echo "[4] 构建镜像..."
    ssh "$TARGET" "cd $BDIR && docker compose -f docker-compose.k1.yml build"

    echo "[5] 启动容器..."
    ssh "$TARGET" "
        cd $BDIR
        docker compose -f docker-compose.k1.yml down 2>/dev/null || true
        docker compose -f docker-compose.k1.yml up -d
        sleep 20
        echo '--- 容器状态 ---'
        docker compose -f docker-compose.k1.yml ps
        echo '--- 健康检查 ---'
        curl -sk https://127.0.0.1:443/health | python3 -m json.tool 2>/dev/null || echo '⏳ 启动中...'
    "
    echo ""
    echo "===== ✓ Docker 部署完成 ====="
    echo "  HTTPS:  https://${TARGET#*@}"
    echo "  管理:   ssh $TARGET 'cd $BDIR && docker compose -f docker-compose.k1.yml logs -f'"
fi

