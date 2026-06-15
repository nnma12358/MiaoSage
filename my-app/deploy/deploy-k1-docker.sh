#!/bin/bash
# ============================================================
# 苗绣·识裳 — K1 单板部署（Docker 容器 + 宿主机 Ollama）
# ============================================================
# 用法：
#   bash deploy/deploy-k1-docker.sh root@192.168.x.x
#   OLLAMA_HOST=192.168.1.50 bash deploy/deploy-k1-docker.sh root@192.168.x.x
#
# 前置：
#   - K1 板上已安装 Docker + docker compose
#   - K1 板上已运行 Ollama（ollama serve）
#   - yolov8n.onnx 已放在项目根目录（与 Dockerfile.k1 同级）
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BDIR="/opt/miao-xiu"

TARGET="${1:-}"
[ -z "$TARGET" ] && { echo "用法: $0 root@192.168.x.x"; exit 1; }

cd "$PROJECT_DIR"

echo "========================================="
echo "  苗绣·识裳 — K1 Docker 部署"
echo "  目标: $TARGET"
echo "  架构: 双端口容器 (80 HTTP + 443 HTTPS) + 宿主机 Ollama"
echo "========================================="

# ---- [1/4] PC 构建前端 ----
echo "[1/4] PC 构建前端..."
npm install --silent && npm run build
[ -f build/index.html ] || { echo "❌ build 失败"; exit 1; }
echo "  ✓ 前端已构建"

# ---- [2/4] 检查模型文件 ----
echo "[2/4] 检查 YOLO 模型..."
[ -f yolov8n.onnx ] || { echo "❌ 请将 yolov8n.onnx 放到项目根目录"; exit 1; }
echo "  ✓ yolov8n.onnx ($(du -h yolov8n.onnx | cut -f1))"

# ---- [3/4] 传输到 K1 ----
echo "[3/4] 传输文件到 K1..."
ssh "$TARGET" "mkdir -p $BDIR/server $BDIR/deploy" 2>/dev/null || true

rsync -avz --delete build/ "$TARGET:$BDIR/build/" 2>/dev/null || \
    scp -r build "$TARGET:$BDIR/"

scp Dockerfile.k1 docker-compose.k1.yml yolov8n.onnx "$TARGET:$BDIR/"
scp server/board_server.py server/perf.py server/requirements.txt "$TARGET:$BDIR/server/"
echo "  ✓ 文件已传输"

# ---- [4/4] K1 构建并启动 ----
echo "[4/4] K1 构建镜像并启动..."
echo "  ⚠️ 首次构建约 10-15 分钟（含 scipy/Pillow/numpy 等编译）"

ssh "$TARGET" "
    cd $BDIR
    echo '--- 停止旧容器 ---'
    docker compose -f docker-compose.k1.yml down 2>/dev/null || true
    echo '--- 构建 + 启动 ---'
    docker compose -f docker-compose.k1.yml up -d --build
    echo '--- 等待就绪（首次需下载 ASR 模型 ~450MB）---'
    sleep 20
    echo '--- 健康检查 (HTTP) ---'
    curl -s http://127.0.0.1:80/health | python3 -m json.tool 2>/dev/null || \
        echo '⏳ 服务启动中，请稍候...'
    echo ''
    echo '--- 健康检查 (HTTPS) ---'
    curl -sk https://127.0.0.1:443/health | python3 -m json.tool 2>/dev/null || \
        echo '⏳ HTTPS 就绪中...'

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
echo "  HTTP 前端:     http://$TARGET:80"
echo "  HTTPS 前端:    https://$TARGET          (摄像头/麦克风)"
echo "  健康检查:       curl -k https://$TARGET/health"
echo "  性能监控:       curl -k https://$TARGET/stats"
echo "  ASR 语音:       POST /asr"
echo "  TTS 语音:       POST /tts"
echo ""
echo "  ⚠️  HTTPS 使用自签名证书，浏览器需点「高级」→「继续前往」"
echo ""
echo "  容器管理（在 K1 上执行）:"
echo "    cd $BDIR"
echo "    docker compose -f docker-compose.k1.yml logs -f"
echo "    docker compose -f docker-compose.k1.yml restart"
echo "    docker compose -f docker-compose.k1.yml down"

