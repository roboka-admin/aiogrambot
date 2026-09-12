import ssl

import pytest

from core.database_url import build_connection_config


def test_plain_url_is_left_untouched() -> None:
    config = build_connection_config("mysql+asyncmy://user:pass@host:3306/db")

    assert config.url.render_as_string(hide_password=False) == (
        "mysql+asyncmy://user:pass@host:3306/db"
    )
    assert config.connect_args == {}


def test_driver_is_swapped_and_backend_kept() -> None:
    config = build_connection_config(
        "mysql+asyncmy://user:pass@host/db", driver="pymysql"
    )

    assert config.url.drivername == "mysql+pymysql"


def test_ssl_mode_required_becomes_ssl_context_without_verification() -> None:
    config = build_connection_config(
        "mysql://user:pass@host:3306/db?ssl-mode=REQUIRED"
    )

    assert "ssl-mode" not in config.url.query
    assert config.url.drivername == "mysql+asyncmy"
    context = config.connect_args["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False


@pytest.mark.parametrize("key", ["ssl-mode", "ssl_mode", "sslmode"])
def test_all_ssl_mode_spellings_are_stripped(key: str) -> None:
    config = build_connection_config(f"mysql://u:p@h/db?{key}=required")

    assert key not in config.url.query
    assert "ssl" in config.connect_args


def test_verify_identity_enables_full_verification() -> None:
    config = build_connection_config("mysql://u:p@h/db?ssl-mode=VERIFY_IDENTITY")

    context = config.connect_args["ssl"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_verify_ca_skips_hostname_check() -> None:
    config = build_connection_config("mysql://u:p@h/db?ssl-mode=VERIFY_CA")

    context = config.connect_args["ssl"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is False


def test_disabled_produces_no_ssl_args() -> None:
    config = build_connection_config("mysql://u:p@h/db?ssl-mode=DISABLED")

    assert config.connect_args == {}
    assert "ssl-mode" not in config.url.query


def test_other_query_params_survive() -> None:
    config = build_connection_config(
        "mysql://u:p@h/db?ssl-mode=REQUIRED&charset=utf8mb4"
    )

    assert dict(config.url.query) == {"charset": "utf8mb4"}


def test_unknown_ssl_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported ssl-mode"):
        build_connection_config("mysql://u:p@h/db?ssl-mode=WHATEVER")
