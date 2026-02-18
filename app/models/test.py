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
