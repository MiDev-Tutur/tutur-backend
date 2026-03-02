import hashlib
from fastapi import FastAPI, HTTPException, Depends, Path
from pydantic import BaseModel, EmailStr
from sqlalchemy import Enum, create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship, aliased
from passlib.context import CryptContext
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import os
import random
import json
import re
import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration

MODEL_PATH = "./translator_model_lite"

app = FastAPI(title="Tutur API Gateway")

DATASET_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "datasets",
    "DatasetLanguage.xlsx"
)
COURSE_PATH = os.path.join("courses", "courses.json")
URBAN_LEGENDS_PATH = os.path.join("datasets", "urbanLegends")
BASE_DATASET_PATH = os.path.join("datasets", "folkSongs")
DATABASE_URL = "mysql+pymysql://root@localhost/db_tutur"

engine = create_engine(
    DATABASE_URL,
    echo=True 
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

app = FastAPI()

if not os.path.exists(DATASET_PATH):
    raise FileNotFoundError("DatasetLanguage.xlsx not found in datasets folder")

df = pd.read_excel(DATASET_PATH)
df.columns = df.columns.str.lower()

if "english" not in df.columns:
    raise Exception("Dataset must contain 'english' column")

tokenizer = T5Tokenizer.from_pretrained(MODEL_PATH)
model = T5ForConditionalGeneration.from_pretrained(MODEL_PATH)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

class TranslateRequest(BaseModel):
    text: str
    target_language: str

class User(Base):
    __tablename__ = "users"

    idUser = Column(Integer, primary_key=True, index=True)
    userName = Column(String(100))
    userEmail = Column(String(100), unique=True)
    userPassword = Column(String(255))
    userParticipantStatus = Column(Enum("active", "nonactive"), default="nonactive", nullable=True)
    userReferenceFolderId = Column(String(255))

class UserCreate(BaseModel):
    userName: str
    userEmail: EmailStr
    userPassword: str

class UserUpdate(BaseModel):
    userName: str | None = None
    userEmail: EmailStr | None = None
    userPassword: str | None = None
    userParticipantStatus: str | None = None
    userReferenceFolderId: str | None = None

class Course(Base):
    __tablename__ = "courses"

    idCourse = Column(Integer, primary_key=True, index=True)
    idUser = Column(Integer, ForeignKey("users.idUser"), nullable=False)
    idDominantLanguage = Column(Integer, nullable=False)
    idLocalLanguage = Column(Integer, nullable=False)
    courseStep = Column(Integer, default=0)

    user = relationship("User")

class CourseCreate(BaseModel):
    idUser: int
    idDominantLanguage: int
    idLocalLanguage: int
    courseStep: int = 0

class CourseUpdate(BaseModel):
    idDominantLanguage: int | None = None
    idLocalLanguage: int | None = None
    courseStep: int | None = None

class Language(Base):
    __tablename__ = "languages"

    idLanguage = Column(Integer, primary_key=True, index=True)
    languageName = Column(String(100), nullable=False, unique=True)
    languageType = Column(Enum("dominant", "local"), nullable=False)
    languageStatus = Column(Enum("registered", "unregistered"), default="unregistered", nullable=True)

class LanguageCreate(BaseModel):
    languageName: str
    languageType: str
    languageStatus: str = "unregistered"

class LanguageUpdate(BaseModel):
    languageName: Optional[str] = None
    languageType: Optional[str] = None
    languageStatus: Optional[str] = None

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

# User Management Endpoints

@app.post("/api/tutur/users")
def create_user(user: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.userEmail == user.userEmail).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(user.userPassword)
    userReferenceFolderId = f"folder_{hashlib.sha256(user.userEmail.encode()).hexdigest()[:8]}"

    new_user = User(
        userName=user.userName,
        userEmail=user.userEmail,
        userPassword=hashed_password,
        userParticipantStatus="nonactive",
        userReferenceFolderId=userReferenceFolderId
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
        "userEmail": user.userEmail,
        "userParticipantStatus": user.userParticipantStatus,
        "userReferenceFolderId": user.userReferenceFolderId
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

    if user_update.userParticipantStatus:
        user.userParticipantStatus = user_update.userParticipantStatus

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

# User Courses Management Endpoints

@app.post("/api/tutur/courses")
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.idUser == course.idUser).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_course = Course(
        idUser=course.idUser,
        idDominantLanguage=course.idDominantLanguage,
        idLocalLanguage=course.idLocalLanguage,
        courseStep=course.courseStep
    )

    db.add(new_course)
    db.commit()
    db.refresh(new_course)

    return {
        "message": "Course created successfully",
        "idCourse": new_course.idCourse
    }

@app.get("/api/tutur/courses")
def get_all_courses(db: Session = Depends(get_db)):

    courses = db.query(Course).all()

    return courses

@app.get("/api/tutur/courses/{idCourse}")
def get_course(idCourse: int, db: Session = Depends(get_db)):

    DominantLanguage = aliased(Language)
    LocalLanguage = aliased(Language)

    result = (
        db.query(Course, User, DominantLanguage, LocalLanguage)
        .join(User, Course.idUser == User.idUser)
        .join(DominantLanguage, Course.idDominantLanguage == DominantLanguage.idLanguage)
        .join(LocalLanguage, Course.idLocalLanguage == LocalLanguage.idLanguage)
        .filter(Course.idCourse == idCourse)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Course not found")

    course, user, dominant_language, local_language = result

    def to_dict(obj):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    return {
        "idCourse": course.idCourse,
        "idUser": course.idUser,
        "idDominantLanguage": course.idDominantLanguage,
        "idLocalLanguage": course.idLocalLanguage,
        "courseStep": course.courseStep,
        "detail": {
            "user": to_dict(user),
            "dominantLanguage": to_dict(dominant_language),
            "localLanguage": to_dict(local_language)
        }
    }

@app.put("/api/tutur/courses/{idCourse}")
def update_course(idCourse: int, course: CourseUpdate, db: Session = Depends(get_db)):
    existing_course = db.query(Course).filter(Course.idCourse == idCourse).first()

    if not existing_course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course.idDominantLanguage is not None:
        existing_course.idDominantLanguage = course.idDominantLanguage

    if course.idLocalLanguage is not None:
        existing_course.idLocalLanguage = course.idLocalLanguage

    if course.courseStep is not None:
        existing_course.courseStep = course.courseStep

    db.commit()
    db.refresh(existing_course)

    return {
        "message": "Course updated successfully"
    }

@app.delete("/api/tutur/courses/{idCourse}")
def delete_course(idCourse: int, db: Session = Depends(get_db)):

    course = db.query(Course).filter(Course.idCourse == idCourse).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    db.delete(course)
    db.commit()

    return {
        "message": "Course deleted successfully"
    }

# Language Management Endpoints

@app.post("/api/tutur/languages")
def create_language(language: LanguageCreate, db: Session = Depends(get_db)):

    existing_language = db.query(Language).filter(
        Language.languageName == language.languageName
    ).first()

    if existing_language:
        raise HTTPException(status_code=400, detail="Language already exists")

    new_language = Language(
        languageName=language.languageName,
        languageType=language.languageType,
        languageStatus=language.languageStatus
    )

    db.add(new_language)
    db.commit()
    db.refresh(new_language)

    return {
        "message": "Language created successfully",
        "idLanguage": new_language.idLanguage
    }

@app.get("/api/tutur/languages")
def get_all_languages(db: Session = Depends(get_db)):

    languages = db.query(Language).all()
    return languages

@app.get("/api/tutur/languages/{idLanguage}")
def get_language(idLanguage: int, db: Session = Depends(get_db)):

    language = db.query(Language).filter(
        Language.idLanguage == idLanguage
    ).first()

    if not language:
        raise HTTPException(status_code=404, detail="Language not found")

    return language

@app.put("/api/tutur/languages/{idLanguage}")
def update_language(idLanguage: int, language: LanguageUpdate, db: Session = Depends(get_db)):

    existing_language = db.query(Language).filter(
        Language.idLanguage == idLanguage
    ).first()

    if not existing_language:
        raise HTTPException(status_code=404, detail="Language not found")

    if language.languageName is not None:
        existing_language.languageName = language.languageName

    if language.languageType is not None:
        existing_language.languageType = language.languageType

    if language.languageStatus is not None:
        existing_language.languageStatus = language.languageStatus

    db.commit()
    db.refresh(existing_language)

    return {
        "message": "Language updated successfully"
    }

@app.delete("/api/tutur/languages/{idLanguage}")
def delete_language(idLanguage: int, db: Session = Depends(get_db)):

    language = db.query(Language).filter(
        Language.idLanguage == idLanguage
    ).first()

    if not language:
        raise HTTPException(status_code=404, detail="Language not found")

    db.delete(language)
    db.commit()

    return {
        "message": "Language deleted successfully"
    }

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

# Folk Song Endpoint

@app.get("/api/tutur/folk-songs")
def get_all_folk_songs():

    if not os.path.exists(BASE_DATASET_PATH):
        raise HTTPException(status_code=404, detail="Dataset folder not found")

    all_songs = []

    for language_folder in os.listdir(BASE_DATASET_PATH):
        language_path = os.path.join(BASE_DATASET_PATH, language_folder)

        if os.path.isdir(language_path):

            for file in os.listdir(language_path):
                if file.endswith(".json"):
                    file_path = os.path.join(language_path, file)

                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        all_songs.append(data)

    return {
        "total": len(all_songs),
        "songs": all_songs
    }

@app.get("/api/tutur/folk-songs/{language}")
def get_songs_by_language(language: str = Path(...)):

    language_path = os.path.join(BASE_DATASET_PATH, language.lower())

    if not os.path.exists(language_path):
        raise HTTPException(status_code=404, detail="Language folder not found")

    songs = []

    for file in os.listdir(language_path):
        if file.endswith(".json"):
            file_path = os.path.join(language_path, file)

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                songs.append(data)

    return {
        "language": language,
        "total": len(songs),
        "songs": songs
    }

@app.get("/api/tutur/folk-song/{song_key}")
def get_song_by_key(song_key: str):

    if not os.path.exists(BASE_DATASET_PATH):
        raise HTTPException(status_code=404, detail="Dataset folder not found")
    
    for language_folder in os.listdir(BASE_DATASET_PATH):
        language_path = os.path.join(BASE_DATASET_PATH, language_folder)

        if os.path.isdir(language_path):

            for file in os.listdir(language_path):
                if file.endswith(".json"):

                    file_name_without_ext = os.path.splitext(file)[0]

                    if file_name_without_ext.lower() == song_key.lower():
                        file_path = os.path.join(language_path, file)

                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        return data

    raise HTTPException(status_code=404, detail="Song not found")

@app.get("/api/tutur/test/folk-song/{song_key}")
def generate_test_from_song(song_key: str):

    if not os.path.exists(BASE_DATASET_PATH):
        raise HTTPException(status_code=404, detail="Dataset folder not found")

    song_data = None

    for language_folder in os.listdir(BASE_DATASET_PATH):
        language_path = os.path.join(BASE_DATASET_PATH, language_folder)

        if os.path.isdir(language_path):
            for file in os.listdir(language_path):
                if file.endswith(".json"):
                    name_without_ext = os.path.splitext(file)[0]

                    if name_without_ext.lower() == song_key.lower():
                        file_path = os.path.join(language_path, file)
                        with open(file_path, "r", encoding="utf-8") as f:
                            song_data = json.load(f)
                        break

    if not song_data:
        raise HTTPException(status_code=404, detail="Song not found")

    timestamps = song_data.get("timestamp", [])

    word_pool = []
    for item in timestamps:
        words = re.findall(r'\b\w+\b', item["text"])
        word_pool.extend(words)

    word_pool = list(set(word_pool))

    questions = []

    for item in timestamps:

        original_text = item["text"]
        words = re.findall(r'\b\w+\b', original_text)

        if len(words) < 2:
            continue

        remove_count = random.randint(1, min(3, len(words)))
        remove_indexes = sorted(random.sample(range(len(words)), remove_count))

        removed_words = [words[i] for i in remove_indexes]

        blank_words = words.copy()
        for i in remove_indexes:
            blank_words[i] = "____"

        question_sentence = " ".join(blank_words)

        options = removed_words.copy()

        distractor_pool = [w for w in word_pool if w not in removed_words]

        while len(options) < 5 and distractor_pool:
            random_word = random.choice(distractor_pool)
            if random_word not in options:
                options.append(random_word)

        random.shuffle(options)

        questions.append({
            "start": item["start"],
            "end": item["end"],
            "question": question_sentence,
            "answer": removed_words,
            "option": options,
            "text": original_text
        })

    return {
        "title": song_data.get("title"),
        "lang": song_data.get("lang"),
        "link": song_data.get("link"),
        "start": song_data.get("start"),
        "end": song_data.get("end"),
        "total_questions": len(questions),
        "timestamp": questions
    }

# NLP Model Translation Endpoint

def lookup_translation(text: str, target_lang: str):
    text = text.strip().lower()
    target_lang = target_lang.strip().lower()

    if target_lang not in df.columns:
        return None

    match = df[df["english"].str.lower() == text]

    if not match.empty:
        return match.iloc[0][target_lang]

    return None

def model_translate(text: str, target_lang: str):
    input_text = f"translate english to {target_lang}: {text}"

    inputs = tokenizer(
        input_text,
        return_tensors="pt",
        max_length=64,
        truncation=True
    ).to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_length=64,
            num_beams=4,
            early_stopping=True
        )

    return tokenizer.decode(outputs[0], skip_special_tokens=True)

@app.post("/api/tutur/translate")
def translate(req: TranslateRequest):

    text = req.text.strip()
    target_lang = req.target_language.lower()

    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    direct_result = lookup_translation(text, target_lang)

    if direct_result:
        return {
            "method": "dataset_lookup",
            "source_language": "english",
            "target_language": target_lang,
            "original_text": text,
            "translated_text": direct_result
        }

    model_result = model_translate(text, target_lang)

    return {
        "method": "model_inference",
        "source_language": "english",
        "target_language": target_lang,
        "original_text": text,
        "translated_text": model_result
    }









