import os
import random
import shutil
from pathlib import Path

src_img_dir = Path("images/train")
src_lbl_dir = Path("labels/train")
dst_img_dir = Path("images/val")
dst_lbl_dir = Path("labels/val")

# 获取所有图片文件（支持 jpg, png, jpeg）
img_files = list(src_img_dir.glob("*.jpg")) + list(src_img_dir.glob("*.png")) + list(src_img_dir.glob("*.jpeg"))
random.seed(42)  # 固定随机种子，确保可复现
random.shuffle(img_files)

# 选择 20% 作为验证集
val_ratio = 0.2
val_count = int(len(img_files) * val_ratio)
val_imgs = img_files[:val_count]

for img_path in val_imgs:
    # 移动图片
    shutil.move(str(img_path), str(dst_img_dir / img_path.name))
    # 对应的标签文件
    lbl_path = src_lbl_dir / (img_path.stem + ".txt")
    if lbl_path.exists():
        shutil.move(str(lbl_path), str(dst_lbl_dir / lbl_path.name))
    else:
        print(f"警告：{lbl_path} 不存在，跳过")
print(f"已移动 {len(val_imgs)} 个样本到验证集")