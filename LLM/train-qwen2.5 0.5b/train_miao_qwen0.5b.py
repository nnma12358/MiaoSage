import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# 配置
model_name = "unsloth/Qwen2.5-0.5B-Instruct-bnb-4bit"   # 改用 0.5B
max_seq_length = 2048
output_dir = "./miao_qwen_lora_0.5b"

# 加载4-bit量化模型
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=max_seq_length,
    dtype=torch.float16,
    load_in_4bit=True,
)

# 配置LoRA参数
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0.1,
    use_gradient_checkpointing=True,
    random_state=3407,
)

# 加载数据集（请确保路径正确）
dataset = load_dataset("json", data_files="dataset/miao_culture.jsonl", split="train")

def format_conversation(example):
    messages = example["messages"]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False
    )
    return {"text": text}

dataset = dataset.map(format_conversation)

# 设置训练参数
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        max_steps=600,
        learning_rate=5e-4,
        fp16=True,
        logging_steps=10,
        output_dir=output_dir,
        optim="adamw_8bit",
        seed=3407,
    ),
)

trainer.train()

model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)
print(f"微调完成！模型保存至 {output_dir}")
