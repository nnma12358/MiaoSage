from ultralytics import YOLO

# 1. 加载预训练模型
model = YOLO('yolov8n.pt')

# 2. 训练（请确认 data.yaml 路径正确）
model.train(
    data='D:/Desktop/yolo_dataset/data.yaml',   # 之前重写的配置文件
    epochs=100,
    imgsz=640,
    batch=8,                 # 如果用 CPU 或无独立显卡，建议减小到 4 或 8
    device='cpu',            # 没有 N 卡就写 'cpu'；有则写 0
    workers=0,               # Windows 下建议设为 0，避免多进程报错
    optimizer='auto',
    lr0=0.01,
    patience=50,
    save=True,
    name='miao_silver',      # 结果保存在 runs/detect/miao_silver 下
)

# 3. 验证（使用训练得到的最佳权重）
model = YOLO('./runs/detect/miao_silver/weights/best.pt')
model.val(data='D:/Desktop/yolo_dataset/data.yaml', imgsz=640)

# 4. 预测新图片（假设测试图片放在 D:/test_images/）
model = YOLO('./runs/detect/miao_silver/weights/best.pt')
results = model.predict(source='D:/test_images/', save=True)

# 5. 导出 ONNX
model.export(format='onnx')