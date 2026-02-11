from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from pathlib import Path

from app.database import get_db
from app.models.db_models import QuestionDB
from app.services.pdf_extraction_service import extract_and_save_questions
from app.models.question import QuestionType


router = APIRouter(
    prefix="/question",
    tags=["question"]
)

@router.get("/count")
def get_questions_count(db: Session = Depends(get_db)):
    """
    Get the total count of questions in the database.
    
    Returns:
        A JSON object with the total number of questions.
    """
    count = db.query(QuestionDB).count()
    return {"questions_count": count}

@router.get("")
def get_all_questions(db: Session = Depends(get_db)):
    """
    Get a list of all questions in the database.
    
    Returns:
        A JSON array of question objects.
    """
    questions = db.query(QuestionDB).all()
    return questions

@router.get("/{question_id}")
def get_question_by_id(question_id: int, db: Session = Depends(get_db)):
    """
    Get a specific question by its ID.
    
    Parameters:
        question_id: The ID of the question to retrieve.
    
    Returns:
        A JSON object representing the question, or a 404 error if not found.
    """
    question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


@router.get("/{question_id}/image")
def get_question_image(question_id: int, db: Session = Depends(get_db)):
    """
    Get the actual image file for a specific question.
    
    Parameters:
        question_id: The ID of the question.
    
    Returns:
        The image file (PNG format).
    """
    question = db.query(QuestionDB).filter(QuestionDB.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Construct the full path to the image file
    image_path = Path(question.path_to_question)
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    
    return FileResponse(
        path=str(image_path),
        media_type="image/png",
        filename=image_path.name
    )

