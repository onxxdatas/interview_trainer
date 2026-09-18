"""Adaptive question selection.

Priority-scores concepts due for review, then picks a question of
appropriate difficulty for the user's current mastery of that concept,
avoiding recently-asked questions where possible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Concept, Question, ReviewSchedule, User, utcnow
from app.database.repositories import (
    get_or_create_schedule,
    list_concepts,
    list_questions_for_concept,
    list_schedules_for_user,
    recent_question_ids_for_user,
)


@dataclass
class Candidate:
    concept: Concept
    schedule: ReviewSchedule
    score: float


def _difficulty_band(mastery: float) -> tuple[int, int]:
    """Return an inclusive (min, max) difficulty range appropriate for mastery."""
    if mastery < 0.25:
        return (1, 2)
    if mastery < 0.5:
        return (1, 3)
    if mastery < 0.75:
        return (2, 4)
    return (3, 5)


async def _score_candidates(session: AsyncSession, user: User) -> list[Candidate]:
    concepts = await list_concepts(session)
    now = utcnow()
    candidates: list[Candidate] = []

    for concept in concepts:
        schedule = await get_or_create_schedule(session, user, concept, user.interval_minutes)
        overdue_minutes = max(0.0, (now - schedule.next_review_at).total_seconds() / 60.0)
        is_due = schedule.next_review_at <= now
        never_asked = schedule.attempts == 0

        weakness_score = (1.0 - schedule.mastery) * 0.5
        overdue_score = min(overdue_minutes / 120.0, 1.0) * 0.3  # normalize over 2h
        novelty_score = 0.2 if never_asked else 0.0

        total = weakness_score + overdue_score + novelty_score
        if not is_due and not never_asked:
            # Not due yet: heavily deprioritize, but don't fully exclude so the
            # queue never goes completely empty.
            total *= 0.05

        candidates.append(Candidate(concept=concept, schedule=schedule, score=total))

    return candidates


async def select_question(session: AsyncSession, user: User, exclude_recent: bool = True) -> Question | None:
    """Pick the next best question for this user."""
    candidates = await _score_candidates(session, user)
    if not candidates:
        return None

    candidates.sort(key=lambda c: c.score, reverse=True)
    recent_ids = await recent_question_ids_for_user(session, user.id) if exclude_recent else set()

    # Try top candidates in order; for each, look for a question in the
    # right difficulty band that hasn't been asked recently.
    for candidate in candidates[:8]:
        questions = await list_questions_for_concept(session, candidate.concept.id)
        if not questions:
            continue
        lo, hi = _difficulty_band(candidate.schedule.mastery)
        in_band = [q for q in questions if lo <= q.difficulty <= hi]
        pool = in_band or questions

        fresh = [q for q in pool if q.id not in recent_ids]
        chosen_pool = fresh or pool
        return random.choice(chosen_pool)

    # Fallback: any active question at all.
    for candidate in candidates:
        questions = await list_questions_for_concept(session, candidate.concept.id)
        if questions:
            return random.choice(questions)
    return None
