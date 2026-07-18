# ==================== 1. 导入必要库 ====================
import torch
import torchvision
from torchvision.models.detection import FasterRCNN
from torchvision.models.detection.rpn import AnchorGenerator
from torch.optim.lr_scheduler import CosineAnnealingLR, StepLR
import argparse
import os
import numpy as np
from tqdm import tqdm  # 进度条，终端看训练进度用的

# ==================== 2. 定义早停类（双重正则化防过拟合） ====================
class EarlyStopping:
    """
    早停机制：若验证损失连续 patience 轮不下降，则停止训练，防止过拟合。
    """
    def __init__(self, patience=10, min_delta=0.001):
        self.patience = patience
        self.min_delta = min_delta  # 最小改善阈值
        self.counter = 0
        self.best_loss = None
        self.early_stop = False

    def __call__(self, val_loss):
        if self.best_loss is None:
            self.best_loss = val_loss
        elif val_loss > self.best_loss - self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
                print(f"⚠️ 早停触发！验证损失已连续 {self.patience} 轮未改善。")
        else:
            self.best_loss = val_loss
            self.counter = 0

# ==================== 3. 定义训练与验证函数 ====================
def train_one_epoch(model, optimizer, dataloader, device, epoch):
    """
    单轮训练逻辑
    """
    model.train()
    total_loss = 0
    # tqdm 用于在 Ubuntu 终端显示漂亮的进度条
    progress_bar = tqdm(dataloader, desc=f'Epoch {epoch} [Train]')
    for images, targets in progress_bar:
        # 数据搬到 GPU 上
        images = [img.to(device) for img in images]
        targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

        # 前向传播计算损失（Faster R-CNN 返回损失字典）
        loss_dict = model(images, targets)
        losses = sum(loss for loss in loss_dict.values())

        # 反向传播
        optimizer.zero_grad()
        losses.backward()
        optimizer.step()

        # 记录损失
        total_loss += losses.item()
        progress_bar.set_postfix({'loss': losses.item()})

    return total_loss / len(dataloader)

@torch.no_grad()  # 验证时关闭梯度，节省显存
def validate(model, dataloader, device):
    """
    单轮验证逻辑，返回平均验证损失
    """
    model.eval()
    total_loss = 0
    progress_bar = tqdm(dataloader, desc=f'Validating')
    for images, targets in progress_bar:
        images = [img.to(device) for img in images]
        targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

        loss_dict = model(images, targets)
        losses = sum(loss for loss in loss_dict.values())
        total_loss += losses.item()
        progress_bar.set_postfix({'val_loss': losses.item()})

    return total_loss / len(dataloader)

# ==================== 4. 主函数（整合全部策略） ====================
def main():
    # --- 4.1 通过 argparse 接收终端参数（替代手动改代码） ---
    parser = argparse.ArgumentParser(description='两阶段迁移学习训练脚本')
    parser.add_argument('--stage1_epochs', type=int, default=20, help='第一阶段训练轮数')
    parser.add_argument('--stage2_epochs', type=int, default=10, help='第二阶段精调轮数')
    parser.add_argument('--batch_size', type=int, default=4, help='批次大小')
    parser.add_argument('--num_classes', type=int, default=5, help='数据集类别数（不含背景）')
    parser.add_argument('--patience', type=int, default=10, help='早停轮数')
    args = parser.parse_args()

    # --- 4.2 设置设备（Ubuntu下自动识别GPU） ---
    device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
    print(f"✅ 正在使用设备: {device}")
    if device.type == 'cuda':
        print(f"   显卡型号: {torch.cuda.get_device_name(0)}")

    # --- 4.3 加载 COCO 预训练模型（骨干网络权重是 ImageNet 预训练好的） ---
    print("📦 正在加载 COCO 预训练模型...")
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
    
    # 替换检测头（适配你的苗族服饰类别）
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = torchvision.models.detection.faster_rcnn.FastRCNNPredictor(
        in_features, args.num_classes + 1  # +1 是因为要加背景类
    )
    model.to(device)

    # --- 4.4 模拟数据加载器（实际使用时，请替换为你的 DataLoader） ---
    # 注意：这里只是占位，实际替换成你的数据集加载代码
    # train_loader = get_your_dataloader('train', args.batch_size)
    # val_loader = get_your_dataloader('val', args.batch_size)
    print("⚠️ 警告：当前使用的是模拟数据加载器，请替换为真实数据！")
    from torch.utils.data import DataLoader
    from torchvision.datasets import CocoDetection  # 仅作占位，实际不会跑通
    # 实际使用请注释掉下面两行，换上你的真实 dataloader
    train_loader = None 
    val_loader = None
    # 如果真实运行，请确保 train_loader 和 val_loader 不为 None

    # ==================== 5. 第一阶段：冻结骨干，训练检测头 ====================
    print("\n🚀 阶段一：冻结骨干网络，训练检测头（余弦退火调度）")
    
    # 冻结 backbone 所有参数
    for param in model.backbone.parameters():
        param.requires_grad = False
    
    # 优化器只管理需要梯度的参数（即头部）
    params_to_optimize = [p for p in model.parameters() if p.requires_grad]
    optimizer_stage1 = torch.optim.SGD(
        params_to_optimize, 
        lr=1e-3,          # 较大学习率
        momentum=0.9, 
        weight_decay=1e-4  # 权重衰减（L2正则化防过拟合）
    )
    # 余弦退火调度：让学习率周期性震荡，跳出局部最优
    scheduler_stage1 = CosineAnnealingLR(optimizer_stage1, T_max=args.stage1_epochs)
    
    early_stopping = EarlyStopping(patience=args.patience)
    
    for epoch in range(1, args.stage1_epochs + 1):
        train_loss = train_one_epoch(model, optimizer_stage1, train_loader, device, epoch)
        val_loss = validate(model, val_loader, device)
        scheduler_stage1.step()  # 更新学习率
        
        print(f"阶段一 Epoch {epoch}: Train Loss={train_loss:.4f}, Val Loss={val_loss:.4f}, LR={scheduler_stage1.get_last_lr()[0]:.6f}")
        
        # 早停检查
        early_stopping(val_loss)
        if early_stopping.early_stop:
            break

    # ==================== 6. 第二阶段：解冻全网络，极低学习率精调 ====================
    print("\n🎯 阶段二：解冻全网络，差异化极低学习率精调（恒定小学习率）")
    
    # 解冻所有层
    for param in model.parameters():
        param.requires_grad = True
    
    # 差异化学习率：骨干极小（1e-5），检测头稍大（1e-4），精细适配细节
    optimizer_stage2 = torch.optim.SGD([
        {'params': model.backbone.parameters(), 'lr': 1e-5},
        {'params': model.rpn.parameters(), 'lr': 1e-5},
        {'params': model.roi_heads.parameters(), 'lr': 1e-4},
    ], momentum=0.9, weight_decay=1e-4)  # 依然保留权重衰减
    
    # 第二阶段使用恒定小学习率（StepLR 且 gamma=1 即不变）
    scheduler_stage2 = StepLR(optimizer_stage2, step_size=1, gamma=1.0)
    
    early_stopping = EarlyStopping(patience=args.patience)  # 重置早停
    
    for epoch in range(1, args.stage2_epochs + 1):
        train_loss = train_one_epoch(model, optimizer_stage2, train_loader, device, epoch)
        val_loss = validate(model, val_loader, device)
        scheduler_stage2.step()  # 实际不变
        
        print(f"阶段二 Epoch {epoch}: Train Loss={train_loss:.4f}, Val Loss={val_loss:.4f}, LR={scheduler_stage2.get_last_lr()[0]:.6f}")
        
        early_stopping(val_loss)
        if early_stopping.early_stop:
            break

    # ==================== 7. 保存最终模型 ====================
    torch.save(model.state_dict(), 'miao_final_model.pth')
    print("\n🎉 训练完成！模型已保存为 miao_final_model.pth")

if __name__ == "__main__":
    main()