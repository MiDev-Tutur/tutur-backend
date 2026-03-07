# Tutur Application

> Backend service for the **Tutur Application** — a Natural Language Processing platform.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [NLP Model Setup](#nlp-model-setup) *(Optional)*
- [Running the Server](#running-the-server)

---

## Prerequisites

Ensure **Python** is installed on your system before proceeding.

**Recommended Version:** Python `3.14.3`

📥 Download Python from the official website:
[https://www.python.org/downloads/](https://www.python.org/downloads/)

---

## Installation

Install all required project dependencies by running the following command in the **project root directory**:

```bash
pip install -r requirements.txt
```

---

## Database Setup

The backend requires a local MySQL database to function properly. Follow the steps below to set it up.

1. Make sure **XAMPP** (or any local server with phpMyAdmin) is installed and running, with both **Apache** and **MySQL** services active.

2. Open your browser and navigate to:

   ```
   http://localhost/phpmyadmin
   ```

3. Log in using the **default credentials**:

   | Field    | Value   |
   |----------|---------|
   | Username | `root`  |
   | Password | *(leave blank)* |

4. Create a new database named:

   ```
   db_tutur
   ```

5. Select the newly created database, then go to the **Import** tab.

6. Click **Choose File** and select the SQL file located at:

   ```
   databases/db_tutur.sql
   ```

7. Click **Go** to import the database.

Once the import is complete, the backend server will be able to connect to the database.

---

## NLP Model Setup

> ⚠️ **Optional** — Only required if you want to test the **Natural Language Translation** endpoint.

1. Create a new folder in the project root directory named:

   ```
   translator_model_lite
   ```

2. Download the pre-trained NLP model from the link below:

   📦 [Download Model (Google Drive)](https://drive.google.com/file/d/1JzCOA6eQk7oBbPuhTzsonz3aPq8FNSts/view?usp=sharing)

3. Extract the contents of the downloaded `.zip` file into the `translator_model_lite` folder.

---

## Running the Server

Once all dependencies are installed and the database is configured, start the backend server by running the following command in the **project root directory**:

```bash
uvicorn apiGateway:app --reload
```

The server will start and hot-reload automatically on any code changes.

---

## Project Structure

```
project-root/
├── apiGateway.py
├── requirements.txt
├── databases/
│   └── db_tutur.sql              # Import this file into phpMyAdmin
└── translator_model_lite/        # Optional: place extracted NLP model here
```

---

*For any issues or questions, please open an issue in this repository.*
