import os

# ===== 配置区（已按您的要求修改） =====
folder_path = r'D:\Desktop\立柱花丝银头冠'
extensions = ('.jpg', '.jpeg', '.png')
start_number = 420

# ===== 以下代码无需修改 =====
files = [f for f in os.listdir(folder_path) if f.lower().endswith(extensions)]
files.sort()  # 按文件名排序

if not files:
    print("❌ 该文件夹下没有找到 jpg 或 png 图片，请检查路径！")
    exit()

total = len(files)
end_number = start_number + total - 1
padding = len(str(end_number))  # 自动计算补零位数

print(f"📁 共找到 {total} 张图片，从 {start_number} 开始命名，补 {padding} 位零\n")

for number, filename in enumerate(files, start=start_number):
    old_path = os.path.join(folder_path, filename)
    ext = os.path.splitext(filename)[1]
    new_name = f"{str(number).zfill(padding)}{ext}"
    new_path = os.path.join(folder_path, new_name)

    # 防覆盖：如果新名字已存在且不是自己，跳过
    if os.path.exists(new_path) and old_path != new_path:
        print(f"⚠️  跳过 {filename}，因为 {new_name} 已存在")
        continue

    os.rename(old_path, new_path)
    print(f"✅ {filename} -> {new_name}")

print("\n🎉 全部重命名完成！")