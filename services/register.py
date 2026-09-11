from dataclasses import dataclass

from core.transaction import NullTransactionManager, TransactionManager, transactional
from exceptions.user import UserAlreadyExistsError
from models.user import RegistrationStatus, User
from repositories.interfaces.user import IUserRepository
from services.referral import ReferralReward, ReferralService


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    """Outcome of a completed registration, including any referral payout."""

    user: User
    referral_reward: ReferralReward | None


class RegisterService:
    """Completes registration for an already tracked Telegram user."""

    def __init__(
        self,
        *,
        user_repository: IUserRepository,
        referral_service: ReferralService,
        transaction_manager: TransactionManager | None = None,
    ) -> None:
        self._user_repository = user_repository
        self._referral_service = referral_service
        self._transaction_manager = transaction_manager or NullTransactionManager()

    @transactional
    async def register(
        self, *, telegram_id: int, name: str, age: int
    ) -> RegistrationResult:
        """Mark the user registered and pay the referrer, atomically.

        The referral payout runs inside this transaction on purpose: the
        transaction manager reuses the outer transaction for nested service
        calls, so either both the registration and the reward commit, or
        neither does. A crash between the two can no longer leave a
        registered user whose referrer was never credited.
        """
        user = await self._user_repository.get_by_telegram_id(telegram_id)
        if user is None:
            raise RuntimeError("Telegram user must be tracked before registration")
        if user.registration_status == RegistrationStatus.REGISTERED:
            raise UserAlreadyExistsError
        user.name = name.strip()
        user.age = age
        user.registration_status = RegistrationStatus.REGISTERED
        updated = await self._user_repository.update(user)
        assert updated is not None

        reward = await self._referral_service.reward_referrer_for_registration(
            registered_user=updated
        )
        return RegistrationResult(user=updated, referral_reward=reward)
