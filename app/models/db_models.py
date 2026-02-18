from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SQLEnum, Table
from sqlalchemy.orm import relationship
from app.database import Base
from enum import Enum


# Association table: many-to-many between tests and questions (ordered by position)
test_questions = Table(
    "test_questions",
    Base.metadata,
    Column("test_id", Integer, ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True),
    Column("question_id", Integer, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, nullable=False),  # preserves question ordering in the test
)


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


class AnswerDB(Base):
    """SQLAlchemy model for Answer table."""
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    path_to_answer = Column(String(500), nullable=False)
    question_number = Column(Integer, nullable=True)
    
    # Relationship to questions
    questions = relationship("QuestionDB", back_populates="answer")


class QuestionDB(Base):
    """SQLAlchemy model for Question table."""
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    path_to_question = Column(String(500), nullable=False)
    answer_id = Column(Integer, ForeignKey("answers.id"), nullable=True)  # Nullable since answers uploaded separately
    type = Column(SQLEnum(QuestionType), nullable=False, index=True)
    question_number = Column(Integer, nullable=False, index=True)
    language = Column(String(50), nullable=True)  # Optional field for language of the question
    
    # Relationship to answer
    answer = relationship("AnswerDB", back_populates="questions")


class TestDB(Base):
    """SQLAlchemy model for Test table."""
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type = Column(SQLEnum(QuestionType), nullable=False, index=True)
    language = Column(String(10), nullable=True, index=True)

    # Ordered list of questions via association table
    questions = relationship(
        "QuestionDB",
        secondary=test_questions,
        order_by=test_questions.c.position,
    )
