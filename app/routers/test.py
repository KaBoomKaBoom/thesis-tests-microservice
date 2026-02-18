"""
test.py
-------
Router for test generation and retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.cache import get_redis
from app.services.cache_service import cache_get_test, cache_set_test
from app.models.test import (
    GenerateTestRequest, GenerateTestResponse, QuestionEntry,
    VerifyTestRequest, VerifyTestResponse, AnswerResult,
)
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
        result = generate_test(request, db)
        # Persist in Redis (best-effort, never blocks the response)
        try:
            cache_set_test(get_redis(), result)
        except Exception:
            pass
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Test generation failed: {exc}")


@router.get("/{test_id}", response_model=GenerateTestResponse)
def get_test_by_id(test_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a previously generated test by its ID.

    Checks Redis first (24-hour cache). Falls back to the database.
    """
    # ── Cache hit ─────────────────────────────────────────────────────────────
    try:
        cached = cache_get_test(get_redis(), test_id)
        if cached is not None:
            return cached
    except Exception:
        pass  # Redis unavailable – continue to DB

    # ── Cache miss: load from DB ──────────────────────────────────────────────
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

    response = GenerateTestResponse(
        test_id=test_db.id,
        type=test_db.type.value,
        language=test_db.language,
        questions=entries,
    )

    # Backfill the cache so subsequent requests are served from Redis
    try:
        cache_set_test(get_redis(), response)
    except Exception:
        pass

    return response


@router.post("/verify", response_model=VerifyTestResponse)
def verify_test(
    request: VerifyTestRequest,
    db: Session = Depends(get_db),
):
    """
    Verify a completed test.

    Accepts the test_id and the list of answers submitted by the user.
    Returns per-question correctness and an overall score percentage.
    """
    # Load test
    test_db: TestDB | None = db.query(TestDB).filter(TestDB.id == request.test_id).first()
    if not test_db:
        raise HTTPException(status_code=404, detail="Test not found")

    # Load ordered question slots
    rows = (
        db.query(test_questions.c.question_id, test_questions.c.position)
        .filter(test_questions.c.test_id == request.test_id)
        .order_by(test_questions.c.position)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Test has no questions")

    question_ids = [r.question_id for r in rows]
    questions: list[QuestionDB] = (
        db.query(QuestionDB).filter(QuestionDB.id.in_(question_ids)).all()
    )
    q_map = {q.id: q for q in questions}

    # Index submitted answers by question_id for O(1) lookup
    submitted_map = {a.question_id: a.answer_id for a in request.answers}

    results: list[AnswerResult] = []
    correct_count = 0
    skipped_count = 0

    for row in rows:
        q = q_map.get(row.question_id)
        if q is None:
            continue

        correct_id = q.answer_id
        submitted_id = submitted_map.get(q.id)  # None if not submitted

        if submitted_id is None:
            skipped_count += 1

        is_correct = (submitted_id is not None) and (submitted_id == correct_id)
        if is_correct:
            correct_count += 1

        results.append(
            AnswerResult(
                position=row.position,
                question_id=q.id,
                submitted_answer_id=submitted_id,
                correct_answer_id=correct_id,
                is_correct=is_correct,
            )
        )

    total = len(results)
    score_pct = round((correct_count / total) * 100, 2) if total > 0 else 0.0

    return VerifyTestResponse(
        test_id=request.test_id,
        total_questions=total,
        correct_answers=correct_count,
        skipped=skipped_count,
        score_percentage=score_pct,
        results=results,
    )
