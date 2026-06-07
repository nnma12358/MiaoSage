#!/bin/sh
# ============================================================
# 苗绣·识裳 — K1 板安装脚本
# 在进迭时空 K1 Muse Pi Pro 上直接运行
#
# 前置：
#   - Python 3.10+
#   - Ollama 已运行（ollama serve）
#   - 已拉取 qwen2.5-instruct 模型
#
# 用法：
#   cd /opt/miao-xiu
#   bash board-install.sh
# ============================================================
set -e

BOARD_ARCH=$(uname -m)
echo "========================================="
echo "  苗绣·识裳 — K1 板安装"
echo "  架构: $BOARD_ARCH"
echo "========================================="

# ---------- 1. 检查 Python ----------
echo "[1/4] 检查 Python..."
PYTHON=""
for py in python3 python3.11 python3.10 python3.12 python; do
    if command -v "$py" >/dev/null 2>&1; then
        PYTHON="$py"; break
    fi
done
[ -z "$PYTHON" ] && { echo "❌ 未找到 Python3"; exit 1; }
echo "  ✓ $($PYTHON --version)"

# ---------- 2. 创建 venv + 安装依赖 ----------
echo "[2/4] 创建虚拟环境 + 安装依赖..."

VENV_DIR="$(pwd)/venv"

# 检查 python3-venv 是否可用
if ! $PYTHON -m venv --help >/dev/null 2>&1; then
    echo "  安装 python3-venv..."
    sudo apt update && sudo apt install -y python3-venv python3-full
fi

# 删除旧 venv（如果之前安装失败）
if [ -d "$VENV_DIR" ]; then
    echo "  删除旧 venv..."
    rm -rf "$VENV_DIR"
fi

# 创建新 venv
$PYTHON -m venv "$VENV_DIR"
echo "  ✓ venv 创建完成"

# K1 板专用 SpacemiT ONNX Runtime（官方优化版，riscv64 预编译）
echo "  安装 spacemit-ort (ONNX Runtime)..."
"$VENV_DIR/bin/pip" install --index-url https://git.spacemit.com/api/v4/projects/33/packages/pypi/simple spacemit-ort

# 其余纯 Python 依赖
echo "  安装其余依赖..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install fastapi uvicorn Pillow requests python-multipart

# 验证
echo "  验证依赖..."
"$VENV_DIR/bin/python" -c "
import onnxruntime, fastapi, uvicorn, PIL, requests
print('  ✓ onnxruntime (spacemit-ort) ✓ fastapi ✓ uvicorn ✓ Pillow ✓ requests')
"


# ---------- 3. 检查 Ollama ----------
echo "[3/4] 检查 Ollama..."
if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "  ✓ Ollama 运行中"
    # 检查是否有 qwen2.5 模型
    if curl -sf http://127.0.0.1:11434/api/tags | grep -q "qwen2.5-instruct"; then
        echo "  ✓ qwen2.5-instruct 模型已就绪"
    else
        echo "  ⚠ 未找到 qwen2.5-instruct，正在拉取..."
        ollama pull qwen2.5-instruct || echo "  ⚠ 请手动: ollama pull qwen2.5-instruct"
    fi
else
    echo "  ⚠ Ollama 未运行，请先启动: ollama serve &"
fi

# ---------- 4. 生成启动脚本 ----------
echo "[4/4] 生成启动脚本..."

cat > start.sh << 'STARTSCRIPT'
#!/bin/sh
# 苗绣·识裳 启动脚本 (K1)
cd "$(dirname "$0")"
mkdir -p logs

# 使用 venv 中的 python
PYTHON="./venv/bin/python"

# 确保 venv 存在
if [ ! -f "$PYTHON" ]; then
    echo "❌ venv 未找到，请先运行: bash board-install-k1.sh"
    exit 1
fi

# 确保 Ollama 在运行
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "[启动] 等待 Ollama..."
    ollama serve &
    sleep 3
fi

echo "[启动] 端口 ${PORT:-80}"
exec $PYTHON server/board_server.py --port ${PORT:-80} "$@" 2>&1 | tee logs/server.log
STARTSCRIPT

chmod +x start.sh

echo ""
echo "========================================="
echo "  ✓ 安装完成！"
echo ""
echo "  启动服务:"
echo "    cd $(pwd) && bash start.sh"
echo ""
echo "  自定义端口:"
echo "    PORT=8080 bash start.sh"
echo ""
echo "  systemd 自启:"
echo "    sudo cp miao-xiu.service /etc/systemd/system/"
echo "    sudo systemctl enable --now miao-xiu"
echo "========================================="

# 生成 systemd service 文件
cat > miao-xiu.service << SERVICEOF
[Unit]
Description=苗绣·识裳
After=network.target ollama.service

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/server/board_server.py --port 80
Restart=always
RestartSec=10
Environment=PORT=80

[Install]
WantedBy=multi-user.target
SERVICEOF

echo "  systemd 文件已生成: miao-xiu.service"
