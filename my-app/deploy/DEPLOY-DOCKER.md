# 苗绣·识裳 — Docker 部署指南（LLM 联动版）

## 架构

```
┌──────────────────────────────────────────────────────────┐
│                    docker compose                         │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │  nginx   │  │   yolo   │  │   llm    │  │ ollama  │  │
│  │  :80     │→ │  :8000   │  │  :8001   │→ │ :11434  │  │
│  │ 前端+代理 │  │ YOLOv8n │  │ Qwen2.5  │  │ 推理引擎 │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │
│   /detect ────→ yolo:8000                                 │
│   /chat ──────→ llm:8001 ──→ ollama:11434                │
│   /*    ────→ 静态 SPA                                    │
└──────────────────────────────────────────────────────────┘
```

## 快速开始

### 方式 1：完整版（含 Ollama + Qwen2.5，推荐）

```bash
# 1. PC 构建前端
npm install && npm run build

# 2. 启动所有服务
docker compose up -d

# 3. 拉取 Qwen2.5 模型（首次运行，~500MB）
docker compose exec ollama ollama pull qwen2.5:0.5b

# 4. 访问
#    http://localhost         前端
#    http://localhost/health  YOLO 健康
#    http://localhost/health/llm  LLM 健康
```

### 方式 2：一键远程部署到开发板

```bash
# PC 上执行（自动构建 → 打包 → 传输 → SSH 启动）
npm run deploy -- root@192.168.1.100 board

# 或完整模式（含 Ollama，需开发板支持）
npm run deploy -- root@192.168.1.100 full
```

### 方式 3：开发板精简版（无 Ollama，LLM 直连）

```bash
# 在开发板上
docker compose -f docker-compose.board.yml up -d
```

## 交互流程

```
用户拍照 → YOLOv8n 检测 → 展示识别结果
                              ↓
                   自动调用 LLM 获取文化解说
                              ↓
                    Qwen2.5 生成苗族文化解读
                              ↓
                    对话区展示 AI 回复

用户提问 → /chat API → LLM → Qwen2.5 → 回复
```

## 服务端口

| 服务 | 端口 | API |
|------|------|-----|
| Nginx 前端 | 80 | `/` |
| YOLOv8n 检测 | 8000 | `/detect` `/health` |
| LLM 对话 | 8001 | `/chat` `/chat/stream` `/health` |
| Ollama 引擎 | 11434 | Ollama API |

## 常用命令

```bash
docker compose up -d              # 启动
docker compose down               # 停止
docker compose logs -f llm        # 查看 LLM 日志
docker compose restart yolo       # 重启 YOLO
docker compose exec ollama ollama list  # 查看已拉取模型
```

## LLM 切换模型

```bash
# 拉取更大的模型（更好但更慢）
docker compose exec ollama ollama pull qwen2.5:1.5b

# 修改 docker-compose.yml 中 llm 服务的 OLLAMA_MODEL 环境变量
# OLLAMA_MODEL=qwen2.5:1.5b
docker compose up -d llm
```
