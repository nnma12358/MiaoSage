# 苗绣·识裳 (MiaoSage) — x86_64 边缘 AI

> 苗族服饰文化智能识别与交互系统 — x86_64 边缘 AI 轻量化部署

[![Platform](https://img.shields.io/badge/platform-x86__64-0078D4)](https://www.amd.com/)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-4%20containers-2496ED)](https://www.docker.com/)
[![Edge AI](https://img.shields.io/badge/edge--ai-optimized-4cd9b2)]()

---

## 📂 分支导航

| 分支 | 部署模式 | 目标平台 |
|------|---------|---------|
| **[main](https://github.com/nnma12358/MiaoSage/tree/main)** | K1 纯本地 | riscv64 |
| **[x86](https://github.com/nnma12358/MiaoSage/tree/x86)** | ⚡ 边缘 AI | x86_64 (当前) |
| **[swarm](https://github.com/nnma12358/MiaoSage/tree/swarm)** | 分布式 | K1 + PC |

---

## 🎯 边缘 AI 定位

面向 **AI 边缘开发**场景，极致轻量化：

| 指标 | 传统部署 | 边缘优化 | 节省 |
|------|---------|---------|:--:|
| TTS 内存 | MeloTTS ~2GB | edge-tts ~100MB | **95%** |
| ASR 模型 | Whisper-small ~500MB | Whisper-tiny ~75MB | **85%** |
| 容器总内存 | ~5.5GB | ~1.6GB | **71%** |

## 功能

| 功能 | 边缘实现 | 内存 |
|------|---------|:--:|
| 🔍 目标检测 | ONNX Runtime · 银饰6+服装10类 | ~800M |
| 🎤 语音识别 | faster-whisper tiny · int8 量化 | ~400M |
| 🔊 语音合成 | edge-tts 微软神经网络 | ~150M |
| 💬 智能对话 | Ollama qwen2.5-instruct · 幻觉过滤 | ~3G (宿主机) |
| 📊 性能监控 | CPU/内存/延迟百分位 | ~50M |

## 架构

```
x86_64 边缘 AI 主机
├── Gateway :443   → SPA + 路由 + 幻觉过滤 (~200M)
├── YOLO :8000     → ONNX Runtime · 2 threads (~800M)
├── ASR :8001      → faster-whisper tiny · int8 (~400M)
├── TTS :8002      → edge-tts · 微软 TTS API (~150M)
└── Ollama :11434  → qwen2.5-instruct (宿主机 ~3G)
```

## 快速开始

### 环境要求

- **系统**: Linux (Ubuntu 22.04+) / Windows WSL2 / macOS
- **CPU**: 4 核+, 8GB+ 内存（推荐 16GB）
- **Docker**: 24.0+
- **Ollama**: 宿主机安装

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-instruct
```

### 部署

```bash
git clone https://github.com/nnma12358/MiaoSage.git
cd MiaoSage/my-app && git checkout x86

# 一键部署（推荐）
bash deploy-x86.sh

# 或手动逐步执行：
npm install && npm run build
cp /path/to/Sliver.onnx . && cp /path/to/Clothes.onnx .
docker compose -f docker-compose.x86.yml up -d --build
```

访问 `https://localhost:443`（自签名证书 → 高级 → 继续访问）。

> 💡 `bash deploy-x86.sh --minimal` 仅启动 YOLO+Gateway (~1GB)

### 目录结构

```
my-app/
├── deploy-x86.sh                # 一键部署脚本
├── docker-compose.x86.yml       # 边缘 AI 编排
├── Dockerfile.x86-{yolo,asr,tts,gateway}
├── server/
│   ├── yolo_server.py           # YOLO 双模型 (共享)
│   ├── gateway_server.py        # API 网关 (共享)
│   ├── hallucination_filter.py  # LLM 幻觉过滤 (共享)
│   ├── perf.py                  # 性能监控 (共享)
│   ├── asr_server_x86.py        # faster-whisper tiny
│   └── tts_edge_server.py       # edge-tts
├── src/                         # Svelte 前端源码
└── build/                       # 前端构建产物
```

### 按需启动（省内存）

```bash
# 最小化：仅检测 + 对话 (~1G 容器)
docker compose -f docker-compose.x86.yml up -d yolo gateway

# 语音全功能
docker compose -f docker-compose.x86.yml up -d asr tts gateway

# GPU 加速 ASR（需 nvidia-container-toolkit）
WHISPER_DEVICE=cuda WHISPER_COMPUTE_TYPE=float16 \
  docker compose -f docker-compose.x86.yml up -d asr
```

### 容器管理

```bash
docker compose -f docker-compose.x86.yml ps
docker compose -f docker-compose.x86.yml logs -f yolo
docker compose -f docker-compose.x86.yml restart
docker compose -f docker-compose.x86.yml down
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/detect` | POST | 上传图片 → 检测 (`?mode=silver\|clothes\|pipeline`) |
| `/asr` | POST | 上传音频 → 文字 |
| `/tts` | POST | `{"text":"..."}` → MP3 音频 |
| `/chat` | POST | LLM 对话 |
| `/chat/stream` | POST | LLM 流式对话 (SSE) |
| `/health` | GET | 全服务健康检查 |
| `/stats` | GET | CPU/内存/延迟百分位 |

## 边缘优化详解

| 组件 | 选择 | 替代方案 | 权衡 |
|------|------|---------|------|
| **TTS** | edge-tts (~100M) | MeloTTS (~2G) | 需联网，音质最佳 |
| **ASR** | whisper-tiny (~75M) | whisper-small (~500M) | 识别率略低，延迟更低 |
| **YOLO** | ONNX 2线程 | ONNX 4线程 | 避免 CPU 与 ASR/LLM 争抢 |
| **网关** | 1 uvicorn worker | 多 worker | 边缘单用户足够 |

## 技术栈

| 组件 | 技术 | 定位 |
|------|------|------|
| 前端 | SvelteKit | 轻量响应式 |
| 后端 | FastAPI + Uvicorn | 异步高性能 |
| 目标检测 | YOLOv8n ONNX (onnxruntime) | CPU 推理 |
| 语音识别 | faster-whisper tiny (CTranslate2) | 边缘量化 |
| 语音合成 | edge-tts (微软神经网络) | 云端 TTS |
| 大语言模型 | Ollama + Qwen2.5-Instruct | 本地推理 |
| 容器化 | Docker Compose (host 网络) | 零开销网络 |

## 许可证

MIT
