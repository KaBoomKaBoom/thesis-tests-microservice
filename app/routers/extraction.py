"""
extraction.py
-------------
Router for PDF extraction endpoints.
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from pathlib import Path

from app.database import get_db
from app.services.pdf_extraction_math_service import extract_and_save_questions
from app.services.answer_extraction_math_service import extract_and_save_answers
from app.models.question import QuestionType
from app.models.db_models import TestDB, test_questions


router = APIRouter(
    prefix="/extraction",
    tags=["extraction"]
)


@router.post("/upload-pdf")
async def upload_and_extract_pdf(
    files: List[UploadFile] = File(..., description="PDF file(s) containing questions"),
    user_id: int = Form(..., description="Uploader user ID", ge=1),
    question_type: Optional[QuestionType] = Form(QuestionType.MATH, description="Type of questions in the PDF"),
    language: Optional[str] = Form(None, description="Language code (ro, ru, en) - if not provided, detected from filename"),
    db: Session = Depends(get_db)
):
    """
    Upload one or more PDF files and extract questions from them.
    
    - **files**: PDF file(s) to extract questions from
    - **question_type**: Type of questions (math, physics, etc.) - defaults to math
    
    Returns extraction results for all files and saves questions to the database.
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one PDF file is required"
        )
    
    results = []
    
    for file in files:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            results.append({
                "filename": file.filename,
                "success": False,
                "message": "Only PDF files are allowed"
            })
            continue
        
        # Read file content
        pdf_content = await file.read()
        
        if len(pdf_content) == 0:
            results.append({
                "filename": file.filename,
                "success": False,
                "message": "Empty file provided"
            })
            continue
        
        # Extract and save questions
        result = extract_and_save_questions(
            pdf_content=pdf_content,
            pdf_filename=file.filename,
            db=db,
            question_type=question_type,
            language=language
        )
        
        if not result["success"]:
            results.append({
                "filename": file.filename,
                **result
            })
            continue

        # Save uploaded test metadata and link extracted questions to the test
        try:
            test_name = Path(file.filename).stem
            uploaded_test = TestDB(
                user_id=user_id,
                name=test_name,
                type=question_type,
                language=result.get("language"),
            )
            db.add(uploaded_test)
            db.flush()

            for item in sorted(result.get("questions", []), key=lambda q: q.get("number", 0)):
                question_id = item.get("id")
                position = item.get("number")
                if question_id is None or position is None:
                    continue
                db.execute(
                    test_questions.insert().values(
                        test_id=uploaded_test.id,
                        question_id=question_id,
                        position=position,
                    )
                )

            db.commit()
            result["filename"] = file.filename
            result["test_id"] = uploaded_test.id
            result["test_name"] = uploaded_test.name
            result["userId"] = uploaded_test.user_id
            results.append(result)
        except Exception as e:
            db.rollback()
            results.append({
                "filename": file.filename,
                "success": False,
                "message": f"Questions were extracted, but creating test metadata failed: {str(e)}"
            })
    
    return {
        "total_files": len(files),
        "processed": len([r for r in results if r.get("success", False)]),
        "failed": len([r for r in results if not r.get("success", False)]),
        "results": results
    }


@router.get("/status")
def extraction_status():
    """
    Check if extraction service is available.
    """
    return {
        "service": "PDF Extraction",
        "status": "available"
    }


@router.post("/upload-barem")
async def upload_and_extract_barem(
    file: UploadFile = File(..., description="Barem PDF file containing answer keys"),
    db: Session = Depends(get_db)
):
    """
    Upload a barem (answer key) PDF file and extract answers.
    
    The barem filename should follow the pattern: XX_subject_baremN_..._esYY.pdf
    Corresponding test file should be: XX_subject_testN_..._esYY.pdf
    
    - **file**: Barem PDF file to extract answers from
    
    Returns the extraction results, saves answers to the database,
    and links them to corresponding questions.
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )
    
    # Validate barem filename pattern
    if "_barem" not in file.filename:
        raise HTTPException(
            status_code=400,
            detail="File must be a barem PDF (filename should contain '_barem')"
        )
    
    # Read file content
    pdf_content = await file.read()
    
    if len(pdf_content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty file provided"
        )
    
    # Extract and save answers
    result = extract_and_save_answers(
        pdf_content=pdf_content,
        pdf_filename=file.filename,
        db=db
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=result["message"]
        )
    
    return result
