"""Alembic environment."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from packages.storage.db import Base
from packages.domain.tenant import Tenant  # noqa: F401
from packages.domain.job import Job  # noqa: F401
from packages.domain.user import User, TenantMembership  # noqa: F401
from packages.domain.webhook_inbox import WebhookInbox  # noqa: F401
from packages.storage.outbox import OutboxEvent  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    connectable = engine_from_config({"sqlalchemy.url": url}, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
