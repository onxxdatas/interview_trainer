from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.bot.keyboards.main import main_menu_keyboard
from app.database.database import get_session
from app.database.models import AttemptStatus
from app.database.repositories import (
    create_attempt,
    get_pending_attempt,
    list_active_users,
)
from app.training.question_engine import select_question
from app.training.question_rendering import format_question_message

logger = logging.getLogger(__name__)

_JOB_PREFIX = "question_job_"


def _job_id(telegram_id: int) -> str:
    return f"{_JOB_PREFIX}{telegram_id}"

from datetime import datetime, timezone, timedelta

async def send_next_question(bot: Bot, telegram_id: int) -> None:
    """Send (or re-send) the next question to a user. Also resolves any
    still-pending question from the previous tick into OVERDUE if its deadline
    has passed so the training loop never gets stuck on one unanswered question."""
    async with get_session() as session:
        from app.database.repositories import get_user_by_telegram_id

        user = await get_user_by_telegram_id(session, telegram_id)
        if user is None or user.is_paused:
            return

        pending = await get_pending_attempt(session, user.id)
        if pending is not None:
            # Check if pending attempt has passed its deadline
            deadline = pending.asked_at + timedelta(minutes=user.interval_minutes)
            now = datetime.now(timezone.utc)
            
            # If naive, make timezone-aware for comparison
            if pending.asked_at.tzinfo is None:
                now = datetime.utcnow()

            if now >= deadline:
                pending.status = AttemptStatus.OVERDUE.value
                await session.commit()
                try:
                    await bot.send_message(telegram_id, "⏱ Question overdue. Moving to the next question.")
                except Exception:
                    logger.exception("Failed to notify user %s about overdue question", telegram_id)
            else:
                # Still within interval/fresh; do not overwrite or replace yet
                return

        question = await select_question(session, user)
        if question is None:
            logger.warning("No question available for user %s", telegram_id)
            return

        attempt = await create_attempt(session, user, question)

    text = format_question_message(question, attempt_number=attempt.id)
    try:
        await bot.send_message(telegram_id, text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    except Exception:
        logger.exception("Failed to send question to user %s", telegram_id)


class TrainingScheduler:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        self.scheduler.start()

    async def load_jobs_from_db(self) -> None:
        """Rebuild all per-user interval jobs on startup. Deterministic job
        ids mean re-running this never creates duplicate jobs."""
        async with get_session() as session:
            users = await list_active_users(session)
        for user in users:
            self.schedule_user(user.telegram_id, user.interval_minutes)

    def schedule_user(self, telegram_id: int, interval_minutes: int) -> None:
        job_id = _job_id(telegram_id)
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)
        self.scheduler.add_job(
            send_next_question,
            trigger=IntervalTrigger(minutes=interval_minutes),
            args=[self.bot, telegram_id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=300,
        )

    def unschedule_user(self, telegram_id: int) -> None:
        job_id = _job_id(telegram_id)
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
