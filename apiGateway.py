import hashlib
from fastapi import FastAPI, HTTPException, Depends, Path
from pydantic import BaseModel, EmailStr
from sqlalchemy import Enum, create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship, aliased
from passlib.context import CryptContext
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List, Optional
from typing import List, Optional
from gtts import gTTS
import pandas as pd
import io
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

class JoinRequest(BaseModel):
    idUser: int

class AddLanguageRequest(BaseModel):
    idUser: int
    languageName: str
    dominantLanguage: str

class TranslationUpdateItem(BaseModel):
    row_position: int
    translation: Optional[str]

class UpdateTranslationRequest(BaseModel):
    translations: List[TranslationUpdateItem]

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

def generate_word_questions(words_df, dominant, local):

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

        options = distractors[:4] + [correct_answer]
        options = list(set(options))
        random.shuffle(options)

        questions.append({
            "question": question_text,
            "options": options,
            "answer": correct_answer,
            "type": direction
        })

    random.shuffle(questions)
    return questions[:10]

def generate_phrase_questions(phrase_df, word_df, dominant, local):

    questions = []

    phrase_list = phrase_df.to_dict("records")
    word_list = word_df.to_dict("records")

    while len(questions) < 10:

        row = random.choice(phrase_list)
        question_type = random.choice(["dominant", "local", "blank"])

        if question_type == "dominant":

            question_text = row[dominant]
            correct_answer = row[local]

            option_pool = [p[local] for p in phrase_list]

        elif question_type == "local":

            question_text = row[local]
            correct_answer = row[dominant]

            option_pool = [p[dominant] for p in phrase_list]

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

            continue

        distractors = [x for x in option_pool if x != correct_answer]
        random.shuffle(distractors)

        options = distractors[:4] + [correct_answer]
        options = list(set(options))
        random.shuffle(options)

        questions.append({
            "question": question_text,
            "options": options,
            "answer": correct_answer,
            "type": question_type
        })

    return questions

def generate_sentence_questions(sentence_df, word_df, dominant, local):

    questions = []

    sentence_list = sentence_df.to_dict("records")
    word_list = word_df.to_dict("records")

    while len(questions) < 10:

        row = random.choice(sentence_list)
        question_type = random.choice(["dominant", "local", "blank"])

        if question_type == "dominant":

            question_text = row[dominant]
            correct_answer = row[local]

            option_pool = [s[local] for s in sentence_list]

        elif question_type == "local":

            question_text = row[local]
            correct_answer = row[dominant]

            option_pool = [s[dominant] for s in sentence_list]

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

            continue

        distractors = [x for x in option_pool if x != correct_answer]
        random.shuffle(distractors)

        options = distractors[:4] + [correct_answer]
        options = list(set(options))
        random.shuffle(options)

        questions.append({
            "question": question_text,
            "options": options,
            "answer": correct_answer,
            "type": question_type
        })

    return questions

def find_step(courses, step):

    for topic in courses.values():
        for item in topic:
            if item["step"] == step:
                return item

    return None

@app.get("/api/tutur/course/{dominant}/{local}")
def get_all_course(dominant: str, local: str):

    if dominant not in df.columns or local not in df.columns:
        raise HTTPException(status_code=400, detail="Language column not found")

    if not os.path.exists(COURSE_PATH):
        raise HTTPException(status_code=404, detail="Course file not found")

    with open(COURSE_PATH, "r", encoding="utf-8") as f:
        courses = json.load(f)

    result = []

    for topic in courses.values():
        for item in topic:

            step = item["step"]

            if "listWords" in item:

                rows = item["listWords"]
                words_df = df[df["row_position"].isin(rows)]

                questions = generate_word_questions(words_df, dominant, local)

            elif "listPhrases" in item:

                prev_step = find_step(courses, step - 1)

                if not prev_step:
                    continue

                phrase_df = df[df["row_position"].isin(item["listPhrases"])]
                word_df = df[df["row_position"].isin(prev_step["listWords"])]

                questions = generate_phrase_questions(
                    phrase_df,
                    word_df,
                    dominant,
                    local
                )

            elif "listSentences" in item:

                word_step = find_step(courses, step - 2)

                if not word_step:
                    continue

                sentence_df = df[df["row_position"].isin(item["listSentences"])]
                word_df = df[df["row_position"].isin(word_step["listWords"])]

                questions = generate_sentence_questions(
                    sentence_df,
                    word_df,
                    dominant,
                    local
                )

            else:
                continue

            result.append({
                "step": step,
                "questions": questions
            })

    result = sorted(result, key=lambda x: x["step"])

    return {
        "total_step": len(result),
        "total_questions": len(result) * 10,
        "courses": result
    }

@app.get("/api/tutur/course/{step}/{dominant}/{local}")
def get_course_by_step(step: int, dominant: str, local: str):

    if dominant not in df.columns or local not in df.columns:
        raise HTTPException(status_code=400, detail="Language column not found")

    if not os.path.exists(COURSE_PATH):
        raise HTTPException(status_code=404, detail="Course file not found")

    with open(COURSE_PATH, "r", encoding="utf-8") as f:
        courses = json.load(f)

    selected_step = None
    previous_step = None
    word_step = None

    for topic in courses.values():
        for item in topic:

            if item["step"] == step:
                selected_step = item

            if item["step"] == step - 1:
                previous_step = item

            if item["step"] == step - 2:
                word_step = item

    if not selected_step:
        raise HTTPException(status_code=404, detail="Step not found")

    if "listWords" in selected_step:

        rows = selected_step["listWords"]
        words_df = df[df["row_position"].isin(rows)]

        questions = generate_word_questions(words_df, dominant, local)

    elif "listPhrases" in selected_step:

        phrase_df = df[df["row_position"].isin(selected_step["listPhrases"])]
        word_df = df[df["row_position"].isin(previous_step["listWords"])]

        questions = generate_phrase_questions(phrase_df, word_df, dominant, local)

    elif "listSentences" in selected_step:

        sentence_df = df[df["row_position"].isin(selected_step["listSentences"])]
        word_df = df[df["row_position"].isin(word_step["listWords"])]

        questions = generate_sentence_questions(sentence_df, word_df, dominant, local)

    else:
        raise HTTPException(status_code=400, detail="Unknown step type")

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

# Community Participation Endpoints

@app.post("/api/tutur/community/join")
def join_community(data: JoinRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.idUser == data.idUser).first()
    string_idUser = str(data.idUser)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.userParticipantStatus == "active":
        return {
            "status": "success",
            "message": "User already joined community",
            "folder": user.userReferenceFolderId
        }

    try:
        hashtext = hashlib.md5(string_idUser.encode()).hexdigest()[:8]

        folder_name = f"folder_{hashtext}"
        base_dir = os.path.dirname(os.path.abspath(__file__))
        folder_path = os.path.join(
            base_dir,
            "databases",
            "activeParticipants",
            folder_name
        )

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        user.userParticipantStatus = "active"
        user.userReferenceFolderId = folder_name

        db.commit()

        return {
            "status": "success",
            "message": "User successfully joined community",
            "folderCreated": folder_name
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Gagal join community: {str(e)}"
        )

def normalize_language_name(name: str):
    return name.lower().replace(" ", "_")

@app.post("/api/tutur/community/addLanguage")
def add_language(data: AddLanguageRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.idUser == data.idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.userReferenceFolderId:
        raise HTTPException(status_code=400, detail="User not joined community")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    user_folder = os.path.join(
        base_dir,
        "databases",
        "activeParticipants",
        user.userReferenceFolderId
    )

    if not os.path.exists(user_folder):
        raise HTTPException(status_code=404, detail="Participant folder hasn't been created")

    # path dataset excel
    dataset_path = os.path.join(
        base_dir,
        "datasets",
        "DatasetLanguage.xlsx"
    )

    if not os.path.exists(dataset_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    # baca excel
    df = pd.read_excel(dataset_path)

    dominant_lang = normalize_language_name(data.dominantLanguage)

    if dominant_lang not in df.columns:
        raise HTTPException(
            status_code=400,
            detail=f"Dominant language '{dominant_lang}' not found in dataset"
        )

    # generate temp id language
    temp_id = random.randint(100000, 999999)

    translations = []

    for index, row in df.iterrows():

        source_text = row[dominant_lang]
        row_type = row["type"] if "type" in df.columns else "phrase"

        if pd.isna(source_text):
            continue

        translations.append({
            "row_position": int(index) + 2,
            "type": row_type,
            "source": source_text,
            "translation": None
        })

    language_json = {
        "tempIdLanguage": str(temp_id),
        "languageName": data.languageName,
        "dominantLanguage": data.dominantLanguage,
        "translations": translations
    }

    filename = normalize_language_name(data.languageName) + ".json"

    file_path = os.path.join(user_folder, filename)

    if os.path.exists(file_path):
        raise HTTPException(
            status_code=400,
            detail="Language name already exists"
        )

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(language_json, f, indent=4, ensure_ascii=False)

    return {
        "status": "success",
        "message": "Language added successfully",
        "languageFile": filename,
        "totalTranslations": len(translations)
    }

@app.get("/api/tutur/community/dataset/{idUser}")
def get_translation_dataset(idUser: int, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.userParticipantStatus != "active":
        raise HTTPException(status_code=400, detail="User is not a participant")

    folder_path = os.path.join(
        "databases",
        "activeParticipants",
        user.userReferenceFolderId
    )

    translation_file = os.path.join(folder_path, "translation.json")

    if not os.path.exists(translation_file):
        raise HTTPException(status_code=404, detail="Translation file not found")

    with open(translation_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data

@app.get("/api/tutur/community/listLanguages/{idUser}")
def list_languages(idUser: str, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.userReferenceFolderId:
        raise HTTPException(status_code=400, detail="User not joined community")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    user_folder = os.path.join(
        base_dir,
        "databases",
        "activeParticipants",
        user.userReferenceFolderId
    )

    if not os.path.exists(user_folder):
        raise HTTPException(status_code=404, detail="Participant folder hasn't been created")

    languages = []

    for file in os.listdir(user_folder):

        if file.endswith(".json"):

            file_path = os.path.join(user_folder, file)

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                languages.append(data)

    return {
        "status": "success",
        "totalLanguages": len(languages),
        "languages": languages
    }

@app.get("/api/tutur/community/listLanguages/{idUser}/{languageName}")
def get_language(idUser: str, languageName: str, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.userReferenceFolderId:
        raise HTTPException(status_code=400, detail="User not joined community")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    user_folder = os.path.join(
        base_dir,
        "databases",
        "activeParticipants",
        user.userReferenceFolderId
    )

    if not os.path.exists(user_folder):
        raise HTTPException(status_code=404, detail="Participant folder hasn't been created")

    language_target = normalize_language_name(languageName)

    for file in os.listdir(user_folder):

        if file.endswith(".json"):

            file_path = os.path.join(user_folder, file)

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                if normalize_language_name(data["languageName"]) == language_target:

                    return {
                        "status": "success",
                        "language": data
                    }

    raise HTTPException(
        status_code=404,
        detail="Language not found"
    )

@app.get("/api/tutur/community/progress/{idUser}/{languageName}")
def translation_progress(
    idUser: str,
    languageName: str,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    user_folder = os.path.join(
        base_dir,
        "databases",
        "activeParticipants",
        user.userReferenceFolderId
    )

    if not os.path.exists(user_folder):
        raise HTTPException(status_code=404, detail="Participant folder hasn't been created")

    target_language = normalize_language_name(languageName)

    for file in os.listdir(user_folder):

        if file.endswith(".json"):

            file_path = os.path.join(user_folder, file)

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                if normalize_language_name(data["languageName"]) == target_language:

                    translations = data["translations"]

                    total = len(translations)

                    filled = sum(
                        1 for t in translations
                        if t["translation"] not in [None, "", "null"]
                    )

                    progress = round((filled / total) * 100, 2) if total > 0 else 0

                    return {
                        "status": "success",
                        "languageName": data["languageName"],
                        "totalRows": total,
                        "translatedRows": filled,
                        "progressPercent": progress
                    }

    raise HTTPException(status_code=404, detail="Language not found")

@app.post("/api/tutur/community/updateTranslation/{idUser}/{languageName}")
def update_translation(
    idUser: str,
    languageName: str,
    data: UpdateTranslationRequest,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    user_folder = os.path.join(
        base_dir,
        "databases",
        "activeParticipants",
        user.userReferenceFolderId
    )

    if not os.path.exists(user_folder):
        raise HTTPException(status_code=404, detail="Participant folder hasn't been created")

    target_language = normalize_language_name(languageName)

    target_file = None
    language_json = None

    for file in os.listdir(user_folder):

        if file.endswith(".json"):

            file_path = os.path.join(user_folder, file)

            with open(file_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)

                if normalize_language_name(json_data["languageName"]) == target_language:
                    target_file = file_path
                    language_json = json_data
                    break

    if not target_file:
        raise HTTPException(status_code=404, detail="Language not found")

    translation_map = {
        item.row_position: item.translation
        for item in data.translations
    }

    updated_count = 0

    for row in language_json["translations"]:

        pos = row["row_position"]

        if pos in translation_map:

            if translation_map[pos] is not None:
                row["translation"] = translation_map[pos]
                updated_count += 1

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(language_json, f, indent=4, ensure_ascii=False)

    return {
        "status": "success",
        "message": "Translations updated successfully",
        "updatedRows": updated_count
    }

@app.post("/api/tutur/community/save/{idUser}/{languageName}")
def save_language(
    idUser: str,
    languageName: str,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    user_folder = os.path.join(
        base_dir,
        "databases",
        "activeParticipants",
        user.userReferenceFolderId
    )

    if not os.path.exists(user_folder):
        raise HTTPException(status_code=404, detail="Participant folder hasn't been created")

    language_key = normalize_language_name(languageName)

    json_path = os.path.join(user_folder, f"{language_key}.json")

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Json file not found")

    with open(json_path, "r", encoding="utf-8") as f:
        language_data = json.load(f)

    translations = language_data["translations"]

    total = len(translations)
    filled = sum(
        1 for t in translations
        if t["translation"] not in [None, "", "null"]
    )

    progress = (filled / total) * 100 if total > 0 else 0

    if progress < 100:
        raise HTTPException(
            status_code=400,
            detail=f"Translation progress not complete ({round(progress,2)}%)"
        )

    dataset_path = os.path.join(
        base_dir,
        "datasets",
        "DatasetLanguage.xlsx"
    )

    if not os.path.exists(dataset_path):
        raise HTTPException(status_code=404, detail="DatasetLanguage.xlsx not found")

    df = pd.read_excel(dataset_path)

    if language_key in df.columns:
        raise HTTPException(status_code=400, detail="Language already exists")

    insert_position = df.columns.get_loc("type")

    df.insert(insert_position, language_key, "")

    for t in translations:

        row_index = t["row_position"] - 2
        df.at[row_index, language_key] = t["translation"]

    df.to_excel(dataset_path, index=False)

    existing_language = db.query(Language).filter(
        Language.languageName == languageName
    ).first()

    if not existing_language:

        new_language = Language(
            languageName=languageName,
            languageType="local",
            languageStatus="active"
        )

        db.add(new_language)
        db.commit()
        db.refresh(new_language)

        language_id = new_language.idLanguage

    else:
        language_id = existing_language.idLanguage

    return {
        "status": "success",
        "message": "Language saved successfully",
        "languageName": languageName,
        "idLanguage": language_id
    }

@app.delete("/api/tutur/community/delete/{idUser}/{languageName}")
def delete_language(
    idUser: str,
    languageName: str,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(User.idUser == idUser).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    user_folder = os.path.join(
        base_dir,
        "databases",
        "activeParticipants",
        user.userReferenceFolderId
    )

    if not os.path.exists(user_folder):
        raise HTTPException(status_code=404, detail="Participant folder hasn't been created")

    language_key = normalize_language_name(languageName)

    json_path = os.path.join(user_folder, f"{language_key}.json")

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Language not found")

    os.remove(json_path)

    return {
        "status": "success",
        "message": "Language deleted successfully",
        "deletedLanguage": languageName
    }

LANGUAGE_MAP = {
    "indonesia": "id",
    "english": "en",
    "malay": "ms",
    "iban" : "ms",
    "melayu_serawak" : "ms",
}

@app.get("/api/tutur/speak/{lang}")
def generate_audio(
    text: str,
    lang: str
):

    if lang not in LANGUAGE_MAP:
        lang = "id"

    language_code = LANGUAGE_MAP.get(lang.lower(), "id")

    mp3_fp = io.BytesIO()

    tts = gTTS(text, lang=language_code)
    tts.write_to_fp(mp3_fp)

    mp3_fp.seek(0)

    return StreamingResponse(
        mp3_fp,
        media_type="audio/mpeg"
    )




