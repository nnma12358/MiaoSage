#!/bin/bash
# ============================================================
# 苗绣·识裳 → K1 板一键部署（venv 直跑 / 无 Docker）
# 用法: bash deploy/deploy-k1.sh root@192.168.x.x
#
# 前置：
#   - yolov8n.onnx 已放在项目根目录
#   - K1 板上已运行 Ollama（ollama serve）
# ============================================================
set -e

D="$(cd "$(dirname "$0")/.." && pwd)"
PKG="miao-xiu-k1"; PF="${PKG}.tar.gz"
BDIR="/opt/miao-xiu"

TARGET="${1:-}"
[ -z "$TARGET" ] && { echo "用法: $0 root@192.168.x.x"; exit 1; }

cd "$D"
echo "===== 苗绣·识裳 → K1 部署 ====="

# ---- [1/5] PC 构建前端 ----
echo "[1/5] 构建前端..."
npm install && npm run build
[ -f build/index.html ] || { echo "❌ build 失败"; exit 1; }

# ---- [2/5] 检查模型 ----
echo "[2/5] 检查 YOLO 模型..."
[ -f yolov8n.onnx ] || { echo "❌ 请将 yolov8n.onnx 放到项目根目录"; exit 1; }
echo "  ✓ yolov8n.onnx ($(du -h yolov8n.onnx | cut -f1))"

# ---- [3/5] 打包 ----
echo "[3/5] 打包..."
TMP=$(mktemp -d); DIR="$TMP/$PKG"
mkdir -p "$DIR/server"
cp -r build "$DIR/"
cp yolov8n.onnx "$DIR/server/"
cp server/board_server.py "$DIR/server/"
cp server/perf.py "$DIR/server/"
cp server/requirements.txt "$DIR/server/"
cp deploy/board-install-k1.sh "$DIR/"
cd "$TMP"; tar czf "$D/$PF" "$PKG"; cd "$D"; rm -rf "$TMP"
echo "  ✓ $PF ($(du -h "$PF"|cut -f1))"

# ---- [4/5] 传输 ----
echo "[4/5] 传输到 $TARGET ..."
scp "$PF" "$TARGET:$BDIR/"; rm -f "$PF"

# ---- [5/5] 安装 + 启动 ----
echo "[5/5] 安装依赖并启动..."
ssh "$TARGET" "
cd $BDIR
tar xzf $PF --strip-components=1 && rm $PF
bash board-install-k1.sh

# 先停止旧进程
pkill -f board_server.py 2>/dev/null || true
sleep 1

# 使用 venv python 后台启动
mkdir -p logs
nohup ./venv/bin/python server/board_server.py --port 80 > logs/server.log 2>&1 &
sleep 5
echo '--- 健康检查 ---'
curl -s http://127.0.0.1:80/health | python3 -m json.tool 2>/dev/null || \
    echo '⏳ 服务启动中（首次需下载 ASR 模型 ~450MB）'
"

echo ""
echo "===== ✓ 部署完成 ====="
echo "  前端:        http://$TARGET:80"
echo "  健康检查:    curl http://$TARGET:80/health"
echo "  性能监控:    curl http://$TARGET:80/stats"
echo "  日志:        ssh $TARGET 'tail -f $BDIR/logs/server.log'"
