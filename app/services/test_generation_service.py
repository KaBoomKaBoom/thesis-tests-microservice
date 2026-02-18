"""
test_generation_service.py
--------------------------
Generates a randomised test from the questions already stored in the DB.

Rules
------
* A test must cover all question_number values 1-12.
* For each question_number, ONE question is picked at random from the pool
  that matches (type, language, question_number).
* The correct answer is the answer_id already linked to the chosen question.
* 3 wrong answers are picked at random from answers that belong to OTHER
  question_numbers of the same test (they are just distractors by position –
  no answer content analysis is needed here).
* The assembled test is persisted in the `tests` + `test_questions` tables.
"""

import random
from typing import List, Dict, Optional

from sqlalchemy.orm import Session

from app.models.db_models import QuestionDB, AnswerDB, TestDB, test_questions
from app.models.test import GenerateTestRequest, GenerateTestResponse, QuestionEntry

REQUIRED_QUESTION_NUMBERS = list(range(1, 13))   # 1 – 12
WRONG_ANSWERS_COUNT = 3


def generate_test(request: GenerateTestRequest, db: Session) -> GenerateTestResponse:
    """
    Generate a test, persist it, and return the full response payload.

    Raises
    ------
    ValueError  – if any of the 12 question positions cannot be filled.
    """
    # ── 1. For each required question_number pick one random question ─────────
    selected_questions: List[QuestionDB] = []

    for q_num in REQUIRED_QUESTION_NUMBERS:
        candidates: List[QuestionDB] = (
            db.query(QuestionDB)
            .filter(
                QuestionDB.type == request.type,
                QuestionDB.language == request.language,
                QuestionDB.question_number == q_num,
            )
            .all()
        )

        if not candidates:
            raise ValueError(
                f"No question found for type='{request.type}', "
                f"language='{request.language}', question_number={q_num}"
            )

        selected_questions.append(random.choice(candidates))

    # ── 2. Persist the test ───────────────────────────────────────────────────
    test_db = TestDB(type=request.type, language=request.language)
    db.add(test_db)
    db.flush()  # get test_db.id without committing yet

    for position, question in enumerate(selected_questions, start=1):
        db.execute(
            test_questions.insert().values(
                test_id=test_db.id,
                question_id=question.id,
                position=position,
            )
        )

    db.commit()
    db.refresh(test_db)

    # ── 3. Build the pool of correct answer ids for distractor selection ─────
    # We only use answer_ids that are actually linked (not None) and belong to
    # a *different* position than the question being described.
    all_correct_answer_ids: List[Optional[int]] = [q.answer_id for q in selected_questions]

    # Distractor pool = unique non-None answer ids from the whole test
    distractor_pool: List[int] = list({
        aid for aid in all_correct_answer_ids if aid is not None
    })

    # Fallback: if the pool is very small, pull from all answers in the DB
    if len(distractor_pool) < WRONG_ANSWERS_COUNT + 1:
        extra_ids: List[int] = [
            row.id for row in db.query(AnswerDB.id).all()  # type: ignore[attr-defined]
        ]
        distractor_pool = list(set(distractor_pool) | set(extra_ids))

    # ── 4. Build response entries ─────────────────────────────────────────────
    entries: List[QuestionEntry] = []

    for position, question in enumerate(selected_questions, start=1):
        correct_id = question.answer_id

        # Wrong answers: random picks from pool, excluding the correct one
        wrong_pool = [aid for aid in distractor_pool if aid != correct_id]
        wrong_count = min(WRONG_ANSWERS_COUNT, len(wrong_pool))
        incorrect_ids = random.sample(wrong_pool, wrong_count) if wrong_pool else []

        entries.append(
            QuestionEntry(
                position=position,
                question_id=question.id,
                correct_answer_id=correct_id,
                incorrect_answer_ids=incorrect_ids,
            )
        )

    return GenerateTestResponse(
        test_id=test_db.id,
        type=request.type.value,
        language=request.language,
        questions=entries,
    )
