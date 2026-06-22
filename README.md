# 🪡 苗绣·识裳 (MiaoSage)

<p align="center">
  <em>苗族服饰文化智能识别与交互系统</em><br>
  <sub>RISC-V 国产开发板 · 前后端一体化 · 双模式部署 · 四引擎 AI</sub>
</p>

<p align="center">
  <a href="https://www.spacemit.com/"><img src="https://img.shields.io/badge/platform-riscv64-ff69b4?style=for-the-badge&logo=riscv" alt="Platform"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.12-blue?style=for-the-badge&logo=python" alt="Python"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/docker-4_containers-2496ED?style=for-the-badge&logo=docker" alt="Docker"></a>
  <a href="https://svelte.dev/"><img src="https://img.shields.io/badge/frontend-SvelteKit-FF3E00?style=for-the-badge&logo=svelte" alt="SvelteKit"></a>
  <a href="https://github.com/nnma12358/MiaoSage"><img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License"></a>
</p>

---

## 📑 目录

- [✨ 核心特性](#-核心特性)
- [📦 克隆仓库](#-克隆仓库)
- [📁 项目结构](#-项目结构)
- [🚀 部署方式](#-部署方式)
- [🏗️ 系统架构](#-系统架构)
- [🖥️ 硬件要求](#-硬件要求)
- [🛠️ 技术栈](#-技术栈)
- [🔗 链接](#-链接)

---

## ✨ 核心特性

| 🎯 能力 | 🧠 引擎 | ⚡ 说明 |
|:---:|------|------|
| 👁️ **视觉识别** | YOLOv8n (ONNX) | 实时目标检测 · 80 类物体 · <1s 推理 |
| 👂 **语音识别** | SenseVoice | 中文语音 → 文字 · 高精度 ASR |
| 🗣️ **语音合成** | MeloTTS | 文字 → 自然语音 · 中文多音色 |
| 🧠 **智能对话** | Qwen2.5-Instruct | 苗族文化专家问答 · Ollama 部署 |
| 🔧 **模型微调** | Qwen2.5-0.5B LoRA | Unsloth 高效微调 · GGUF 量化 · 端侧运行 |

> 💡 **双模式部署**：Docker 多容器（8GB 内存）或单进程静态部署（2GB 即可），灵活适配不同硬件条件

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
│   ├── docker-compose.k1.yml         # 多容器编排
│   ├── Dockerfile.yolo               # YOLO 检测容器
│   ├── Dockerfile.asr                # ASR 语音识别容器
│   ├── Dockerfile.tts                # TTS 语音合成容器
│   ├── Dockerfile.k1                 # K1 静态部署容器
│   ├── .vscode/
│   │   └── extensions.json
│   ├── server/                       # Python 后端
│   │   ├── board_server.py           # 静态部署（单进程一体化）
│   │   ├── gateway_server.py         # Docker 部署（API 网关）
│   │   ├── yolo_server.py            # YOLO 检测微服务
│   │   ├── asr_server.py             # ASR 语音识别微服务
│   │   ├── tts_server.py             # TTS 语音合成微服务
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
│   ├── best.pt
│   ├── best_fp16.onnx
│   ├── clothes.pt
│   └── clothesfp16.onnx
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

### 🐳 方式一：Docker 多容器（推荐 · 8GB 内存）

```bash
cd my-app
bash deploy/deploy-k1-docker-only.sh root@192.168.x.x
```

> 四容器各司其职（YOLO / ASR / TTS / Gateway），易于维护和独立扩缩容。

### 📦 方式二：静态单进程（轻量 · 2GB 内存可用）

```bash
cd my-app
bash deploy/deploy-k1-docker.sh root@192.168.x.x static
```

> 单 Python 进程搞定一切，适合资源受限的嵌入式场景。

📖 **详细文档** → [my-app/README.md](my-app/README.md)

---

## 🏗️ 系统架构

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
│:8000 │  │ :8001    │  │ :8002   │        │ Qwen2.5-Inst. │
└──────┘  └──────────┘  └─────────┘        └──────────────┘
```

---

## 🖥️ 硬件要求

| 📋 项目 | 📐 规格 |
|---------|---------|
| 🛠️ 开发板 | **SpacemiT Muse Pi Pro (K1)** |
| 🏗️ 架构 | riscv64 |
| 💿 系统 |Bianbu LXQt V2.3.3 |
| 🧮 内存 | 8GB（Docker 模式）/ 2GB（静态模式） |
| 💾 存储 | 16GB+（模型文件约 3GB） |
| 🌐 网络 | host 模式 + 宿主机 Ollama |

---

## 🛠️ 技术栈

| 🧱 层次 | 🔧 技术选型 |
|---------|------------|
| 🎨 前端框架 | **SvelteKit** |
| ⚙️ 后端框架 | **FastAPI** + Uvicorn |
| 🧠 推理引擎 | ONNX Runtime (`spacemit-ort`) |
| 🤖 大语言模型 | Ollama + Qwen2.5-Instruct |
| 🐳 容器编排 | Docker Compose（4 容器） |
| 💻 目标平台 | RISC-V (riscv64) |
| 🐍 开发语言 | Python 3.12 + TypeScript |

---

## 🔗 链接

| 📌 | 链接 |
|:--:|------|
| 📖 | [应用详细文档](my-app/README.md) |
| 🐳 | [Docker 部署脚本](my-app/deploy/deploy-k1-docker-only.sh) |
| 📦 | [GitHub 仓库](https://github.com/nnma12358/MiaoSage) |

---

## 📄 许可证

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="MIT License"><br>
  <sub>MIT License © 2025 nnma12358</sub>
</p>