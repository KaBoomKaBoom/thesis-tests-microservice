"""
test.py
-------
Router for test generation and retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.test import GenerateTestRequest, GenerateTestResponse, QuestionEntry
from app.models.db_models import TestDB, test_questions, QuestionDB
from app.services.test_generation_service import generate_test

router = APIRouter(
    prefix="/test",
    tags=["test"],
)


@router.post("/generate", response_model=GenerateTestResponse, status_code=201)
def generate_test_endpoint(
    request: GenerateTestRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a randomised test.

    - Picks one question per position (1-12) matching **type** and **language**.
    - Saves the test to the database.
    - Returns: test_id, per-question slot with correct answer id and 3 random incorrect answer ids.
    """
    try:
        return generate_test(request, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Test generation failed: {exc}")


@router.get("/{test_id}", response_model=GenerateTestResponse)
def get_test_by_id(test_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a previously generated test by its ID.

    Returns the same structure as the generate endpoint, reconstructing
    correct / incorrect answer ids on the fly.
    """
    test_db: TestDB | None = db.query(TestDB).filter(TestDB.id == test_id).first()
    if not test_db:
        raise HTTPException(status_code=404, detail="Test not found")

    # Load ordered questions via the association table
    rows = (
        db.query(test_questions.c.question_id, test_questions.c.position)
        .filter(test_questions.c.test_id == test_id)
        .order_by(test_questions.c.position)
        .all()
    )

    question_ids = [r.question_id for r in rows]
    questions: list[QuestionDB] = (
        db.query(QuestionDB).filter(QuestionDB.id.in_(question_ids)).all()
    )
    q_map = {q.id: q for q in questions}

    all_correct = [q_map[qid].answer_id for qid in question_ids if qid in q_map]
    distractor_pool = list({aid for aid in all_correct if aid is not None})

    import random

    entries: list[QuestionEntry] = []
    for row in rows:
        q = q_map.get(row.question_id)
        if q is None:
            continue
        correct_id = q.answer_id
        wrong_pool = [aid for aid in distractor_pool if aid != correct_id]
        from app.services.test_generation_service import WRONG_ANSWERS_COUNT
        wrong_count = min(WRONG_ANSWERS_COUNT, len(wrong_pool))
        incorrect_ids = random.sample(wrong_pool, wrong_count) if wrong_pool else []
        entries.append(
            QuestionEntry(
                position=row.position,
                question_id=q.id,
                correct_answer_id=correct_id,
                incorrect_answer_ids=incorrect_ids,
            )
        )

    return GenerateTestResponse(
        test_id=test_db.id,
        type=test_db.type.value,
        language=test_db.language,
        questions=entries,
    )
