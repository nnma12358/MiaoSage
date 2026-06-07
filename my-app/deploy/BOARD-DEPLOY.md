# 苗绣·识裳 — 开发板部署指南（无 Docker / 无 npm）

## 架构概览

```
┌──────────────────────────────────────────────────┐
│              开发板 (K1 / ARM / RISC-V)           │
│                                                    │
│   python server/unified_server.py                  │
│   ┌──────────────────────────────────────────┐    │
│   │  FastAPI (端口 80)                        │    │
│   │  ├─ /           → 前端 SPA (build/)      │    │
│   │  ├─ /detect     → YOLOv8n 目标检测 API   │    │
│   │  └─ /health     → 健康检查               │    │
│   └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

## 前置条件

| 组件 | 要求 |
|------|------|
| Python | ≥ 3.10 |
| pip | 可用（`python -m pip`） |
| 网络 | pip 安装依赖 + 首次下载 yolov8n.pt (~6MB) |
| 存储 | ~200MB（依赖 + 模型 + 前端） |

## 快速部署

### 方式 1：一键远程部署（推荐）

```bash
# 在 PC 上执行（需要 SSH 免密或输入密码）
./deploy/deploy-board.sh root@192.168.x.x
```

### 方式 2：手动部署

**PC 端：**

```bash
# 1. 构建前端 + 打包
./deploy/package.sh
# 生成: miao-xiu-board.tar.gz

# 2. 传输到开发板
scp miao-xiu-board.tar.gz root@<开发板IP>:/opt/
```

**开发板端：**

```bash
# 3. 解压
cd /opt
tar xzf miao-xiu-board.tar.gz
cd miao-xiu-board

# 4. 安装依赖
bash board-install.sh

# 5. 启动
bash start.sh
```

## 管理命令

```bash
# 启动（默认端口 80）
bash start.sh

# 自定义端口
bash start.sh --port 8080

# 自定义模型
bash start.sh --model /path/to/custom_yolo.pt

# 查看日志
tail -f logs/server.log

# 停止
pkill -f unified_server.py
```

## 设置开机自启

```bash
cat > /etc/systemd/system/miao-xiu.service << 'EOF'
[Unit]
Description=苗绣·识裳
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/miao-xiu-board
ExecStart=/opt/miao-xiu-board/start.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable miao-xiu --now
```

## 访问

```
前端界面：http://<开发板IP>
API 健康：http://<开发板IP>/health
```

## 启用 NPU 加速（进迭时空 K1）

```bash
# 1. 安装 SpacemiT NN SDK（从官方获取）
# 2. 转换模型
spacemit-nn-converter --model yolov8n.pt --output yolov8n.smnn

# 3. 启动时启用 NPU
export SPACEMIT_NPU_ENABLED=1
bash start.sh --model yolov8n.smnn
```

## 常见问题

| 问题 | 解决 |
|------|------|
| `python: not found` | `ln -s /usr/bin/python3 /usr/bin/python` |
| `pip: not found` | 用 `python -m pip install ...` |
| 端口 80 被占用 | `bash start.sh --port 8080` |
| 首次启动慢 | YOLO 模型首次下载需 ~30s，后续秒启动 |
| 内存不足 | 减少 `imgsz` 参数或使用 yolov8n 模型 |
| 前端无法访问 | 检查防火墙：`iptables -A INPUT -p tcp --dport 80 -j ACCEPT` |
