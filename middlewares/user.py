from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from exceptions.user import UserNotFoundError
from models.user import User
from services.user import UserService


class UserMiddleware(BaseMiddleware):
    """Load the current user from database and inject into handler data.
    
    This middleware loads the registered user associated with the Telegram update
    and injects the domain User object into the handler data as data["user"].
    
    Unregistered users will have user=None in their handler data, allowing
    handlers to gracefully handle both registered and unregistered users.
    """

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Get user_service from data (injected by ServicesMiddleware)
        user_service: UserService = data["user_service"]
        
        # Load current user if available
        user: User | None = None
        if event.from_user is not None:
            try:
                user = await user_service.get_user(event.from_user.id)
            except UserNotFoundError:
                # Unregistered users - user remains None
                pass

        # Inject user into handler data
        data["user"] = user

        return await handler(event, data)