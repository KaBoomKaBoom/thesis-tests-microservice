from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class QuestionType(str, Enum):
    """Enumeration of valid question types."""
    MATH = "math"
    ROMANIAN = "romanian"
    HISTORY = "history"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"
    GEOGRAPHY = "geography"
    COMPUTER_SCIENCE = "computer_science"
    ENGINEERING = "engineering"
    OTHER = "other"


class QuestionBase(BaseModel):
    """Base model for Question with common fields."""
    path_to_question: str = Field(..., description="Path to the question file", min_length=1)
    answer_id: int = Field(..., description="ID of the associated answer", ge=1)
    type: QuestionType = Field(..., description="Type/category of the question")
    question_number: int = Field(..., description="Question number in sequence", ge=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "path_to_question": "/questions/math/q1.png",
                "answer_id": 1,
                "type": "math",
                "question_number": 1
            }
        }
    )


class Question(QuestionBase):
    """Complete Question model including ID."""
    id: int = Field(..., description="Unique identifier for the question", ge=1)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "path_to_question": "/questions/math/q1.png",
                "answer_id": 1,
                "type": "math",
                "question_number": 1
            }
        }
    )


class QuestionCreate(QuestionBase):
    """Model for creating a new Question (without ID)."""
    pass


class QuestionUpdate(BaseModel):
    """Model for updating an existing Question (all fields optional)."""
    path_to_question: Optional[str] = Field(None, description="Path to the question file", min_length=1)
    answer_id: Optional[int] = Field(None, description="ID of the associated answer", ge=1)
    type: Optional[QuestionType] = Field(None, description="Type/category of the question")
    question_number: Optional[int] = Field(None, description="Question number in sequence", ge=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "path_to_question": "/questions/math/q2.png",
                "question_number": 2
            }
        }
    )