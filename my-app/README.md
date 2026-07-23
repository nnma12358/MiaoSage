# 苗绣·识裳 (MiaoSage)

> 苗族服饰文化智能识别与交互系统 — 支持 K1 (riscv64) / x86_64 双平台纯本地部署

[![Platform](https://img.shields.io/badge/platform-riscv64-ff69b4)](https://www.spacemit.com/)
[![Platform](https://img.shields.io/badge/platform-x86__64-0078D4)](https://www.amd.com/)
[![Python](https://img.shields.io/badge/python-3.11|3.12-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-4%20containers-2496ED)](https://www.docker.com/)

---

## 📂 分支导航

> 根据你的部署场景选择对应分支：

| 分支 | 部署模式 | 目标平台 | 适用场景 |
|------|---------|---------|---------|
| **[main](https://github.com/nnma12358/MiaoSage/tree/main)** | 🏠 纯本地 · K1 | riscv64 (SpacemiT K1) | K1 开发板单机全功能部署 |
| **[x86](https://github.com/nnma12358/MiaoSage/tree/x86)** | 🖥️ 纯本地 · x86 | x86_64 (Linux/Windows) | PC/服务器单机全功能部署 |
| **[swarm](https://github.com/nnma12358/MiaoSage/tree/swarm)** | 🌐 分布式 Swarm | K1 + PC 混合 | K1 推理 + PC TTS，内存卸载 |

> 💡 **当前分支 (main)**: K1 纯本地部署。切换分支: `git checkout x86` 或 `git checkout swarm`

## 功能

| 功能 | 说明 |
|------|------|
| 🔍 **双模型目标检测** | ONNX Runtime 推理，银饰 6 类 + 服装 10 类 · 三模式 Pipeline |
| 🎤 **ASR 语音识别** | K1: SenseVoice / x86: faster-whisper 中文语音转文字 |
| 🔊 **TTS 语音合成** | K1: spacemit_tts / x86: MeloTTS 文字转语音 |
| 💬 **LLM 智能对话** | Ollama (qwen2.5-instruct) 苗族文化知识问答 + 幻觉过滤 |
| 📊 **性能监控** | CPU/内存/温度/延迟百分位实时监控 |

## 架构

> 纯本地容器编排：所有微服务 + Ollama 在同一台机器上运行，无需外部依赖。

```
浏览器 HTTPS :443 → Gateway (SPA + API 路由 + 幻觉过滤)
                      ├── /detect  → YOLO 双模型  :8000
                      │     ?mode=silver|clothes|pipeline
                      ├── /asr     → ASR   :8001
                      ├── /tts     → TTS   :8002
                      └── /chat    → Ollama :11434 (宿主机)
```

| 平台 | YOLO 推理引擎 | ASR 引擎 | TTS 引擎 |
|------|-------------|---------|---------|
| K1 (riscv64) | spacemit-ort | spacemit_asr (SenseVoice) | spacemit_tts |
| x86_64 | onnxruntime | faster-whisper (CTranslate2) | MeloTTS |

## 目录结构

> 当前分支 (main) 仅含 K1 + 共享服务代码。x86/swarm 专属文件见对应分支。

```
server/                     # Python 服务端
├── board_server.py          # 静态部署一体化服务器
├── gateway_server.py        # Docker API 网关 (Ollama 自动发现)
├── yolo_server.py           # YOLO 双模型微服务 (银饰6类+服装10类)
├── asr_server.py            # ASR 微服务 (K1 · spacemit_asr)
├── tts_server.py            # TTS 微服务 (K1 · spacemit_tts)
├── hallucination_filter.py  # LLM 幻觉过滤器
├── perf.py                  # 性能监控模块
└── requirements.txt         # 静态部署 pip 依赖
deploy/                     # 部署脚本
├── deploy-k1-docker-only.sh
├── deploy-k1-docker.sh
└── pack-send.sh
src/                        # Svelte 前端源码
build/                      # 前端构建产物
Dockerfile.yolo             # YOLO 检测容器 (spacemit-ort)
Dockerfile.asr              # ASR 语音识别容器
Dockerfile.tts              # TTS 语音合成容器
Dockerfile.k1               # API 网关容器
docker-compose.yml          # 纯本地编排 (默认)
docker-compose.k1.yml       # K1 专用编排 (含内存优化)
```

## 快速开始

### 环境要求

#### K1 (riscv64)
- **K1 板**: SpacemiT Muse Pi Pro (riscv64), Ubuntu 24.04, 8GB+ 内存
- **宿主机**: Ollama + qwen2.5-instruct 模型
- **NLP 模块**: `/home/bainbu/spacemit-demo/examples/NLP`
- **PC**: Node.js 18+ (仅构建前端)

#### x86_64 (PC / 服务器)
- **系统**: Linux (Ubuntu 22.04+ / Debian 12+) 或 Windows (WSL2)
- **CPU**: 4 核+, 16GB+ 内存（推荐 32GB）
- **GPU**: 可选（CUDA 12.1+ 可加速 ASR/TTS）
- **Docker**: 24.0+
- **Ollama**: 宿主机运行 + qwen2.5-instruct 模型

### Docker 多容器部署

#### K1 (riscv64)

```bash
cd /home/bainbu/miao-xiu-k1-d
docker compose up -d --build
```

#### x86_64

```bash
git checkout main
npm install && npm run build

# 放置 ONNX 模型文件
cp /path/to/Sliver.onnx my-app/
cp /path/to/Clothes.onnx my-app/

docker compose -f docker-compose.x86.yml up -d --build
```

访问 `https://<K1_IP>:443`（自签名证书，浏览器点"高级→继续"）。

### 容器管理

```bash
docker compose ps          # 查看状态
docker compose logs -f      # 全部日志
docker compose logs yolo    # 单容器日志
docker compose restart      # 重启全部
docker compose down         # 停止
```

> 💡 **平台切换**: K1 用默认 `docker-compose.yml`，x86 需 `git checkout x86` 后使用 `docker-compose.x86.yml`。
> API 完全兼容，前端无需任何修改。

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
| `/detect` | POST | 上传图片 → 苗族服饰/银饰检测 (支持 ?mode=silver\|clothes\|pipeline) |
| `/asr` | POST | 上传音频 → 文字 |
| `/tts` | POST | `{"text":"..."}` → WAV 音频 |
| `/chat` | POST | LLM 对话 |
| `/chat/stream` | POST | LLM 流式对话 (SSE) |
| `/health` | GET | 全服务健康检查 |
| `/stats` | GET | CPU/内存/温度/延迟百分位 |

## 技术栈

| 组件 | K1 (riscv64) | x86_64 |
|------|-------------|--------|
| 前端 | SvelteKit | SvelteKit |
| 后端 | FastAPI + Uvicorn | FastAPI + Uvicorn |
| 目标检测 | YOLOv8n ONNX (spacemit-ort) | YOLOv8n ONNX (onnxruntime) |
| 语音识别 | SenseVoice (spacemit_asr) | faster-whisper (CTranslate2) |
| 语音合成 | spacemit_tts | MeloTTS |
| 大语言模型 | Ollama + Qwen2.5-Instruct | Ollama + Qwen2.5-Instruct |
| 容器化 | Docker Compose (host 网络) | Docker Compose (host 网络) |
| 目标平台 | riscv64 (SpacemiT K1) | x86_64 (Linux/Windows) |

## 许可证

MIT
