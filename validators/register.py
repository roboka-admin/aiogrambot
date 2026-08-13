from typing import Final


MIN_NAME_LENGTH: Final[int] = 2
MIN_AGE: Final[int] = 1
MAX_AGE: Final[int] = 120


def validate_name(name: str) -> bool:
    """
    Validate a user's name.

    Rules:
    - Must contain at least MIN_NAME_LENGTH characters.
    - Cannot consist only of digits.
    """

    name = name.strip()

    if len(name) < MIN_NAME_LENGTH:
        return False

    if name.isdigit():
        return False

    return True


def validate_age(age: str) -> bool:
    """
    Validate a user's age.

    Rules:
    - Must be numeric.
    - Must be between MIN_AGE and MAX_AGE.
    """

    if not age.isdigit():
        return False

    age_value = int(age)

    return MIN_AGE <= age_value <= MAX_AGE