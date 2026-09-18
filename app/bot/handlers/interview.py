from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.evaluator import evaluate_answer
from app.ai.gemini import GeminiClientError, get_gemini_client
from app.ai.prompts import INTERVIEW_ASSESSMENT_SYSTEM_PROMPT
from app.ai.schemas import InterviewAssessment
from app.bot.keyboards.main import interview_keyboard, main_menu_keyboard
from app.config import get_settings
from app.database.database import get_session
from app.database.models import Question, QuestionAttempt, SessionMode
from app.database.repositories import (
    create_attempt,
    end_training_session,
    get_or_create_schedule,
    get_or_create_user,
    get_pending_attempt,
    get_question,
    mark_answered,
    save_evaluation,
    start_training_session,
)
from app.training.question_engine import select_question
from app.training.question_rendering import format_question_message
from app.training.spaced_repetition import apply_result

logger = logging.getLogger(__name__)
router = Router(name="interview")


class InterviewStates(StatesGroup):
    active = State()


async def _ask_next_interview_question(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    settings = get_settings()
    async with get_session() as session:
        user = await get_or_create_user(session, message.chat.id, None, settings.default_interval_minutes)
        question = await select_question(session, user)
        if question is None:
            await message.answer("Ran out of questions to ask. Ending the interview.")
            await _end_interview(message, state)
            return
        attempt = await create_attempt(session, user, question, session_id=data["session_id"])
    await message.answer(format_question_message(question, attempt.id), reply_markup=interview_keyboard(), parse_mode="Markdown")


@router.message(Command("interview"))
async def cmd_interview(message: Message, state: FSMContext) -> None:
    settings = get_settings()
    async with get_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, settings.default_interval_minutes)
        ts = await start_training_session(session, user, SessionMode.INTERVIEW.value)
    await state.set_state(InterviewStates.active)
    await state.update_data(session_id=ts.id, question_count=0)
    await message.answer(
        "🎤 Mock interview started. I'll ask one question at a time — answer as you would live. "
        "Tap *End Interview* when you're done.",
        parse_mode="Markdown",
    )
    await _ask_next_interview_question(message, state)


@router.message(StateFilter(InterviewStates.active), F.text & ~F.text.startswith("/"))
async def handle_interview_answer(message: Message, state: FSMContext) -> None:
    settings = get_settings()
    async with get_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, settings.default_interval_minutes)
        attempt = await get_pending_attempt(session, user.id)
        if attempt is None:
            await message.answer("No open interview question right now.")
            return
        question = await get_question(session, attempt.question_id)
        await mark_answered(session, attempt, message.text)

        client = get_gemini_client()
        result = await evaluate_answer(client, question, message.text)
        await save_evaluation(session, attempt, result.model_dump())

        schedule = await get_or_create_schedule(session, user, question.concept, user.interval_minutes)
        mistake = result.incorrect_claims[0] if result.incorrect_claims else None
        apply_result(schedule, result.correctness, mistake)
        await session.commit()

    # Real-interviewer style: brief acknowledgment only, no full feedback yet.
    await message.answer("Got it. Next question…")

    data = await state.get_data()
    await state.update_data(question_count=data.get("question_count", 0) + 1)
    await _ask_next_interview_question(message, state)


@router.callback_query(F.data == "end_interview", StateFilter(InterviewStates.active))
async def cb_end_interview(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _end_interview(callback.message, state)


@router.message(Command("end_interview"), StateFilter(InterviewStates.active))
async def cmd_end_interview(message: Message, state: FSMContext) -> None:
    await _end_interview(message, state)


async def _end_interview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    session_id = data.get("session_id")
    await state.clear()

    if session_id is None:
        await message.answer("No active interview to end.")
        return

    async with get_session() as session:
        result = await session.execute(
            select(QuestionAttempt)
            .where(QuestionAttempt.session_id == session_id)
            .options(
                selectinload(QuestionAttempt.question).selectinload(Question.concept),
                selectinload(QuestionAttempt.evaluation),
            )
        )
        attempts = list(result.scalars().all())

        evaluated = [a for a in attempts if a.evaluation is not None]
        if not evaluated:
            await message.answer("Interview ended — no questions were answered, so there's nothing to assess.")
            return

        avg_score = round(sum(a.evaluation.score for a in evaluated) / len(evaluated), 1)
        correct_count = sum(1 for a in evaluated if a.evaluation.correctness in ("correct", "mostly_correct"))

        transcript_lines = []
        for a in evaluated:
            transcript_lines.append(
                f"Q ({a.question.concept.name}): {a.question.body}\n"
                f"A: {a.answer_text}\n"
                f"Score: {a.evaluation.score}/10, correctness: {a.evaluation.correctness}, "
                f"missing: {a.evaluation.missing_concepts}"
            )
        transcript = "\n\n".join(transcript_lines)

        user_prompt = (
            f"Session had {len(evaluated)} answered questions. Average score: {avg_score}/10. "
            f"{correct_count}/{len(evaluated)} were correct or mostly correct.\n\n"
            f"Transcript:\n{transcript}"
        )

        client = get_gemini_client()
        try:
            assessment = await client.generate_structured(
                system_prompt=INTERVIEW_ASSESSMENT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=InterviewAssessment,
            )
        except GeminiClientError:
            assessment = None

        summary = {
            "questions": len(evaluated),
            "average_score": avg_score,
            "correct_or_mostly_correct": correct_count,
        }
        if assessment is not None:
            summary["assessment"] = assessment.model_dump()

        from app.database.models import TrainingSession

        ts = await session.get(TrainingSession, session_id)
        if ts is not None:
            await end_training_session(session, ts, summary)

    lines = [
        "*Interview complete*",
        "",
        f"Questions answered: {len(evaluated)}",
        f"Average score: {avg_score}/10",
        f"Correct / mostly correct: {correct_count}/{len(evaluated)}",
    ]
    if assessment is not None:
        lines += ["", "*Strengths:*"] + [f"• {s}" for s in assessment.technical_strengths]
        lines += ["", "*Weak areas:*"] + [f"• {s}" for s in assessment.weak_areas]
        if assessment.repeatedly_missed_concepts:
            lines += ["", "*Repeatedly missed:*"] + [f"• {c}" for c in assessment.repeatedly_missed_concepts]
        lines += ["", f"Communication clarity: {assessment.communication_clarity}"]
        lines += [f"Code reasoning: {assessment.code_reasoning_ability}"]
        lines += ["", assessment.observations]
    else:
        lines += ["", "(AI assessment unavailable right now — raw stats above are still accurate.)"]

    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard(), parse_mode="Markdown")
