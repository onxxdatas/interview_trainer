from __future__ import annotations

import logging

from app.ai.gemini import GeminiClient, GeminiClientError
from app.ai.prompts import EVALUATION_SYSTEM_PROMPT, build_evaluation_user_prompt
from app.ai.schemas import EvaluationResult
from app.database.models import Correctness, Question

logger = logging.getLogger(__name__)

_FALLBACK_FEEDBACK = (
    "I couldn't reach the evaluator right now, so this answer wasn't scored. "
    "It has been recorded — try /review shortly, or reply again in a bit."
)


async def evaluate_answer(client: GeminiClient, question: Question, answer_text: str) -> EvaluationResult:
    prompt = build_evaluation_user_prompt(
        topic=question.concept.topic.name if question.concept.topic else "",
        concept=question.concept.name,
        difficulty=question.difficulty,
        qtype=question.qtype,
        question_body=question.body,
        code_snippet=question.code_snippet,
        answer_text=answer_text,
        expected_points=question.expected_points or [],
    )
    try:
        result = await client.generate_structured(
            system_prompt=EVALUATION_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=EvaluationResult,
        )
        assert isinstance(result, EvaluationResult)
        return result
    except GeminiClientError as exc:
        logger.error("Evaluation failed, using safe fallback: %s", exc)
        # Never crash the training loop because Gemini is down — record a
        # neutral, clearly-labeled fallback instead of losing the attempt.
        return EvaluationResult(
            correctness=Correctness.NO_ANSWER.value if not answer_text.strip() else Correctness.PARTIALLY_CORRECT.value,
            score=0 if not answer_text.strip() else 5,
            strengths=[],
            missing_concepts=[],
            incorrect_claims=[],
            feedback=_FALLBACK_FEEDBACK,
            follow_up_question=None,
            concepts_to_review=[],
        )
