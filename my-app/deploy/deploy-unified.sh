#!/bin/bash
# ============================================================
# 苗绣·识裳 — Docker 统一部署脚本（单容器方案）
# ============================================================
# 用法：
#   bash deploy/deploy-unified.sh                    # 仅图像识别
#   bash deploy/deploy-unified.sh --llm              # 含 LLM 对话
#   bash deploy/deploy-unified.sh root@192.168.x.x   # 远程部署
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

WITH_LLM=false
TARGET=""

for arg in "$@"; do
    case "$arg" in
        --llm) WITH_LLM=true ;;
        *) TARGET="$arg" ;;
    esac
done

cd "$PROJECT_DIR"

echo "===== 苗绣·识裳 — 统一容器部署 ====="

# ---- [1/3] 构建 ----
echo "[1/3] 构建统一镜像..."
docker build -f Dockerfile.unified -t miao-xiu:unified .
echo "  ✓ miao-xiu:unified"

# ---- [2/3] 远程传输（可选）----
if [ -n "$TARGET" ]; then
    echo "[2/3] 导出并传输到 $TARGET ..."
    docker save miao-xiu:unified | gzip > miao-xiu-unified.tar.gz
    scp miao-xiu-unified.tar.gz docker-compose.unified.yml "$TARGET:/opt/miao-xiu/"
    rm miao-xiu-unified.tar.gz
    ssh "$TARGET" "
        cd /opt/miao-xiu
        docker load < miao-xiu-unified.tar.gz
        rm miao-xiu-unified.tar.gz
    "
    echo "  ✓ 已传输"
fi

# ---- [3/3] 启动 ----
echo "[3/3] 启动服务..."

if [ -n "$TARGET" ]; then
    PROFILE=""
    $WITH_LLM && PROFILE="--profile llm"
    ssh "$TARGET" "cd /opt/miao-xiu && docker compose -f docker-compose.unified.yml $PROFILE up -d"
    echo ""
    echo "===== ✓ 部署完成 ====="
    echo "  前端: http://$TARGET"
    echo "  健康: http://$TARGET/health"
    echo "  性能: http://$TARGET/stats"
else
    PROFILE=""
    $WITH_LLM && PROFILE="--profile llm"
    
    # 如果启用 LLM，先拉取模型
    if $WITH_LLM; then
        docker compose -f docker-compose.unified.yml --profile llm up -d ollama
        echo "  等待 Ollama 就绪..."
        sleep 5
        docker compose -f docker-compose.unified.yml exec ollama ollama pull qwen2.5:0.5b 2>/dev/null || \
        docker compose -f docker-compose.unified.yml exec ollama ollama pull qwen2.5-instruct 2>/dev/null || \
        echo "  ⚠ 请手动拉取 LLM 模型"
        docker compose -f docker-compose.unified.yml --profile llm down ollama
    fi
    
    docker compose -f docker-compose.unified.yml $PROFILE up -d --build
    
    echo ""
    echo "===== ✓ 部署完成 ====="
    echo "  前端: http://localhost"
    echo "  健康: http://localhost/health"
    echo "  性能: http://localhost/stats"
    echo ""
    if $WITH_LLM; then
        echo "  LLM 模型拉取（首次）："
        echo "    docker compose -f docker-compose.unified.yml exec ollama ollama pull qwen2.5:0.5b"
    fi
fi
