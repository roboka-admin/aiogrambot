from unittest.mock import AsyncMock, MagicMock

import pytest

from core.transaction import SessionTransactionManager


class TransactionContext:
    def __init__(self) -> None:
        self.exited_with = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited_with = exc_type
        return False


@pytest.mark.asyncio
async def test_session_transaction_manager_commits_service_operation():
    session = MagicMock()
    session.in_transaction.return_value = False
    transaction = TransactionContext()
    session.begin.return_value = transaction

    manager = SessionTransactionManager(session)
    async with manager.transaction():
        pass

    session.begin.assert_called_once_with()
    assert transaction.exited_with is None


@pytest.mark.asyncio
async def test_session_transaction_manager_rolls_back_on_service_exception():
    session = MagicMock()
    session.in_transaction.return_value = False
    transaction = TransactionContext()
    session.begin.return_value = transaction

    manager = SessionTransactionManager(session)
    with pytest.raises(RuntimeError, match="boom"):
        async with manager.transaction():
            raise RuntimeError("boom")

    session.begin.assert_called_once_with()
    assert transaction.exited_with is RuntimeError


@pytest.mark.asyncio
async def test_session_transaction_manager_reuses_existing_transaction_for_nested_service_calls():
    session = MagicMock()
    session.in_transaction.return_value = True
    manager = SessionTransactionManager(session)

    async with manager.transaction():
        pass

    session.begin.assert_not_called()
