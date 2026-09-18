from __future__ import annotations

from datetime import timedelta

import pytest

from app.database.models import AttemptStatus, Question, QuestionAttempt, User, utcnow
from app.database.repositories import (
    create_attempt,
    get_pending_attempt,
    mark_answered,
    mark_overdue_attempts,
)
from app.training.seed import seed_question_bank
from app.training.question_engine import select_question


@pytest.mark.asyncio
async def test_overdue_marking(session):
    await seed_question_bank(session)
    user = User(telegram_id=10, interval_minutes=15)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    question = await select_question(session, user)
    attempt = await create_attempt(session, user, question)

    # Simulate the attempt being old.
    attempt.asked_at = utcnow() - timedelta(minutes=60)
    await session.commit()

    overdue = await mark_overdue_attempts(session, older_than_minutes=30)
    assert len(overdue) == 1
    assert overdue[0].status == AttemptStatus.OVERDUE.value


@pytest.mark.asyncio
async def test_pending_attempt_found_and_answered(session):
    await seed_question_bank(session)
    user = User(telegram_id=11, interval_minutes=15)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    question = await select_question(session, user)
    attempt = await create_attempt(session, user, question)

    pending = await get_pending_attempt(session, user.id)
    assert pending is not None
    assert pending.id == attempt.id

    await mark_answered(session, attempt, "my answer")
    pending_after = await get_pending_attempt(session, user.id)
    assert pending_after is None
