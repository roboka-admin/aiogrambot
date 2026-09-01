from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from models.base import Base
from models.antispam_db import AntiSpamEventRecord
from models.broadcast_db import BroadcastRecordRecord
from models.support_db import SupportTicketRecord
from models.user_db import UserRecord

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url = os.getenv("DATABASE_URL")
if not url:
    raise RuntimeError("DATABASE_URL is not configured")

config.set_main_option("sqlalchemy.url", url.replace("+asyncmy", "+pymysql"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
