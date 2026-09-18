from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    AttemptStatus,
    Concept,
    Evaluation,
    Question,
    QuestionAttempt,
    ReviewSchedule,
    Topic,
    TrainingSession,
    User,
    utcnow,
)


# ---------------------------------------------------------------- Users ----

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None, default_interval: int) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        if username and user.username != username:
            user.username = username
            await session.commit()
        return user
    user = User(telegram_id=telegram_id, username=username, interval_minutes=default_interval)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def set_paused(session: AsyncSession, user: User, paused: bool) -> None:
    user.is_paused = paused
    await session.commit()


async def set_interval(session: AsyncSession, user: User, minutes: int) -> None:
    user.interval_minutes = minutes
    await session.commit()


async def list_active_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.is_paused == False))  # noqa: E712
    return list(result.scalars().all())


# ------------------------------------------------------- Topics/Concepts ----

async def get_or_create_topic(session: AsyncSession, name: str, slug: str) -> Topic:
    result = await session.execute(select(Topic).where(Topic.slug == slug))
    topic = result.scalar_one_or_none()
    if topic:
        return topic
    topic = Topic(name=name, slug=slug)
    session.add(topic)
    await session.flush()
    return topic


async def get_or_create_concept(session: AsyncSession, topic: Topic, name: str, slug: str) -> Concept:
    result = await session.execute(select(Concept).where(Concept.slug == slug))
    concept = result.scalar_one_or_none()
    if concept:
        return concept
    concept = Concept(topic_id=topic.id, name=name, slug=slug)
    session.add(concept)
    await session.flush()
    return concept


async def list_concepts(session: AsyncSession) -> list[Concept]:
    result = await session.execute(select(Concept).options(selectinload(Concept.topic)))
    return list(result.scalars().all())


# --------------------------------------------------------------- Schedules --

async def get_or_create_schedule(session: AsyncSession, user: User, concept: Concept, default_interval: int) -> ReviewSchedule:
    result = await session.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.user_id == user.id, ReviewSchedule.concept_id == concept.id
        )
    )
    schedule = result.scalar_one_or_none()
    if schedule:
        return schedule
    schedule = ReviewSchedule(
        user_id=user.id,
        concept_id=concept.id,
        mastery=0.0,
        interval_minutes=default_interval,
        next_review_at=utcnow(),
    )
    schedule.concept = concept  # avoid a surprise lazy-load in async context
    session.add(schedule)
    await session.flush()
    return schedule


async def list_schedules_for_user(session: AsyncSession, user: User) -> list[ReviewSchedule]:
    result = await session.execute(
        select(ReviewSchedule)
        .where(ReviewSchedule.user_id == user.id)
        .options(selectinload(ReviewSchedule.concept).selectinload(Concept.topic))
    )
    return list(result.scalars().all())


# --------------------------------------------------------------- Questions --

async def list_questions_for_concept(session: AsyncSession, concept_id: int) -> list[Question]:
    result = await session.execute(
        select(Question)
        .where(Question.concept_id == concept_id, Question.is_active == True)  # noqa: E712
        .options(selectinload(Question.concept).selectinload(Concept.topic))
    )
    return list(result.scalars().all())


async def get_question(session: AsyncSession, question_id: int) -> Question | None:
    stmt = (
        select(Question)
        .options(selectinload(Question.concept).selectinload(Concept.topic))
        .where(Question.id == question_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def recent_question_ids_for_user(session: AsyncSession, user_id: int, limit: int = 15) -> set[int]:
    result = await session.execute(
        select(QuestionAttempt.question_id)
        .where(QuestionAttempt.user_id == user_id)
        .order_by(QuestionAttempt.asked_at.desc())
        .limit(limit)
    )
    return set(result.scalars().all())


async def add_question(session: AsyncSession, **kwargs) -> Question:
    q = Question(**kwargs)
    session.add(q)
    await session.flush()
    return q


# ----------------------------------------------------------------- Attempts --

async def create_attempt(
    session: AsyncSession, user: User, question: Question, is_follow_up: bool = False, session_id: int | None = None
) -> QuestionAttempt:
    attempt = QuestionAttempt(
        user_id=user.id,
        question_id=question.id,
        status=AttemptStatus.PENDING.value,
        is_follow_up=is_follow_up,
        session_id=session_id,
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return attempt


async def get_pending_attempt(session: AsyncSession, user_id: int) -> QuestionAttempt | None:
    result = await session.execute(
        select(QuestionAttempt)
        .where(QuestionAttempt.user_id == user_id, QuestionAttempt.status == AttemptStatus.PENDING.value)
        .options(selectinload(QuestionAttempt.question).selectinload(Question.concept))
        .order_by(QuestionAttempt.asked_at.desc())
    )
    return result.scalars().first()


async def mark_answered(session: AsyncSession, attempt: QuestionAttempt, answer_text: str) -> None:
    attempt.answer_text = answer_text
    attempt.answered_at = utcnow()
    attempt.status = AttemptStatus.ANSWERED.value
    await session.commit()


async def mark_overdue_attempts(session: AsyncSession, older_than_minutes: int = 30) -> list[QuestionAttempt]:
    cutoff = utcnow() - timedelta(minutes=older_than_minutes)
    result = await session.execute(
        select(QuestionAttempt).where(
            QuestionAttempt.status == AttemptStatus.PENDING.value,
            QuestionAttempt.asked_at < cutoff,
        )
    )
    overdue = list(result.scalars().all())
    for attempt in overdue:
        attempt.status = AttemptStatus.OVERDUE.value
    if overdue:
        await session.commit()
    return overdue


async def save_evaluation(session: AsyncSession, attempt: QuestionAttempt, data: dict) -> Evaluation:
    evaluation = Evaluation(
        attempt_id=attempt.id,
        correctness=data["correctness"],
        score=data["score"],
        strengths=data.get("strengths", []),
        missing_concepts=data.get("missing_concepts", []),
        incorrect_claims=data.get("incorrect_claims", []),
        feedback=data["feedback"],
        follow_up_question=data.get("follow_up_question"),
        concepts_to_review=data.get("concepts_to_review", []),
        raw_response=data,
    )
    session.add(evaluation)
    await session.commit()
    await session.refresh(evaluation)
    return evaluation


# ------------------------------------------------------------------- Stats --

async def get_user_stats(session: AsyncSession, user: User) -> dict:
    result = await session.execute(
        select(QuestionAttempt).where(QuestionAttempt.user_id == user.id)
    )
    attempts = list(result.scalars().all())
    total = len(attempts)
    answered = [a for a in attempts if a.status == AttemptStatus.ANSWERED.value]
    overdue = [a for a in attempts if a.status == AttemptStatus.OVERDUE.value]

    eval_result = await session.execute(
        select(Evaluation)
        .join(QuestionAttempt, Evaluation.attempt_id == QuestionAttempt.id)
        .where(QuestionAttempt.user_id == user.id)
    )
    evaluations = list(eval_result.scalars().all())
    avg_score = round(sum(e.score for e in evaluations) / len(evaluations), 1) if evaluations else None

    if answered:
        first = min(a.asked_at for a in attempts)
        span = utcnow() - first
        training_hours = round(span.total_seconds() / 3600, 1)
    else:
        training_hours = 0.0

    schedules = await list_schedules_for_user(session, user)
    schedules_sorted = sorted(schedules, key=lambda s: s.mastery)
    weak = [s for s in schedules_sorted if s.attempts > 0][:3]
    strong = [s for s in reversed(schedules_sorted) if s.attempts > 0][:3]

    recent_mistakes: list[str] = []
    for s in schedules:
        recent_mistakes.extend(s.common_mistakes[-2:])

    return {
        "training_hours": training_hours,
        "questions": total,
        "answered": len(answered),
        "overdue": len(overdue),
        "average_score": avg_score,
        "weak": weak,
        "strong": strong,
        "recent_mistakes": recent_mistakes[-5:],
    }


# --------------------------------------------------------------- Sessions --

async def start_training_session(session: AsyncSession, user: User, mode: str) -> TrainingSession:
    ts = TrainingSession(user_id=user.id, mode=mode)
    session.add(ts)
    await session.commit()
    await session.refresh(ts)
    return ts


async def end_training_session(session: AsyncSession, ts: TrainingSession, summary: dict) -> None:
    ts.ended_at = utcnow()
    ts.summary = summary
    await session.commit()
