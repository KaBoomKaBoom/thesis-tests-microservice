import sys
from pathlib import Path

# Add parent directory to path when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import init_db


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


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8070)