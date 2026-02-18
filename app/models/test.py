from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.models.question import QuestionType


class GenerateTestRequest(BaseModel):
    """Request body for generating a new test."""
    type: QuestionType = Field(..., description="Subject type of the test")
    language: str = Field(..., description="Language code: ro | ru | en", pattern="^(ro|ru|en)$")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "math",
                "language": "ro"
            }
        }
    )


class QuestionEntry(BaseModel):
    """A single question slot inside a generated test response."""
    position: int = Field(..., description="1-based position in the test (equals question_number)")
    question_id: int
    correct_answer_id: Optional[int] = Field(None, description="The linked correct answer id (may be null if not yet uploaded)")
    incorrect_answer_ids: List[int] = Field(default_factory=list, description="3 randomly chosen wrong answer ids")


class GenerateTestResponse(BaseModel):
    """Response returned after generating a test."""
    test_id: int
    type: str
    language: Optional[str]
    questions: List[QuestionEntry]


# ── Verification models ───────────────────────────────────────────────────────

class SubmittedAnswer(BaseModel):
    """A single answer submitted by the user for one question slot."""
    question_id: int = Field(..., description="ID of the question being answered")
    answer_id: Optional[int] = Field(None, description="ID of the answer chosen by the user (null = skipped)")


class VerifyTestRequest(BaseModel):
    """Request body for verifying a completed test."""
    test_id: int = Field(..., description="ID of the test to verify", ge=1)
    answers: List[SubmittedAnswer] = Field(..., description="One entry per question in the test")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "test_id": 1,
                "answers": [
                    {"question_id": 42, "answer_id": 7},
                    {"question_id": 43, "answer_id": None}
                ]
            }
        }
    )


class AnswerResult(BaseModel):
    """Per-question verification result."""
    position: int
    question_id: int
    submitted_answer_id: Optional[int]
    correct_answer_id: Optional[int]
    is_correct: bool


class VerifyTestResponse(BaseModel):
    """Response returned after verifying a test."""
    test_id: int
    total_questions: int
    correct_answers: int
    skipped: int
    score_percentage: float = Field(..., description="Percentage of correctly answered questions (0-100)")
    results: List[AnswerResult]
