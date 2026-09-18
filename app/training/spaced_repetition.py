"""Simplified, interview-tuned spaced repetition.

Not a copy of SM-2 — optimized for short-term interview retention rather
than long-term academic memorization, per the spec.
"""

from __future__ import annotations

from datetime import timedelta

from app.database.models import Correctness, ReviewSchedule, utcnow

MIN_INTERVAL_MINUTES = 15
MAX_INTERVAL_MINUTES = 60 * 24 * 30  # 30 days

_MASTERY_DELTA = {
    Correctness.CORRECT.value: 0.18,
    Correctness.MOSTLY_CORRECT.value: 0.12,
    Correctness.PARTIALLY_CORRECT.value: 0.05,
    Correctness.INCORRECT.value: -0.15,
    Correctness.NO_ANSWER.value: -0.10,
}

_INTERVAL_MULTIPLIER = {
    Correctness.CORRECT.value: 2.5,
    Correctness.MOSTLY_CORRECT.value: 2.0,
    Correctness.PARTIALLY_CORRECT.value: 1.5,
    Correctness.INCORRECT.value: None,  # reset
    Correctness.NO_ANSWER.value: None,  # reset
}


def apply_result(schedule: ReviewSchedule, correctness: str, mistake: str | None = None) -> None:
    """Mutate `schedule` in place based on the latest evaluation result."""
    # ORM `default=` values are only applied on flush/insert, so a freshly
    # constructed-but-not-yet-flushed schedule can still have None here.
    # Coalesce defensively rather than relying on flush timing.
    schedule.attempts = (schedule.attempts or 0) + 1
    schedule.last_asked_at = utcnow()
    schedule.last_result = correctness

    is_negative = correctness in (Correctness.INCORRECT.value, Correctness.NO_ANSWER.value)
    if is_negative:
        schedule.incorrect = (schedule.incorrect or 0) + 1
        schedule.consecutive_incorrect = (schedule.consecutive_incorrect or 0) + 1
        schedule.consecutive_correct = 0
    else:
        schedule.correct = (schedule.correct or 0) + 1
        schedule.consecutive_correct = (schedule.consecutive_correct or 0) + 1
        schedule.consecutive_incorrect = 0

    delta = _MASTERY_DELTA.get(correctness, 0.0)
    schedule.mastery = max(0.0, min(1.0, (schedule.mastery or 0.0) + delta))

    multiplier = _INTERVAL_MULTIPLIER.get(correctness)
    if multiplier is None:
        schedule.interval_minutes = MIN_INTERVAL_MINUTES
    else:
        new_interval = (schedule.interval_minutes or MIN_INTERVAL_MINUTES) * multiplier
        if schedule.consecutive_correct >= 3:
            new_interval *= 1.3
        schedule.interval_minutes = int(max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, new_interval)))

    if schedule.consecutive_incorrect >= 2:
        schedule.interval_minutes = MIN_INTERVAL_MINUTES

    if mistake:
        mistakes = list(schedule.common_mistakes or [])
        mistakes.append(mistake)
        schedule.common_mistakes = mistakes[-10:]

    schedule.next_review_at = utcnow() + timedelta(minutes=schedule.interval_minutes)
