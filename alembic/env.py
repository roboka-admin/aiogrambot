from logging.config import fileConfig
import os
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from core.database_url import build_connection_config
from models.base import Base
from models.antispam_db import AntiSpamEventRecord
from models.bot_settings_db import BotSettingsRecord
from models.broadcast_db import BroadcastRecordRecord
from models.force_subscription_db import ForceSubscriptionMembershipEventRecord
from models.force_subscription_db import ForceSubscriptionTargetRecord
from models.referral_reward_db import ReferralRewardRecord
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


# Alembic runs synchronously, so swap the async driver for pymysql. This also
# strips cloud-style ``?ssl-mode=...`` parameters that the driver rejects and
# turns them into ``connect_args``.
connection_config = build_connection_config(get_database_url(), driver="pymysql")
config.set_main_option(
    "sqlalchemy.url",
    connection_config.url.render_as_string(hide_password=False).replace("%", "%%"),
)
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
        connect_args=connection_config.connect_args,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
