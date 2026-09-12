"""Translate cloud-style MySQL URLs into what the Python drivers accept.

Managed MySQL providers (Aiven, DigitalOcean, TiDB, PlanetScale, ...) hand
out URLs such as ``mysql://u:p@host/db?ssl-mode=REQUIRED``. ``ssl-mode`` is
an option of the official ``mysql`` CLI; SQLAlchemy forwards unknown query
parameters verbatim to the driver, and neither ``asyncmy`` nor ``pymysql``
has such a keyword, so connecting fails with
``TypeError: ... unexpected keyword argument 'ssl-mode'``.

Both drivers do accept ``ssl=<SSLContext>``. This module strips the
``ssl-mode`` parameter from the URL and returns the matching
``connect_args`` so ``create_engine`` / ``create_async_engine`` get a
configuration they understand.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.engine import URL, make_url

_SSL_MODE_KEYS = ("ssl-mode", "ssl_mode", "sslmode")

# Values as documented for the MySQL CLI, normalized to upper case.
_SSL_MODES_DISABLED = {"DISABLED"}
_SSL_MODES_ENCRYPT_ONLY = {"PREFERRED", "REQUIRED"}
_SSL_MODES_VERIFY = {"VERIFY_CA", "VERIFY_IDENTITY"}


@dataclass(frozen=True, slots=True)
class DatabaseConnectionConfig:
    url: URL
    connect_args: dict[str, Any] = field(default_factory=dict)


def build_connection_config(
    database_url: str, *, driver: str = "asyncmy"
) -> DatabaseConnectionConfig:
    """Return the driver URL plus ``connect_args`` for the given URL string.

    ``driver`` selects the DBAPI (``asyncmy`` for the bot, ``pymysql`` for
    Alembic); the backend part of the URL (``mysql`` / ``mariadb``) is kept.
    """
    url = make_url(database_url)
    backend = url.get_backend_name()
    if backend in ("mysql", "mariadb"):
        url = url.set(drivername=f"{backend}+{driver}")
    query = dict(url.query)

    ssl_mode: str | None = None
    for key in _SSL_MODE_KEYS:
        if key in query:
            ssl_mode = str(query.pop(key)).upper()

    url = url.set(query=query)
    connect_args: dict[str, Any] = {}

    if ssl_mode is None or ssl_mode in _SSL_MODES_DISABLED:
        return DatabaseConnectionConfig(url=url, connect_args=connect_args)

    if ssl_mode in _SSL_MODES_ENCRYPT_ONLY:
        # Encrypt the connection but do not verify the server certificate.
        # This mirrors the MySQL CLI semantics of REQUIRED and is what most
        # managed providers expect when they hand out ssl-mode=REQUIRED
        # without also shipping a CA bundle.
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    elif ssl_mode in _SSL_MODES_VERIFY:
        # Full verification against the system CA store. VERIFY_IDENTITY also
        # checks the hostname; VERIFY_CA does not.
        context = ssl.create_default_context()
        context.check_hostname = ssl_mode == "VERIFY_IDENTITY"
        context.verify_mode = ssl.CERT_REQUIRED
    else:
        raise ValueError(
            f"Unsupported ssl-mode {ssl_mode!r} in database URL. "
            "Expected one of DISABLED, PREFERRED, REQUIRED, VERIFY_CA, VERIFY_IDENTITY."
        )

    connect_args["ssl"] = context
    return DatabaseConnectionConfig(url=url, connect_args=connect_args)
