# 苗绣·识裳 (MiaoSage)

> 苗族服饰文化智能识别与交互系统 — 基于 SpacemiT K1 (riscv64) 开发板

[![Platform](https://img.shields.io/badge/platform-riscv64-ff69b4)](https://www.spacemit.com/)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-4%20containers-2496ED)](https://www.docker.com/)

---

## 功能

| 功能 | 说明 |
|------|------|
| 🔍 **YOLOv8n 目标检测** | ONNX Runtime 推理，COCO 80 类物体识别 |
| 🎤 **ASR 语音识别** | SenseVoice 中文语音转文字 |
| 🔊 **TTS 语音合成** | spacemit_tts 文字转语音 |
| 💬 **LLM 智能对话** | Ollama (qwen2.5-instruct) 苗族文化知识问答 |
| 📊 **性能监控** | CPU/内存/温度/延迟百分位实时监控 |

## 架构

```
浏览器 HTTPS :443 → Gateway (SPA + API 路由)
                      ├── /detect  → YOLO  :8000
                      ├── /asr     → ASR   :8001
                      ├── /tts     → TTS   :8002
                      └── /chat    → Ollama :11434 (宿主机)
```

## 目录结构

```
server/                     # Python 服务端
├── board_server.py          # 静态部署一体化服务器
├── gateway_server.py        # Docker API 网关
├── yolo_server.py           # YOLO 微服务
├── asr_server.py            # ASR 微服务
├── tts_server.py            # TTS 微服务
├── perf.py                  # 性能监控模块
└── requirements.txt         # 静态部署 pip 依赖
deploy/                     # 部署脚本
├── deploy-k1-docker-only.sh # Docker 专用部署
├── deploy-k1-docker.sh      # 双模式部署 (static|docker)
└── pack-send.sh             # 打包发送
src/                        # Svelte 前端源码
build/                      # 前端构建产物
Dockerfile.{yolo,asr,tts,k1} # 四容器 Dockerfile
docker-compose.k1.yml       # 多容器编排
```

## 快速开始

### 环境要求

- **K1 板**: SpacemiT Muse Pi Pro (riscv64), Ubuntu 24.04, 8GB+ 内存
- **宿主机**: Ollama + qwen2.5-instruct 模型
- **NLP 模块**: `/home/bainbu/spacemit-demo/examples/NLP`
- **PC**: Node.js 18+ (仅构建前端)

### Docker 多容器部署（推荐）

```bash
# PC 端一键部署
bash deploy/deploy-k1-docker-only.sh root@192.168.x.x

# 或 K1 手动：
cd /home/bainbu/miao-xiu-k1-d
cp /home/bainbu/miao-xiu-k1/yolov8n.onnx .   # 复用模型
docker compose -f docker-compose.k1.yml build
docker compose -f docker-compose.k1.yml up -d
```

访问 `https://<K1_IP>:443`（自签名证书，浏览器点"高级→继续"）。

### 静态单进程部署

```bash
# PC 端
bash deploy/deploy-k1-docker.sh root@192.168.x.x static

# K1 手动：
cd /home/bainbu/miao-xiu-k1
pip install --break-system-packages -r server/requirements.txt
pip install --break-system-packages \
  --index-url https://git.spacemit.com/api/v4/projects/33/packages/pypi/simple \
  spacemit-ort
python3 server/board_server.py --port 8443
```

### 容器管理

```bash
docker compose -f docker-compose.k1.yml ps          # 查看状态
docker compose -f docker-compose.k1.yml logs -f      # 全部日志
docker compose -f docker-compose.k1.yml logs yolo    # 单容器日志
docker compose -f docker-compose.k1.yml restart      # 重启全部
docker compose -f docker-compose.k1.yml down         # 停止
```

### 按需启动

```bash
# 仅目标检测 + 对话
docker compose -f docker-compose.k1.yml up -d yolo gateway

# 仅语音功能
docker compose -f docker-compose.k1.yml up -d asr tts gateway
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端 SPA |
| `/detect` | POST | 上传图片 → YOLOv8n 检测结果 |
| `/asr` | POST | 上传音频 → 文字 |
| `/tts` | POST | `{"text":"..."}` → WAV 音频 |
| `/chat` | POST | LLM 对话 |
| `/chat/stream` | POST | LLM 流式对话 (SSE) |
| `/health` | GET | 全服务健康检查 |
| `/stats` | GET | CPU/内存/温度/延迟百分位 |

## 技术栈

| 组件 | 技术 |
|------|------|
| 前端 | SvelteKit |
| 后端 | FastAPI + Uvicorn |
| 目标检测 | YOLOv8n ONNX (spacemit-ort) |
| 语音识别 | SenseVoice (spacemit_asr) |
| 语音合成 | MeloTTS (spacemit_tts) |
| 大语言模型 | Ollama + Qwen2.5-Instruct |
| 容器化 | Docker Compose (4 容器 host 网络) |
| 目标平台 | riscv64 (SpacemiT K1) |

## 许可证

MIT
