from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

class AnswerBase(BaseModel):
    """Base model for Answer with common fields."""
    path_to_answer: str = Field(..., description="Path to the answer file", min_length=1)
    question_number: Optional[int] = Field(None, description="Question number in sequence", ge=1)    

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "path_to_answer": "/answers/math/a1.png",
                "question_number": 1
            }
        }
    )

class Answer(AnswerBase):
    """Complete Answer model including ID."""
    id: int = Field(..., description="Unique identifier for the answer", ge=1)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "path_to_answer": "/answers/math/a1.png",
                "question_number": 1
            }
        }
    )
    
class AnswerCreate(AnswerBase):
    """Model for creating a new Answer (without ID)."""
    pass

class AnswerUpdate(BaseModel):
    """Model for updating an existing Answer (all fields optional)."""
    path_to_answer: Optional[str] = Field(None, description="Path to the answer file", min_length=1)
    question_number: Optional[int] = Field(None, description="Question number in sequence", ge=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "path_to_answer": "/answers/math/a2.png",
                "question_number": 2
            }
        }
    )

