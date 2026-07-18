import shutil
import os
import subprocess
from datetime import datetime

# ===== 配置区域 =====
DATASET_PATH = "D:/Desktop/test1"          # 你的数据集路径
RUNS_PATH = "runs"                         # 如果相对路径不对，改为绝对路径，例如 "D:/Desktop/test1/runs"
BACKUP_ROOT = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
# ===================

os.makedirs(BACKUP_ROOT, exist_ok=True)

# 1. 备份 runs（训练进度）
if os.path.exists(RUNS_PATH):
    shutil.copytree(RUNS_PATH, os.path.join(BACKUP_ROOT, "runs"))
    print("✓ 备份 runs 目录")
else:
    print("✗ runs 目录不存在，尝试在数据集目录下查找...")
    alt_runs = os.path.join(DATASET_PATH, "runs")
    if os.path.exists(alt_runs):
        shutil.copytree(alt_runs, os.path.join(BACKUP_ROOT, "runs"))
        print("✓ 备份 runs 目录（从数据集目录）")
    else:
        print("✗ 未找到 runs 目录")

# 2. 备份整个数据集
if os.path.exists(DATASET_PATH):
    shutil.copytree(DATASET_PATH, os.path.join(BACKUP_ROOT, "dataset"))
    print("✓ 备份数据集")
else:
    print("✗ 数据集路径不存在，请修改 DATASET_PATH 变量")

# 3. 导出 conda 环境
try:
    env_file = os.path.join(BACKUP_ROOT, "conda_env_export.yaml")
    with open(env_file, "w") as f:
        subprocess.run(["conda", "env", "export"], stdout=f, check=True)
    print("✓ 导出 Conda 环境到", env_file)
except Exception as e:
    print("✗ 导出 Conda 环境失败:", e)

print(f"\n所有备份已保存到文件夹: {BACKUP_ROOT}")
print("你现在可以安全重启电脑。")
input("按 Enter 键退出...")
