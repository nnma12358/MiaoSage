# 苗绣·识裳 — 进迭时空 K1 Muse Pi Pro 部署指南

## 一、开发板环境要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| 系统 | Yocto / Buildroot (riscv64) | 需支持 Docker |
| Docker | ≥ 24.0 | `docker` + `docker compose` |
| NPU 驱动 | SpacemiT NN SDK | 可选，启用 NPU 加速需要 |
| 内存 | ≥ 512MB 可用 | 建议 1GB+ |

## 二、快速部署（推荐）

### 方式 1：在开发板上直接构建（最简单）

```bash
# 1. 将项目拷贝到开发板
scp -r my-app root@k1-board:/opt/miao-xiu
ssh root@k1-board

# 2. 在开发板上构建并启动
cd /opt/miao-xiu
npm install && npm run build    # 构建前端
docker compose up -d            # 构建镜像并启动

# 3. 验证
curl http://localhost:8000/health
```

### 方式 2：交叉编译 + 传输（在 x86 PC 上操作）

```bash
# 1. 在 PC 上安装 Docker buildx（支持多架构）
docker buildx create --name cross-builder --use
docker buildx inspect --bootstrap

# 2. 构建 riscv64 镜像并导出
./deploy/build.sh --cross
docker save miao-xiu:latest | gzip > miao-xiu-riscv64.tar.gz

# 3. 传输到开发板
scp miao-xiu-riscv64.tar.gz docker-compose.yml root@k1-board:/opt/miao-xiu/
ssh root@k1-board

# 4. 在开发板上加载并启动
cd /opt/miao-xiu
gunzip -c miao-xiu-riscv64.tar.gz | docker load
docker compose up -d
```

### 方式 3：一键远程部署

```bash
# 配置好 SSH 免密登录后
./deploy/deploy.sh root@192.168.x.x
```

## 三、NPU 加速配置（进迭时空 K1）

### 3.1 安装 SpacemiT NN SDK

```bash
# 从进迭时空官方获取 SDK
# https://developer.spacemit.com/

# 安装到开发板后，确保库在 LD_LIBRARY_PATH 中
export LD_LIBRARY_PATH=/usr/lib/spacemit:$LD_LIBRARY_PATH
```

### 3.2 转换 YOLO 模型为 NPU 格式

```bash
# 使用 SpacemiT 模型转换工具
# 将 yolov8n.pt → yolov8n.onnx → yolov8n.smnn
spacemit-nn-converter \
    --model yolov8n.pt \
    --output yolov8n.smnn \
    --input-shape 1,3,640,640
```

### 3.3 启用 NPU 后端

```bash
# 修改 docker-compose.yml，挂载 NPU 设备和模型
# 或设置环境变量：
export SPACEMIT_NPU_ENABLED=1
export YOLO_MODEL=/app/models/yolov8n.smnn
docker compose up -d
```

## 四、自定义苗族服饰模型训练

当前的 COCO 预训练模型对苗族服饰识别精度有限，建议：

```bash
# 1. 收集苗族服饰数据集（银角、百鸟衣、围腰、银项圈等）
# 2. 用 ultralytics 训练自定义模型
yolo detect train \
    data=miao_clothing.yaml \
    model=yolov8n.pt \
    epochs=100 \
    imgsz=640

# 3. 将训练好的 best.pt 替换到容器中
docker compose down
cp best.pt ./models/miao_yolo.pt
# 修改 docker-compose.yml 中的 YOLO_MODEL 环境变量
docker compose up -d
```

## 五、常见问题

| 问题 | 解决方案 |
|------|---------|
| Docker 启动失败 | `docker compose logs` 查看日志 |
| 模型下载慢 | 预先下载 yolov8n.pt 放入 models/ 目录 |
| NPU 未识别 | `ls /dev/spacemit*` 确认设备节点存在 |
| 内存不足 | 在 docker-compose.yml 中降低 memory 限制 |
| 前端无法访问 | 防火墙开放 80 端口：`iptables -A INPUT -p tcp --dport 80 -j ACCEPT` |
