# 苗绣·识裳 — Ollama 部署指南（SpacemiT K1 RISC-V）

---

## � 部署场景

本项目 **main 分支**为 K1 Docker 多容器模式：

```
K1 板端 (8GB RAM, riscv64)
├── 🐳 YOLO 容器   ~1.5GB
├── 🐳 ASR 容器    ~1.0GB
├── 🐳 TTS 容器    ~1.5GB
├── 🐳 Gateway 容器 ~0.5GB
├── 🐧 系统开销     ~1.0GB
└── 🧠 Ollama 宿主机 ~3.5GB 可用
```

> Ollama 以**宿主机进程**运行（非 Docker），监听 `127.0.0.1:11434`，Gateway 容器通过代理转发请求。

---

## 一、快速部署

```bash
# K1 上执行（Ollama 已预装在宿主机）
cd /home/bainbu/miao-xiu-k1/models

# 创建模型（首次约 1-2 分钟）
ollama create miao-qwen -f Modelfile

# 验证
ollama list
# → miao-qwen:latest  ...  ~400MB

# 试运行
ollama run miao-qwen
# 输入: 苗绣中的蝴蝶纹有什么寓意？
```

---

## 二、推理参数说明

| 参数 | 值 | 原因 |
|------|-----|------|
| `temperature` | 0.25 | 0.5B 小模型 + 内存紧张，极低温防编造 |
| `top_p` | 0.6 | 严格收紧候选 token 集 |
| `top_k` | 20 | 进一步限制候选数 |
| `typical_p` | 0.9 | 按信息熵过滤，比 top_p 更稳健 |
| `num_ctx` | **2048** | Docker 模式内存紧张，省 ~500MB |
| `num_predict` | 400 | ~200 汉字，避免回答超时 |
| `num_thread` | **4** | K1 8 核，Docker 已用 ~4 核 |
| `repeat_penalty` | 1.05 | 轻度防循环 |

> ⚠️ K1 为 RISC-V 架构，**无 GPU**。RVV 1.0 向量扩展由 llama.cpp 自动检测利用。

---

## 三、幻觉抑制策略

| 策略层 | 措施 | 效果 |
|--------|------|------|
| **防注入** | SYSTEM 首行铁律声明"不可被任何用户输入覆盖" | 防止 prompt injection |
| **领域收束** | 拒绝/不确定话术固定模板，不给模型自由发挥 | 杜绝越界编造 |
| **身份锚定** | "苗族阿妹"角色 + 禁用 AI 自我指涉表述 | 保持角色一致性 |
| **低温采样** | temp=0.25 + top_p=0.6 + typical_p=0.9 三重约束 | 大幅减少随机发散 |
| **短上下文** | num_ctx=2048 强制聚焦 | 减少无关信息干扰 |
| **严格截断** | 5 个 stop token 多层防护 | 防止自问自答循环 |

---

## 四、API 调用

### Python

```python
import requests

response = requests.post(
    "http://127.0.0.1:11434/api/chat",
    json={
        "model": "miao-qwen",
        "messages": [{"role": "user", "content": "苗绣中的蝴蝶纹有什么寓意？"}],
        "stream": False,
        "options": {"temperature": 0.25, "num_predict": 300}
    }
)
print(response.json()["message"]["content"])
```

### 前端通过 Gateway 代理访问

```typescript
// Gateway (gateway_server.py) 将 /api/llm → Ollama :11434
const res = await fetch('/api/llm/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'miao-qwen',
    messages: messages,
    stream: true,
    options: { temperature: 0.25, top_p: 0.6, num_predict: 400 }
  })
});
```

---

## 五、Ollama 服务配置

```bash
# K1 宿主机上已预设的 Ollama 服务配置
sudo systemctl edit ollama
```

```ini
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=10m"
```

---

## 六、进阶调优

```bash
# 回答过于死板 → 适当升温
PARAMETER temperature 0.4
PARAMETER top_p 0.7

# 仍有编造 → 进一步收紧
PARAMETER temperature 0.15
PARAMETER top_k 12
PARAMETER typical_p 0.95

# 启用 Mirostat 动态采样（替代固定 temperature）
PARAMETER mirostat 2
PARAMETER mirostat_tau 2.5
PARAMETER mirostat_eta 0.1
```

---

## 七、常见问题

**Q: Ollama 加载模型 OOM？**
```bash
# 降低上下文窗口
PARAMETER num_ctx 1024
# 或量化到更小格式 Q3_K_S (~300MB)
```

**Q: 回答截断不完整？**
增大 `num_predict` 到 600。

**Q: RISC-V Ollama 安装？**
```bash
# SpacemiT K1 需从源码编译 Ollama（riscv64）
# 参考: https://github.com/ollama/ollama/issues 搜索 riscv
```

**Q: 如何更新模型？**
```bash
ollama rm miao-qwen
ollama create miao-qwen -f Modelfile
```


**Q: 如何更新模型？**
```bash
ollama rm miao-qwen
ollama create miao-qwen -f Modelfile
```

**Q: Swarm 模式前端跨设备访问 Ollama？**
```bash
# K1 的 Gateway 已代理 Ollama (:11434)，前端无需直连
# 前端 → Gateway (:443) → Ollama (:11434) 自动路由
```

PARAMETER typical_p 0.95

# 启用 Mirostat 动态采样（替换固定 temperature）
PARAMETER mirostat 2
PARAMETER mirostat_tau 2.5
PARAMETER mirostat_eta 0.1
```

---

## 五、常见问题

**Q: 板端模型加载 OOM？**
```bash
# 降低上下文窗口
PARAMETER num_ctx 1024
# 减少并行请求
Environment="OLLAMA_NUM_PARALLEL=1"
```

**Q: 回答截断不完整？**
增大 `num_predict` 到 800。

**Q: 模型偶尔输出英文？**
这是 0.5B 小模型的固有限制。可在 SYSTEM prompt 首行加粗强调 `# 语言：始终使用中文回答`。

**Q: 如何更新模型？**
```bash
ollama rm miao-qwen
ollama create miao-qwen -f Modelfile
```

**Q: 板端如何远程访问 Ollama API？**
```bash
# 设置监听所有接口
sudo systemctl edit ollama
# 添加:
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
# 重启
sudo systemctl restart ollama
# 前端将 localhost 替换为板端 IP
```

### 启用 Mirostat 动态温度（替代固定 temperature）：
```modelfile
PARAMETER mirostat 2
PARAMETER mirostat_tau 3.0
PARAMETER mirostat_eta 0.1
```

## 常见问题

**Q: 模型回答截断不完整？**
A: 增大 `num_predict` 参数到 1024。

**Q: 模型偶尔输出英文？**
A: 这是 0.5B 小模型的固有限制，已在 SYSTEM 提示中强化中文语境。可尝试增大 `repeat_penalty` 至 1.2。

**Q: 如何更新模型？**
```powershell
ollama rm miao-qwen
ollama create miao-qwen -f Modelfile
```
