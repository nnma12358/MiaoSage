#!/bin/bash
# ============================================================
# 苗绣·识裳 — K1 单板全功能部署
# ============================================================
# 用法：
#   bash deploy/deploy-k1-docker.sh root@192.168.x.x           # 纯本地
#   bash deploy/deploy-k1-docker.sh root@192.168.x.x --llm     # 含 Ollama
#   OLLAMA_HOST=192.168.1.50 bash deploy/deploy-k1-docker.sh .. # 外接PC
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BDIR="/opt/miao-xiu"

TARGET=""
WITH_LLM=false

for arg in "$@"; do
    case "$arg" in
        --llm) WITH_LLM=true ;;
        *) TARGET="$arg" ;;
    esac
done

[ -z "$TARGET" ] && { echo "用法: $0 root@192.168.x.x [--llm]"; exit 1; }

cd "$PROJECT_DIR"

echo "========================================="
echo "  苗绣·识裳 — K1 单板全功能部署"
echo "  目标: $TARGET"
if $WITH_LLM; then
    echo "  模式: LLM 对话（Ollama + qwen2.5:0.5b）"
    echo "  要求: K1 6GB+ 内存"
else
    echo "  模式: 纯本地（YOLO + 内置知识库）"
fi
echo "========================================="

# ---- [1/4] PC 构建前端 ----
echo "[1/4] PC 构建前端..."
npm install --silent && npm run build
[ -f build/index.html ] || { echo "❌ build 失败"; exit 1; }
echo "  ✓ 前端已构建"

# ---- [2/4] 传输到 K1 ----
echo "[2/4] 传输文件到 K1..."
ssh "$TARGET" "mkdir -p $BDIR/server" 2>/dev/null || true

rsync -avz --delete build/ "$TARGET:$BDIR/build/" 2>/dev/null || \
    scp -r build "$TARGET:$BDIR/"

scp Dockerfile.k1 docker-compose.k1.yml "$TARGET:$BDIR/"
scp server/board_server.py server/perf.py server/requirements.txt "$TARGET:$BDIR/server/"
echo "  ✓ 文件已传输"

# ---- [3/4] K1 构建并启动 ----
echo "[3/4] K1 构建镜像并启动..."

if $WITH_LLM; then
    ssh "$TARGET" "
        cd $BDIR
        echo '--- 停止旧容器 ---'
        docker compose -f docker-compose.k1.yml down 2>/dev/null || true
        echo '--- 构建镜像 ---'
        docker compose -f docker-compose.k1.yml build
        echo '--- 启动服务（含 Ollama）---'
        docker compose -f docker-compose.k1.yml --profile llm up -d
        echo '--- 等待 Ollama 就绪 ---'
        sleep 15
        echo '--- 拉取 LLM 模型（qwen2.5:0.5b, ~400MB）---'
        docker compose -f docker-compose.k1.yml exec ollama ollama pull qwen2.5:0.5b || \
            echo '⚠ 模型拉取失败，请手动执行：docker compose -f docker-compose.k1.yml exec ollama ollama pull qwen2.5:0.5b'
        echo '--- 功能自检 ---'
        curl -s http://127.0.0.1/health | python3 -m json.tool 2>/dev/null
    "
else
    ssh "$TARGET" "
        cd $BDIR
        echo '--- 停止旧容器 ---'
        docker compose -f docker-compose.k1.yml down 2>/dev/null || true
        echo '--- 构建镜像 ---'
        docker compose -f docker-compose.k1.yml build
        echo '--- 启动服务（纯本地模式）---'
        docker compose -f docker-compose.k1.yml up -d
        echo '--- 等待就绪 ---'
        sleep 10
        echo '--- 功能自检 ---'
        curl -s http://127.0.0.1/health | python3 -m json.tool 2>/dev/null || \
            echo '⏳ 服务启动中，请稍候...'
    "
fi

echo ""
echo "===== ✓ 部署完成 ====="
echo "  前端:        http://$TARGET"
echo "  健康+功能:   curl http://$TARGET/health"
echo "  性能监控:    curl http://$TARGET/stats"
echo ""
if $WITH_LLM; then
    echo "  功能清单:"
    echo "    ✅ 苗绣图像识别   (YOLOv8n ONNX)"
    echo "    ✅ LLM 智能对话   (Ollama qwen2.5:0.5b)"
    echo "    ✅ 实时性能监控   (CPU/内存/延迟)"
else
    echo "  功能清单:"
    echo "    ✅ 苗绣图像识别   (YOLOv8n ONNX)"
    echo "    ✅ 文化智能问答   (内置知识库)"
    echo "    ✅ 实时性能监控   (CPU/内存/延迟)"
    echo ""
    echo "  启用 LLM 对话:"
    echo "    ssh $TARGET 'cd $BDIR && docker compose -f docker-compose.k1.yml --profile llm up -d'"
    echo "    ssh $TARGET 'cd $BDIR && docker compose -f docker-compose.k1.yml exec ollama ollama pull qwen2.5:0.5b'"
fi
echo ""
echo "  管理命令（在 K1 上执行）:"
echo "    cd $BDIR"
echo "    docker compose -f docker-compose.k1.yml logs -f"
echo "    docker compose -f docker-compose.k1.yml restart"
echo "    docker compose -f docker-compose.k1.yml down"

