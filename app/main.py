import sys
import logging
from pathlib import Path

# Configure logging before anything else
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)
# Silence noisy third-party loggers
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Add parent directory to path when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from app.routers import answer, question, test
from app.models.question import Question
from app.models.db_models import QuestionDB, AnswerDB
from sqlalchemy.orm import Session
from fastapi import Depends, FastAPI
from contextlib import asynccontextmanager
from app.database import get_db, init_db
from app.routers import extraction


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup: Initialize database
    init_db()
    yield
    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="Thesis Tests Microservice",
    description="API for managing thesis test questions and answers",
    version="1.0.0",
    lifespan=lifespan
)

# Register routers
app.include_router(extraction.router)
app.include_router(question.router)
app.include_router(answer.router)
app.include_router(test.router)

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}

#check db health
@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8070)