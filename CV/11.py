import os
import random
import shutil
from pathlib import Path

def split_dataset(data_dir, val_ratio=0.2, seed=42):
    """
    将 images/train 和 labels/train 中的部分文件移动到 images/val 和 labels/val
    data_dir: 数据集根目录（例如 D:/Desktop/1111）
    val_ratio: 验证集比例（默认 0.2）
    seed: 随机种子，保证每次划分一致
    """
    data_dir = Path(data_dir)
    train_img = data_dir / "images" / "train"
    train_lbl = data_dir / "labels" / "train"
    val_img = data_dir / "images" / "val"
    val_lbl = data_dir / "labels" / "val"

    # 检查训练集目录是否存在
    if not train_img.exists():
        print(f"错误：{train_img} 不存在")
        return
    if not train_lbl.exists():
        print(f"错误：{train_lbl} 不存在")
        return

    # 如果验证集目录非空，先警告并退出（避免数据混乱）
    if (val_img.exists() and any(val_img.iterdir())) or (val_lbl.exists() and any(val_lbl.iterdir())):
        print("警告：验证集目录非空，请清空 images/val 和 labels/val 后再运行")
        return

    # 创建验证集目录
    val_img.mkdir(parents=True, exist_ok=True)
    val_lbl.mkdir(parents=True, exist_ok=True)

    # 获取所有图片文件
    img_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tif')
    images = [f for f in train_img.iterdir() if f.suffix.lower() in img_extensions]
    total = len(images)
    if total == 0:
        print("错误：训练集图片为空")
        return

    n_val = int(total * val_ratio)
    random.seed(seed)
    selected = random.sample(images, n_val)

    moved_img = 0
    moved_lbl = 0
    for img_path in selected:
        # 移动图片
        shutil.move(str(img_path), str(val_img / img_path.name))
        moved_img += 1

        # 移动对应的标签文件
        lbl_path = train_lbl / f"{img_path.stem}.txt"
        if lbl_path.exists():
            shutil.move(str(lbl_path), str(val_lbl / lbl_path.name))
            moved_lbl += 1
        else:
            print(f"警告：图片 {img_path.name} 没有对应的标签文件")

    print(f"完成！已将 {moved_img} 张图片移动到 {val_img}")
    print(f"已移动 {moved_lbl} 个标签文件到 {val_lbl}")
    print(f"训练集剩余图片：{total - moved_img} 张")

if __name__ == "__main__":
    # 修改为你的实际数据集路径
    split_dataset("D:/Desktop/1111")