from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.ai.evaluator import evaluate_answer
from app.ai.gemini import get_gemini_client
from app.bot.keyboards.main import main_menu_keyboard
from app.config import get_settings
from app.database.database import get_session
from app.database.repositories import (
    create_attempt,
    get_or_create_schedule,
    get_or_create_user,
    get_pending_attempt,
    get_question,
    mark_answered,
    save_evaluation,
    set_interval,
    set_paused,
)
from app.training.question_engine import select_question
from app.training.question_rendering import format_question_message
from app.training.spaced_repetition import apply_result

logger = logging.getLogger(__name__)
router = Router(name="training")


async def _send_question(message: Message) -> None:
    settings = get_settings()
    async with get_session() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            settings.default_interval_minutes,
        )
        
        # Check if there is already a pending question for this user
        pending = await get_pending_attempt(session, user.id)
        if pending is not None:
            question = await get_question(session, pending.question_id)
            attempt = pending
        else:
            question = await select_question(session, user)
            if question is None:
                await message.answer("No questions available yet — the question bank looks empty.")
                return
            attempt = await create_attempt(session, user, question)

    text = format_question_message(question, attempt.id)
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")


@router.message(Command("question"))
async def cmd_question(message: Message) -> None:
    await _send_question(message)


@router.callback_query(F.data == "next_question")
async def cb_next_question(callback: CallbackQuery) -> None:
    await callback.answer()
    await _send_question(callback.message)


@router.message(Command("answer"))
async def cmd_answer(message: Message) -> None:
    await message.answer("Just reply directly with your answer text to the current question — no special command needed.")


@router.message(Command("pause"))
async def cmd_pause(message: Message, scheduler=None) -> None:
    async with get_session() as session:
        settings = get_settings()
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, settings.default_interval_minutes)
        await set_paused(session, user, True)
    if scheduler is not None:
        scheduler.unschedule_user(user.telegram_id)
    await message.answer("Paused. Scheduled questions won't be sent until you /resume.")


@router.callback_query(F.data == "pause")
async def cb_pause(callback: CallbackQuery, scheduler=None) -> None:
    await callback.answer("Paused")
    async with get_session() as session:
        settings = get_settings()
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username, settings.default_interval_minutes)
        await set_paused(session, user, True)
    if scheduler is not None:
        scheduler.unschedule_user(user.telegram_id)
    await callback.message.answer("Paused. Scheduled questions won't be sent until you /resume.")


@router.message(Command("resume"))
async def cmd_resume(message: Message, scheduler=None) -> None:
    async with get_session() as session:
        settings = get_settings()
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, settings.default_interval_minutes)
        await set_paused(session, user, False)
    if scheduler is not None:
        scheduler.schedule_user(user.telegram_id, user.interval_minutes)
    await message.answer("Resumed. You'll get questions on your usual interval again.")


@router.callback_query(F.data == "resume")
async def cb_resume(callback: CallbackQuery, scheduler=None) -> None:
    await callback.answer("Resumed")
    async with get_session() as session:
        settings = get_settings()
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username, settings.default_interval_minutes)
        await set_paused(session, user, False)
    if scheduler is not None:
        scheduler.schedule_user(user.telegram_id, user.interval_minutes)
    await callback.message.answer("Resumed. You'll get questions on your usual interval again.")


@router.message(Command("interval"))
async def cmd_interval(message: Message, scheduler=None) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage: /interval <minutes>, e.g. /interval 30")
        return
    minutes = max(5, min(24 * 60, int(parts[1])))
    async with get_session() as session:
        settings = get_settings()
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, settings.default_interval_minutes)
        await set_interval(session, user, minutes)
    if scheduler is not None and not user.is_paused:
        scheduler.schedule_user(user.telegram_id, minutes)
    await message.answer(f"Interval set to {minutes} minutes.")


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    async with get_session() as session:
        settings = get_settings()
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, settings.default_interval_minutes)
    status = "paused" if user.is_paused else "active"
    await message.answer(f"Interval: {user.interval_minutes} min\nStatus: {status}")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_answer(message: Message) -> None:
    """Any plain text message is treated as an answer to the pending question."""
    settings = get_settings()
    async with get_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, settings.default_interval_minutes)
        attempt = await get_pending_attempt(session, user.id)
        if attempt is None:
            await message.answer("No question is currently waiting for an answer. Use /question to get one.")
            return

        question = await get_question(session, attempt.question_id)
        await mark_answered(session, attempt, message.text)

        client = get_gemini_client()
        result = await evaluate_answer(client, question, message.text)
        await save_evaluation(session, attempt, result.model_dump())

        schedule = await get_or_create_schedule(session, user, question.concept, user.interval_minutes)
        mistake = result.incorrect_claims[0] if result.incorrect_claims else (result.missing_concepts[0] if result.missing_concepts else None)
        apply_result(schedule, result.correctness, mistake)
        await session.commit()

        follow_up_attempt = None
        if result.follow_up_question:
            follow_up_attempt = await create_attempt(session, user, question, is_follow_up=True)

    reply_lines = [f"*Score: {result.score}/10* ({result.correctness.replace('_', ' ')})", "", result.feedback]
    if result.missing_concepts:
        reply_lines += ["", "Missing:"] + [f"• {m}" for m in result.missing_concepts]
    if result.incorrect_claims:
        reply_lines += ["", "Incorrect:"] + [f"• {c}" for c in result.incorrect_claims]
    await message.answer("\n".join(reply_lines), parse_mode="Markdown")

    if result.follow_up_question:
        await message.answer(f"*Follow-up:*\n{result.follow_up_question}", parse_mode="Markdown")
