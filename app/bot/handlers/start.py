from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import get_settings
from app.database.database import get_session
from app.database.repositories import get_or_create_user
from app.bot.keyboards.main import main_menu_keyboard

router = Router(name="start")

HELP_TEXT = """\
*Python/Backend Interview Trainer*

I send you interview questions on a schedule, evaluate your answers with AI, \
and adapt future questions to your weak spots using spaced repetition.

*Commands*
/question — get a question right now
/answer — reminder of how to answer (just reply to the question message)
/stats — your overall progress
/topics — mastery per topic/concept
/progress — alias for /stats
/weak — your weakest concepts right now
/history — your recent attempts
/review — force-review your weakest concept now
/interview — start a mock interview session
/interval <minutes> — change how often you get questions (e.g. /interval 30)
/pause — pause scheduled questions
/resume — resume scheduled questions
/settings — show current settings
"""


@router.message(CommandStart())
async def cmd_start(message: Message, scheduler=None) -> None:
    settings = get_settings()
    async with get_session() as session:
        user = await get_or_create_user(
            session, message.from_user.id, message.from_user.username, settings.default_interval_minutes
        )
    if scheduler is not None and not user.is_paused:
        scheduler.schedule_user(user.telegram_id, user.interval_minutes)
    await message.answer(
        f"Welcome. You'll get a new question every *{user.interval_minutes} minutes*.\n\n"
        "Use the buttons below or /help to see all commands.",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="Markdown")
