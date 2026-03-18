from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from pathlib import Path

from app.database import get_db
from app.models.db_models import AnswerDB, QuestionDB
# from app.services.pdf_extraction_service import extract_and_save_questions
from app.models.question import QuestionType


router = APIRouter(
    prefix="/answer",
    tags=["answer"]
)

@router.get("/count")
def get_answers_count(db: Session = Depends(get_db)):
    """
    Get the total count of answers in the database.
    
    Returns:
        A JSON object with the total number of answers.
    """
    count = db.query(AnswerDB).count()
    return {"answers_count": count}

@router.get("")
def get_all_answers(db: Session = Depends(get_db)):
    """
    Get a list of all answers in the database.
    
    Returns:
        A JSON array of answer objects.
    """
    answers = db.query(AnswerDB).all()
    return answers

@router.get("/{answer_id}")
def get_answer_by_id(answer_id: int, db: Session = Depends(get_db)):
    """
    Get a specific answer by its ID.
    
    Parameters:
        answer_id: The ID of the answer to retrieve.
    
    Returns:
        A JSON object representing the answer, or a 404 error if not found.
    """
    answer = db.query(AnswerDB).filter(AnswerDB.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    return answer

@router.get("/{answer_id}/answer_image")
def get_answer_image(answer_id: int, db: Session = Depends(get_db)):
    """
    Get the image associated with a specific answer by its ID.
    
    Parameters:
        answer_id: The ID of the answer to retrieve the image for.
    
    Returns:
        A FileResponse with the image, or a 404 error if not found.
    """
    answer = db.query(AnswerDB).filter(AnswerDB.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    
    image_path = Path(answer.path_to_answer)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(image_path)

@router.get("/{answer_id}/explanation_image")
def get_explanation_image(answer_id: int, db: Session = Depends(get_db)):
    """
    Get the explanation image associated with a specific answer by its ID.
    
    Parameters:
        answer_id: The ID of the answer to retrieve the explanation image for.
    
    Returns:
        A FileResponse with the explanation image, or a 404 error if not found.
    """
    answer = db.query(AnswerDB).filter(AnswerDB.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    
    explanation_image_path = Path(answer.path_to_answer.replace("_answer.png", "_steps.png"))
    if not explanation_image_path.exists():
        raise HTTPException(status_code=404, detail="Explanation image not found")
    
    return FileResponse(explanation_image_path)