from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.ai.evaluator import evaluate_answer
from app.ai.gemini import GeminiClientError
from app.ai.schemas import EvaluationResult
from app.database.models import Concept, Question, Topic


def _fake_question() -> Question:
    topic = Topic(id=1, name="Python Fundamentals", slug="python-fundamentals")
    concept = Concept(id=1, topic_id=1, name="Mutability", slug="mutability")
    concept.topic = topic
    q = Question(
        id=1,
        concept_id=1,
        difficulty=1,
        qtype="conceptual",
        body="What is the difference between is and ==?",
        expected_points=["is checks identity", "== checks equality"],
    )
    q.concept = concept
    return q


@pytest.mark.asyncio
async def test_evaluate_answer_success():
    client = AsyncMock()
    client.generate_structured.return_value = EvaluationResult(
        correctness="correct",
        score=9,
        strengths=["clear explanation"],
        missing_concepts=[],
        incorrect_claims=[],
        feedback="Great answer.",
        follow_up_question=None,
        concepts_to_review=[],
    )
    result = await evaluate_answer(client, _fake_question(), "is checks identity, == checks value")
    assert result.correctness == "correct"
    assert result.score == 9


@pytest.mark.asyncio
async def test_evaluate_answer_falls_back_on_gemini_error():
    client = AsyncMock()
    client.generate_structured.side_effect = GeminiClientError("boom")
    result = await evaluate_answer(client, _fake_question(), "some answer")
    assert result.correctness == "partially_correct"
    assert result.score == 5
    assert "couldn't reach the evaluator" in result.feedback


@pytest.mark.asyncio
async def test_evaluate_answer_falls_back_with_no_answer_text():
    client = AsyncMock()
    client.generate_structured.side_effect = GeminiClientError("boom")
    result = await evaluate_answer(client, _fake_question(), "")
    assert result.correctness == "no_answer"
    assert result.score == 0
