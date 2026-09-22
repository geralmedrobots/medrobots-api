from sqlalchemy.pool import QueuePool

from app.core.config import Settings
from app.db.session import build_engine


def test_build_engine_applies_pool_settings_for_postgres() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://user:pass@localhost/db",
        cors_origins="https://example.com",
        db_pool_size=7,
        db_max_overflow=3,
    )
    engine = build_engine(settings)
    assert isinstance(engine.pool, QueuePool)
    assert engine.pool.size() == 7
    engine.dispose()


def test_build_engine_skips_pool_sizing_for_sqlite(tmp_path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'pool.db'}"
    settings = Settings(database_url=url)
    engine = build_engine(settings)
    assert engine.url.drivername == "sqlite+pysqlite"
    engine.dispose()
