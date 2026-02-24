import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration

MODEL_PATH = "./translator_model"

tokenizer = T5Tokenizer.from_pretrained(MODEL_PATH)
model = T5ForConditionalGeneration.from_pretrained(MODEL_PATH)

def translate(text, source_lang, target_lang):
    input_text = f"translate {source_lang} to {target_lang}: {text}"
    input_ids = tokenizer.encode(input_text, return_tensors="pt")

    outputs = model.generate(
        input_ids,
        max_length=128,
        num_beams=4,
        early_stopping=True
    )

    return tokenizer.decode(outputs[0], skip_special_tokens=True)

if __name__ == "__main__":
    hasil = translate(
        text="siapa namamu",
        source_lang="indonesian",
        target_lang="english"
    )
    print("Hasil:", hasil)