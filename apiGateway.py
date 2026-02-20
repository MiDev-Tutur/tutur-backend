import hashlib
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext
from fastapi.responses import JSONResponse
import pandas as pd
import os
import random
import json
import re

app = FastAPI(title="Tutur API Gateway")

DATASET_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "datasets",
    "DatasetLanguage.xlsx"
)
COURSE_PATH = os.path.join("courses", "courses.json")
URBAN_LEGENDS_PATH = os.path.join("datasets", "urbanLegends")
DATABASE_URL = "mysql+pymysql://root@localhost/db_tutur"

engine = create_engine(
    DATABASE_URL,
    echo=True 
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

class User(Base):
    __tablename__ = "users"

    idUser = Column(Integer, primary_key=True, index=True)
    userName = Column(String(100))
    userEmail = Column(String(100), unique=True)
    userPassword = Column(String(255))

class UserCreate(BaseModel):
    userName: str
    userEmail: EmailStr
    userPassword: str

class UserUpdate(BaseModel):
    userName: str | None = None
    userEmail: EmailStr | None = None
    userPassword: str | None = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

df = pd.read_excel(DATASET_PATH)
df["row_position"] = df.index + 2

# Dictionary Endpoints

@app.get("/api/tutur/dic/{dominant}/{local}")
def get_dictionary(dominant: str, local: str):

    if not os.path.exists(DATASET_PATH):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    try:
        df = pd.read_excel(DATASET_PATH, engine="openpyxl")
        df.columns = df.columns.str.lower()

        dominant_col = dominant.lower()
        local_col = local.lower()

        if dominant_col not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{dominant}' not found in dataset"
            )

        if local_col not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{local}' not found in dataset"
            )

        if "type" not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="Column 'type' not found in dataset"
            )

        filtered_df = df[df["type"].str.lower() == "word"]
        filtered_df = filtered_df[[dominant_col, local_col]].dropna(subset=[dominant_col])
        filtered_df = filtered_df.sort_values(by=dominant_col)

        words = [
            {
                dominant_col: str(row[dominant_col]),
                local_col: str(row[local_col]) if pd.notna(row[local_col]) else None
            }
            for _, row in filtered_df.iterrows()
        ]

        return JSONResponse(
            content={
                "dominant_language": dominant_col,
                "local_language": local_col,
                "total": len(words),
                "words": words
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tutur/translate/{dominant}/{local}/{words}")
def translate_word(dominant: str, local: str, words: str):

    if not os.path.exists(DATASET_PATH):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    try:
        df = pd.read_excel(DATASET_PATH, engine="openpyxl")
        df.columns = df.columns.str.lower()

        dominant_col = dominant.lower()
        local_col = local.lower()
        search_word = words.lower()

        if dominant_col not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{dominant}' not found in dataset"
            )

        if local_col not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{local}' not found in dataset"
            )

        if "type" not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="Column 'type' not found in dataset"
            )

        filtered_df = df[df["type"].str.lower() == "word"]
        result = filtered_df[
            filtered_df[dominant_col].astype(str).str.lower() == search_word
        ]

        if result.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Word '{words}' not found in '{dominant}' dictionary"
            )

        row = result.iloc[0]

        return JSONResponse(
            content={
                "dominant_language": dominant_col,
                "local_language": local_col,
                "input_word": words,
                "translation": str(row[local_col]) if pd.notna(row[local_col]) else None
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# User Management Endpoints

@app.post("/api/tutur/users")
def create_user(user: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.userEmail == user.userEmail).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(user.userPassword)

    new_user = User(
        userName=user.userName,
        userEmail=user.userEmail,
        userPassword=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User created successfully",
        "idUser": new_user.idUser
    }

@app.get("/api/tutur/users/{idUser}")
def get_user(idUser: int, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "idUser": user.idUser,
        "userName": user.userName,
        "userEmail": user.userEmail
    }

@app.put("/api/tutur/users/{idUser}")
def update_user(idUser: int, user_update: UserUpdate, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_update.userName:
        user.userName = user_update.userName

    if user_update.userEmail:
        user.userEmail = user_update.userEmail

    if user_update.userPassword:
        user.userPassword = pwd_context.hash(user_update.userPassword)

    db.commit()
    db.refresh(user)

    return {"message": "User updated successfully"}

@app.delete("/api/tutur/users/{idUser}")
def delete_user(idUser: int, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully"}

# Courses Management Endpoints

@app.get("/api/tutur/course/word/{step}/{dominant}/{local}")
def get_word_course(step: int, dominant: str, local: str):

    if dominant not in df.columns or local not in df.columns:
        raise HTTPException(status_code=400, detail="Language column not found")

    if not os.path.exists(COURSE_PATH):
        raise HTTPException(status_code=404, detail="Course file not found")

    with open(COURSE_PATH, "r", encoding="utf-8") as f:
        courses = json.load(f)

    selected_step = None

    for topic in courses.values():
        for item in topic:
            if item["step"] == step:
                selected_step = item
                break

    if not selected_step:
        raise HTTPException(status_code=404, detail="Step not found")

    if "listWords" not in selected_step:
        raise HTTPException(status_code=400, detail="Step is not word type")

    row_positions = selected_step["listWords"]

    if not row_positions:
        raise HTTPException(status_code=400, detail="No word data available")

    words_df = df[df["row_position"].isin(row_positions)]

    if words_df.empty:
        raise HTTPException(status_code=404, detail="No matching data found")

    questions = []

    for _, row in words_df.iterrows():

        direction = random.choice(["dominant", "local"])

        if direction == "dominant":
            question_text = row[dominant]
            correct_answer = row[local]
            option_pool = words_df[local].tolist()
        else:
            question_text = row[local]
            correct_answer = row[dominant]
            option_pool = words_df[dominant].tolist()

        distractors = [w for w in option_pool if w != correct_answer]
        random.shuffle(distractors)

        options = distractors[:4]
        options.append(correct_answer)

        options = list(set(options))

        random.shuffle(options)

        questions.append({
            "question": question_text,
            "options": options,        # daftar pilihan
            "answer": correct_answer,  # jawaban benar
            "type": direction
        })

    random.shuffle(questions)
    questions = questions[:10]

    return {
        "questions": questions
    }

@app.get("/api/tutur/course/phrase/{step}/{dominant}/{local}")
def get_phrase_course(step: int, dominant: str, local: str):

    if dominant not in df.columns or local not in df.columns:
        raise HTTPException(status_code=400, detail="Language column not found")

    if not os.path.exists(COURSE_PATH):
        raise HTTPException(status_code=404, detail="Course file not found")

    with open(COURSE_PATH, "r", encoding="utf-8") as f:
        courses = json.load(f)

    selected_step = None
    previous_step = None

    for topic in courses.values():
        for item in topic:
            if item["step"] == step:
                selected_step = item
            if item["step"] == step - 1:
                previous_step = item

    if not selected_step:
        raise HTTPException(status_code=404, detail="Step not found")

    if "listPhrases" not in selected_step:
        raise HTTPException(status_code=400, detail="Step is not phrase type")

    if not previous_step or "listWords" not in previous_step:
        raise HTTPException(status_code=400, detail="Previous step must be word type")

    phrase_rows = selected_step["listPhrases"]
    word_rows = previous_step["listWords"]

    phrase_df = df[df["row_position"].isin(phrase_rows)]
    word_df = df[df["row_position"].isin(word_rows)]

    if phrase_df.empty:
        raise HTTPException(status_code=404, detail="No phrase data found")

    questions = []

    phrase_list = phrase_df.to_dict("records")
    word_list = word_df.to_dict("records")

    if not phrase_list:
        raise HTTPException(status_code=404, detail="No phrase data found")

    while len(questions) < 10:

        row = random.choice(phrase_list)
        question_type = random.choice(["dominant", "local", "blank"])

        if question_type == "dominant":

            question_text = row[dominant]
            correct_answer = row[local]

            option_pool = [p[local] for p in phrase_list]
            distractors = [x for x in option_pool if x != correct_answer]
            random.shuffle(distractors)

            options = distractors[:4] + [correct_answer]
            options = list(set(options))
            random.shuffle(options)

            questions.append({
                "question": question_text,
                "options": options,
                "answer": correct_answer,
                "type": "dominant"
            })

        elif question_type == "local":

            question_text = row[local]
            correct_answer = row[dominant]

            option_pool = [p[dominant] for p in phrase_list]
            distractors = [x for x in option_pool if x != correct_answer]
            random.shuffle(distractors)

            options = distractors[:4] + [correct_answer]
            options = list(set(options))
            random.shuffle(options)

            questions.append({
                "question": question_text,
                "options": options,
                "answer": correct_answer,
                "type": "local"
            })

        else:

            local_phrase = row[local]
            words = local_phrase.split()

            if len(words) < 2:
                continue

            removed_word = random.choice(words)
            blank_phrase = local_phrase.replace(removed_word, "____", 1)

            option_pool = [w[local] for w in word_list]
            distractors = [w for w in option_pool if w != removed_word]
            random.shuffle(distractors)

            options = distractors[:4] + [removed_word]
            options = list(set(options))
            random.shuffle(options)

            questions.append({
                "question": blank_phrase,
                "options": options,
                "answer": removed_word,
                "type": "blank"
            })

    return {"questions": questions}

@app.get("/api/tutur/course/sentence/{step}/{dominant}/{local}")
def get_sentence_course(step: int, dominant: str, local: str):

    if dominant not in df.columns or local not in df.columns:
        raise HTTPException(status_code=400, detail="Language column not found")

    if not os.path.exists(COURSE_PATH):
        raise HTTPException(status_code=404, detail="Course file not found")

    with open(COURSE_PATH, "r", encoding="utf-8") as f:
        courses = json.load(f)

    selected_step = None
    word_step = None  # step -2

    for topic in courses.values():
        for item in topic:
            if item["step"] == step:
                selected_step = item
            if item["step"] == step - 2:
                word_step = item

    if not selected_step:
        raise HTTPException(status_code=404, detail="Step not found")

    if "listSentences" not in selected_step:
        raise HTTPException(status_code=400, detail="Step is not sentence type")

    if not word_step or "listWords" not in word_step:
        raise HTTPException(status_code=400, detail="Step -2 must be word type")

    sentence_rows = selected_step["listSentences"]
    word_rows = word_step["listWords"]

    sentence_df = df[df["row_position"].isin(sentence_rows)]
    word_df = df[df["row_position"].isin(word_rows)]

    if sentence_df.empty:
        raise HTTPException(status_code=404, detail="No sentence data found")

    questions = []

    sentence_list = sentence_df.to_dict("records")
    word_list = word_df.to_dict("records")

    if not sentence_list:
        raise HTTPException(status_code=404, detail="No sentence data found")

    while len(questions) < 10:

        row = random.choice(sentence_list)
        question_type = random.choice(["dominant", "local", "blank"])

        if question_type == "dominant":

            question_text = row[dominant]
            correct_answer = row[local]

            option_pool = [s[local] for s in sentence_list]
            distractors = [x for x in option_pool if x != correct_answer]
            random.shuffle(distractors)

            options = distractors[:4] + [correct_answer]
            options = list(set(options))
            random.shuffle(options)

            questions.append({
                "question": question_text,
                "options": options,
                "answer": correct_answer,
                "type": "dominant"
            })

        elif question_type == "local":

            question_text = row[local]
            correct_answer = row[dominant]

            option_pool = [s[dominant] for s in sentence_list]
            distractors = [x for x in option_pool if x != correct_answer]
            random.shuffle(distractors)

            options = distractors[:4] + [correct_answer]
            options = list(set(options))
            random.shuffle(options)

            questions.append({
                "question": question_text,
                "options": options,
                "answer": correct_answer,
                "type": "local"
            })

        else:

            local_sentence = row[local]
            words = local_sentence.split()

            if len(words) < 3:
                continue

            removed_word = random.choice(words)
            blank_sentence = local_sentence.replace(removed_word, "____", 1)

            option_pool = [w[local] for w in word_list]
            distractors = [w for w in option_pool if w != removed_word]
            random.shuffle(distractors)

            options = distractors[:4] + [removed_word]
            options = list(set(options))
            random.shuffle(options)

            questions.append({
                "question": blank_sentence,
                "options": options,
                "answer": removed_word,
                "type": "blank"
            })

    return {"questions": questions}

# Urban Legends Endpoint

@app.get("/api/tutur/urban-legends")
def get_all_urban_legends():

    if not os.path.exists(URBAN_LEGENDS_PATH):
        raise HTTPException(status_code=404, detail="urbanLegends folder not found")

    all_data = {}

    for filename in os.listdir(URBAN_LEGENDS_PATH):

        if filename.endswith(".json"):
            file_path = os.path.join(URBAN_LEGENDS_PATH, filename)

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                all_data.update(data)

    return all_data

@app.get("/api/tutur/urban-legends/{lang}")
def get_urban_legend_by_lang(lang: str):

    file_path = os.path.join(URBAN_LEGENDS_PATH, f"{lang}.json")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Language file not found")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data

@app.get("/api/tutur/urban-legends/test/{lang}/{title}")
def generate_urban_legend_test(lang: str, title: str):

    if not lang.isalpha():
        raise HTTPException(status_code=400, detail="Invalid language parameter")

    file_path = os.path.join(URBAN_LEGENDS_PATH, f"{lang}.json")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Language file not found")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if title not in data:
        raise HTTPException(status_code=404, detail="Story title not found")

    story_data = data[title]
    story_sentences = story_data.get("story", [])

    if not story_sentences:
        raise HTTPException(status_code=404, detail="Story content empty")

    full_text = " ".join(story_sentences).lower()

    full_text = re.sub(r"[^\w\s]", "", full_text)

    all_words = list(set(full_text.split()))

    questions = []

    for sentence in story_sentences:

        clean_sentence = re.sub(r"[^\w\s]", "", sentence)
        words = clean_sentence.split()

        if len(words) < 3:
            continue

        blank_count = random.randint(1, min(3, len(words)))
        removed_words = random.sample(words, blank_count)

        blank_sentence = sentence
        for word in removed_words:
            blank_sentence = blank_sentence.replace(word, "____", 1)

        distractors = [w for w in all_words if w not in removed_words]
        random.shuffle(distractors)

        options = distractors[:5 - len(removed_words)]
        options.extend(removed_words)

        options = list(set(options))
        random.shuffle(options)

        questions.append({
            "question": blank_sentence,
            "options": options,
            "answer": removed_words
        })

    return {
        "title": story_data.get("title"),
        "lang": story_data.get("lang"),
        "questions": questions
    }







