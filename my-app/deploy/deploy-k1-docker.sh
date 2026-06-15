#!/bin/bash
# ============================================================
# 苗绣·识裳 — K1 多容器部署（4 容器架构）
# ============================================================
# 用法：
#   bash deploy/deploy-k1-docker.sh root@192.168.x.x
#
# 前置：
#   - K1 已安装 Docker + docker compose
#   - K1 宿主机已运行 Ollama（ollama serve）
#   - yolov8n.onnx 在项目根目录
#   - tokenizer*.whl 在项目根目录（TTS 容器需要）
#   - /home/bainbu/spacemit-demo/examples/NLP 存在（ASR/TTS）
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BDIR="/opt/miao-xiu"

TARGET="${1:-}"
[ -z "$TARGET" ] && { echo "用法: $0 root@192.168.x.x"; exit 1; }

cd "$PROJECT_DIR"

echo "========================================="
echo "  苗绣·识裳 — K1 多容器部署"
echo "  目标: $TARGET"
echo "  架构: 网关(443) + YOLO(8000) + ASR(8001) + TTS(8002)"
echo "========================================="

# ---- [1/6] PC 构建前端 ----
echo "[1/6] PC 构建前端..."
npm install --silent && npm run build
[ -f build/index.html ] || { echo "❌ build 失败"; exit 1; }
echo "  ✓ 前端已构建"

# ---- [2/6] 检查模型文件 ----
echo "[2/6] 检查模型文件..."
[ -f yolov8n.onnx ] || { echo "❌ 请将 yolov8n.onnx 放到项目根目录"; exit 1; }
echo "  ✓ yolov8n.onnx ($(du -h yolov8n.onnx | cut -f1))"

# ---- [3/6] 传输到 K1 ----
echo "[3/6] 传输文件到 K1..."
ssh "$TARGET" "mkdir -p $BDIR/server $BDIR/deploy" 2>/dev/null || true

# 前端
rsync -avz --delete build/ "$TARGET:$BDIR/build/" 2>/dev/null || \
    scp -r build "$TARGET:$BDIR/"

# Docker 文件
scp Dockerfile.yolo Dockerfile.asr Dockerfile.tts Dockerfile.k1 \
    docker-compose.k1.yml yolov8n.onnx "$TARGET:$BDIR/"

# 服务端脚本
scp server/yolo_server.py server/asr_server.py \
    server/tts_server.py server/gateway_server.py "$TARGET:$BDIR/server/"

# tokenizer wheel（TTS 容器需要）
if ls tokenizer*.whl 1>/dev/null 2>&1; then
    scp tokenizer*.whl "$TARGET:$BDIR/"
    echo "  ✓ tokenizer wheel 已传输"
else
    echo "  ⚠ 未找到 tokenizer*.whl，TTS 容器构建可能失败"
    echo "    请将预编译的 tokenizers wheel 放到项目根目录"
fi

echo "  ✓ 文件已传输"

# ---- [4/6] 构建 YOLO 镜像 ----
echo "[4/6] 构建 YOLO 镜像..."
ssh "$TARGET" "cd $BDIR && docker compose -f docker-compose.k1.yml build yolo"

# ---- [5/6] 构建 ASR + TTS + 网关 ----
echo "[5/6] 构建 ASR / TTS / 网关镜像..."
ssh "$TARGET" "cd $BDIR && docker compose -f docker-compose.k1.yml build asr tts gateway"

# ---- [6/6] 启动全部服务 ----
echo "[6/6] 启动全部服务..."
ssh "$TARGET" "
    cd $BDIR
    echo '--- 停止旧容器 ---'
    docker compose -f docker-compose.k1.yml down 2>/dev/null || true
    echo '--- 启动容器 ---'
    docker compose -f docker-compose.k1.yml up -d
    echo '--- 等待就绪 ---'
    sleep 30
    echo ''
    echo '--- 容器状态 ---'
    docker compose -f docker-compose.k1.yml ps
    echo ''
    echo '--- 网关健康检查 ---'
    curl -sk https://127.0.0.1:443/health | python3 -m json.tool 2>/dev/null || \
        echo '⏳ 网关启动中...'
    echo ''
    echo '--- YOLO 健康检查 ---'
    curl -s http://127.0.0.1:8000/health 2>/dev/null || echo '⏳ YOLO 启动中...'
    echo ''
    echo '--- ASR 健康检查 ---'
    curl -s http://127.0.0.1:8001/health 2>/dev/null || echo '⏳ ASR 启动中...'
    echo ''
    echo '--- TTS 健康检查 ---'
    curl -s http://127.0.0.1:8002/health 2>/dev/null || echo '⏳ TTS 启动中...'

    # 检查宿主机 Ollama
    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo '✓ 宿主机 Ollama 可用 — LLM 对话已就绪'
    else
        echo '⚠ 未检测到宿主机 Ollama'
        echo '  安装: curl -fsSL https://ollama.com/install.sh | sh'
        echo '  拉取: ollama pull qwen2.5-instruct'
    fi
"

echo ""
echo "===== ✓ 部署完成 ====="
echo "  HTTPS 前端:  https://${TARGET#*@}"
echo "  健康检查:    curl -k https://${TARGET#*@}/health"
echo "  YOLO:        curl http://${TARGET#*@}:8000/health"
echo "  ASR:         curl http://${TARGET#*@}:8001/health"
echo "  TTS:         curl http://${TARGET#*@}:8002/health"
echo ""
echo "  ⚠️  HTTPS 使用自签名证书，浏览器需点「高级」→「继续前往」"
echo ""
echo "  容器管理（在 K1 上执行）:"
echo "    cd $BDIR"
echo "    docker compose -f docker-compose.k1.yml logs -f         # 查看全部"
echo "    docker compose -f docker-compose.k1.yml logs yolo       # 单容器"
echo "    docker compose -f docker-compose.k1.yml restart         # 重启全部"
echo "    docker compose -f docker-compose.k1.yml down            # 停止全部"
echo "    docker compose -f docker-compose.k1.yml up -d yolo      # 仅启动 YOLO"

