"""
extraction.py
-------------
Router for PDF extraction endpoints.
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services.pdf_extraction_service import extract_and_save_questions
from app.models.question import QuestionType


router = APIRouter(
    prefix="/extraction",
    tags=["extraction"]
)


@router.post("/upload-pdf")
async def upload_and_extract_pdf(
    file: UploadFile = File(..., description="PDF file containing questions"),
    question_type: Optional[QuestionType] = Form(QuestionType.MATH, description="Type of questions in the PDF"),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF file and extract questions from it.
    
    - **file**: PDF file to extract questions from
    - **question_type**: Type of questions (math, physics, etc.) - defaults to math
    
    Returns the extraction results and saves questions to the database.
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )
    
    # Read file content
    pdf_content = await file.read()
    
    if len(pdf_content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty file provided"
        )
    
    # Extract and save questions
    result = extract_and_save_questions(
        pdf_content=pdf_content,
        pdf_filename=file.filename,
        db=db,
        question_type=question_type
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=result["message"]
        )
    
    return result


@router.get("/status")
def extraction_status():
    """
    Check if extraction service is available.
    """
    return {
        "service": "PDF Extraction",
        "status": "available"
    }
