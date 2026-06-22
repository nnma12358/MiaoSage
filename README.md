# 苗绣·识裳 (MiaoSage)

> 苗族服饰文化智能识别与交互系统  
> 基于 SpacemiT K1 (riscv64) 开发板 · 前后端一体化 · 双模式部署

[![Platform](https://img.shields.io/badge/platform-riscv64-ff69b4)](https://www.spacemit.com/)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-4%20containers-2496ED)](https://www.docker.com/)
[![Frontend](https://img.shields.io/badge/frontend-SvelteKit-FF3E00)](https://svelte.dev/)

---

## 项目简介

**苗绣·识裳**是一个面向苗族服饰文化的智能识别与交互系统，运行于国产 RISC-V 开发板。用户可通过拍照识图、语音问答、文字对话等方式，学习苗族银饰、刺绣（苗绣）、蜡染、百鸟衣等传统服饰知识。

系统集成了四大 AI 能力：

| 能力 | 模型 | 说明 |
|------|------|------|
| 👁️ **视觉识别** | YOLOv8n ONNX | 实时目标检测，支持 80 类物体 |
| 👂 **语音识别** (ASR) | SenseVoice | 中文语音转文字 |
| 🗣️ **语音合成** (TTS) | MeloTTS | 文字转自然语音 |
| 🧠 **智能对话** (LLM) | Qwen2.5-Instruct | 苗族文化专家问答 |
| 🔧 **LLM 微调** | Qwen2.5-0.5B LoRA | Unsloth 微调 + GGUF 量化 |

## 克隆仓库

> ⚠️ 本项目使用 **Git LFS** 管理大模型文件，直接 `git clone` 只会拉取指针文件，**无法获取真实模型**。

```bash
# 1. 安装 Git LFS（如未安装）
#    Windows/macOS: https://git-lfs.com/
#    Linux: sudo apt install git-lfs

# 2. 初始化 Git LFS（仅需执行一次）
git lfs install

# 3. 克隆仓库（LFS 文件将自动下载）
git clone git@github.com:nnma12358/MiaoSage.git
cd MiaoSage

# 如果已克隆但缺少 LFS 文件，手动拉取
git lfs pull
```

## 项目结构

```
miao-sage/
├── .gitattributes
├── README.md                         # 本文件
├── translate_miao.py                 # 苗语翻译工具
├── verify_translations.py            # 翻译校验工具
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

## 部署方式

### 方式一：Docker 多容器（推荐 · 8GB 内存）

```bash
cd my-app
bash deploy/deploy-k1-docker-only.sh root@192.168.x.x
```

四容器各司其职，易于维护和独立扩缩。

### 方式二：静态单进程（轻量 · 2GB 内存可用）

```bash
cd my-app
bash deploy/deploy-k1-docker.sh root@192.168.x.x static
```

单 Python 进程搞定一切，适合资源受限场景。

> 📖 详细文档见 [my-app/README.md](my-app/README.md)

## 系统架构

```
┌──────────────────────────────────────────────────┐
│                    浏览器                         │
│               https://K1_IP:443                   │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────┐
│              Gateway (443 HTTPS)                  │
│          SPA 前端 + API 路由代理                   │
└──┬────────────┬────────────┬─────────────────────┘
   │            │            │
┌──▼──┐   ┌────▼────┐  ┌───▼───┐     ┌────────────┐
│YOLO │   │  ASR    │  │  TTS  │     │  Ollama    │
│:8000│   │ :8001   │  │ :8002 │     │ :11434     │
└─────┘   └─────────┘  └───────┘     └────────────┘
```

## 硬件要求

| 项目 | 规格 |
|------|------|
| 开发板 | SpacemiT Muse Pi Pro (K1) |
| 架构 | riscv64 |
| 系统 | Ubuntu 24.04 |
| 内存 | 8GB（Docker）/ 2GB（静态） |
| 存储 | 16GB+ |
| 网络 | host 模式 + 宿主机 Ollama |

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端框架 | SvelteKit |
| 后端框架 | FastAPI + Uvicorn |
| 推理引擎 | ONNX Runtime (spacemit-ort) |
| 大语言模型 | Ollama + Qwen2.5-Instruct |
| 容器编排 | Docker Compose |
| 目标平台 | RISC-V (riscv64) |
| 开发语言 | Python 3.12 + TypeScript |

## 链接

- 📖 [应用详细文档](my-app/README.md)
- 🐳 [Docker 部署脚本](my-app/deploy/deploy-k1-docker-only.sh)
- 📦 [GitHub 仓库](https://github.com/nnma12358/MiaoSage)

## 许可证

MIT License