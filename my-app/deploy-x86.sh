#!/bin/bash
# ============================================================
# 苗绣·识裳 — x86_64 边缘 AI 一键部署
# ============================================================
# 用法:
#   bash deploy-x86.sh              # 构建前端 + 启动全部服务
#   bash deploy-x86.sh --no-build   # 跳过前端构建
#   bash deploy-x86.sh --minimal    # 仅 YOLO + Gateway
#   bash deploy-x86.sh --down       # 停止全部服务
#
# 前置:
#   - Docker 24.0+
#   - Node.js 18+ (前端构建)
#   - Ollama + qwen2.5-instruct (宿主机)
#   - Sliver.onnx + Clothes.onnx 在项目根目录
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.x86.yml"
MODE="full"
NO_BUILD=false

# 解析参数
for arg in "$@"; do
    case "$arg" in
        --no-build) NO_BUILD=true ;;
        --minimal)  MODE="minimal" ;;
        --down)     docker compose -f "$COMPOSE_FILE" down; exit 0 ;;
        --logs)     docker compose -f "$COMPOSE_FILE" logs -f; exit 0 ;;
        --restart)  docker compose -f "$COMPOSE_FILE" restart; exit 0 ;;
        --help|-h)  echo "用法: $0 [--no-build|--minimal|--down|--logs|--restart]"; exit 0 ;;
    esac
done

echo "========================================="
echo "  苗绣·识裳 — x86_64 边缘 AI 部署"
echo "  模式: $([ "$MODE" = "minimal" ] && echo '最小化 (YOLO+Gateway)' || echo '全功能')"
echo "========================================="

# ====== [1] 检查前置条件 ======
echo "[1/4] 检查环境..."

if ! command -v docker &>/dev/null; then
    echo "❌ 未安装 Docker"; exit 1
fi
echo "  ✓ Docker $(docker --version | awk '{print $3}' | tr -d ',')"

# 检查模型文件
if [ ! -f "Sliver.onnx" ]; then
    echo "  ⚠ 未找到 Sliver.onnx (银饰模型)"
    MISSING_MODEL=1
fi
if [ ! -f "Clothes.onnx" ]; then
    echo "  ⚠ 未找到 Clothes.onnx (服装模型)"
    MISSING_MODEL=1
fi
if [ -n "$MISSING_MODEL" ]; then
    echo "  请放置模型文件到 $SCRIPT_DIR 后重试"
    echo "  cp /path/to/Sliver.onnx $SCRIPT_DIR/"
    echo "  cp /path/to/Clothes.onnx $SCRIPT_DIR/"
    exit 1
fi
echo "  ✓ 模型文件就绪"

# 检查 Ollama
if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "  ✓ Ollama 可用"
else
    echo "  ⚠ 未检测到 Ollama (LLM 对话将不可用)"
fi

# ====== [2] 构建前端 ======
if [ "$NO_BUILD" = false ]; then
    echo "[2/4] 构建前端..."
    if command -v npm &>/dev/null; then
        npm install --silent 2>/dev/null || npm install
        npm run build
        [ -f build/index.html ] || { echo "❌ 前端构建失败"; exit 1; }
        echo "  ✓ 前端已构建"
    else
        echo "  ⚠ 未安装 Node.js，跳过前端构建"
        echo "  安装: https://nodejs.org/ 或使用 --no-build"
    fi
else
    echo "[2/4] 跳过前端构建 (--no-build)"
    [ -f build/index.html ] || { echo "  ⚠ build/ 目录不存在，请先运行 npm run build"; }
fi

# ====== [3] 构建镜像 ======
echo "[3/4] 构建 Docker 镜像 (首次 ~10 分钟)..."

case "$MODE" in
    minimal)
        docker compose -f "$COMPOSE_FILE" build yolo gateway
        ;;
    full)
        docker compose -f "$COMPOSE_FILE" build
        ;;
esac
echo "  ✓ 镜像构建完成"

# ====== [4] 启动 ======
echo "[4/4] 启动容器..."

# 释放旧容器
docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true

case "$MODE" in
    minimal)
        docker compose -f "$COMPOSE_FILE" up -d yolo gateway
        ;;
    full)
        docker compose -f "$COMPOSE_FILE" up -d
        ;;
esac

echo "  等待服务就绪..."
sleep 15

# 健康检查
echo ""
echo "--- 容器状态 ---"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "--- 健康检查 ---"
curl -sk https://127.0.0.1:443/health 2>/dev/null | python3 -m json.tool 2>/dev/null || \
    echo "⏳ 服务启动中，请稍后访问 https://localhost:443"

echo ""
echo "===== ✓ 部署完成 ====="
echo ""
echo "  访问:     https://localhost:443"
echo "            (自签名证书 → 高级 → 继续访问)"
echo ""
echo "  管理:"
echo "    状态:   docker compose -f $COMPOSE_FILE ps"
echo "    日志:   docker compose -f $COMPOSE_FILE logs -f [yolo|asr|tts|gateway]"
echo "    重启:   docker compose -f $COMPOSE_FILE restart"
echo "    停止:   docker compose -f $COMPOSE_FILE down"
echo ""
if [ "$MODE" = "minimal" ]; then
    echo "  💡 当前为最小化模式 (YOLO+Gateway)，启动语音功能:"
    echo "     docker compose -f $COMPOSE_FILE up -d asr tts"
fi
