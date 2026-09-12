"""Minimal HTTP health endpoint for platforms that require an open port.

The bot uses long polling and does not need to listen on any port. Some
PaaS free tiers (e.g. Koyeb "Web Service") only offer HTTP services and
health-check a TCP port; without a listener the instance is marked
unhealthy and restarted. When ``PORT`` is set we serve ``200 OK`` on it
next to the polling loop. Locally (no ``PORT``) nothing is started.

``aiohttp`` is already a dependency of aiogram, so this adds no new
requirement.
"""

from __future__ import annotations

import logging
import os

from aiohttp import web

logger = logging.getLogger(__name__)


async def _healthcheck(_: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_health_server() -> web.AppRunner | None:
    """Start the health server if ``PORT`` is configured; return its runner."""
    port_value = os.getenv("PORT")
    if not port_value:
        return None

    app = web.Application()
    app.router.add_get("/", _healthcheck)
    app.router.add_get("/health", _healthcheck)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(port_value))
    await site.start()
    logger.info("Health server listening on port %s", port_value)
    return runner


async def stop_health_server(runner: web.AppRunner | None) -> None:
    if runner is not None:
        await runner.cleanup()
