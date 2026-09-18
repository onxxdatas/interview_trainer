from __future__ import annotations

import pytest

from app.database.models import User
from app.training.question_bank import SEED_DATA
from app.training.question_engine import _difficulty_band, select_question
from app.training.seed import seed_question_bank


@pytest.mark.parametrize(
    "mastery,expected",
    [
        (0.0, (1, 2)),
        (0.3, (1, 3)),
        (0.6, (2, 4)),
        (0.9, (3, 5)),
    ],
)
def test_difficulty_band(mastery, expected):
    assert _difficulty_band(mastery) == expected


@pytest.mark.asyncio
async def test_select_question_returns_something_after_seeding(session):
    await seed_question_bank(session)
    user = User(telegram_id=1, interval_minutes=15)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    question = await select_question(session, user)
    assert question is not None
    assert question.concept_id is not None


@pytest.mark.asyncio
async def test_select_question_none_without_questions(session):
    user = User(telegram_id=2, interval_minutes=15)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    question = await select_question(session, user)
    assert question is None


def test_seed_data_covers_expected_topics():
    # Sanity check that the curated bank isn't accidentally emptied.
    assert "python-fundamentals" in SEED_DATA
    assert "dsa" in SEED_DATA
    assert "concurrency" in SEED_DATA
    total_questions = sum(
        len(c["questions"])
        for topic in SEED_DATA.values()
        for c in topic["concepts"].values()
    )
    assert total_questions > 10
