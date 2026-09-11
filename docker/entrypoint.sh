#!/bin/sh
# Container entrypoint: apply pending Alembic migrations, then start the bot.
#
# Migrations run against the *main* database on purpose (alembic/env.py
# refuses to choose a target implicitly). Set RUN_MIGRATIONS=false to
# skip this step, e.g. when a separate release job owns migrations.
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] Applying database migrations..."
    python -m alembic -x database=main upgrade head
    echo "[entrypoint] Migrations up to date."
else
    echo "[entrypoint] RUN_MIGRATIONS=${RUN_MIGRATIONS}; skipping migrations."
fi

exec "$@"
