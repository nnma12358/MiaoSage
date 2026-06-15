#!/bin/bash
# ============================================================
# 苗绣·识裳 — K1 Docker 多容器部署（独立于静态部署）
# ============================================================
# 用法：
#   bash deploy/deploy-k1-docker-only.sh root@192.168.x.x
#
# 目录规划：
#   /home/bainbu/miao-xiu-k1      静态部署（board_server.py）
#   /home/bainbu/miao-xiu-k1-d    Docker 多容器（本脚本）
#
# 模型/依赖复用：
#   yolov8n.onnx     → 从 /home/bainbu/miao-xiu-k1/ 复制
#   NLP 模块          → 宿主机 /home/bainbu/spacemit-demo/examples/NLP
#   Ollama            → 宿主机 127.0.0.1:11434
# ============================================================
set -e

TARGET="${1:-}"
[ -z "$TARGET" ] && { echo "用法: $0 root@192.168.x.x"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

BDIR_STATIC="/home/bainbu/miao-xiu-k1"      # 静态部署目录（已存在）
BDIR_DOCKER="/home/bainbu/miao-xiu-k1-d"    # Docker 部署目录（新建）

cd "$PROJECT_DIR"

echo "========================================="
echo "  苗绣·识裳 — K1 Docker 多容器部署"
echo "  目标:      $TARGET"
echo "  静态目录:  $BDIR_STATIC (复用模型)"
echo "  Docker目录: $BDIR_DOCKER"
echo "========================================="

# ====== [1/5] 构建前端 ======
echo "[1/5] PC 构建前端..."
npm install --silent && npm run build
[ -f build/index.html ] || { echo "❌ build 失败"; exit 1; }
echo "  ✓ 前端已构建"

# ====== [2/5] 创建目录 & 复制模型 ======
echo "[2/5] 准备 K1 目录 & 复用模型..."
ssh "$TARGET" "
    mkdir -p $BDIR_DOCKER/server
    # 从静态目录复用 yolov8n.onnx（不重复传输大文件）
    if [ -f $BDIR_STATIC/yolov8n.onnx ]; then
        cp $BDIR_STATIC/yolov8n.onnx $BDIR_DOCKER/
        echo '  ✓ 模型复用自 $BDIR_STATIC/yolov8n.onnx'
    else
        echo '  ⚠ 未找到 $BDIR_STATIC/yolov8n.onnx，请手动放置'
    fi
"

# ====== [3/5] 传输 Docker 文件 ======
echo "[3/5] 传输 Docker 文件..."
rsync -avz --delete build/ "$TARGET:$BDIR_DOCKER/build/" 2>/dev/null || \
    scp -r build "$TARGET:$BDIR_DOCKER/"

# 只传容器相关文件（不传静态部署文件）
scp Dockerfile.yolo Dockerfile.asr Dockerfile.tts Dockerfile.k1 \
    docker-compose.k1.yml "$TARGET:$BDIR_DOCKER/"

scp server/yolo_server.py server/asr_server.py \
    server/tts_server.py server/gateway_server.py "$TARGET:$BDIR_DOCKER/server/"

# tokenizer wheel（TTS 容器需要）
if ls tokenizer*.whl 1>/dev/null 2>&1; then
    scp tokenizer*.whl "$TARGET:$BDIR_DOCKER/"
    echo "  ✓ tokenizer wheel 已传输"
else
    echo "  ⚠ 未找到 tokenizer*.whl (TTS 容器构建会失败)"
fi

echo "  ✓ Docker 文件已传输"

# ====== [4/5] 构建镜像 ======
echo "[4/5] K1 构建镜像 (首次 ~15 分钟)..."
ssh "$TARGET" "
    cd $BDIR_DOCKER
    echo '--- 构建 YOLO ---'
    docker compose -f docker-compose.k1.yml build yolo
    echo '--- 构建 ASR ---'
    docker compose -f docker-compose.k1.yml build asr
    echo '--- 构建 TTS ---'
    docker compose -f docker-compose.k1.yml build tts
    echo '--- 构建 Gateway ---'
    docker compose -f docker-compose.k1.yml build gateway
    echo '✓ 全部镜像构建完成'
"

# ====== [5/5] 启动 ======
echo "[5/5] 启动容器..."
ssh "$TARGET" "
    cd $BDIR_DOCKER

    # 停止旧容器（如果有）
    docker compose -f docker-compose.k1.yml down 2>/dev/null || true

    # 确保静态部署不占用 443 端口
    if pgrep -f board_server.py >/dev/null 2>&1; then
        echo '⚠ 检测到静态部署正在运行 (board_server.py 占用 443)'
        echo '  请先停止: pkill -f board_server.py'
        echo '  或让静态部署换端口: --port 8443'
        exit 1
    fi

    echo '--- 启动全部容器 ---'
    docker compose -f docker-compose.k1.yml up -d

    echo '--- 等待就绪 ---'
    sleep 20

    echo ''
    echo '--- 容器状态 ---'
    docker compose -f docker-compose.k1.yml ps

    echo ''
    echo '--- 网关健康检查 ---'
    curl -sk https://127.0.0.1:443/health | python3 -m json.tool 2>/dev/null || echo '⏳ 启动中...'

    echo ''
    echo '--- YOLO 健康检查 ---'
    curl -s http://127.0.0.1:8000/health 2>/dev/null || echo '⏳'

    echo ''
    echo '--- ASR 健康检查 ---'
    curl -s http://127.0.0.1:8001/health 2>/dev/null || echo '⏳'

    echo ''
    echo '--- TTS 健康检查 ---'
    curl -s http://127.0.0.1:8002/health 2>/dev/null || echo '⏳'

    # 检查 Ollama
    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo ''
        echo '✓ 宿主机 Ollama 可用'
    else
        echo ''
        echo '⚠ 未检测到 Ollama'
    fi
"

echo ""
echo "===== ✓ Docker 部署完成 ====="
echo ""
echo "  静态部署: $BDIR_STATIC  (board_server.py)"
echo "  Docker:   $BDIR_DOCKER  (4 容器)"
echo ""
echo "  访问:     https://${TARGET#*@}"
echo "  管理:     ssh $TARGET 'cd $BDIR_DOCKER && docker compose -f docker-compose.k1.yml logs -f'"
echo "  停止:     ssh $TARGET 'cd $BDIR_DOCKER && docker compose -f docker-compose.k1.yml down'"
echo ""
echo "  静态部署启动 (换端口避免冲突):"
echo "    ssh $TARGET 'cd $BDIR_STATIC && python3 server/board_server.py --port 8443'"
