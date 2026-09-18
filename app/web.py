"""A tiny HTTP server whose only job is to give free-tier hosts (like
Render's free Web Service plan) something to bind a port to and ping.

The actual bot runs on Telegram long polling, which needs no HTTP endpoint
at all — this exists purely so the process satisfies "must listen on
$PORT and answer requests" requirements of free web-service hosting.
"""

from __future__ import annotations

import logging

from aiohttp import web

logger = logging.getLogger(__name__)


async def _health(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_health_server(port: int) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info("Health-check server listening on 0.0.0.0:%s", port)
    return runner
