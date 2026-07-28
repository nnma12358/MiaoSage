# 🪡 苗绣·识裳 (MiaoSage)

<p align="center">
  <em>苗族服饰文化智能识别与交互系统</em><br>
  <sub>进迭时空 SpacemiT K1 (RISC-V) · 前后端一体化 · 三模式部署 · 四引擎 AI</sub>
</p>

<p align="center">
  <a href="https://www.spacemit.com/"><img src="https://img.shields.io/badge/platform-riscv64-ff69b4?style=for-the-badge&logo=riscv" alt="Platform"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.12-blue?style=for-the-badge&logo=python" alt="Python"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/docker-5_containers-2496ED?style=for-the-badge&logo=docker" alt="Docker"></a>
  <a href="https://github.com/nnma12358/MiaoSage/tree/swarm"><img src="https://img.shields.io/badge/swarm-K1%2BPC-orange?style=for-the-badge&logo=swarm" alt="Swarm"></a>
  <a href="https://svelte.dev/"><img src="https://img.shields.io/badge/frontend-SvelteKit-FF3E00?style=for-the-badge&logo=svelte" alt="SvelteKit"></a>
  <a href="https://github.com/nnma12358/MiaoSage"><img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License"></a>
</p>

---

## 📑 目录

- [✨ 核心特性](#-核心特性)
- [📦 克隆仓库](#-克隆仓库)
- [📁 项目结构](#-项目结构)
- [🚀 部署方式](#-部署方式)
- [🐝 Swarm 分布式部署](#-swarm-分布式部署)
- [🏗️ 系统架构](#-系统架构)
- [🖥️ 硬件要求](#-硬件要求)
- [🛠️ 技术栈](#-技术栈)
- [🔗 链接](#-链接)

---

## ✨ 核心特性

| 🎯 能力 | 🧠 引擎 | ⚡ 说明 |
|:---:|------|------|
| 👁️ **视觉识别** | YOLOv8n 双模型 (ONNX) | 银饰 8 类 + 服装 2 类 · Pipeline 串行 · <1s 推理 |
| 👂 **语音识别** | SenseVoice | 中文语音 → 文字 · 高精度 ASR |
| 🗣️ **语音合成** | edge-tts / MeloTTS | 文字 → 自然语音 · K1 轻量联网 / 离线本地 / 可卸载到 PC |
| 🧠 **智能对话** | Qwen2.5-0.5B LoRA | 苗族文化专家问答 · Ollama 部署 · 模型自动发现 · K1 推理优化 |
| 🔧 **模型微调** | Qwen2.5-0.5B LoRA | Unsloth 高效微调 · GGUF 量化 · 端侧运行 |

> 💡 **三模式部署**：Swarm 分布式（K1+PC） / Docker 多容器（8GB） / 单进程静态（2GB），灵活适配不同硬件条件

---

## 📖 项目简介

**苗绣·识裳** 是一个面向苗族服饰文化的智能识别与交互系统，运行于 **国产 RISC-V 开发板**。用户可通过拍照识图、语音问答、文字对话等方式，学习苗族银饰、刺绣（苗绣）、蜡染、百鸟衣等传统服饰知识。

---

## 📦 克隆仓库

> ⚠️ **重要提示**：本项目使用 **Git LFS** 管理大模型文件（合计约 2GB+）。直接 `git clone` 只会拉取指针文件，**必须执行以下步骤才能获取真实模型文件**。

```bash
# 第一步：安装 Git LFS（仅需一次）
#   • Windows / macOS → https://git-lfs.com/
#   • Linux → sudo apt install git-lfs

# 第二步：初始化 Git LFS（仅需一次）
git lfs install

# 第三步：克隆仓库（LFS 大文件自动下载）
git clone git@github.com:nnma12358/MiaoSage.git
cd MiaoSage

# 🔄 如果已克隆但文件是"指针"状态，运行：
git lfs pull
```

---

## 📁 项目结构

```
miao-sage/
├── .gitattributes
├── README.md                         # 本文件
├── my-app/                           # 主应用
│   ├── .dockerignore
│   ├── .gitattributes
│   ├── .gitignore
│   ├── .npmrc
│   ├── README.md                     # 应用详细文档
│   ├── package.json
│   ├── package-lock.json
│   ├── svelte.config.js
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── docker-compose.k1.yml         # K1 多容器编排
│   ├── docker-compose.swarm.yml      # Swarm 分布式编排（K1 + PC）
│   ├── .env.swarm.example            # Swarm 环境变量模板
│   ├── Dockerfile.k1                 # K1 静态部署容器
│   ├── Dockerfile.yolo               # YOLO 检测容器
│   ├── Dockerfile.asr                # ASR 语音识别容器
│   ├── Dockerfile.tts                # TTS 语音合成容器（K1 端）
│   ├── Dockerfile.swarm-pc           # PC 端 TTS 容器（swarm 用）
│   ├── .vscode/
│   │   └── extensions.json
│   ├── server/                       # Python 后端
│   │   ├── board_server.py           # 静态部署（单进程一体化）
│   │   ├── gateway_server.py         # Docker 部署（API 网关）
│   │   ├── yolo_server.py            # YOLO 检测微服务
│   │   ├── asr_server.py             # ASR 语音识别微服务（K1）
│   │   ├── tts_server.py             # TTS 语音合成微服务（K1）
│   │   ├── asr_whisper.py            # Whisper ASR（PC 可选）
│   │   ├── tts_pc.py                 # TTS PC 服务（MeloTTS）
│   │   ├── perf.py                   # 性能监控模块
│   │   └── requirements.txt
│   ├── src/                          # SvelteKit 前端源码
│   │   ├── app.d.ts
│   │   ├── app.html
│   │   ├── lib/
│   │   │   ├── index.ts
│   │   │   └── assets/
│   │   │       └── favicon.svg
│   │   └── routes/
│   │       ├── +layout.js
│   │       ├── +layout.svelte
│   │       └── +page.svelte
│   ├── static/
│   │   └── robots.txt
│   └── deploy/                       # 部署脚本
│       ├── deploy-k1-docker-only.sh
│       ├── deploy-k1-docker.sh
│       └── pack-send.sh
├── CV/                               # 计算机视觉模型
│   ├── best.pt / best_fp16.onnx      # 苗族银饰检测（8 类）
│   ├── clothes.pt / clothesfp16.onnx # 苗族服装检测（2 类）
│   ├── dataset.yaml                  # 银饰数据集配置
│   └── clothes.yaml                  # 服装数据集配置
└── LLM/                              # 大语言模型微调
    └── train-qwen2.5 0.5b/           # Qwen2.5-0.5B 苗族文化 LoRA 微调
        ├── train_miao_qwen0.5b.py    # 训练脚本 (Unsloth)
        ├── merge_peft_fp16.py        # LoRA 合并脚本
        ├── miao_qwen_lora_0.5b/      # LoRA 适配器权重
        │   ├── adapter_model.safetensors
        │   ├── adapter_config.json
        │   ├── tokenizer.json
        │   ├── checkpoint-300/       # 训练检查点
        │   ├── checkpoint-500/
        │   └── checkpoint-600/
        ├── miao_qwen_merged_0.5b_fp16/  # 合并后 FP16 模型
        │   ├── model.safetensors
        │   ├── config.json
        │   └── tokenizer.json
        ├── models/                   # GGUF 量化模型
        │   ├── miao_qwen_0.5b_f16.gguf
        │   └── miao_qwen_0.5b_q4km.gguf
        └── unsloth_compiled_cache/   # Unsloth 编译缓存
```

---

## 🚀 部署方式

### � 方式一：Swarm 分布式（推荐 · K1 + PC 协同）

> TTS 卸载到 PC，K1 专注 YOLO + ASR + LLM，释放 ~1.5GB 内存给 Ollama。
>
> 详见 [🐝 Swarm 分布式部署](#-swarm-分布式部署) 完整文档。

### 🐳 方式二：Docker 多容器（8GB 内存）

```bash
cd my-app
docker compose -f docker-compose.k1.yml up -d --build
```

> 五容器各司其职（YOLO / ASR / TTS edge-tts + MeloTTS / Gateway），或通过 Swarm 编排卸载 TTS 到 PC。

### 📦 方式三：静态单进程（轻量 · 2GB 内存可用）

```bash
cd my-app
bash deploy/deploy-k1-docker.sh root@192.168.x.x static
```

> 单 Python 进程搞定一切，适合资源受限的嵌入式场景。

📖 **详细文档** → [my-app/README.md](my-app/README.md)

---

## 🐝 Swarm 分布式部署

> **适用场景**：有一台 PC（x86_64，Windows/Linux）与 K1 在同一局域网，希望将 TTS 等重计算任务卸载到 PC 以释放 K1 内存。

### 架构概览

```
┌──── K1 板 (riscv64) ─────────────────┐     ┌──── PC (x86_64) ────┐
│                                       │     │                      │
│  🚪 Gateway  :443  ← SPA + API 路由   │     │  🗣️ TTS  :8002     │
│  👁️ YOLO    :8000 ← 双模型物体检测    │     │  MeloTTS            │
│  👂 ASR     :8001 ← SenseVoice 语音   │     │                      │
│  🧠 Ollama  :11434                    │     │                      │
│                                       │     │                      │
└───────────────────────────────────────┘     └──────────────────────┘
         ▲                                            ▲
         │         LAN (192.168.x.x)                  │
         └────────────────┬───────────────────────────┘
                          │
                    🌐 浏览器 HTTPS
```

> **关键变化**：TTS 从 K1 移除，K1 节省 ~1.5GB 内存，Ollama 可使用更大上下文窗口。

### 第一步：配置环境变量

```bash
cd my-app

# 复制环境变量模板
cp .env.swarm.example .env.swarm

# 编辑 PC_IP 为你的 PC 实际 IP 地址
# 例如：PC_IP=192.168.1.100
```

`.env.swarm` 关键配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PC_IP` | `192.168.1.100` | **必改** — PC 的局域网 IP |
| `TTS_LANGUAGE` | `ZH` | MeloTTS 语言代码 |
| `TTS_SPEAKER` | `0` | MeloTTS 说话人 ID（0=默认女声） |
| `TTS_SPEED` | `1.0` | 语速 (0.5-2.0) |
| `TTS_MAX_LEN` | `300` | 单次合成最大字符数（PC 端可设更大） |
| `OLLAMA_MODEL` | （自动发现） | K1 端 Ollama 模型名，留空自动匹配 miao*/qwen* |
| `YOLO_MODEL` | `yolov8n.onnx` | YOLO 检测模型 |

### 第二步：PC 端启动 TTS

```bash
# 在 PC 上执行（需要 Docker）
cd my-app
docker compose -f docker-compose.swarm.yml --profile pc up -d --build

# 验证 TTS 就绪
curl http://localhost:8002/health
```

### 第三步：K1 端启动核心服务

```bash
# 在 K1 上执行
cd /path/to/MiaoSage/my-app
docker compose -f docker-compose.swarm.yml --profile k1 up -d --build

# 验证全链路
curl -k https://localhost/health
```

### 第四步：浏览器访问

```
https://<K1_IP>:443
```

前端照常使用语音功能——ASR 在 K1 本地处理，TTS 自动路由到 PC 合成后返回音频流，用户无感知。

### 故障排查

| 现象 | 可能原因 | 解决 |
|------|---------|------|
| TTS 无响应 | PC_IP 配置错误 | `ping <PC_IP>` 确认 K1 能访问 PC |
| TTS 合成失败 | MeloTTS 模型未下载或路径错误 | 检查 PC 端模型文件，确认 `/app/models` 挂载正确 |
| 网关 503 | PC 防火墙阻止 8002 端口 | `ufw allow 8002` 或关闭防火墙测试 |
| PC 容器启动失败 | 镜像拉取慢 | 挂代理或手动 `docker pull python:3.11-slim-bookworm` |

### TTS 后端选择

| 模式 | 后端 | 网络 | 音质 | 内存 | 说明 |
|------|------|:--:|:--:|------|------|
| **K1 默认** | edge-tts | 需联网 | ⭐⭐⭐⭐⭐ | ~100MB | 微软免费 API，纯 Python 无架构依赖 |
| **K1 离线** | MeloTTS | 离线 | ⭐⭐⭐⭐ | ~1.5GB | spacemit-ort 推理，`--profile offline` |
| **Swarm PC** | MeloTTS | 离线 | ⭐⭐⭐⭐ | ~2GB | Docker 容器化，Torch CPU 推理 |

> **推荐**：日常使用 K1 默认 edge-tts（轻量高音质），无网络时切换 `--profile offline` 用 MeloTTS，内存紧张时 Swarm 卸载 TTS 到 PC。

#### K1 切换为 MeloTTS 离线模式

```bash
# 停止 edge-tts，启动 MeloTTS（需先构建 Dockerfile.tts）
docker compose -f docker-compose.k1.yml --profile offline up -d --build tts
```

#### Swarm PC 端 MeloTTS

模型首次启动时自动下载到 `/app/models`，建议挂载 volume 持久化：

```yaml
# docker-compose.swarm.yml 中 tts-pc 的 volumes
tts-pc:
  volumes:
    - melo-models:/app/models
```

---

## 🏗️ 系统架构

### K1 单机模式（Docker / 静态）

<p align="center">
  <em>浏览器 HTTPS 请求 → Gateway 统一入口 → 微服务路由分发</em>
</p>

```
┌──────────────────────────────────────────────────┐
│                     🌐 浏览器                      │
│               https://K1_IP:443                   │
└────────────────────┬─────────────────────────────┘
                     │  HTTPS
┌────────────────────▼─────────────────────────────┐
│           🚪 Gateway (443 HTTPS)                  │
│        SPA 前端分发  +  API 路由代理               │
└──┬────────────┬────────────┬─────────────────────┘
   │            │            │
   ▼            ▼            ▼              ┌──────────────┐
┌──────┐  ┌──────────┐  ┌─────────┐        │  🧠 Ollama    │
│👁️YOLO│  │ 👂 ASR   │  │ 🗣️ TTS │        │  :11434       │
│双模型 │  │ :8001    │  │ :8002   │        │ Qwen2.5-Inst. │
│:8000 │  └──────────┘  └─────────┘        └──────────────┘
│silver│
│+cloth│
└──────┘
```

---

## 🎛️ 模型配置

### 自动发现机制

网关启动时自动查询 Ollama 已注册模型，按优先级匹配：

```
OLLAMA_MODEL 环境变量 → 关键字匹配 (miao > qwen > ...) → 首个可用 → 兜底
```

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `OLLAMA_MODEL` | 显式指定模型名（跳过自动发现） | 空 |
| `OLLAMA_MODEL_KEYWORDS` | 自动发现关键字（逗号分隔） | `miao,qwen` |
| `OLLAMA_HOST` | Ollama 服务地址 | `http://127.0.0.1:11434` |

```bash
# 查看可用模型与当前选用
curl -k https://127.0.0.1:443/ollama/models

# 热切换模型后刷新
curl -k -X POST https://127.0.0.1:443/ollama/refresh
```

### K1 推理优化 (Modelfile)

| 参数 | 值 | 说明 |
|------|-----|------|
| `num_ctx` | 512 | 上下文窗口 — CPU 推理每减 256 tokens 提速 ~30% |
| `num_predict` | 150 | 最大输出 tokens |
| `num_thread` | 2 | K1 4 核留 2 核给 OS + Docker 四容器 |
| `temperature` | 0.6 | 0.5B 小模型需更高随机性防 token 重复死循环 |
| `repeat_penalty` | 1.25 | 增强重复惩罚，打断输出循环 |
| `top_k` / `top_p` | 50 / 0.85 | 核采样参数，增加输出多样性 |

> 📖 完整 Modelfile 参见 [`LLM/train-qwen2.5 0.5b/models/Modelfile`](LLM/train-qwen2.5%200.5b/models/Modelfile)

---

## 🖥️ 硬件要求

| 📋 项目 | 📐 规格 |
|---------|---------|
| 🛠️ 开发板 | **SpacemiT Muse Pi Pro (K1)** + **PC**（Swarm 模式） |
| 🏗️ 架构 | riscv64 |
| 💿 系统 |Bianbu LXQt V2.3.3 |
| 🧮 内存 | K1: 8GB / PC: 4GB+（Swarm 模式） |
| 💾 存储 | 16GB+（模型文件约 3GB） |
| 🌐 网络 | host 模式 + 宿主机 Ollama + Swarm 跨设备 LAN |

---

## 🛠️ 技术栈

| 🧱 层次 | 🔧 技术选型 |
|---------|------------|
| 🎨 前端框架 | **SvelteKit** |
| ⚙️ 后端框架 | **FastAPI** + Uvicorn |
| 🧠 推理引擎 | ONNX Runtime (`spacemit-ort`) |
| 🤖 大语言模型 | Ollama + Qwen2.5-Instruct |
| 🐳 容器编排 | Docker Compose（5 容器 · Swarm 模式） |
| 💻 目标平台 | RISC-V (riscv64) + x86_64（Swarm PC） |
| 🐍 开发语言 | Python 3.12 + TypeScript |

---

## 🔗 链接

| 📌 | 链接 |
|:--:|------|
| 📖 | [应用详细文档](my-app/README.md) |
| � | [Swarm 分布式编排](my-app/docker-compose.swarm.yml) |
| 🐳 | [Docker 部署脚本](my-app/deploy/deploy-k1-docker-only.sh) |
| 📦 | [GitHub 仓库](https://github.com/nnma12358/MiaoSage) |
| 🌿 | [Swarm 分支](https://github.com/nnma12358/MiaoSage/tree/swarm) |

---

## 📄 许可证

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="MIT License"><br>
  <sub>MIT License © 2026 nnma12358</sub>
</p>
