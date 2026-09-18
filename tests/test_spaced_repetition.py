from __future__ import annotations

from app.database.models import Correctness, ReviewSchedule
from app.training.spaced_repetition import MAX_INTERVAL_MINUTES, MIN_INTERVAL_MINUTES, apply_result


def _fresh_schedule(interval: int = 15) -> ReviewSchedule:
    return ReviewSchedule(user_id=1, concept_id=1, mastery=0.5, interval_minutes=interval)


def test_correct_increases_mastery_and_interval():
    s = _fresh_schedule()
    apply_result(s, Correctness.CORRECT.value)
    assert s.mastery > 0.5
    assert s.interval_minutes > 15
    assert s.correct == 1
    assert s.consecutive_correct == 1


def test_incorrect_decreases_mastery_and_resets_interval():
    s = _fresh_schedule(interval=120)
    apply_result(s, Correctness.INCORRECT.value)
    assert s.mastery < 0.5
    assert s.interval_minutes == MIN_INTERVAL_MINUTES
    assert s.incorrect == 1
    assert s.consecutive_incorrect == 1


def test_two_consecutive_incorrect_floors_interval():
    s = _fresh_schedule(interval=500)
    apply_result(s, Correctness.PARTIALLY_CORRECT.value)  # not full reset
    apply_result(s, Correctness.INCORRECT.value)
    apply_result(s, Correctness.INCORRECT.value)
    assert s.interval_minutes == MIN_INTERVAL_MINUTES
    assert s.consecutive_incorrect == 2


def test_mastery_is_clamped_between_zero_and_one():
    s = _fresh_schedule()
    s.mastery = 0.95
    for _ in range(10):
        apply_result(s, Correctness.CORRECT.value)
    assert 0.0 <= s.mastery <= 1.0

    s2 = _fresh_schedule()
    s2.mastery = 0.05
    for _ in range(10):
        apply_result(s2, Correctness.INCORRECT.value)
    assert 0.0 <= s2.mastery <= 1.0


def test_interval_never_exceeds_cap():
    s = _fresh_schedule(interval=MAX_INTERVAL_MINUTES)
    apply_result(s, Correctness.CORRECT.value)
    assert s.interval_minutes <= MAX_INTERVAL_MINUTES


def test_common_mistakes_recorded_and_capped():
    s = _fresh_schedule()
    for i in range(15):
        apply_result(s, Correctness.INCORRECT.value, mistake=f"mistake-{i}")
    assert len(s.common_mistakes) == 10
    assert s.common_mistakes[-1] == "mistake-14"
