from typing import Final

from aiogram.enums import ContentType
from aiogram.types import Message


MAX_SUPPORT_TEXT_LENGTH: Final[int] = 1800

SUPPORTED_CONTENT_TYPES: Final[frozenset[ContentType]] = frozenset(
    {
        ContentType.TEXT,
        ContentType.PHOTO,
        ContentType.VIDEO,
        ContentType.DOCUMENT,
        ContentType.AUDIO,
        ContentType.VOICE,
        ContentType.STICKER,
        ContentType.ANIMATION,
        ContentType.VIDEO_NOTE,
    }
)


def validate_support_message(message: Message) -> bool:
    """Validate whether a Telegram message is allowed for support."""

    if message.content_type not in SUPPORTED_CONTENT_TYPES:
        return False

    if message.text is not None and len(message.text) > MAX_SUPPORT_TEXT_LENGTH:
        return False

    if message.caption is not None and len(message.caption) > MAX_SUPPORT_TEXT_LENGTH:
        return False

    return True
