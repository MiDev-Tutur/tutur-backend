# Tutur Application

> Backend service for the **Tutur Application** — a Natural Language Processing platform.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
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

Once all dependencies are installed, start the backend server by running the following command in the **project root directory**:

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
└── translator_model_lite/    # Optional: place extracted NLP model here
```

---

*For any issues or questions, please open an issue in this repository.*
