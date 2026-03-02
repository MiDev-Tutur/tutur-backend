import os
import pandas as pd
import re
import nltk
import torch
from sklearn.model_selection import train_test_split
from transformers import T5Tokenizer, T5ForConditionalGeneration, Trainer, TrainingArguments
from datasets import Dataset

nltk.download('punkt')

def clean_text(text):
    text = str(text).lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def tokenize_text(text):
    return nltk.word_tokenize(text)

DATA_PATH = "datasets/DatasetLanguage.xlsx"

df = pd.read_excel(DATA_PATH)

language_columns = []
for col in df.columns:
    if col == "type":
        break
    language_columns.append(col)

print("Detected languages:", language_columns)

data_pairs = []

for _, row in df.iterrows():
    for src_lang in language_columns:
        for tgt_lang in language_columns:
            if src_lang != tgt_lang:
                source_text = clean_text(row[src_lang])
                target_text = clean_text(row[tgt_lang])

                if source_text and target_text:
                    input_text = f"translate {src_lang} to {tgt_lang}: {source_text}"
                    data_pairs.append({
                        "input_text": input_text,
                        "target_text": target_text
                    })

print("Total translation pairs:", len(data_pairs))

dataset = Dataset.from_pandas(pd.DataFrame(data_pairs))

tokenizer = T5Tokenizer.from_pretrained("t5-small")

def tokenize_function(example):
    model_inputs = tokenizer(
        example["input_text"],
        max_length=128,
        truncation=True,
        padding="max_length"
    )

    labels = tokenizer(
        example["target_text"],
        max_length=128,
        truncation=True,
        padding="max_length"
    )

    model_inputs["labels"] = labels["input_ids"]
    return model_inputs

tokenized_dataset = dataset.map(tokenize_function, batched=True)

train_test = tokenized_dataset.train_test_split(test_size=0.1)
train_dataset = train_test["train"]
eval_dataset = train_test["test"]

model = T5ForConditionalGeneration.from_pretrained("t5-small")

training_args = TrainingArguments(
    output_dir="./translator_model",
    do_train=True,
    do_eval=True,
    num_train_epochs=3,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    logging_steps=50,
    save_steps=500
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
)

trainer.train()

trainer.save_model("./translator_model")
tokenizer.save_pretrained("./translator_model")

print("Training complete.")