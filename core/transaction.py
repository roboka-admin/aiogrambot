from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Awaitable, Callable, Protocol, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession


class TransactionManager(Protocol):
    """Application-level transaction boundary used by services."""

    def transaction(self):
        """Return an async context manager for one database transaction."""
        ...


class NullTransactionManager:
    """No-op transaction manager for service unit tests without a database."""

    @asynccontextmanager
    async def transaction(self):
        yield


class SessionTransactionManager:
    """Own transaction boundaries for one request-scoped SQLAlchemy session.

    Nested service calls reuse the current transaction instead of opening a
    second transaction. The outermost service operation commits on success and
    rolls back automatically when an exception escapes.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def transaction(self):
        if self._session.in_transaction():
            yield
            return

        async with self._session.begin():
            yield


T = TypeVar("T")


def transactional(method: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Wrap one service operation in its application transaction boundary."""

    @wraps(method)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
        async with self._transaction_manager.transaction():
            return await method(self, *args, **kwargs)

    return wrapper
