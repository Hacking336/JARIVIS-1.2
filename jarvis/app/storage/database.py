from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base


class DatabaseManager:
    def __init__(self):
        self._settings = get_settings()
        self._engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None

    def initialize(self) -> None:
        sync_url = self._settings.database_url.replace("sqlite:///", "sqlite:///")
        if sync_url.startswith("sqlite:///"):
            db_path = sync_url.replace("sqlite:///", "")
            import os
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        self._engine = create_engine(
            sync_url,
            echo=self._settings.app_debug,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False} if "sqlite" in sync_url else {},
        )

        async_url = self._settings.database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        self._async_engine = create_async_engine(
            async_url,
            echo=self._settings.app_debug,
            pool_pre_ping=True,
        )

        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._async_session_factory = async_sessionmaker(
            bind=self._async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        if "sqlite" in sync_url:
            @event.listens_for(self._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

    def create_tables(self) -> None:
        if self._engine:
            Base.metadata.create_all(self._engine)

    async def create_tables_async(self) -> None:
        if self._async_engine:
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

    @property
    def session_factory(self) -> sessionmaker:
        if not self._session_factory:
            self.initialize()
        return self._session_factory

    @property
    def async_session_factory(self) -> async_sessionmaker:
        if not self._async_session_factory:
            self.initialize()
        return self._async_session_factory

    def get_session(self) -> Session:
        return self.session_factory()

    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def close(self) -> None:
        if self._engine:
            self._engine.dispose()
        if self._async_engine:
            import asyncio
            asyncio.run(self._async_engine.dispose())


_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()
    return _db_manager


def init_database() -> None:
    db = get_database_manager()
    db.create_tables()


async def init_database_async() -> None:
    db = get_database_manager()
    await db.create_tables_async()