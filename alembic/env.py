from logging.config import fileConfig
import os
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from models.base import Base
from models.antispam_db import AntiSpamEventRecord
from models.broadcast_db import BroadcastRecordRecord
from models.support_db import SupportTicketRecord
from models.user_db import UserRecord

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Load the project's .env so Alembic can resolve the explicitly selected
# database target when invoked directly from the command line.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def get_database_url() -> str:
    """Return the URL for the explicitly selected Alembic database target."""
    database = context.get_x_argument(as_dictionary=True).get("database")

    env_var_by_database = {
        "test": "TEST_DATABASE_URL",
        "main": "DATABASE_URL",
    }

    if database not in env_var_by_database:
        raise RuntimeError(
            "Database target is required. Use '-x database=test' or "
            "'-x database=main'. Refusing to choose a database implicitly."
        )

    env_var = env_var_by_database[database]
    url = os.getenv(env_var)
    if not url:
        raise RuntimeError(f"{env_var} is not configured")

    return url


url = get_database_url()
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
