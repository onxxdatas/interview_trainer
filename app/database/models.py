from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    # Naive UTC on purpose: SQLite (this project's default DB) silently
    # drops tzinfo on round-trip, which breaks aware/naive comparisons.
    # Keeping every stored timestamp naive-but-UTC avoids that mismatch and
    # still compares correctly if/when the app moves to Postgres later.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class AttemptStatus(str, enum.Enum):
    PENDING = "pending"
    ANSWERED = "answered"
    OVERDUE = "overdue"


class QuestionType(str, enum.Enum):
    CONCEPTUAL = "conceptual"
    CODE_PREDICTION = "code_prediction"
    DEBUGGING = "debugging"
    OUTPUT_PREDICTION = "output_prediction"
    IMPLEMENTATION = "implementation"
    BIG_O = "big_o"
    ARCHITECTURE = "architecture"
    CPYTHON = "cpython"
    FOLLOW_UP = "follow_up"


class QuestionSource(str, enum.Enum):
    CURATED = "curated"
    AI_GENERATED = "ai_generated"


class Correctness(str, enum.Enum):
    CORRECT = "correct"
    MOSTLY_CORRECT = "mostly_correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"
    NO_ANSWER = "no_answer"


class SessionMode(str, enum.Enum):
    NORMAL = "normal"
    INTERVIEW = "interview"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    attempts: Mapped[list["QuestionAttempt"]] = relationship(back_populates="user")
    schedules: Mapped[list["ReviewSchedule"]] = relationship(back_populates="user")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)

    concepts: Mapped[list["Concept"]] = relationship(back_populates="topic")


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(160), unique=True)

    topic: Mapped["Topic"] = relationship(back_populates="concepts")
    questions: Mapped[list["Question"]] = relationship(back_populates="concept")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"))
    difficulty: Mapped[int] = mapped_column(Integer)  # 1..5
    qtype: Mapped[str] = mapped_column(String(30))
    body: Mapped[str] = mapped_column(Text)
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_points: Mapped[list] = mapped_column(JSON, default=list)
    hints: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default=QuestionSource.CURATED.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    concept: Mapped["Concept"] = relationship(back_populates="questions")
    attempts: Mapped[list["QuestionAttempt"]] = relationship(back_populates="question")


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=AttemptStatus.PENDING.value)
    is_follow_up: Mapped[bool] = mapped_column(Boolean, default=False)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("training_sessions.id"), nullable=True)

    user: Mapped["User"] = relationship(back_populates="attempts")
    question: Mapped["Question"] = relationship(back_populates="attempts")
    evaluation: Mapped["Evaluation | None"] = relationship(back_populates="attempt", uselist=False)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("question_attempts.id"), unique=True)
    correctness: Mapped[str] = mapped_column(String(30))
    score: Mapped[int] = mapped_column(Integer)  # 0..10
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    missing_concepts: Mapped[list] = mapped_column(JSON, default=list)
    incorrect_claims: Mapped[list] = mapped_column(JSON, default=list)
    feedback: Mapped[str] = mapped_column(Text)
    follow_up_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    concepts_to_review: Mapped[list] = mapped_column(JSON, default=list)
    raw_response: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    attempt: Mapped["QuestionAttempt"] = relationship(back_populates="evaluation")


class ReviewSchedule(Base):
    """Per-user, per-concept mastery + spaced-repetition state."""

    __tablename__ = "review_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"))

    mastery: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    next_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    incorrect: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_incorrect: Mapped[int] = mapped_column(Integer, default=0)

    last_asked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result: Mapped[str | None] = mapped_column(String(30), nullable=True)
    common_mistakes: Mapped[list] = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship(back_populates="schedules")
    concept: Mapped["Concept"] = relationship()


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(String(20), default=SessionMode.NORMAL.value)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
