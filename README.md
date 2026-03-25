# Thesis Backend - Test and Exercise Handling Microservice

## Contents
- [1. Project title](#1-project-title)
- [2. Project purpose](#2-project-purpose)
- [3. Technologies and instruments used in the project](#3-technologies-and-instruments-used-in-the-project)
- [4. Instructions to run the project](#4-instructions-to-run-the-project)
- [5. Project structure](#5-project-structure)
- [6. Endpoint description](#6-endpoint-description)
- [7. Model and DTO description](#7-model-and-dto-description)

## 1. Project title
### **Educational Web Platform for Assessing and Preparing Students for National Examinations** 

## 2. Project purpose
This project provides a backend API for thesis test workflows:
- upload test PDFs and extract question images;
- upload answer-key (barem) PDFs and extract/link answers;
- store questions, answers, and generated tests in PostgreSQL;
- generate randomized tests (positions 1-12) by type/language;
- verify submitted answers and compute the final score percentage;
- cache generated tests in Redis for faster retrieval.

## 3. Technologies and instruments used in the project
- **Language:** Python 3
- **API framework:** FastAPI
- **ASGI server:** Uvicorn
- **ORM / DB layer:** SQLAlchemy
- **Database:** PostgreSQL (Docker service: `thesis_tests_db`)
- **Cache:** Redis (Docker service: `redis-cache`)
- **Config management:** pydantic-settings + python-dotenv
- **PDF processing / image extraction:** pdfplumber, pdf2image, Pillow, camelot
- **Container orchestration:** Docker Compose

## 4. Instructions to run the project
### Prerequisites
- Python 3.11+ (or compatible with installed dependencies)
- Docker Desktop (or Docker Engine + Compose)

### Step A - Install dependencies
```bash
pip install -r requirements.txt
```

### Step B - Create `.env` in project root
Add at least these variables (names must match exactly):
```env
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_db
DATABASE_URL=postgresql+psycopg2://your_user:your_password@localhost:5433/your_db

API_TITLE=Thesis Tests Microservice
API_VERSION=1.0.0

CORS_ORIGINS=http://localhost:3000

JWT_SECRET=replace_me
JWT_ISSUER=replace_me
JWT_AUDIENCE=replace_me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

REDIS_URL=redis://localhost:6379/0
```

### Step C - Start infrastructure (PostgreSQL + Redis)
```bash
docker compose up -d
```

### Step D - Run the API
From project root:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8070
```

### Step E - Open API docs
- Swagger UI: `http://localhost:8070/docs`
- ReDoc: `http://localhost:8070/redoc`
- Health check: `http://localhost:8070/health`

### Notes
- Tables are created at startup via `init_db()` in app lifespan.
- If schema changes are not reflected, recreate volumes:
```bash
docker compose down -v
docker compose up -d
```

## 5. Project structure
```text
thesis-tests-microservice/
├── app/
│   ├── main.py                  # FastAPI app bootstrap and router registration
│   ├── config.py                # Environment-based settings
│   ├── database.py              # SQLAlchemy engine/session/init
│   ├── cache.py                 # Redis client factory
│   ├── models/
│   │   ├── db_models.py         # SQLAlchemy models (Question, Answer, Test)
│   │   ├── question.py          # Pydantic question schemas/enums
│   │   ├── answer.py            # Pydantic answer schemas
│   │   └── test.py              # Pydantic test generation/verification schemas
│   ├── routers/
│   │   ├── extraction.py        # PDF upload + extraction endpoints
│   │   ├── question.py          # Question endpoints
│   │   ├── answer.py            # Answer endpoints
│   │   └── test.py              # Test generate/get/verify endpoints
│   ├── services/
│   │   ├── pdf_extraction_math_service.py     # Question extraction logic
│   │   ├── answer_extraction_math_service.py  # Barem/answer extraction logic
│   │   ├── test_generation_service.py          # Randomized test generation + DB persist
│   │   └── cache_service.py                    # Redis cache helpers for tests
│   ├── repositories/            # Data-access abstractions (currently minimal)
│   └── utils/                   # Shared helpers/utilities
├── docker-compose.yml           # PostgreSQL + Redis services
├── requirements.txt             # Python dependencies
└── README.md
```

## 6. Endpoint description

### Health / utility
- `GET /` - Basic root endpoint.
- `GET /health` - Service health check.

### Extraction endpoints (`/extraction`)
- `POST /extraction/upload-pdf`
	- Uploads a test PDF and extracts question images.
	- Input: `multipart/form-data` (`file`, optional `question_type`).
	- Output: extraction summary (`success`, `questions_saved`, `questions`, etc.).

- `POST /extraction/upload-barem`
	- Uploads a barem PDF, extracts answer keys, saves answers, and links answers to questions.
	- Input: `multipart/form-data` (`file`).
	- Output: extraction/linking summary.

- `GET /extraction/status`
	- Returns extraction service availability.

### Question endpoints (`/question`)
- `GET /question/count` - Total number of questions.
- `GET /question` - List all questions.
- `GET /question/{question_id}` - Get question metadata by ID.
- `GET /question/{question_id}/image` - Get question image file.

### Answer endpoints (`/answer`)
- `GET /answer/count` - Total number of answers.
- `GET /answer` - List all answers.
- `GET /answer/{answer_id}` - Get answer metadata by ID.
- `GET /answer/{answer_id}/answer_image` - Get answer image file.
- `GET /answer/{answer_id}/explanation_image` - Get explanation/steps image file.

### Test endpoints (`/test`)
- `POST /test/generate`
	- Generates a randomized test (question positions 1-12), saves it in DB, and caches it in Redis.
	- Input DTO: `GenerateTestRequest`.
	- Output DTO: `GenerateTestResponse`.

- `GET /test`
	- Returns tests filtered by `type` and optional `language`, including question IDs in `questions`.

- `GET /test/{test_id}`
	- Returns full test content by ID.
	- Uses Redis cache first, then DB fallback.

- `POST /test/verify`
	- Verifies submitted answers against stored correct answers and returns score percentage.
	- Input DTO: `VerifyTestRequest`.
	- Output DTO: `VerifyTestResponse`.

## 7. Model and DTO description

### Database models (SQLAlchemy)
- `AnswerDB` (`answers` table)
	- `id`, `path_to_answer`, `question_number`
	- One-to-many relation with `QuestionDB` (`questions` backref).

- `QuestionDB` (`questions` table)
	- `id`, `path_to_question`, `answer_id`, `type`, `question_number`, `language`
	- `answer_id` references `answers.id`.

- `TestDB` (`tests` table)
	- `id`, `type`, `language`
	- Many-to-many relation with `QuestionDB` via `test_questions`.

- `test_questions` (association table)
	- `test_id`, `question_id`, `position`
	- Stores ordered question membership for each generated test.

### DTOs / API schemas (Pydantic)

#### Question DTOs (`app/models/question.py`)
- `QuestionBase`: shared fields (`path_to_question`, `answer_id`, `type`, `question_number`)
- `Question`: `QuestionBase` + `id`
- `QuestionCreate`: create payload
- `QuestionUpdate`: partial update payload

#### Answer DTOs (`app/models/answer.py`)
- `AnswerBase`: shared fields (`path_to_answer`, `question_number`)
- `Answer`: `AnswerBase` + `id`
- `AnswerCreate`: create payload
- `AnswerUpdate`: partial update payload

#### Test DTOs (`app/models/test.py`)
- `GenerateTestRequest`: input for test generation (`type`, `language`)
- `QuestionEntry`: per-question response object (`position`, `question_id`, `correct_answer_id`, `incorrect_answer_ids`)
- `GenerateTestResponse`: generated test payload (`test_id`, `type`, `language`, `questions`)
- `SubmittedAnswer`: one submitted answer item (`question_id`, `answer_id`)
- `VerifyTestRequest`: verification request (`test_id`, `answers`)
- `AnswerResult`: per-question verification result (`is_correct`, expected/submitted answer IDs)
- `VerifyTestResponse`: final verification summary (`total_questions`, `correct_answers`, `skipped`, `score_percentage`, `results`)

