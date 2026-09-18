from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import interview, start, stats, training
from app.bot.middleware.access import AllowedUserMiddleware
from app.config import get_settings
from app.database.database import get_session, init_db
from app.training.scheduler import TrainingScheduler
from app.training.seed import seed_question_bank
from app.web import start_health_server


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Never let secrets leak into logs even if a library logs request bodies.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger("app.main")

    logger.info("Initializing database...")
    await init_db()
    async with get_session() as session:
        await seed_question_bank(session)
    logger.info("Database ready.")

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())

    access_middleware = AllowedUserMiddleware()
    dp.message.middleware(access_middleware)
    dp.callback_query.middleware(access_middleware)

    # Interview router must be included before training's catch-all text
    # handler so answers during an active interview are routed correctly.
    dp.include_router(start.router)
    dp.include_router(interview.router)
    dp.include_router(stats.router)
    dp.include_router(training.router)

    scheduler = TrainingScheduler(bot)
    scheduler.start()
    await scheduler.load_jobs_from_db()
    logger.info("Scheduler started, per-user jobs loaded.")

    dp["scheduler"] = scheduler

    health_runner = None
    if settings.port is not None:
        # Running as a free-tier Web Service: must bind $PORT and answer
        # HTTP or the host will consider the deploy failed / keep killing it.
        health_runner = await start_health_server(settings.port)

    try:
        logger.info("Starting polling...")
        await dp.start_polling(bot)
    finally:
        if health_runner is not None:
            await health_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
