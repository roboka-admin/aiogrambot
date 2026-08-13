class UserError(Exception):
    """
    Base exception for all user-related errors.
    """


class UserAlreadyExistsError(UserError):
    """
    Raised when attempting to register
    a user that already exists.
    """


class UserNotFoundError(UserError):
    """
    Raised when a requested user
    cannot be found.
    """


class UserBlockedError(UserError):
    """
    Raised when a blocked user
    attempts to perform an action.
    """