import hashlib
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext
from fastapi.responses import JSONResponse
import pandas as pd
import os

app = FastAPI(title="Tutur API Gateway")

DATASET_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "datasets",
    "DatasetLanguage.xlsx"
)

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
