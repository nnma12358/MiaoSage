import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# ✅ 使用非量化的官方基座模型（关键改动）
base_model_name = "Qwen/Qwen2.5-0.5B-Instruct"

# LoRA 适配器路径（你微调保存的）
lora_path = "./miao_qwen_lora_0.5b"

# 输出路径
output_path = "./miao_qwen_merged_0.5b_fp16"

print("正在加载基座模型（FP16）...")
model = AutoModelForCausalLM.from_pretrained(
    base_model_name,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True
)

print("正在加载分词器...")
tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)

print("正在加载 LoRA 适配器...")
model = PeftModel.from_pretrained(model, lora_path)

print("正在合并 LoRA 并卸载...")
model = model.merge_and_unload()

# 确保全部转为 FP16（无量化状态）
model = model.to(torch.float16)

print("正在保存干净 FP16 模型...")
model.save_pretrained(output_path, safe_serialization=True)
tokenizer.save_pretrained(output_path)

print(f"✅ 合并完成！干净 FP16 模型已保存至 {output_path}")
