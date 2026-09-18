from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database.database import get_session
from app.database.models import Question, QuestionAttempt
from app.database.repositories import (
    get_or_create_schedule,
    get_or_create_user,
    get_user_stats,
    list_schedules_for_user,
)
from app.training.progress import format_stats_message, format_topics_message, format_weak_message

router = Router(name="stats")


@router.message(Command("stats", "progress"))
async def cmd_stats(message: Message) -> None:
    async with get_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, get_settings().default_interval_minutes)
        stats = await get_user_stats(session, user)
    await message.answer(format_stats_message(stats), parse_mode="Markdown")


@router.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery) -> None:
    await callback.answer()
    async with get_session() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username, get_settings().default_interval_minutes)
        stats = await get_user_stats(session, user)
    await callback.message.answer(format_stats_message(stats), parse_mode="Markdown")


@router.message(Command("topics"))
async def cmd_topics(message: Message) -> None:
    async with get_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, get_settings().default_interval_minutes)
        schedules = await list_schedules_for_user(session, user)
    await message.answer(format_topics_message(schedules), parse_mode="Markdown")


@router.message(Command("weak"))
async def cmd_weak(message: Message) -> None:
    async with get_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, get_settings().default_interval_minutes)
        schedules = await list_schedules_for_user(session, user)
    await message.answer(format_weak_message(schedules), parse_mode="Markdown")


@router.callback_query(F.data == "weak")
async def cb_weak(callback: CallbackQuery) -> None:
    await callback.answer()
    async with get_session() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username, get_settings().default_interval_minutes)
        schedules = await list_schedules_for_user(session, user)
    await callback.message.answer(format_weak_message(schedules), parse_mode="Markdown")


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    async with get_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, get_settings().default_interval_minutes)
        result = await session.execute(
            select(QuestionAttempt)
            .where(QuestionAttempt.user_id == user.id)
            .options(selectinload(QuestionAttempt.question).selectinload(Question.concept), selectinload(QuestionAttempt.evaluation))
            .order_by(QuestionAttempt.asked_at.desc())
            .limit(10)
        )
        attempts = list(result.scalars().all())

    if not attempts:
        await message.answer("No attempts yet.")
        return

    lines = ["*Last 10 attempts*", ""]
    for a in attempts:
        concept = a.question.concept.name if a.question and a.question.concept else "?"
        score = f"{a.evaluation.score}/10" if a.evaluation else "-"
        lines.append(f"• [{a.status}] {concept} — {score}")
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("review"))
async def cmd_review(message: Message) -> None:
    """Force-review the single weakest concept right now, ignoring its schedule timer."""
    async with get_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, get_settings().default_interval_minutes)
        schedules = await list_schedules_for_user(session, user)
        attempted = [s for s in schedules if s.attempts > 0]
        if not attempted:
            await message.answer("Not enough history yet to pick a weak concept — try /question first.")
            return
        weakest = min(attempted, key=lambda s: s.mastery)

        from app.database.repositories import list_questions_for_concept, create_attempt
        import random

        questions = await list_questions_for_concept(session, weakest.concept_id)
        if not questions:
            await message.answer("No questions stored for your weakest concept yet.")
            return
        question = random.choice(questions)
        attempt = await create_attempt(session, user, question)

    from app.training.question_rendering import format_question_message
    from app.bot.keyboards.main import main_menu_keyboard

    await message.answer(
        f"Reviewing your weakest concept: *{weakest.concept.name}*\n\n" + format_question_message(question, attempt.id),
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )
