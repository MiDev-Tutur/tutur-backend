import pandas as pd
import re
import torch
from transformers import (
    T5Tokenizer,
    T5ForConditionalGeneration,
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq
)
from datasets import Dataset

def clean_text(text):
    text = str(text).lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text.strip()

df = pd.read_excel("datasets/DatasetLanguage.xlsx")

language_columns = []
for col in df.columns:
    if col == "type":
        break
    language_columns.append(col)

print("Detected languages:", language_columns)

data_pairs = []

pivot = "english"

for _, row in df.iterrows():
    for lang in language_columns:
        if lang != pivot:
            src = clean_text(row[lang])
            tgt = clean_text(row[pivot])

            if src and tgt:
                data_pairs.append({
                    "input_text": f"translate {lang} to {pivot}: {src}",
                    "target_text": tgt
                })

                data_pairs.append({
                    "input_text": f"translate {pivot} to {lang}: {tgt}",
                    "target_text": src
                })

print("Total reduced pairs:", len(data_pairs))

dataset = Dataset.from_pandas(pd.DataFrame(data_pairs))

tokenizer = T5Tokenizer.from_pretrained("t5-small")

def tokenize_function(examples):
    model_inputs = tokenizer(
        examples["input_text"],
        max_length=64,
        truncation=True
    )

    labels = tokenizer(
        examples["target_text"],
        max_length=64,
        truncation=True
    )

    model_inputs["labels"] = labels["input_ids"]
    return model_inputs

tokenized_dataset = dataset.map(tokenize_function, batched=True)

train_test = tokenized_dataset.train_test_split(test_size=0.1)
train_dataset = train_test["train"]
eval_dataset = train_test["test"]

model = T5ForConditionalGeneration.from_pretrained("t5-small")

training_args = TrainingArguments(
    output_dir="./translator_model_lite",
    do_train=True,
    num_train_epochs=3,
    per_device_train_batch_size=4,
    logging_steps=200,
    save_steps=1000
)

data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    data_collator=data_collator
)

trainer.train()

trainer.save_model("./translator_model_lite")
tokenizer.save_pretrained("./translator_model_lite")

print("Training complete.")