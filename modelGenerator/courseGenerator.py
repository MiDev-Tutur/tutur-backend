import os
import json
import random
import pandas as pd

DATASET_PATH = os.path.join("datasets", "DatasetLanguage.xlsx")
OUTPUT_PATH = os.path.join("courses", "courses.json")

df = pd.read_excel(DATASET_PATH)
df["indonesian"] = df["indonesian"].astype(str).str.lower()
df["type"] = df["type"].astype(str).str.lower()
df["category_topic"] = df["category_topic"].astype(str)

df["row_position"] = df.index + 2

topics = df["category_topic"].unique()

result = {}
global_step = 1

for topic in topics:

    topic_df = df[df["category_topic"] == topic]
    topic_data = []

    for group in range(2):

        sentence_df = topic_df[topic_df["type"] == "sentence"]

        if len(sentence_df) == 0:
            continue

        selected_sentences = sentence_df.sample(
            min(3, len(sentence_df))
        )

        sentence_rows = selected_sentences["row_position"].tolist()
        sentence_text = " ".join(selected_sentences["indonesian"])
        sentence_words = set(sentence_text.split())

        phrase_df = topic_df[topic_df["type"] == "phrase"]

        valid_phrases = phrase_df[
            phrase_df["indonesian"].apply(
                lambda x: len(set(x.split()) & sentence_words) >= 1
            )
        ]

        selected_phrases = valid_phrases.sample(
            min(5, len(valid_phrases))
        )

        phrase_rows = selected_phrases["row_position"].tolist()

        word_df = topic_df[topic_df["type"] == "word"]

        valid_words = word_df[
            word_df["indonesian"].apply(
                lambda x: x in sentence_words
            )
        ]

        selected_words = valid_words.sample(
            min(10, len(valid_words))
        )

        word_rows = selected_words["row_position"].tolist()

        topic_data.append({
            "step": global_step,
            "type": "word",
            "listWords": word_rows
        })
        global_step += 1

        topic_data.append({
            "step": global_step,
            "type": "phrase",
            "listPhrases": phrase_rows
        })

        global_step += 1

        topic_data.append({
            "step": global_step,
            "type": "sentence",
            "listSentences": sentence_rows
        })
        global_step += 1

    result[topic] = topic_data

os.makedirs("courses", exist_ok=True)

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=4, ensure_ascii=False)

print("Output file saved at :", OUTPUT_PATH)