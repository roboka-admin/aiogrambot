import logging
from datetime import timedelta

from core.log_buffer import ErrorLogBuffer
from core.timezone import tehran_now


def _logger(name: str, handler: logging.Handler) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger


def test_buffer_groups_repeated_messages_by_template() -> None:
    buffer = ErrorLogBuffer()
    logger = _logger("test.buffer.group", buffer)
    since = tehran_now() - timedelta(seconds=1)

    for user_id in (1, 2, 3):
        logger.warning("Broadcast failed for user %s", user_id)
    logger.error("Database exploded")

    issues = buffer.issues_since(since)

    assert [issue.count for issue in issues] == [3, 1]
    assert issues[0].level == "WARNING"
    assert issues[0].sample == "Broadcast failed for user 3"
    assert issues[1].level == "ERROR"
    assert buffer.count_since(since) == 4
    assert buffer.count_since(since, min_level=logging.ERROR) == 1


def test_buffer_ignores_info_and_ignored_loggers() -> None:
    buffer = ErrorLogBuffer()
    since = tehran_now() - timedelta(seconds=1)

    _logger("test.buffer.info", buffer).info("just info")
    _logger("aiogram.event", buffer).warning("Update id=1 is not handled")

    assert buffer.issues_since(since) == []


def test_buffer_records_exception_type_in_fingerprint() -> None:
    buffer = ErrorLogBuffer()
    logger = _logger("test.buffer.exc", buffer)
    since = tehran_now() - timedelta(seconds=1)

    try:
        raise ValueError("bad value")
    except ValueError:
        logger.exception("Handler crashed")
    logger.error("Handler crashed")

    issues = buffer.issues_since(since)

    assert len(issues) == 2
    assert any(issue.sample.endswith("[ValueError]") for issue in issues)


def test_buffer_respects_time_window_and_capacity() -> None:
    buffer = ErrorLogBuffer(max_entries=2)
    logger = _logger("test.buffer.cap", buffer)

    logger.warning("one")
    logger.warning("two")
    logger.warning("three")

    since = tehran_now() - timedelta(seconds=1)
    samples = sorted(issue.sample for issue in buffer.issues_since(since))
    assert samples == ["three", "two"]
    assert buffer.issues_since(tehran_now() + timedelta(minutes=1)) == []


def test_buffer_flags_first_occurrence_of_an_error_fingerprint_as_new() -> None:
    buffer = ErrorLogBuffer()
    logger = _logger("test.buffer.new", buffer)
    since = tehran_now() - timedelta(seconds=1)

    logger.error("Payment failed for %s", 1)
    logger.error("Payment failed for %s", 2)
    logger.warning("Slow query")  # warnings are never "new"

    by_level = {issue.level: issue for issue in buffer.issues_since(since)}
    assert by_level["ERROR"].is_new is True
    assert by_level["ERROR"].count == 2
    assert by_level["WARNING"].is_new is False

    # A later window that only contains repeats is not "new" anymore.
    later = tehran_now()
    logger.error("Payment failed for %s", 3)
    (issue,) = buffer.issues_since(later)
    assert issue.is_new is False


def test_buffer_notifies_listeners_for_errors_only_with_exception_type() -> None:
    buffer = ErrorLogBuffer()
    logger = _logger("test.buffer.listen", buffer)
    seen = []
    buffer.subscribe(seen.append)

    logger.warning("ignored by listeners")
    try:
        raise ConnectionError("db gone")
    except ConnectionError:
        logger.exception("Query failed")
    logger.error("Plain error")

    assert [issue.exc_type for issue in seen] == ["ConnectionError", ""]
    assert seen[0].is_new is True and seen[0].count == 1
    assert seen[0].sample.endswith("[ConnectionError]")


def test_listener_exception_does_not_break_logging() -> None:
    buffer = ErrorLogBuffer()
    logger = _logger("test.buffer.badlistener", buffer)
    since = tehran_now() - timedelta(seconds=1)

    def bad(_issue):
        raise RuntimeError("listener bug")

    buffer.subscribe(bad)
    logger.error("still recorded")

    assert len(buffer.issues_since(since)) == 1
