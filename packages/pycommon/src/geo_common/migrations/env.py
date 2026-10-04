from alembic import context
from sqlalchemy import create_engine, pool

config = context.config


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    assert url is not None
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
