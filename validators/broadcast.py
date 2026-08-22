from typing import Final

from aiogram.enums import ContentType
from aiogram.types import Message

SUPPORTED_BROADCAST_CONTENT_TYPES: Final[frozenset[ContentType]] = frozenset(
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


def validate_broadcast_message(message: Message) -> bool:
    """Return whether a message can be safely copied for broadcast."""
    return message.content_type in SUPPORTED_BROADCAST_CONTENT_TYPES
